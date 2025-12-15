from flask import Blueprint, render_template, g
from utils.db import test_user_context
from utils.supabase_auth import verify_rls_working, login_required
from utils.supabase_auth import get_current_user

main_bp = Blueprint('main', __name__)

# @main_bp.route('/',  methods=['GET'])
# def index():
#     """Render the main index page."""
#     return render_template('login.html')

@main_bp.route('/',  methods=['GET'])
def index():
    """Render the main index page."""
    user = get_current_user()
    
    # 1. If user is logged in, show the Dashboard
    if user:
        return render_template('index.html', user=user)
    
    # 2. If NOT logged in, show Login page
    return render_template('login.html')

@main_bp.route('/test-rls')
@login_required
def test_rls():
    """
    Test endpoint to verify RLS is working
    Visit /test-rls after logging in to check
    """
    from flask import jsonify
    
    # Get test results
    db_test = test_user_context()
    auth_test = verify_rls_working()
    
    return jsonify({
        "database_test": db_test,
        "auth_test": auth_test,
        "instructions": "If both tests show success, RLS with RPC is working!"
    })