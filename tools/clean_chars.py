"""
Clean non-ASCII / mojibake / emoji characters from all text source files.
Run from repo root: python tools/clean_chars.py
"""
import os
from pathlib import Path

EXTS = {'.py', '.sh', '.md', '.yml', '.yaml', '.toml', '.json',
        '.ps1', '.txt', '.env', '.example', '.cfg', '.ini', '.sql'}
SKIP_DIRS = {'.git', 'venv', 'venv_new', 'node_modules', '__pycache__',
             '.mypy_cache', '.ruff_cache', '.pytest_cache', 'tools'}

# ---------------------------------------------------------------------------
# Ordered replacement table (longest / most specific first where needed)
# ---------------------------------------------------------------------------
REPLACEMENTS = [
    # Mojibake arrow patterns (double-encoded Unicode in source code)
    ('Ã¢â€ â€™', '=>'),   # => arrow mojibake
    ('â€“', '--'),   # em-dash mojibake variant
    ('â€”', '--'),   # em-dash mojibake variant 2
    ('â€™', "'"),    # right single quote mojibake
    ('â€œ', '"'),    # left double quote mojibake
    ('â€…', '...'),  # ellipsis mojibake

    # Smart / curly quotes
    ('“', '"'),   # LEFT DOUBLE QUOTATION MARK
    ('”', '"'),   # RIGHT DOUBLE QUOTATION MARK
    ('‘', "'"),   # LEFT SINGLE QUOTATION MARK
    ('’', "'"),   # RIGHT SINGLE QUOTATION MARK
    ('‚', "'"),   # SINGLE LOW-9 QUOTATION MARK (mojibake artifact)
    ('„', '"'),   # DOUBLE LOW-9 QUOTATION MARK

    # Em / en dash
    ('—', '--'),  # EM DASH
    ('–', '-'),   # EN DASH

    # Ellipsis
    ('…', '...'), # HORIZONTAL ELLIPSIS

    # Box-drawing characters
    ('─', '-'),   # BOX DRAWINGS LIGHT HORIZONTAL ─
    ('━', '-'),   # BOX DRAWINGS HEAVY HORIZONTAL
    ('│', '|'),   # BOX DRAWINGS LIGHT VERTICAL |
    ('┃', '|'),   # BOX DRAWINGS HEAVY VERTICAL
    ('┌', '+'),   # BOX DRAWINGS LIGHT DOWN AND RIGHT
    ('┐', '+'),   # BOX DRAWINGS LIGHT DOWN AND LEFT
    ('└', '+'),   # BOX DRAWINGS LIGHT UP AND RIGHT
    ('┘', '+'),   # BOX DRAWINGS LIGHT UP AND LEFT
    ('├', '+-'),  # BOX DRAWINGS LIGHT VERTICAL AND RIGHT
    ('┤', '-+'),  # BOX DRAWINGS LIGHT VERTICAL AND LEFT
    ('┬', '-'),   # BOX DRAWINGS LIGHT DOWN AND HORIZONTAL
    ('┴', '-'),   # BOX DRAWINGS LIGHT UP AND HORIZONTAL
    ('┼', '+'),   # BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
    ('═', '='),   # BOX DRAWINGS DOUBLE HORIZONTAL
    ('║', '|'),   # BOX DRAWINGS DOUBLE VERTICAL
    ('█', '#'),   # FULL BLOCK
    ('░', '.'),   # LIGHT SHADE
    ('▒', ':'),   # MEDIUM SHADE
    ('▓', '#'),   # DARK SHADE

    # Arrows
    ('←', '<-'),  # LEFTWARDS ARROW
    ('→', '->'),  # RIGHTWARDS ARROW
    ('⇐', '<='),  # LEFTWARDS DOUBLE ARROW
    ('⇒', '=>'),  # RIGHTWARDS DOUBLE ARROW
    ('↠', '=>'),  # RIGHTWARDS TWO HEADED ARROW
    ('↔', '<->'), # LEFT RIGHT ARROW

    # Math symbols
    ('≥', '>='),  # GREATER-THAN OR EQUAL TO
    ('≤', '<='),  # LESS-THAN OR EQUAL TO
    ('≠', '!='),  # NOT EQUAL TO
    ('≈', '~='),  # ALMOST EQUAL TO
    ('×', 'x'),   # MULTIPLICATION SIGN
    ('±', '+-'),  # PLUS-MINUS SIGN

    # Greek letters (used in math comments)
    ('α', 'alpha'),
    ('β', 'beta'),
    ('γ', 'gamma'),
    ('δ', 'delta'),
    ('ε', 'epsilon'),
    ('Σ', 'Sigma'),
    ('π', 'pi'),
    ('λ', 'lambda'),

    # Emoji: replace with short ASCII label or remove
    ('⚠️', '[!]'),    # WARNING SIGN + variation selector
    ('⚠', '[!]'),           # WARNING SIGN
    ('✅', '[OK]'),          # WHITE HEAVY CHECK MARK
    ('✓', '[OK]'),          # CHECK MARK
    ('✗', '[X]'),           # BALLOT X
    ('❌', '[X]'),           # CROSS MARK
    ('⏱', ''),              # STOPWATCH
    ('\U0001f4a1', ''),          # LIGHT BULB
    ('\U0001f4e1', ''),          # SATELLITE ANTENNA
    ('\U0001f534', ''),          # RED CIRCLE
    ('\U0001f9e0', ''),          # BRAIN
    ('\U0001f680', ''),          # ROCKET
    ('\U0001f3c6', ''),          # TROPHY
    ('\U0001f4ca', ''),          # BAR CHART
    ('\U0001f525', ''),          # FIRE
    ('\U0001f4dd', ''),          # MEMO

    # Bullet / list markers
    ('•', '-'),   # BULLET
    ('‣', '-'),   # TRIANGULAR BULLET

    # Invisible / formatting chars: remove
    ('​', ''),    # ZERO WIDTH SPACE
    ('‌', ''),    # ZERO WIDTH NON-JOINER
    ('‍', ''),    # ZERO WIDTH JOINER
    ('­', ''),    # SOFT HYPHEN
    ('﻿', ''),    # BOM / ZERO WIDTH NO-BREAK SPACE
    ('️', ''),    # VARIATION SELECTOR-16
    ('', ''),    # C1 control char (garbage)
    ('', ''),    # C1 control char (garbage)
    ('', ''),    # C1 control char (garbage)

    # Misc typography
    (' ', ' '),   # NO-BREAK SPACE -> regular space
    ('°', 'deg'), # DEGREE SIGN
]


def clean_text(text: str) -> str:
    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new)
    # Strip any remaining non-ASCII that wasn't in the table above
    # (catches all mojibake fragments: Ã, ¢, â, €, ¬, ‚, etc.)
    if any(ord(c) > 127 for c in text):
        text = ''.join(c if ord(c) <= 127 else '' for c in text)
    return text


def process_file(fp: Path) -> bool:
    try:
        raw = fp.read_bytes()
        # Decode; treat BOM-UTF-8 too
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('utf-8', errors='replace')

        cleaned = clean_text(text)
        if cleaned == text:
            return False
        fp.write_text(cleaned, encoding='utf-8')
        return True
    except Exception as e:
        print(f'  SKIP {fp}: {e}')
        return False


def main():
    root = Path(__file__).resolve().parent.parent
    changed = []

    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in EXTS and fname not in {'Makefile', '.env', '.env.example'}:
                continue
            fp = Path(dirpath) / fname
            # Don't clean this script itself
            if fp.name == 'clean_chars.py':
                continue
            rel = fp.relative_to(root)
            if process_file(fp):
                changed.append(str(rel))

    print(f'\nCleaned {len(changed)} file(s):')
    for f in sorted(changed):
        print(f'  {f}')
    if not changed:
        print('  (none needed cleaning)')


if __name__ == '__main__':
    main()
