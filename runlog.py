"""Run folders: every task run gets runs/<run_id>/ with its task, plans and later results."""
import json
from datetime import datetime
from pathlib import Path

RUNS = Path(__file__).resolve().parent / 'runs'


def new_run(task, root=RUNS):
    """Create runs/<run_id>/ (date-time id, suffixed if it already exists) and save task.txt."""
    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    run_dir, n = Path(root) / run_id, 1
    while run_dir.exists():
        n += 1
        run_dir = Path(root) / f'{run_id}-{n}'
    run_dir.mkdir(parents=True)
    (run_dir / 'task.txt').write_text(task + '\n')
    return run_dir


def save_json(run_dir, name, data):
    """Write data as pretty JSON to run_dir/name and return the path."""
    path = Path(run_dir) / name
    path.write_text(json.dumps(data, indent=2, default=str) + '\n')
    return path
