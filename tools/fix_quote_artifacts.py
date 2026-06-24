"""
Fix mojibake-derived quote artifacts: runs of 2+ single-quotes that came
from U+201A being replaced with ' during char-clean pass.

Targets ONLY:
  1. Pure comment lines (stripped line starts with #)
  2. f-string / regular string lines where ''' appears INSIDE double-quoted content
     (i.e. NOT at start/end of a line as a Python string delimiter)

Skips:
  - Lines whose stripped form starts with ''' (docstrings, SQL triple-quotes)
  - Lines whose stripped form ends with ''') or ''', (end of triple-quoted strings)
  - Any line that is a legitimate Python triple-quoted string boundary
"""
import os, re
from pathlib import Path

SKIP_DIRS = {'.git', 'venv', 'venv_new', 'node_modules', '__pycache__',
             '.mypy_cache', '.ruff_cache', '.pytest_cache', 'tools'}
EXTS = {'.py', '.sh', '.md', '.yml', '.yaml', '.toml', '.json',
        '.ps1', '.txt', '.env', '.example', '.cfg', '.ini', '.sql'}

MULTI_QUOTE = re.compile(r"'{2,}")


def is_triple_quote_boundary(line: str) -> bool:
    """Return True if this line is a Python triple-quoted string boundary."""
    stripped = line.strip()
    # Opens a triple-quoted string
    if stripped.startswith("'''") or stripped.startswith('"""'):
        return True
    # Closes a triple-quoted string (common patterns: ''') or ''',)
    if stripped.endswith("''')") or stripped.endswith("''',") or stripped == "'''":
        return True
    return False


def should_fix_line(line: str) -> bool:
    stripped = line.strip()
    # Always fix pure comment lines
    if stripped.startswith('#'):
        return True
    # Fix f-string / regular string content lines that have 2+ quotes
    # but skip triple-quoted string boundaries
    if MULTI_QUOTE.search(line) and not is_triple_quote_boundary(line):
        # Additional guard: skip if it looks like a SQL execute call
        if "execute('''" in line or "execute(\"\"\"" in line:
            return False
        return True
    return False


def fix_line(line: str) -> str:
    def replacer(m):
        return '-' * len(m.group(0))
    return MULTI_QUOTE.sub(replacer, line)


def process_file(fp: Path) -> bool:
    text = fp.read_text(encoding='utf-8')
    if "''" not in text:
        return False
    lines = text.splitlines(keepends=True)
    new_lines = []
    changed = False
    for line in lines:
        if "''" in line and should_fix_line(line):
            fixed = fix_line(line)
            if fixed != line:
                changed = True
                new_lines.append(fixed)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    if not changed:
        return False
    fp.write_text(''.join(new_lines), encoding='utf-8')
    return True


def main():
    root = Path(__file__).resolve().parent.parent
    changed = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in EXTS and fname not in {'Makefile', '.env', '.env.example'}:
                continue
            if fname in {'fix_quote_artifacts.py', 'clean_chars.py', 'verify_clean.py'}:
                continue
            fp = Path(dirpath) / fname
            if process_file(fp):
                changed.append(str(fp.relative_to(root)))

    print(f'Fixed quote artifacts in {len(changed)} file(s):')
    for f in sorted(changed):
        print(f'  {f}')


if __name__ == '__main__':
    main()
