"""Command-line tools: merge-all (local template testing) and launchpad tree diff."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from stage0_launch.launchpad_compare import compare_launchpads
from stage0_launch.operations.merge_all import run_merge_all


def _cmd_merge_all(args: argparse.Namespace) -> int:
    run_merge_all(
        args.launchpad,
        args.specifications,
        args.templates_root,
        sys.stdout,
        skip_umbrella=args.skip_umbrella,
        emit_launchpad_stub=args.write_stub,
    )
    return 0


def _cmd_test(args: argparse.Namespace) -> int:
    return compare_launchpads(
        args.left,
        args.right,
        ignore_file=args.ignore_file,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m stage0_launch.cli")
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser(
        "merge-all",
        help="Copy local stage0 templates into a launchpad and run Docker runbook merge only.",
    )
    m.add_argument(
        "launchpad",
        type=Path,
        help="Output launchpad root (created if missing).",
    )
    m.add_argument(
        "specifications",
        type=Path,
        help="Directory with product.yaml, architecture.yaml, catalog.yaml (source specs for umbrella merge).",
    )
    m.add_argument(
        "--templates-root",
        type=Path,
        required=True,
        help="Parent directory of stage0_template_* folders (Pipfile script uses ..).",
    )
    m.add_argument(
        "--skip-umbrella",
        action="store_true",
        help="Reuse existing launchpad/<slug> and its Specifications; only rebuild service dirs.",
    )
    m.add_argument(
        "--write-stub",
        action="store_true",
        help="Write .stage0-launch.yaml pointing at the umbrella folder.",
    )
    m.set_defaults(func=_cmd_merge_all)

    t = sub.add_parser(
        "test",
        help="Diff two launchpad directories (default ignores for common artifacts).",
    )
    t.add_argument("left", type=Path)
    t.add_argument("right", type=Path)
    t.add_argument(
        "--ignore-file",
        type=Path,
        default=None,
        help="Optional file of extra fnmatch patterns (one per line).",
    )
    t.set_defaults(func=_cmd_test)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
