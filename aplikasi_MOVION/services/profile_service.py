from database.supabase_client import supabase
from services.session_service import get_current_session

def create_profile(data):
    try:
        response = (
            supabase
            .table("profiles")
            .insert(data)
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

def get_profile(user_id):
    #print("GET PROFILE ID:", user_id)
    try:
        response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .execute()
        )

        if response.data:
            return{
                "success": True,
                "exists": True,
                "data": response.data[0]
            }

        return {
            "success": True,
            "exists": False
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def get_email():
    try:
        session = get_current_session()

        if session and session.user:
            return session.user.email

        return "-"
    except Exception as e:
        #print("GET EMAIL ERROR: ", e)
        return "-"

def update_profile(user_id, data):
    try:
        response = (
            supabase
            .table("profiles")
            .update(data)
            .eq("id", user_id)
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

def get_avatar_path(user_id: str) -> str:
    profile = get_profile(user_id)

    if profile["success"] and profile["exists"]:
        avatar_path = profile["data"].get("avatar_url", None)
        if avatar_path:
            return supabase.storage.from_("profile-images").get_public_url(avatar_path)

    return supabase.storage.from_("profile-images").get_public_url("placeholder_profile.png")

def update_avatar_url(user_id: str, file_path: str, file_bytes: bytes, mime_type: str) -> bool:
    try:
        old_profile = get_profile(user_id)
        supabase.storage.from_("profile-images").upload(
            file_path,
            file_bytes,
            {
                "content-type": mime_type
            }
        )

        supabase.table("profiles").update({
            "avatar_url": file_path
        }).eq("id", user_id).execute()

        if old_profile["success"] and old_profile["exists"]:

            old_avatar = old_profile["data"].get("avatar_url")

            if old_avatar and old_avatar != "placeholder_profile.png":
                supabase.storage.from_("profile-images").remove(
                    [old_avatar]
                )

        return True

    except Exception as e:
        #print("Failed to update avatar_url:", e)
        return False
