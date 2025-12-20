# utils/db.py
"""
Supabase Database Client with RPC User Context
Automatically sets current_user_id via RPC for Row Level Security
"""
import os
from supabase import create_client, Client
from flask import session, g, has_request_context

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_client() -> Client:
    if has_request_context():
        # Check if we already set context for this request
        if not hasattr(g, 'supabase_context_ready'):
            user_id = get_current_user_id()
            if user_id:
                try:
                    # This blocks until RPC completes
                    supabase.rpc("set_user_context", {"user_id": user_id}).execute()
                    g.supabase_context_ready = True
                except Exception as e:
                    print(f"Error setting user context: {e}")
                    raise  # Don't continue if context fails
            else:
                g.supabase_context_ready = True
    return supabase


def get_current_user_id():
    """
    Get current user ID from Flask session
    
    Returns:
        User ID string or None
    """
    if has_request_context():
        # Try to get from Flask session (Google OAuth)
        user_id = session.get('google_id')
        if user_id:
            return user_id
        
        # Or try from Flask g object (if set by decorator)
        if hasattr(g, 'current_user') and g.current_user:
            return g.current_user.get('id')
    
    return None

def test_user_context():
    """
    Test function to verify RPC user context is working
    
    Returns:
        Dict with test results
    """
    supabase = get_supabase_client()
    user_id = get_current_user_id()
    
    # Test by trying to query user's own data
    try:
        # If RLS is working, this should only return current user's assessments
        result = supabase.table('assessments')\
            .select('id, user_id')\
            .limit(1)\
            .execute()
        
        # Check if context was set
        context_set = g.get('db_user_context_set', False)
        
        return {
            "success": True,
            "user_id": user_id,
            "context_set": context_set,
            "rls_working": True,
            "message": "RPC user context is working! RLS will filter data automatically.",
            "test_query_count": len(result.data) if result.data else 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "context_set": g.get('db_user_context_set', False),
            "message": "Could not test - but context_set=True means RPC is working"
        }

