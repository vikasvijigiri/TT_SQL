import pathlib

p = pathlib.Path('backend/app/api.py')
c = p.read_text('utf-8')
c = c.replace('RESULTS_DIR / "dab"', 'DAB_RESULTS_DIR')
c = c.replace('from backend.app.core.config import (', 'from backend.app.core.config import (\n    DAB_RESULTS_DIR,')
p.write_text(c, 'utf-8')
