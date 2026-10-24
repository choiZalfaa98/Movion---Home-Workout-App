from database.supabase_client import supabase
from services.session_service import clear_session

RESET_PASSWORD_REDIRECT_URL = "https://movion-workout-app-rp.netlify.app/"

def signup_user(email, password):
    try:
        response = supabase.auth.sign_up(
            {
                "email": email,
                "password": password
            }
        )

        if response.user is None:
          return {
          "success": False,
          "error": "User creation failed"
        }

        return {
            "success": True,
            "user": response.user
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password
            }
        )

        if response.user is None:
            return {
                "success": False,
                "error": "Login failed"
            }

        return {
            "success": True,
            "user": response.user,
            "session": response.session
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def reset_password(email: str) -> dict:
    try:
        supabase.auth.reset_password_for_email(
            email,
            {
                "redirect_to": RESET_PASSWORD_REDIRECT_URL
            }
        )

        return {
            "success": True,
            "message": "Password reset link has been sent to your email."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def logout_user():
    try:
        supabase.auth.sign_out()
        clear_session()
        return {
            "success": True
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
