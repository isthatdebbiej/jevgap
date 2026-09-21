"""Local credentials are supplied by environment, never repository paths."""

import os
from pathlib import Path


def validate_credentials():
    missing = []
    for name in ("ASTRA_KEY_FILE", "JEV_KEY_FILE"):
        value = os.environ.get(name)
        if not value or not Path(value).expanduser().is_file():
            missing.append(name)
        elif Path(value).expanduser().stat().st_size == 0:
            missing.append(name)
        else:
            os.environ[name] = str(Path(value).expanduser().resolve())
    if missing:
        raise ValueError("Set readable credential-file paths for: " + ", ".join(missing))
