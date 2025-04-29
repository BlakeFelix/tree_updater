import os
from pathlib import Path
import datetime

ROOTS = [
    Path.home() / "net_watchdog",
    Path.home() / "editbot",
    Path.home() / "tree_updater",
]

OUTPUT_FILE = Path.home() / "tree_updater" / "tree_output_compact.txt"
BACKUP_DIR = Path.home() / "tree_updater" / "tree_backups"

# Settings
MAX_DEPTH = 2
INCLUDE_SUFFIXES = {'.py', '.txt'}
EXCLUDE_DIRS = {'__pycache__', 'venv', '.git', 'snap'}

def should_include(file_path):
    if file_path.is_dir():
        return file_path.name not in EXCLUDE_DIRS
    return file_path.suffix in INCLUDE_SUFFIXES

def scan_directory(root, max_depth):
    entries = []

    def _scan(current_path, current_depth):
        if current_depth > max_depth:
            return
        for child in sorted(current_path.iterdir()):
            rel_path = child.relative_to(root)
            if should_include(child):
                entries.append(str(rel_path))
            if child.is_dir() and child.name not in EXCLUDE_DIRS:
                _scan(child, current_depth + 1)

    _scan(root, 0)
    return entries

def fade_backups():
    BACKUP_DIR.mkdir(exist_ok=True)
    backups = sorted(BACKUP_DIR.glob("tree_output_*.txt"))
    if len(backups) > 10:
        for backup in backups[:-10]:
            backup.unlink()

def main():
    print("[📦] Scanning project structure...")
    all_entries = []
    for root in ROOTS:
        if root.exists():
            print(f"[📂] Scanning {root}")
            entries = scan_directory(root, MAX_DEPTH)
            all_entries.append(f"# {root.name}/")
            all_entries.extend(entries)
            all_entries.append("")

    print(f"[📋] Total entries: {len(all_entries)}")

    # Backup old tree
    if OUTPUT_FILE.exists():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(exist_ok=True)
        OUTPUT_FILE.rename(BACKUP_DIR / f"tree_output_{timestamp}.txt")

    fade_backups()

    with OUTPUT_FILE.open("w") as f:
        f.write("\n".join(all_entries))

    print(f"[✔] Wrote new tree to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
