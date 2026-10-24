from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

MOVION_SUPABASE_URL = os.getenv(
  "MOVION_SUPABASE_URL"
)
MOVION_SUPABASE_ANON_KEY = os.getenv(
  "MOVION_SUPABASE_ANON_KEY"
)

supabase = create_client(MOVION_SUPABASE_URL, MOVION_SUPABASE_ANON_KEY)