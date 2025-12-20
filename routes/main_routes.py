from flask import Blueprint, render_template, g
from utils.db import test_user_context, get_supabase_client
from utils.supabase_auth import verify_rls_working, login_required
from utils.supabase_auth import get_current_user
from utils.dashboard_service import get_dashboard_counts, get_recent_activities

main_bp = Blueprint('main', __name__)

# @main_bp.route('/',  methods=['GET'])
# def index():
#     """Render the main index page."""
#     return render_template('login.html')

@main_bp.route('/',  methods=['GET'])
@login_required
def index():
    """Render the main index page."""
    user = get_current_user()
    
    # 1. If user is logged in, show the Dashboard
    if user:
        # Fetch simple counts and recent items from the DB via dashboard_service
        dashboard_error = None
        try:
            supabase = get_supabase_client()

            counts = get_dashboard_counts(supabase)
            recent_activities = get_recent_activities(supabase, limit=3)

            total_batches = counts.get('batches', 0)
            total_lesson_plans = counts.get('lesson_plans', 0)
            total_assessments = counts.get('assessments', 0)

            # debug: log raw recent activities for diagnostics
            print(f"Dashboard recent merged: {recent_activities}")
            print("skeys" + str(recent_activities))

        except Exception as e:
            # If DB fails, fall back to zeros so UI still renders
            dashboard_error = str(e)
            print(f"Warning: could not fetch dashboard data: {e}")
            total_batches = 0
            total_lesson_plans = 0
            total_assessments = 0
            recent_activities = []

            

        return render_template(
            'index.html',
            user=user,
            total_batches=total_batches,
            total_lesson_plans=total_lesson_plans,
            total_assessments=total_assessments,
            recent_activities=recent_activities,
            dashboard_error=dashboard_error,
        )
    
    # 2. If NOT logged in, show Login page
    return render_template('login.html')

@main_bp.route('/activity')
@login_required
def activity_page():
    """
    Show all activity history for the current user
    """
    error = None
    activities = []
    
    try:
        supabase = get_supabase_client()
        # Fetch more activities for the full history page (50 instead of 6)
        activities = get_recent_activities(supabase, limit=30)
    except Exception as e:
        error = str(e)
        print(f"Error fetching activity history: {e}")
    
    return render_template(
        'activity.html',
        user=g.current_user,
        activities=activities,
        error=error
    )

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