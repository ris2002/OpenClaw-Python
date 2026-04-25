"""App-wide configuration. Paths and metadata only — no logic beyond path resolution."""

from pathlib import Path

APP_NAME = "OpenClaw-Py"
APP_VERSION = "0.2.0"

# Tiny bootstrap file in home dir — stores the chosen data directory path.
# This is the ONLY file OpenClaw-Py ever writes to the home dir directly.
_BOOTSTRAP = Path.home() / ".openclaw-py-location"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "app://.",
]


def default_data_dir() -> Path:
    """Desktop/openclaw-py on any OS, falling back to home if Desktop doesn't exist."""
    desktop = Path.home() / "Desktop"
    return (desktop if desktop.exists() else Path.home()) / "openclaw-py"


def _resolve() -> Path:
    if _BOOTSTRAP.exists():
        txt = _BOOTSTRAP.read_text().strip()
        if txt:
            return Path(txt)
    return default_data_dir()


# Module-level variable — updated by set_data_dir() when user confirms location.
DATA_DIR: Path = _resolve()


def is_first_run() -> bool:
    """True until the user has confirmed a data directory location."""
    return not _BOOTSTRAP.exists()


def set_data_dir(path: Path) -> None:
    """Create the data directory and save its location to the bootstrap file."""
    global DATA_DIR
    path = Path(path).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    _BOOTSTRAP.write_text(str(path))
    DATA_DIR = path


# If the user already confirmed in a previous run, ensure the dir exists.
if not is_first_run():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
