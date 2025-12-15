# utils/supabase_auth.py
"""
Authentication Helper for Google OAuth + Supabase Database
Uses existing Google OAuth but stores user data in Supabase
NO Supabase Auth - just database
"""
import os
from functools import wraps
from flask import request, jsonify, redirect, url_for, g, session
from utils.db import get_supabase_client


def get_current_user_id():
    """
    Get current user ID from Flask session (set by Google OAuth)
    Returns: user_id string or None
    """
    return session.get('google_id')


def get_current_user_email():
    """
    Get current user email from Flask session
    Returns: email string or None
    """
    return session.get('email')


def get_current_user():
    """
    Get current user data from Flask session
    Returns: dict with user info or None
    """
    google_id = session.get('google_id')
    if not google_id:
        return None
    
    return {
        'id': google_id,
        'email': session.get('email'),
        'name': session.get('name'),
        'picture': session.get('picture')
    }


def login_required(f):
    """
    Decorator to protect routes requiring authentication
    Checks if user has Google ID in session
    
    Usage:
        @app.route('/protected')
        @login_required
        def protected_route():
            return "Hello " + g.current_user['email']
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        
        if not user:
            # For API/AJAX requests - return JSON with redirect
            if request.is_json or request.path.startswith('/api') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Authentication required',
                    'code': 'AUTH_REQUIRED',
                    'redirect_to': url_for('auth.login', _external=True)
                }), 401
            
            # For regular web requests - redirect to login
            return redirect(url_for('auth.login'))
        
        # Store user in Flask's g object for easy access
        g.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function


def require_user_owns_resource(resource_table, resource_id_param='id'):
    """
    Decorator to verify user owns the resource they're accessing
    Checks user_id in Supabase database
    
    Usage:
        @app.route('/assessments/<uuid:assessment_id>')
        @login_required
        @require_user_owns_resource('assessments', 'assessment_id')
        def view_assessment(assessment_id):
            return "Your assessment"
    
    Args:
        resource_table: Database table name (e.g., 'assessments', 'lesson_plans')
        resource_id_param: URL parameter name containing the resource ID
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = get_current_user_id()
            
            if not user_id:
                if request.is_json or request.path.startswith('/api'):
                    return jsonify({
                        'error': 'Unauthorized',
                        'code': 'AUTH_REQUIRED',
                        'redirect_to': url_for('auth.login', _external=True)
                    }), 401
                return redirect(url_for('auth.login'))
            
            # Get resource ID from URL parameters
            resource_id = kwargs.get(resource_id_param)
            if not resource_id:
                return jsonify({
                    'error': 'Bad Request',
                    'message': 'Resource ID not provided'
                }), 400
            
            # Check ownership in Supabase database
            supabase = get_supabase_client()
            try:
                result = (
                     supabase.table(resource_table)
                    .select('user_id')
                    .eq('id', str(resource_id))
                    .single()
                    .execute()
                )
                
                if not result.data:
                    return jsonify({
                        'error': 'Not Found',
                        'message': 'Resource not found'
                    }), 404
                
                if result.data.get('user_id') != user_id:
                    return jsonify({
                        'error': 'Forbidden', 
                        'message': 'You do not have access to this resource',
                        'code': 'ACCESS_DENIED'
                    }), 403
                
            except Exception as e:
                print(f"Authorization error: {e}")
                return jsonify({
                    'error': 'Not Found',
                    'message': 'Resource not found'
                }), 404
            
            # Store user in g for access in route
            g.current_user = get_current_user()
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def ensure_user_exists_in_db():
    """
    Ensure current user exists in Supabase users table
    Called after successful Google OAuth login
    
    Returns:
        User profile dict or None
    """
    user_id = get_current_user_id()
    email = get_current_user_email()
    
    if not user_id or not email:
        return None
    
    supabase = get_supabase_client()
    
    try:
        # Check if user already exists
        existing = (
            supabase.table('users')
            .select('*')
            .eq('id', user_id)
            .execute()
        )
        
        if existing.data:
            # User exists, return profile
            return existing.data[0]
        
        # Create new user profile
        profile = {
            'id': user_id,
            'email': email,
            'full_name': session.get('name'),
            'avatar_url': session.get('picture')
        }
        
        result = supabase.table('users').insert(profile).execute()
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error ensuring user exists: {e}")
        return None


def get_user_profile(user_id: str = None):
    """
    Get user profile from Supabase database
    
    Args:
        user_id: Optional user ID. If not provided, uses current user
        
    Returns:
        User profile dict or None
    """
    if not user_id:
        user_id = get_current_user_id()
        
    if not user_id:
        return None
    
    supabase = get_supabase_client()
    
    try:
        result = (
            supabase.table('users')
            .select('*')
            .eq('id', user_id)
            .single()
            .execute()
        )
        
        return result.data if result.data else None
        
    except Exception as e:
        print(f"Error getting user profile: {e}")
        return None

def verify_rls_working():
    """
    Verify that RLS and user context are working correctly
    
    Returns:
        Dict with verification results
    """
    from utils.db import get_supabase_client
    
    user_id = get_current_user_id()
    if not user_id:
        return {
            "status": "error",
            "message": "No user logged in"
        }
    
    supabase = get_supabase_client()
    
    try:
        # Test 1: Check if we can query assessments
        # RLS should automatically filter by user_id
        result = supabase.table('assessments')\
            .select('id, user_id')\
            .limit(5)\
            .execute()
        
        # Check if all returned rows belong to current user
        all_owned = all(
            row.get('user_id') == user_id 
            for row in (result.data or [])
        )
        
        return {
            "status": "success" if all_owned else "warning",
            "session_user_id": user_id,
            "rls_active": all_owned,
            "test_records_count": len(result.data) if result.data else 0,
            "message": "RLS is working correctly!" if all_owned else "RLS may not be filtering correctly",
            "note": "If test_records_count is 0, create an assessment first to test properly"
        }
    except Exception as e:
        # If we get a permission error, RLS might be TOO strict (which is good!)
        error_msg = str(e)
        if 'permission denied' in error_msg.lower() or 'policy' in error_msg.lower():
            return {
                "status": "success",
                "session_user_id": user_id,
                "rls_active": True,
                "message": "RLS is VERY active - blocking queries (this is actually good security!)",
                "error": error_msg
            }
        
        return {
            "status": "error",
            "session_user_id": user_id,
            "error": error_msg,
            "message": "Could not verify RLS"
        }
