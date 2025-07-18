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


Install dependencies with:
`python -m pip install pathspec>=0.12.0`
