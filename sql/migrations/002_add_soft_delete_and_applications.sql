-- Migration 002: Add soft delete support and student applications table
-- This migration implements application tracking functionality by adding:
-- 1. Soft delete support for job postings to preserve application history
-- 2. Student applications table to track user application activity

-- Add soft delete support to existing job_postings table
-- Add is_deleted column with default false and NOT NULL constraint
ALTER TABLE job_postings 
ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT false;

-- Create index on is_deleted for efficient filtering
CREATE INDEX idx_job_postings_is_deleted ON job_postings(is_deleted);

-- Create compound index for active + visible + not deleted queries
CREATE INDEX idx_job_postings_active_visible_not_deleted 
ON job_postings(active, is_visible, is_deleted) 
WHERE active = true AND is_visible = true AND is_deleted = false;

-- Create student_applications table for tracking ✅ reactions
CREATE TABLE student_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate applications for same job by same user
    UNIQUE(job_id, discord_user_id)
);

-- Create indexes for efficient application queries
CREATE INDEX idx_student_applications_user_id ON student_applications(discord_user_id);
CREATE INDEX idx_student_applications_applied_at ON student_applications(applied_at DESC);
CREATE INDEX idx_student_applications_job_id ON student_applications(job_id);

-- Create compound index for user application history queries
CREATE INDEX idx_student_applications_user_applied ON student_applications(discord_user_id, applied_at DESC);

-- Update the readable view to include soft delete information
DROP VIEW IF EXISTS job_postings_readable;
CREATE VIEW job_postings_readable AS
SELECT 
    jp.*,
    to_timestamp(jp.date_posted) AT TIME ZONE 'UTC' as posted_timestamp,
    to_timestamp(jp.date_updated) AT TIME ZONE 'UTC' as updated_timestamp,
    ARRAY_AGG(DISTINCT jl.location) FILTER (WHERE jl.location IS NOT NULL) as locations,
    ARRAY_AGG(DISTINCT jt.term) FILTER (WHERE jt.term IS NOT NULL) as terms,
    ARRAY_AGG(DISTINCT jd.degree) FILTER (WHERE jd.degree IS NOT NULL) as degrees,
    COUNT(sa.id) as application_count
FROM job_postings jp
LEFT JOIN job_locations jl ON jp.id = jl.id
LEFT JOIN job_terms jt ON jp.id = jt.id
LEFT JOIN job_degrees jd ON jp.id = jd.id
LEFT JOIN student_applications sa ON jp.id = sa.job_id
GROUP BY jp.id, jp.date_updated, jp.url, jp.company_name, jp.title, 
         jp.sponsorship, jp.active, jp.source, jp.date_posted, 
         jp.company_url, jp.is_visible, jp.category, jp.is_deleted;

-- Create a view for active (not soft-deleted) jobs
CREATE VIEW active_job_postings AS
SELECT * FROM job_postings_readable 
WHERE is_deleted = false;

-- Create a view for application statistics
CREATE VIEW application_statistics AS
SELECT 
    jp.company_name,
    jp.title,
    jp.id as job_id,
    COUNT(sa.id) as total_applications,
    COUNT(DISTINCT sa.discord_user_id) as unique_applicants,
    MIN(sa.applied_at) as first_application,
    MAX(sa.applied_at) as latest_application
FROM job_postings jp
LEFT JOIN student_applications sa ON jp.id = sa.job_id
WHERE jp.is_deleted = false AND jp.active = true AND jp.is_visible = true
GROUP BY jp.id, jp.company_name, jp.title
ORDER BY total_applications DESC, latest_application DESC;

-- Verify the migration with test data
DO $$
DECLARE
    test_job_id UUID;
    test_user_id TEXT := 'test_discord_user_123';
BEGIN
    -- Get a test job ID
    SELECT id INTO test_job_id FROM job_postings LIMIT 1;
    
    IF test_job_id IS NOT NULL THEN
        -- Test application insertion
        INSERT INTO student_applications (job_id, discord_user_id)
        VALUES (test_job_id, test_user_id)
        ON CONFLICT (job_id, discord_user_id) DO NOTHING;
        
        -- Test soft delete functionality
        UPDATE job_postings SET is_deleted = true WHERE id = test_job_id;
        UPDATE job_postings SET is_deleted = false WHERE id = test_job_id;
        
        RAISE NOTICE 'Migration 002 completed successfully. Added soft delete support and student_applications table.';
    ELSE
        RAISE NOTICE 'Migration 002 completed. No test jobs available for validation.';
    END IF;
END $$;