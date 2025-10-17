-- ChatD Internships Database Schema - V2
-- Complete schema including soft delete and application tracking features
-- This represents the current target schema state for new installations

-- Enable UUID extension for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main job postings table with soft delete support
CREATE TABLE job_postings (
    id UUID PRIMARY KEY,
    date_updated BIGINT NOT NULL,
    url TEXT NOT NULL,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    sponsorship TEXT,
    active BOOLEAN DEFAULT true,
    source TEXT,
    date_posted BIGINT,
    company_url TEXT,
    is_visible BOOLEAN DEFAULT true,
    category TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT false
);

-- Normalized locations table (one-to-many relationship)
CREATE TABLE job_locations (
    id UUID REFERENCES job_postings(id) ON DELETE CASCADE,
    location TEXT NOT NULL,
    PRIMARY KEY (id, location)
);

-- Normalized terms table (one-to-many relationship)
CREATE TABLE job_terms (
    id UUID REFERENCES job_postings(id) ON DELETE CASCADE,
    term TEXT NOT NULL,
    PRIMARY KEY (id, term)
);

-- Normalized degrees table (one-to-many relationship)
CREATE TABLE job_degrees (
    id UUID REFERENCES job_postings(id) ON DELETE CASCADE,
    degree TEXT NOT NULL,
    PRIMARY KEY (id, degree)
);

-- Message tracking table (one-to-one relationship)
CREATE TABLE message_tracking (
    id UUID PRIMARY KEY REFERENCES job_postings(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id, channel_id)
);

-- Student applications table for tracking ✅ reactions
CREATE TABLE student_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES job_postings(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate applications for same job by same user
    UNIQUE(job_id, discord_user_id)
);

-- Performance indexes for common query patterns
CREATE INDEX idx_job_postings_company ON job_postings(company_name);
CREATE INDEX idx_job_postings_active ON job_postings(active, is_visible);
CREATE INDEX idx_job_postings_date_posted ON job_postings(date_posted DESC);
CREATE INDEX idx_job_postings_url_hash ON job_postings USING hash(url);
CREATE INDEX idx_job_postings_category ON job_postings(category);
CREATE INDEX idx_job_postings_is_deleted ON job_postings(is_deleted);

-- Compound index for active + visible + not deleted queries
CREATE INDEX idx_job_postings_active_visible_not_deleted 
ON job_postings(active, is_visible, is_deleted) 
WHERE active = true AND is_visible = true AND is_deleted = false;

-- Message tracking indexes
CREATE INDEX idx_message_tracking_message_id ON message_tracking(message_id);

-- Location, terms, degrees indexes
CREATE INDEX idx_job_locations_location ON job_locations(location);
CREATE INDEX idx_job_terms_term ON job_terms(term);
CREATE INDEX idx_job_degrees_degree ON job_degrees(degree);

-- Student applications indexes
CREATE INDEX idx_student_applications_user_id ON student_applications(discord_user_id);
CREATE INDEX idx_student_applications_applied_at ON student_applications(applied_at DESC);
CREATE INDEX idx_student_applications_job_id ON student_applications(job_id);
CREATE INDEX idx_student_applications_user_applied ON student_applications(discord_user_id, applied_at DESC);

-- Create a view for human-readable timestamps with application counts
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

-- Insert a test record to verify schema works
INSERT INTO job_postings (id, date_updated, url, company_name, title, active, date_posted, is_visible, is_deleted) 
VALUES (
    uuid_generate_v4(),
    extract(epoch from now())::bigint,
    'https://example.com/test-job',
    'Test Company',
    'Test Software Engineer Intern',
    true,
    extract(epoch from now())::bigint,
    true,
    false
);

-- Add some test data to related tables
INSERT INTO job_locations (id, location) 
SELECT id, 'San Francisco, CA' FROM job_postings WHERE company_name = 'Test Company';

INSERT INTO job_terms (id, term) 
SELECT id, 'Summer 2026' FROM job_postings WHERE company_name = 'Test Company';

-- Test application tracking with sample data
INSERT INTO student_applications (job_id, discord_user_id)
SELECT id, 'test_user_123' FROM job_postings WHERE company_name = 'Test Company'
ON CONFLICT (job_id, discord_user_id) DO NOTHING;

-- Verify the schema works with a test query
DO $$
DECLARE
    record_count INTEGER;
    app_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO record_count FROM job_postings_readable;
    SELECT COUNT(*) INTO app_count FROM student_applications;
    RAISE NOTICE 'Schema V2 initialized successfully. Test records: %, Test applications: %', record_count, app_count;
END $$;