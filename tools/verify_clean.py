"""Verify zero non-ASCII chars remain in source files."""
import os, sys
from pathlib import Path

EXTS = {'.py', '.sh', '.md', '.yml', '.yaml', '.toml', '.json',
        '.ps1', '.txt', '.env', '.example', '.cfg', '.ini', '.sql'}
SKIP_DIRS = {'.git', 'venv', 'venv_new', 'node_modules', '__pycache__',
             '.mypy_cache', '.ruff_cache', '.pytest_cache', 'tools'}

dirty = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        ext = Path(f).suffix.lower()
        if ext in EXTS or f in {'.env', '.env.example', 'Makefile'}:
            fp = os.path.join(root, f)
            try:
                txt = open(fp, encoding='utf-8', errors='replace').read()
                samples = [(i+1, repr(ch), hex(ord(ch))) for i, ch in enumerate(txt) if ord(ch) > 127]
                if samples:
                    dirty.append((fp, samples[:3]))
            except Exception as e:
                pass

if dirty:
    print(f'REMAINING non-ASCII in {len(dirty)} files:')
    for fp, samples in dirty:
        print(f'  {fp}')
        for pos, ch, cp in samples:
            print(f'    pos {pos}: {ch} ({cp})')
else:
    print('All clean -- zero non-ASCII characters remaining.')
