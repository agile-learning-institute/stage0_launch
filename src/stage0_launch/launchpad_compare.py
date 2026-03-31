from __future__ import annotations

import fnmatch
import sys
from pathlib import Path
from typing import TextIO

import pathspec

# Basenames skipped for launchpad-test diffs only (not a rule against committing
# locks in real repos). merge-all also skips copying these from template trees.
DEPENDENCY_LOCK_BASENAMES: frozenset[str] = frozenset(
    {
        "Pipfile.lock",
        "poetry.lock",
        "pdm.lock",
        "uv.lock",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "npm-shrinkwrap.json",
        "Gemfile.lock",
    }
)

# Directory name fragments: skip any path containing these segments.
_IGNORE_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        ".mypy_cache",
        "dist",
        "build",
        ".eggs",
    }
)

_IGNORE_SUFFIXES = (".pyc", ".pyo")


def _load_gitignore_pairs(root: Path) -> list[tuple[Path, pathspec.PathSpec]]:
    """(anchor_dir, spec) sorted shallow-first; patterns apply to paths under anchor."""
    root = root.resolve()
    pairs: list[tuple[Path, pathspec.PathSpec]] = []
    for gi in sorted(root.rglob(".gitignore"), key=lambda p: (len(p.parts), str(p))):
        if not gi.is_file():
            continue
        anchor = gi.parent.resolve()
        lines: list[str] = []
        for ln in gi.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)
        if not lines:
            continue
        pairs.append((anchor, pathspec.PathSpec.from_lines("gitignore", lines)))
    return pairs


def _ignored_by_gitignore(rel: Path, root: Path, pairs: list[tuple[Path, pathspec.PathSpec]]) -> bool:
    """True if ``rel`` (relative to ``root``) matches any loaded ``.gitignore`` rule."""
    try:
        abs_file = (root / rel).resolve()
    except OSError:
        return False
    for anchor, spec in pairs:
        try:
            rel_to_anchor = abs_file.relative_to(anchor)
        except ValueError:
            continue
        if spec.match_file(rel_to_anchor.as_posix()):
            return True
    return False


def _path_is_ignored(
    rel: Path,
    root: Path,
    gitignore_pairs: list[tuple[Path, pathspec.PathSpec]],
    extra_patterns: list[str],
) -> bool:
    parts = rel.parts
    if any(p in _IGNORE_DIR_NAMES for p in parts):
        return True
    name = rel.name
    if name == ".DS_Store":
        return True
    if name in DEPENDENCY_LOCK_BASENAMES:
        return True
    if name.endswith(_IGNORE_SUFFIXES):
        return True
    if name.endswith(".egg-info"):
        return True
    if _ignored_by_gitignore(rel, root, gitignore_pairs):
        return True
    s = rel.as_posix()
    for pat in extra_patterns:
        p = pat.strip()
        if not p or p.startswith("#"):
            continue
        if fnmatch.fnmatch(s, p) or fnmatch.fnmatch(name, p):
            return True
    return False


def _load_extra_patterns(ignore_file: Path | None) -> list[str]:
    if ignore_file is None:
        return []
    text = ignore_file.read_text(encoding="utf-8", errors="replace")
    return [ln.rstrip("\n") for ln in text.splitlines()]


def _bytes_equal_allow_missing_final_newline(a: bytes, b: bytes) -> bool:
    """True if identical, or differ only by a single trailing LF (merge output often omits it)."""
    if a == b:
        return True
    if a == b + b"\n" or a + b"\n" == b:
        return True
    return False


def _collect_files(
    root: Path,
    gitignore_pairs: list[tuple[Path, pathspec.PathSpec]],
    extra_patterns: list[str],
) -> dict[str, Path]:
    """Relative posix path (file only) → absolute path."""
    out: dict[str, Path] = {}
    root = root.resolve()
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if _path_is_ignored(rel, root, gitignore_pairs, extra_patterns):
            continue
        out[rel.as_posix()] = p
    return out


def compare_launchpads(
    left: Path,
    right: Path,
    *,
    ignore_file: Path | None = None,
    out: TextIO | None = None,
) -> int:
    """
    Compare two directory trees. Return 0 if equivalent under ignore rules,
    non-zero if differences exist (also writes a summary to ``out``).

    Ignores match **local diff** expectations: built-in noise, dependency lock
    basenames (so “has run install” vs “fresh merge” trees compare without false
    fails—**not** a recommendation to omit locks from git in real repos),
    per-root ``.gitignore`` (any depth), and optional ``--ignore-file`` patterns.
    """
    sink: TextIO = out if out is not None else sys.stdout
    extra = _load_extra_patterns(ignore_file)
    left_root = left.resolve()
    right_root = right.resolve()
    left_gi = _load_gitignore_pairs(left_root)
    right_gi = _load_gitignore_pairs(right_root)
    left_files = _collect_files(left_root, left_gi, extra)
    right_files = _collect_files(right_root, right_gi, extra)
    all_keys = sorted(set(left_files) | set(right_files))
    diffs: list[str] = []
    for key in all_keys:
        lp = left_files.get(key)
        rp = right_files.get(key)
        if lp is None:
            diffs.append(f"only in right: {key}")
            continue
        if rp is None:
            diffs.append(f"only in left: {key}")
            continue
        try:
            lb = lp.read_bytes()
            rb = rp.read_bytes()
        except OSError as e:
            diffs.append(f"differ (read error): {key} ({e})")
            continue
        if not _bytes_equal_allow_missing_final_newline(lb, rb):
            diffs.append(f"differ: {key}")
            if len(diffs) >= 500:
                diffs.append("… (truncated)")
                break
    if not diffs:
        sink.write("OK — no file differences under ignore rules.\n")
        return 0
    sink.write(f"FAIL — {len(diffs)} difference(s):\n")
    for line in diffs:
        sink.write(f"  {line}\n")
    return 1
