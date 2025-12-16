-- ================================================
-- SUPABASE DATABASE MIGRATION
-- User Isolation & Multi-Tenant Architecture
-- Run this in Supabase SQL Editor
-- ================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================
-- 1. CREATE USERS TABLE
-- ================================================

-- Create users table for storing user profiles
-- Uses google_id as primary key (from Google OAuth)
CREATE TABLE IF NOT EXISTS public.users (
    id TEXT PRIMARY KEY,  -- Google ID (sub from JWT)
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- ================================================
-- 2. ADD user_id TO EXISTING TABLES
-- ================================================

-- Add user_id column to assessments table
ALTER TABLE public.assessments 
ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE;

-- for credit. Add credits column to your existing 'users' table
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 10;

-- 2. (Optional) If you want to make sure no one has NULL credits
UPDATE public.users 
SET credits = 10 
WHERE credits IS NULL;

-- Add user_id column to lesson_plans table (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        ALTER TABLE public.lesson_plans 
        ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add user_id column to batches table (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'batches') THEN
        ALTER TABLE public.batches 
        ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Add user_id column to students table (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'students') THEN
        ALTER TABLE public.students 
        ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ================================================
-- 3. CREATE INDEXES FOR PERFORMANCE
-- ================================================

-- Index on assessments.user_id
CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON public.assessments(user_id);

-- Index on lesson_plans.user_id (if table exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        CREATE INDEX IF NOT EXISTS idx_lesson_plans_user_id ON public.lesson_plans(user_id);
    END IF;
END $$;

-- Index on batches.user_id (if table exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'batches') THEN
        CREATE INDEX IF NOT EXISTS idx_batches_user_id ON public.batches(user_id);
    END IF;
END $$;

-- ================================================
-- 4. ENABLE ROW LEVEL SECURITY (RLS)
-- ================================================

-- Enable RLS on users table
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Enable RLS on assessments table
ALTER TABLE public.assessments ENABLE ROW LEVEL SECURITY;

-- Enable RLS on lesson_plans (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        ALTER TABLE public.lesson_plans ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- Enable RLS on batches (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'batches') THEN
        ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
    END IF;
END $$;

-- ================================================
-- 5. RLS POLICIES - USERS TABLE
-- ================================================

-- Drop existing policies if they exist (for re-running script)
DROP POLICY IF EXISTS "Users can view own profile" ON public.users;
DROP POLICY IF EXISTS "Users can update own profile" ON public.users;
DROP POLICY IF EXISTS "Users can insert own profile" ON public.users;

-- Policy: Users can view their own profile
CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT
    USING (true);  -- Allow all authenticated users to view any profile (for mentions, etc.)

-- Policy: Users can update their own profile
CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE
    USING (id = current_setting('app.current_user_id', true)::TEXT);

-- Policy: Users can insert their own profile
CREATE POLICY "Users can insert own profile" ON public.users
    FOR INSERT
    WITH CHECK (id = current_setting('app.current_user_id', true)::TEXT);

-- ================================================
-- 6. RLS POLICIES - ASSESSMENTS TABLE
-- ================================================

-- Drop existing policies
DROP POLICY IF EXISTS "Users view own assessments" ON public.assessments;
DROP POLICY IF EXISTS "Users insert own assessments" ON public.assessments;
DROP POLICY IF EXISTS "Users update own assessments" ON public.assessments;
DROP POLICY IF EXISTS "Users delete own assessments" ON public.assessments;

-- Policy: Users can only view their own assessments
CREATE POLICY "Users view own assessments" ON public.assessments
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

-- Policy: Users can only insert their own assessments
CREATE POLICY "Users insert own assessments" ON public.assessments
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::TEXT);

-- Policy: Users can only update their own assessments
CREATE POLICY "Users update own assessments" ON public.assessments
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

-- Policy: Users can only delete their own assessments
CREATE POLICY "Users delete own assessments" ON public.assessments
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

-- ================================================
-- 7. RLS POLICIES - LESSON PLANS TABLE
-- ================================================

DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        -- Drop existing policies
        DROP POLICY IF EXISTS "Users view own lesson plans" ON public.lesson_plans;
        DROP POLICY IF EXISTS "Users insert own lesson plans" ON public.lesson_plans;
        DROP POLICY IF EXISTS "Users update own lesson plans" ON public.lesson_plans;
        DROP POLICY IF EXISTS "Users delete own lesson plans" ON public.lesson_plans;

        -- Create policies
        CREATE POLICY "Users view own lesson plans" ON public.lesson_plans
            FOR SELECT
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users insert own lesson plans" ON public.lesson_plans
            FOR INSERT
            WITH CHECK (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users update own lesson plans" ON public.lesson_plans
            FOR UPDATE
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users delete own lesson plans" ON public.lesson_plans
            FOR DELETE
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);
    END IF;
END $$;

-- ================================================
-- 8. RLS POLICIES - BATCHES TABLE
-- ================================================

DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'batches') THEN
        -- Drop existing policies
        DROP POLICY IF EXISTS "Users view own batches" ON public.batches;
        DROP POLICY IF EXISTS "Users insert own batches" ON public.batches;
        DROP POLICY IF EXISTS "Users update own batches" ON public.batches;
        DROP POLICY IF EXISTS "Users delete own batches" ON public.batches;

        -- Create policies
        CREATE POLICY "Users view own batches" ON public.batches
            FOR SELECT
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users insert own batches" ON public.batches
            FOR INSERT
            WITH CHECK (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users update own batches" ON public.batches
            FOR UPDATE
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);

        CREATE POLICY "Users delete own batches" ON public.batches
            FOR DELETE
            USING (user_id = current_setting('app.current_user_id', true)::TEXT);
    END IF;
END $$;

-- ================================================
-- 9. TRIGGERS FOR UPDATED_AT
-- ================================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON public.users;
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON public.users
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ================================================
-- 10. HELPER FUNCTIONS
-- ================================================

-- Function to get user's total assessments
CREATE OR REPLACE FUNCTION get_user_assessment_count(p_user_id TEXT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (SELECT COUNT(*) FROM public.assessments WHERE user_id = p_user_id);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's total lesson plans
CREATE OR REPLACE FUNCTION get_user_lesson_plan_count(p_user_id TEXT)
RETURNS INTEGER AS $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        RETURN (SELECT COUNT(*) FROM public.lesson_plans WHERE user_id = p_user_id);
    ELSE
        RETURN 0;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ================================================
-- 11. GRANT PERMISSIONS
-- ================================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- Grant permissions on users table
GRANT SELECT, INSERT, UPDATE ON public.users TO anon, authenticated;

-- Grant permissions on assessments table
GRANT SELECT, INSERT, UPDATE, DELETE ON public.assessments TO anon, authenticated;

-- Grant permissions on lesson_plans (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lesson_plans') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.lesson_plans TO anon, authenticated;
    END IF;
END $$;

-- Grant permissions on batches (if exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'batches') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON public.batches TO anon, authenticated;
    END IF;
END $$;

-- ================================================
-- MIGRATION COMPLETE
-- ================================================

-- Display summary
DO $$ 
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Created: users table';
    RAISE NOTICE 'Added: user_id columns to existing tables';
    RAISE NOTICE 'Enabled: Row Level Security (RLS)';
    RAISE NOTICE 'Created: RLS policies for data isolation';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Update your application code to use user_id';
    RAISE NOTICE '2. Set app.current_user_id in queries';
    RAISE NOTICE '3. Test with multiple users';
    RAISE NOTICE '========================================';
END $$;


-- ================================================
-- FIX: Enable RLS on Students Table
-- ================================================

-- 1. Enable Row Level Security on students table
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;

-- 2. Add user_id column if it doesn't exist
ALTER TABLE public.students 
ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES public.users(id) ON DELETE CASCADE;

-- 3. Create index for performance
CREATE INDEX IF NOT EXISTS idx_students_user_id ON public.students(user_id);

-- 4. Drop existing policies if they exist
DROP POLICY IF EXISTS "Users view own students" ON public.students;
DROP POLICY IF EXISTS "Users insert own students" ON public.students;
DROP POLICY IF EXISTS "Users update own students" ON public.students;
DROP POLICY IF EXISTS "Users delete own students" ON public.students;

-- 5. Create RLS policies for students table
CREATE POLICY "Users view own students" ON public.students
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

CREATE POLICY "Users insert own students" ON public.students
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::TEXT);

CREATE POLICY "Users update own students" ON public.students
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

CREATE POLICY "Users delete own students" ON public.students
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::TEXT);

-- 6. Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.students TO anon, authenticated;

-- 7. Verify RLS is enabled
DO $$ 
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'students' 
        AND rowsecurity = true
    ) THEN
        RAISE NOTICE 'SUCCESS: RLS is now enabled on students table';
    ELSE
        RAISE WARNING 'FAILED: RLS is not enabled on students table';
    END IF;
END $$;
