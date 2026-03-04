from backend.db.supabase import supabase

def fetch_data(table_name: str):
    """Fetch data from a Supabase table."""
    response = supabase.table(table_name).select("*").execute()
    return response.data
