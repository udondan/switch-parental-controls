"""Persistent credential storage for the CLI.

Token lookup order:
  1. SWITCH_PARENTAL_CONTROL_SESSION_TOKEN environment variable (highest priority — CI/scripting)
  2. Credentials file (~/.config/switch-parental-controls/credentials)
"""

import os
from pathlib import Path


def _credentials_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "switch-parental-controls" / "credentials"


def load_token() -> str | None:
    """Return the saved session token, or None if not found."""
    path = _credentials_path()
    try:
        token = path.read_text().strip()
        return token or None
    except (OSError, UnicodeDecodeError):
        return None


def save_token(token: str) -> Path:
    """Write the session token to the credentials file and return its path."""
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token + "\n")
    except OSError:
        # Non-POSIX (e.g. Windows) — fall back to plain write without permission control
        path.write_text(token + "\n")
    return path


def delete_token() -> bool:
    """Delete the credentials file. Returns True if it existed, False if it was not found.

    Raises OSError for any other failure (e.g. PermissionError, path is a directory).
    """
    path = _credentials_path()
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
