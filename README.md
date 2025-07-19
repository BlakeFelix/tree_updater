# Tree Updater

`tree_updater.py` generates compact listings of project files. It can output
standard Markdown or, with `--json`, a nested JSON structure. The script writes
`tree_output_compact.txt` (or the specified `--out` path) and maintains rolling
backups and diffs.

## Usage

```bash
python tree_updater.py --roots . --out tree_output_compact.txt
```

JSON mode with gitignore support:

```bash
python tree_updater.py --roots . --out tree_output_compact.txt --json --gitignore
```

Import the library function:

```python
from tree_updater import get_tree_dict
```

New in this release:

- `--config FILE` loads defaults for `roots`, `include`, `exclude` and `depth` from a YAML or JSON file (CLI flags override).
- `--skip-unchanged` exits early when the snapshot has not changed.
- Multiple roots are scanned in parallel for faster I/O.

Example YAML config:

```yaml
roots:
  - .
depth: 2
include: [py, md]
exclude: [build/*]
```

Install dependencies with:
`python -m pip install pathspec>=0.12.0 PyYAML>=6.0`
