"""Write minimal run contexts for offline rule tests."""
import json
from pathlib import Path


def write_context(directory, point, **fields):
    path = Path(directory) / f"context-{point}.json"
    path.write_text(json.dumps(dict(execution_point=point, **fields)))
    return str(path)
