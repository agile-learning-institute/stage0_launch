from __future__ import annotations

import json
import os
import shutil
import signal
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

from stage0_launch.config import CONTAINER_LAUNCHPAD, launchpad_dir
from stage0_launch.discovery import DiscoveryResult, discover, launchpad_specs_complete
from stage0_launch.launchpad_stub import (
    read_stub_umbrella,
    stub_path,
    valid_umbrella_folder_name,
    write_stub,
)
from stage0_launch.yqutil import yq_eval
from stage0_launch.jobs.manager import JobManager
from stage0_launch.operations.bootstrap import run_bootstrap
from stage0_launch.operations.umbrella_ops import (
    UmbrellaContext,
    cmd_clone_services,
    cmd_delete_services,
    cmd_launch_services,
)
from stage0_launch.specs_schema import validate_spec_bodies


def _bootstrap_mode(lp: Path) -> bool:
    """True when ``.stage0-launch.yaml`` is absent (not yet bootstrapped on this launchpad)."""
    return not stub_path(lp).is_file()


def _launchpad_dir_entries(lp: Path) -> list[str]:
    if not lp.is_dir():
        return []
    try:
        return sorted(p.name for p in lp.iterdir())
    except OSError:
        return []


def _bootstrap_launchpad_warning(bootstrap_mode: bool, lp: Path) -> dict[str, Any] | None:
    if not bootstrap_mode:
        return None
    entries = _launchpad_dir_entries(lp)
    if not entries:
        return None
    return {"path": str(lp), "items": entries}


def _service_domains(lp: Path, slug: str) -> list[str]:
    arch = lp / slug / "Specifications" / "architecture.yaml"
    if not arch.is_file():
        return []
    import subprocess

    for expr in (".architecture.domains[].name", ".domains[].name"):
        r = subprocess.run(
            ["yq", "-r", expr, str(arch)],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            names = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
            if names:
                return names
    return []


def _schedule_container_shutdown(*, delay_seconds: float = 1.5) -> None:
    """SIGTERM PID 1 after a delay when running in the standard launch container (``/Launchpad`` mount)."""

    def _run() -> None:
        time.sleep(delay_seconds)
        try:
            if CONTAINER_LAUNCHPAD.is_dir():
                os.kill(1, signal.SIGTERM)
        except OSError:
            pass

    threading.Thread(target=_run, daemon=True).start()


def _status_payload() -> dict[str, Any]:
    lp = launchpad_dir()
    disc = discover(lp)
    interactive = disc.ok
    services = _service_domains(lp, disc.slug) if interactive and disc.slug else []
    bmode = _bootstrap_mode(lp)
    return {
        "launchpad": str(lp),
        "discovery_ok": disc.ok,
        "discovery_error": disc.error,
        "specs_dir": str(disc.specs_dir) if disc.specs_dir else None,
        "slug": disc.slug,
        "bootstrap_mode": bmode,
        "interactive_mode": interactive,
        "services": services,
        "launchpad_dir_warning": _bootstrap_launchpad_warning(bmode, lp),
    }


def create_app() -> Flask:
    _root = Path(__file__).resolve().parent.parent
    app = Flask(__name__, root_path=str(_root), template_folder="templates")
    job_manager = JobManager()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/thanks")
    def thanks():
        return render_template("thanks.html")

    @app.get("/exit")
    def exit_page():
        """Shown after Exit from interactive mode (post ``/api/shutdown``)."""
        return render_template("exit.html")

    @app.post("/api/bootstrap/finish")
    def api_bootstrap_finish():
        """
        After a bootstrap job (success or failure), user dismisses the log: read
        ``info.slug`` from ``.stage0-bootstrap/specs/product.yaml`` (if present),
        remove ``.stage0-bootstrap``, then ensure ``.stage0-launch.yaml`` exists
        (``umbrella: <slug>``) from discovery or from that slug. Optionally signal
        PID 1 to stop the container.
        """
        lp = launchpad_dir()
        boot = lp / ".stage0-bootstrap"
        stub = stub_path(lp)
        disc_before = discover(lp)

        if not boot.is_dir() and not (disc_before.ok and disc_before.slug):
            return jsonify(
                {
                    "error": "Nothing to finish (no .stage0-bootstrap and no "
                    "interactive launchpad stub).",
                }
            ), 400

        slug_from_bootstrap_specs: str | None = None
        prod_in_boot = boot / "specs" / "product.yaml"
        if prod_in_boot.is_file():
            try:
                raw = yq_eval(".info.slug", prod_in_boot)
                if raw and raw != "null":
                    cand = raw.strip()
                    if valid_umbrella_folder_name(cand):
                        slug_from_bootstrap_specs = cand
            except Exception:
                pass

        if boot.is_dir():
            try:
                shutil.rmtree(boot)
            except OSError as e:
                return jsonify({"error": f"Could not remove bootstrap folder: {e}"}), 500

        disc = discover(lp)

        if disc.ok and disc.slug:
            if not stub.is_file():
                try:
                    write_stub(lp, disc.slug)
                except ValueError:
                    return jsonify({"error": "Could not write launchpad stub"}), 500
            umbrella = read_stub_umbrella(lp)
            if umbrella and not (lp / umbrella).is_dir():
                return jsonify({"error": "Stub points at missing umbrella folder"}), 500
        elif slug_from_bootstrap_specs:
            if not stub.is_file():
                try:
                    write_stub(lp, slug_from_bootstrap_specs)
                except ValueError:
                    return jsonify({"error": "Could not write launchpad stub"}), 500

        _schedule_container_shutdown(delay_seconds=2.0)
        return jsonify({"ok": True})

    @app.post("/api/shutdown")
    def api_shutdown():
        """Thank-you / Exit: stop the launch container when running under Docker."""
        _schedule_container_shutdown(delay_seconds=0.75)
        return jsonify({"ok": True})

    @app.get("/api/status")
    def api_status():
        return jsonify(_status_payload())

    @app.post("/api/specs/validate")
    def api_specs_validate():
        data = request.get_json(force=True, silent=True) or {}
        py = data.get("product_yaml")
        ay = data.get("architecture_yaml")
        cy = data.get("catalog_yaml")
        if not all(isinstance(x, str) for x in (py, ay, cy)):
            return jsonify({"ok": False, "errors": ["All three YAML bodies must be strings."]}), 400
        errs = validate_spec_bodies(py, ay, cy)
        return jsonify({"ok": len(errs) == 0, "errors": errs})

    @app.post("/api/specs/paste")
    def api_specs_paste():
        lp = launchpad_dir()
        data = request.get_json(force=True, silent=True) or {}
        py = data.get("product_yaml")
        ay = data.get("architecture_yaml")
        cy = data.get("catalog_yaml")
        if not all(isinstance(x, str) for x in (py, ay, cy)):
            return jsonify({"error": "Missing or invalid YAML fields"}), 400
        errs = validate_spec_bodies(py, ay, cy)
        if errs:
            return jsonify({"error": "Schema validation failed", "errors": errs}), 400
        boot = lp / ".stage0-bootstrap" / "specs"
        boot.mkdir(parents=True, exist_ok=True)
        (boot / "product.yaml").write_text(py, encoding="utf-8")
        (boot / "architecture.yaml").write_text(ay, encoding="utf-8")
        (boot / "catalog.yaml").write_text(cy, encoding="utf-8")
        return jsonify({"ok": True, "path": str(boot)})

    def _ctx() -> UmbrellaContext:
        lp = launchpad_dir()
        disc = discover(lp)
        if not disc.ok or not disc.slug:
            raise RuntimeError(disc.error or "Umbrella Specifications not found on launchpad")
        umb = lp / disc.slug
        if not umb.is_dir():
            raise RuntimeError("Umbrella directory missing")
        return UmbrellaContext.load(umb, lp)

    @app.post("/api/jobs/bootstrap")
    def api_jobs_bootstrap():
        if job_manager.current_running():
            return jsonify({"error": "A job is already running"}), 409

        lp = launchpad_dir()
        specs = lp / ".stage0-bootstrap" / "specs"
        if not launchpad_specs_complete(specs):
            return jsonify(
                {"error": "Paste and validate all three specifications before Launch."}
            ), 400

        def work(log) -> None:
            run_bootstrap(specs, lp, log)

        job = job_manager.start("bootstrap", work)
        return jsonify({"job_id": job.id})

    @app.post("/api/jobs/launch-services")
    def api_jobs_launch_services():
        if job_manager.current_running():
            return jsonify({"error": "A job is already running"}), 409
        data = request.get_json(force=True, silent=True) or {}
        svcs = data.get("services")
        if isinstance(svcs, list):
            s = " ".join(str(x).strip() for x in svcs if str(x).strip())
        elif isinstance(svcs, str):
            s = svcs.strip()
        else:
            return jsonify({"error": "services must be a list or string"}), 400
        if not s:
            return jsonify({"error": "Select at least one service"}), 400

        def work(log) -> None:
            ctx = _ctx()
            cmd_launch_services(ctx, s, log)

        job = job_manager.start("launch-services", work)
        return jsonify({"job_id": job.id})

    @app.post("/api/jobs/clone-services")
    def api_jobs_clone_services():
        if job_manager.current_running():
            return jsonify({"error": "A job is already running"}), 409
        data = request.get_json(force=True, silent=True) or {}
        svcs = data.get("services")
        if isinstance(svcs, list):
            s = " ".join(str(x).strip() for x in svcs if str(x).strip())
        elif isinstance(svcs, str):
            s = svcs.strip()
        else:
            return jsonify({"error": "services must be a list or string"}), 400
        if not s:
            return jsonify({"error": "Select at least one service"}), 400

        def work(log) -> None:
            ctx = _ctx()
            cmd_clone_services(ctx, s, log)

        job = job_manager.start("clone-services", work)
        return jsonify({"job_id": job.id})

    @app.post("/api/jobs/delete-services")
    def api_jobs_delete_services():
        if job_manager.current_running():
            return jsonify({"error": "A job is already running"}), 409
        data = request.get_json(force=True, silent=True) or {}
        svcs = data.get("services")
        if isinstance(svcs, list):
            s = " ".join(str(x).strip() for x in svcs if str(x).strip())
        elif isinstance(svcs, str):
            s = svcs.strip()
        else:
            return jsonify({"error": "services must be a list or string"}), 400
        if not s:
            return jsonify({"error": "Select at least one service"}), 400
        conf = (data.get("i_confirm_delete_services") or "").lower()
        slug_conf = data.get("i_confirm_slug") or ""
        if conf != "yes":
            return jsonify({"error": 'Set i_confirm_delete_services to "yes"'}), 400

        def work(log) -> None:
            ctx = _ctx()
            cmd_delete_services(ctx, s, "yes", slug_conf, log)

        job = job_manager.start("delete-services", work)
        return jsonify({"job_id": job.id})

    @app.get("/api/jobs/<job_id>")
    def api_job_get(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        with job._lock:
            text = job.log.getvalue()
        return jsonify(
            {
                "id": job.id,
                "name": job.name,
                "status": job.status,
                "log": text,
                "error": job.error,
            }
        )

    @app.get("/api/jobs/<job_id>/stream")
    def api_job_stream(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404

        def gen():
            last_len = 0
            while True:
                with job._lock:
                    full = job.log.getvalue()
                if len(full) > last_len:
                    chunk = full[last_len:]
                    last_len = len(full)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                if job.status != "running":
                    yield f"data: {json.dumps({'done': True, 'status': job.status, 'error': job.error})}\n\n"
                    break
                time.sleep(0.25)

        return Response(
            stream_with_context(gen()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
