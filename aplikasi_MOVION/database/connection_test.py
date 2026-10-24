from supabase_client import supabase

tables = ["profiles", "workout_sessions", "workout_participants", "workout_reports"]

for t in tables:
    result = supabase.schema("public").table(t).select("*").execute()
    print(f"{t}: {result.data}")
