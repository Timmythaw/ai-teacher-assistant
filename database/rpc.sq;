-- ================================================
-- CREATE RPC FUNCTION FOR USER CONTEXT
-- This allows Python to set current user for RLS
-- ================================================

CREATE OR REPLACE FUNCTION public.set_user_context(user_id TEXT)
RETURNS void AS $$
BEGIN
    -- Set session variable that RLS policies can read
    PERFORM set_config('app.current_user_id', user_id, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.set_user_context(TEXT) TO anon, authenticated;

-- ================================================
-- TEST THE FUNCTION
-- ================================================

-- Test 1: Set user context
SELECT public.set_user_context('test_user_123');

-- Test 2: Verify it's set
SELECT current_setting('app.current_user_id', true);
-- Should output: test_user_123

-- Test 3: Clear it
SELECT public.set_user_context('');

-- ================================================
-- SUCCESS MESSAGE
-- ================================================

DO $$ 
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RPC Function created successfully!';
    RAISE NOTICE 'Function name: set_user_context';
    RAISE NOTICE 'Python can now call this to set user context';
    RAISE NOTICE '========================================';
END $$;
