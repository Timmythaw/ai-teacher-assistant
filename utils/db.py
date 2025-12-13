import os   
from supabase  import create_client, Client

def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)