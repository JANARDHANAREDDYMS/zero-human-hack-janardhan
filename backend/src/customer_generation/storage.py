"""Exclusive run directories and atomic JSON writes; existing demos are untouched."""
import json
import os
import re
import tempfile
from pathlib import Path
from .validation import ContractError


class RunStore:
    def __init__(self, root: Path, run_id: str):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', run_id):
            raise ContractError('Invalid run ID')
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / run_id
        self.path.mkdir(exist_ok=False)

    def write(self, name: str, value):
        if not re.fullmatch(r'[a-z0-9_-]+\.json', name):
            raise ContractError('Invalid artifact name')
        content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        fd, temporary = tempfile.mkstemp(prefix='.writing-', dir=self.path)
        try:
            with os.fdopen(fd, 'w') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path / name)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return name
