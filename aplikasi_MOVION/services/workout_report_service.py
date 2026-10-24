from database.supabase_client import supabase
from datetime import datetime, timezone

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _normalize_gender(value):
    gender = str(value or "").strip().lower()
    if gender in ["female", "f", "wanita", "perempuan"]:
        return "female"
    return "male"

def _safe_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

def _safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def _participant_payload(session_id, participant, user_id=None):
    participant = participant or {}

    height_cm = participant.get("height_cm")
    if height_cm is None:
        height_cm = participant.get("height")

    weight_kg = participant.get("weight_kg")
    if weight_kg is None:
        weight_kg = participant.get("weight")

    return {
        "session_id": session_id,
        "user_id": user_id,
        "name": participant.get("name"),
        "age": _safe_int(participant.get("age")),
        "gender": _normalize_gender(participant.get("gender")),
        "height_cm": _safe_float(height_cm),
        "weight_kg": _safe_float(weight_kg),
    }

def create_workout_session(user_id, mode):
    try:
        response = (
            supabase
            .table("workout_sessions")
            .insert({
                "user_id": user_id,
                "mode": mode,
                "started_at": _now_iso(),
                "status": "ongoing",
            })
            .execute()
        )

        if not response.data:
            return {
                "success": False,
                "error": "Failed to create workout session."
            }

        return {
            "success": True,
            "data": response.data[0]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def insert_workout_participant(session_id, participant, user_id=None):
    try:
        payload = _participant_payload(
            session_id=session_id,
            participant=participant,
            user_id=user_id,
        )

        response = (
            supabase
            .table("workout_participants")
            .insert(payload)
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def upsert_workout_report(session_id, report_data):
    try:
        payload = {
            "session_id": session_id,
            "report_data": report_data,
        }

        response = (
            supabase
            .table("workout_reports")
            .upsert(payload, on_conflict="session_id")
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def complete_workout_session(session_id, report_data, user1, user2=None):
    try:
        if not session_id:
            return {
                "success": False,
                "error": "Missing session_id."
            }

        participant1_result = insert_workout_participant(
            session_id=session_id,
            participant=user1,
            user_id=(user1 or {}).get("id")
        )

        if not participant1_result["success"]:
            return participant1_result

        if user2:
            participant2_result = insert_workout_participant(
                session_id=session_id,
                participant=user2,
                user_id=(user2 or {}).get("id")
            )

            if not participant2_result["success"]:
                return participant2_result

        report_result = upsert_workout_report(
            session_id=session_id,
            report_data=report_data
        )

        if not report_result["success"]:
            return report_result

        response = (
            supabase
            .table("workout_sessions")
            .update({
                "ended_at": _now_iso(),
                "status": "completed",
            })
            .eq("id", session_id)
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def cancel_workout_session(session_id):
    try:
        if not session_id:
            return {
                "success": True,
                "data": None
            }

        response = (
            supabase
            .table("workout_sessions")
            .update({
                "ended_at": _now_iso(),
                "status": "cancelled",
            })
            .eq("id", session_id)
            .eq("status", "ongoing")
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def fail_workout_session(session_id):
    try:
        if not session_id:
            return {
                "success": True,
                "data": None
            }

        response = (
            supabase
            .table("workout_sessions")
            .update({
                "ended_at": _now_iso(),
                "status": "failed",
            })
            .eq("id", session_id)
            .eq("status", "ongoing")
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_workout_history(user_id, mode=None):
    try:
        query = (
            supabase
            .table("workout_sessions")
            .select(
                """
                id,
                mode,
                started_at,
                ended_at,
                created_at,
                status,
                workout_participants (
                    name,
                    user_id
                ),
                workout_reports (
                    id,
                    report_data,
                    created_at
                )
                """
            )
            .eq("user_id", user_id)
            .order("started_at", desc=True)
        )

        if mode in ["single", "multi"]:
            query = query.eq("mode", mode)

        response = query.execute()

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_workout_report(session_id):
    try:
        response = (
            supabase
            .table("workout_reports")
            .select("*")
            .eq("session_id", session_id)
            .single()
            .execute()
        )

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
