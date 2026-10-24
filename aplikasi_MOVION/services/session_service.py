from database.supabase_client import supabase

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
SESSION_FILE = BASE_DIR / "config" / "session.json"

def save_session(session: Any) -> bool:
    if session is None:
        return False

    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)

    if not access_token or not refresh_token:
       return False

    try:
        data = {
           "access_token": access_token,
           "refresh_token": refresh_token,
        }

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

        temporary_file = SESSION_FILE.with_suffix(".tmp")
        temporary_file.write_text(
           json.dumps(data),
           encoding="utf-8",
        )
        temporary_file.replace(SESSION_FILE)

        return True
    except (OSError, TypeError):
        #print("Failed to save session:", e)
        return False

def load_session() -> bool:
    if not SESSION_FILE.exists():
      return False

    try:
        content = SESSION_FILE.read_text(encoding="utf-8").strip()

        if not content:
            raise ValueError("Session file is empty")

        data = json.loads(content)

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token or not refresh_token:
            raise ValueError("Session token is incomplete")

        response = supabase.auth.set_session(
            access_token,
            refresh_token,
        )

        session = getattr(response, "session", None)

        if session is None:
            session = supabase.auth.get_session()

        if session is None:
            raise RuntimeError("Session could not be restored")

        user_response = supabase.auth.get_user(session.access_token)
        user = getattr(user_response, "user", None)

        if user is None:
            raise RuntimeError("Session user could not be verified")

        if not save_session(session):
            raise RuntimeError("Updated session could not be saved")

        return True
    except (
        json.JSONDecodeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        RuntimeError,
    ):
        clear_session()
        return False

    except Exception:
        clear_session()
        return False

def get_current_session():
    try:
        session = supabase.auth.get_session()

        return session

    except Exception:
        return None

def clear_session() -> bool:
    try:
      if SESSION_FILE.exists():
        SESSION_FILE.unlink()
      return True
    except OSError:
        return False
