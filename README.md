# Stage0 Launch

Flask web UI and API to **bootstrap** a new umbrella (from pasted specifications) and run **Launch** / **Clone** / **Delete** on **selected** service domains.

## Quickstart (Docker Compose)

```bash
export GITHUB_TOKEN=ghp_...
pipenv install --dev   # optional; or use pip install -r / local venv
pipenv run compose-up    # runs: docker compose down && docker compose up --build -d
```

Open **http://localhost:8080** (or `LAUNCH_HOST_PORT`).

The container uses **`/Launchpad`** as the launchpad root (created in the image; compose mounts your host folder there). Set **`LAUNCHPAD_HOST`** to the host directory to mount (default **`..`**). You do **not** need `LAUNCHPAD_DIR` inside the container.

Use an **empty** host folder for a clean bootstrap; the UI warns when the launchpad already has entries.

## Launchpad layout

- **`.stage0-launch.yaml`** (at the root of the launchpad) is written when bootstrap **finishes successfully**. It records which child folder is the umbrella, for example:

  ```yaml
  umbrella: my-product-slug
  ```

- **Bootstrap mode** (paste UI): this file is **missing**.
- **Interactive mode** (service checkboxes): stub exists and points at `<launchpad>/<umbrella>/Specifications` with the three YAML files; `info.slug` must match the umbrella folder name.
- If the stub exists but is invalid or the tree is broken, the UI stays in **operations** layout and shows a **discovery error** (not bootstrap).

Pasted specs are still saved under **`.stage0-bootstrap/specs/`** until bootstrap runs.

## Web UI

- **Bootstrap**: title, optional non-empty warning, three text areas, **Launch** (validates against the bundled JSON Schema, saves, then starts the bootstrap job).
- **Interactive**: checkbox list of domains, **All**, **Launch** / **Clone** / **Delete**. Job log opens in a modal (SSE).

## API (selected)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/status` | Launchpad path, `bootstrap_mode`, `interactive_mode`, `discovery_*`, `services`, `launchpad_dir_warning` |
| POST | `/api/specs/validate` | JSON `product_yaml`, `architecture_yaml`, `catalog_yaml` → `{ ok, errors[] }` |
| POST | `/api/specs/paste` | Validates then saves YAML under `.stage0-bootstrap/specs/` |
| POST | `/api/jobs/bootstrap` | Full bootstrap (requires pasted specs); writes `.stage0-launch.yaml` when the job completes successfully |
| POST | `/api/jobs/launch-services` | JSON `services`: list of domain names or space-separated string |
| POST | `/api/jobs/clone-services` | Same body |
| POST | `/api/jobs/delete-services` | `services`, `i_confirm_delete_services`: `"yes"`, `i_confirm_slug` |
| GET | `/api/jobs/<id>` | Job status + full log |
| GET | `/api/jobs/<id>/stream` | SSE log |

## Environment

| Variable | Meaning |
|----------|---------|
| `LAUNCHPAD_DIR` | Optional override for the launchpad path (tests, nonstandard layouts). If unset: use **`/Launchpad`** when that directory exists, else the process current directory. |
| `LAUNCHPAD_HOST` | **Compose only**: host path mounted at **`/Launchpad`** in the container (default **`..`**). |
| `GITHUB_TOKEN` | Required for GitHub / GHCR |

## Testing

Use **`pipenv run compose-up`** (see Quickstart) so the app runs in the same image as production, with Docker socket and launchpad mounts. For fast feedback without the full stack, run **`pipenv run test`**.

## Validate

`pipenv run validate` runs a minimal host check stub; extend `validate_host.py` for full CI checks if needed.
