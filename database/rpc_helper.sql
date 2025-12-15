-- ================================================
-- HELPER: Get current user context (for debugging)
-- ================================================

CREATE OR REPLACE FUNCTION public.get_user_context()
RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.current_user_id', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permission
GRANT EXECUTE ON FUNCTION public.get_user_context() TO anon, authenticated;
