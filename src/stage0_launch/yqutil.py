from __future__ import annotations

import subprocess
from pathlib import Path


def yq_eval(expr: str, yaml_path: Path) -> str:
    r = subprocess.run(
        ["yq", "-r", expr, str(yaml_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return (r.stdout or "").strip()
