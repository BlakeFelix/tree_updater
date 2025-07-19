#!/usr/bin/env python3
"""tree_updater - write project tree snapshots

Supports Markdown or JSON output, optional gitignore filtering,
and automatic diff/backups. Can also be imported as a library via
``get_tree_dict``.
"""

from __future__ import annotations

import argparse
import fnmatch
import gzip
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

try:
    from pathspec import PathSpec
except Exception:  # pragma: no cover - optional dependency
    PathSpec = None  # type: ignore

# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

DEFAULT_INCLUDE_SUFFIXES = {
    ".py",
    ".pyi",
    ".ipynb",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".txt",
    ".md",
    ".rst",
    ".html",
    ".css",
    ".scss",
    ".sh",
    ".bat",
    ".ps1",
    ".ini",
    ".cfg",
    ".gradle",
    ".kt",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".go",
    ".rs",
    ".swift",
}

SPECIAL_NAMES = {"Dockerfile", "Makefile", "LICENSE", "README"}

DEFAULT_EXCLUDE = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    "venv",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
}

BACKUP_DIRNAME = "tree_backups"
DIFF_FILE = "tree_diff_latest.txt"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_gitignore(root: Path) -> PathSpec | None:
    """Load ``.gitignore`` from *root* if ``--gitignore`` is enabled."""

    if not (root / ".gitignore").exists() or PathSpec is None:
        return None
    with (root / ".gitignore").open() as fh:
        return PathSpec.from_lines("gitwildmatch", fh)


def match_exclude(rel: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in patterns)


# ---------------------------------------------------------------------------
# tree building
# ---------------------------------------------------------------------------


def get_tree_dict(
    roots: list[str],
    depth: int = 2,
    include: set[str] | None = None,
    exclude: Sequence[str] | None = None,
    use_gitignore: bool = False,
) -> dict:
    """Return a nested dictionary describing *roots*."""

    inc = {s.lower() for s in (include or DEFAULT_INCLUDE_SUFFIXES)}
    exc = list(exclude or [])

    def build_node(root: Path, cur_depth: int, git: PathSpec | None) -> dict | None:
        rel = root.relative_to(base).as_posix()
        if git and git.match_file(rel):
            return None
        if match_exclude(rel, exc):
            return None
        if root.is_dir():
            if root.name in DEFAULT_EXCLUDE and rel:
                return None
            node = {"name": rel or root.as_posix(), "type": "dir", "children": []}
            if cur_depth >= depth:
                return node
            try:
                for child in sorted(root.iterdir(), key=lambda p: p.name):
                    child_node = build_node(child, cur_depth + 1, git)
                    if child_node:
                        node["children"].append(child_node)
            except PermissionError as exc:  # pragma: no cover - permissions vary
                logging.warning("%s", exc)
            return node
        else:
            if root.name in SPECIAL_NAMES or root.suffix.lower() in inc:
                stat = root.stat()
                return {
                    "name": rel,
                    "type": "file",
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
        return None

    tree = {"name": "", "type": "dir", "children": []}
    for r in map(Path, roots):
        base = r
        git = load_gitignore(r) if use_gitignore else None
        node = build_node(r, 0, git)
        if node:
            tree["children"].append(node)
    return tree


# ---------------------------------------------------------------------------
# scanning / output helpers
# ---------------------------------------------------------------------------


def scandir_paths(
    root: Path,
    depth: int,
    include: set[str],
    exclude: Sequence[str],
    git: PathSpec | None,
) -> Iterable[str]:
    """Yield paths relative to *root* that match filters."""

    def _walk(current: Path, d: int) -> Iterable[str]:
        if d > depth:
            return
        try:
            with os.scandir(current) as it:
                for entry in sorted(it, key=lambda e: e.name):
                    p = Path(entry.path)
                    rel = p.relative_to(root).as_posix()
                    if git and git.match_file(rel):
                        continue
                    if match_exclude(rel, exclude):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if p.name in DEFAULT_EXCLUDE and rel:
                            continue
                        yield rel
                        yield from _walk(p, d + 1)
                    else:
                        if p.name in SPECIAL_NAMES or p.suffix.lower() in include:
                            yield rel
        except PermissionError as exc:
            logging.warning("%s", exc)

    yield from _walk(root, 0)


def rotate_backups(target: Path, keep: int = 10) -> None:
    """Rotate snapshots in ``tree_backups`` directory."""

    bdir = target.parent / BACKUP_DIRNAME
    bdir.mkdir(exist_ok=True)
    if target.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = bdir / f"{target.stem}_{ts}.txt"
        target.replace(backup)
    backups = sorted(bdir.glob(f"{target.stem}_*.txt"))
    if len(backups) > keep:
        for old in backups[:-keep]:
            if not old.with_suffix(old.suffix + ".gz").exists():
                with open(old, "rb") as f_in, gzip.open(
                    old.with_suffix(old.suffix + ".gz"), "wb"
                ) as f_out:
                    f_out.write(f_in.read())
                old.unlink(missing_ok=True)


def compute_diff(prev: Path, new: Path, diff_path: Path) -> tuple[int, int]:
    prev_lines: list[str] = []
    if prev.exists():
        prev_lines = prev.read_text(encoding="utf-8").splitlines()[1:]
    new_lines = new.read_text(encoding="utf-8").splitlines()[1:]
    added = sorted(set(new_lines) - set(prev_lines))
    removed = sorted(set(prev_lines) - set(new_lines))
    with diff_path.open("w", encoding="utf-8") as fh:
        fh.write(f"added: {len(added)}\nremoved: {len(removed)}\n")
        for line in added[:100]:
            fh.write(f"+ {line}\n")
        for line in removed[:100]:
            fh.write(f"- {line}\n")
    return len(added), len(removed)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Write a depth-limited file tree to disk",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--roots", nargs="+", type=Path, required=True)
    p.add_argument(
        "--depth", "-d", type=int, default=2, help="Descending levels per root"
    )
    p.add_argument("--include", "-i", nargs="*", default=list(DEFAULT_INCLUDE_SUFFIXES))
    p.add_argument(
        "--exclude", "-x", nargs="*", default=[], help="Extra glob patterns to exclude"
    )
    p.add_argument("--out", "-o", type=Path, required=True, help="Output snapshot path")
    p.add_argument("--verbose", "-v", action="store_true")

    p.add_argument("--json", action="store_true", help="Write JSON instead of Markdown")
    p.add_argument("--gitignore", action="store_true", help="Honor .gitignore files")
    p.add_argument("--config", type=Path, help="YAML/JSON file with default roots/include/exclude/depth")
    p.add_argument("--skip-unchanged", action="store_true", help="Abort if no tree change (ignoring timestamp line)")
    p.add_argument(
        "--no-backup", action="store_true", help="Skip rotating tree_backups"
    )
    p.add_argument("--no-diff", action="store_true", help="Skip diff generation")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    # ------------------------------------------------------------------
    # If --config supplied, merge values (CLI still wins)
    # ------------------------------------------------------------------
    if args.config and args.config.exists():
        with args.config.open() as fh:
            cfg = yaml.safe_load(fh) if args.config.suffix in {".yml", ".yaml"} \
                else json.load(fh)
        # merge helpers
        def merge(key, default):
            return cfg.get(key, default)

        args.roots = merge("roots", args.roots)
        args.depth = merge("depth", args.depth)
        args.include = merge("include", args.include)
        args.exclude = merge("exclude", args.exclude)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    include = {s if s.startswith(".") else f".{s}" for s in args.include}
    include = {s.lower() for s in include}
    exclude = list(args.exclude)
    roots = [Path(r) for r in args.roots]

    for r in roots:
        if not r.exists():
            logging.warning("Root not found: %s", r)

    unchanged = False
    if args.skip_unchanged and args.out.exists():
        prev_lines = args.out.read_text(encoding="utf-8").splitlines()[1:]
        current = []
        for r in args.roots:
            git = load_gitignore(r) if args.gitignore else None
            current.extend(scandir_paths(Path(r), args.depth,
                {s.lower() if s.startswith('.') else f'.{s}'.lower() for s in args.include},
                list(args.exclude), git))
        unchanged = set(prev_lines) == set(current)
        if unchanged:
            logging.info("snapshot unchanged – exiting")
            return 0

    prev_snapshot = args.out if args.out.exists() else None

    if not args.no_backup:
        rotate_backups(args.out)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        header = f"# project-tree snapshot · {datetime.utcnow().isoformat(timespec='seconds')}Z"
        print(header, file=fh)
        print(file=fh)
        def _one_root(root: Path) -> list[str]:
            git = load_gitignore(root) if args.gitignore else None
            return list(scandir_paths(root, args.depth, include, exclude, git))

        with ThreadPoolExecutor(max_workers=len(roots)) as pool:
            results = pool.map(_one_root, roots)

        for root, rels in zip(roots, results):
            print(f"## {root.as_posix()}", file=fh)
            for rel in rels:
                print(rel, file=fh)
            print(file=fh)

    if args.json:
        tree = get_tree_dict(
            [str(r) for r in roots],
            depth=args.depth,
            include=include,
            exclude=exclude,
            use_gitignore=args.gitignore,
        )
        json_path = args.out.with_suffix(".json")
        json_path.write_text(json.dumps(tree, indent=2), encoding="utf-8")
        logging.info("wrote JSON snapshot %s", json_path)

    if not args.no_diff:
        diff_path = args.out.parent / DIFF_FILE
        added, removed = compute_diff(prev_snapshot or args.out, args.out, diff_path)
        logging.info("diff: +%d -%d (see %s)", added, removed, diff_path)

    return 0


if __name__ == "__main__":  # pragma: no cover - script mode
    raise SystemExit(main())
