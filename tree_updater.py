#!/usr/bin/env python3
"""
tree_updater.py — Compact, configurable project tree snapshot
-------------------------------------------------------------
Generate a depth‑limited, extension‑filtered directory listing for one
or more roots and keep a rolling backup history.

Python 3.8+, std‑lib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

DEFAULT_EXCLUDE = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    "venv",
    ".venv",
    "node_modules",
}
DEFAULT_INCLUDE_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}


def should_include(p: Path, include: set[str], exclude_patterns: Sequence[str]) -> bool:
    """Return True if *p* should appear in the listing."""

    if p.is_dir():
        name = p.name
        if name in DEFAULT_EXCLUDE or any(fnmatch.fnmatch(str(p), pat) for pat in exclude_patterns):
            return False
        return True

    return p.suffix in include and not any(fnmatch.fnmatch(str(p), pat) for pat in exclude_patterns)


def scandir_deep(root: Path, max_depth: int, include: set[str], exclude_patterns: Sequence[str]) -> Iterable[str]:
    """Yield paths **relative to *root***, depth‑first, obeying filters."""

    def _walk(cur: Path, depth: int) -> Iterable[str]:
        if depth > max_depth:
            return
        try:
            with os.scandir(cur) as it:
                for entry in sorted(it, key=lambda e: e.name):
                    p = Path(entry.path)
                    if not should_include(p, include, exclude_patterns):
                        continue
                    rel = p.relative_to(root)
                    yield str(rel)
                    if entry.is_dir(follow_symlinks=False):
                        yield from _walk(p, depth + 1)
        except PermissionError as exc:
            logging.warning("\u26A0  %s", exc)

    yield from _walk(root, 0)


def rotate_backups(target: Path, keep: int = 10) -> None:
    """Move *target* into a ``tree_backups`` folder with a timestamp."""

    bdir = target.parent / "tree_backups"
    bdir.mkdir(exist_ok=True)
    if target.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target.replace(bdir / f"{target.stem}_{ts}.txt")
    backups = sorted(bdir.glob(f"{target.stem}_*.txt"))
    for old in backups[:-keep]:
        old.unlink(missing_ok=True)


def build_listing(roots: Sequence[Path], depth: int, inc: set[str], exc: Sequence[str]) -> str:
    """Return a formatted snapshot for *roots*."""

    lines: List[str] = [
        f"# project-tree snapshot · {datetime.utcnow().isoformat(timespec='seconds')}Z",
        "",
    ]
    for r in roots:
        if not r.exists():
            logging.warning("Root not found: %s", r)
            continue
        lines.append(f"## {r}")
        for entry in scandir_deep(r, depth, inc, exc):
            lines.append(entry)
        lines.append("")  # blank line between roots
    return "\n".join(lines)


def parse_args(argv: List[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Write a depth-limited file tree to disk. "
            "File suffixes may be given without a leading dot to "
            "match any extension of that name."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="One or more directories to scan",
    )
    p.add_argument(
        "--max-depth",
        "-d",
        type=int,
        default=2,
        help="Descending levels per root",
    )
    p.add_argument(
        "--include",
        "-i",
        nargs="*",
        default=list(DEFAULT_INCLUDE_SUFFIXES),
        help="File suffixes to include (omit dot for wildcard match)",
    )
    p.add_argument(
        "--exclude",
        "-x",
        nargs="*",
        default=[],
        help="Extra glob patterns to exclude",
    )
    p.add_argument("--out", "-o", type=Path, required=True, help="Output path")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Do not exclude common project directories like .git or node_modules",
    )
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    include_set = {s if s.startswith(".") else f".{s}" for s in args.include}

    excludes = list(args.exclude)
    if args.no_default_excludes:
        logging.debug("Default exclusions disabled")
    else:
        excludes.extend(DEFAULT_EXCLUDE)

    logging.info("\U0001F4E6 scanning…")
    listing = build_listing(args.roots, args.max_depth, include_set, excludes)

    rotate_backups(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(listing, encoding="utf-8")
    logging.info("\u2705 wrote %s  (%d lines)", args.out, len(listing.splitlines()))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    sys.exit(main())

