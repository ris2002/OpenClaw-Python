"""
Local secret store for provider API keys and other sensitive values.

Stores JSON encrypted with Fernet. Master key lives alongside, chmod 600.
If `cryptography` isn't installed, falls back to plaintext with a warning.

All file paths are resolved at call time (not import time) so they reflect
the user's chosen data directory even if set_data_dir() was called after import.
"""

from __future__ import annotations

import json
import os
import stat
from typing import Optional

from . import config


def _keys_enc():
    return config.DATA_DIR / "keys.enc"

def _keys_plain():
    return config.DATA_DIR / "keys.json"

def _master_key():
    return config.DATA_DIR / "master.key"


def _have_crypto() -> bool:
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        return False


def _get_fernet():
    from cryptography.fernet import Fernet
    mk = _master_key()
    if not mk.exists():
        mk.write_bytes(Fernet.generate_key())
        try:
            os.chmod(mk, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    return Fernet(mk.read_bytes())


def load_keys() -> dict:
    if _have_crypto() and _keys_enc().exists():
        try:
            f = _get_fernet()
            return json.loads(f.decrypt(_keys_enc().read_bytes()).decode("utf-8"))
        except Exception as e:
            print(f"[secret_store] decrypt failed: {e}")
            return {}
    if _keys_plain().exists():
        try:
            return json.loads(_keys_plain().read_text())
        except Exception:
            return {}
    return {}


def _write_keys(keys: dict) -> None:
    if _have_crypto():
        f = _get_fernet()
        _keys_enc().write_bytes(f.encrypt(json.dumps(keys).encode("utf-8")))
        try:
            os.chmod(_keys_enc(), stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        if _keys_plain().exists():
            try:
                _keys_plain().unlink()
            except Exception:
                pass
    else:
        print("[secret_store] WARNING: cryptography not installed — storing keys in plaintext")
        _keys_plain().write_text(json.dumps(keys, indent=2))
        try:
            os.chmod(_keys_plain(), stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass


def save_key(name: str, value: str) -> None:
    keys = load_keys()
    keys[name] = value
    _write_keys(keys)


def delete_key(name: str) -> None:
    keys = load_keys()
    if name in keys:
        del keys[name]
        _write_keys(keys)


def get_key(name: str) -> Optional[str]:
    return load_keys().get(name)
