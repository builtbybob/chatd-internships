-- ChatD Internships Database Schema
-- Initial schema for PostgreSQL database implementation

-- Enable UUID extension for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main job postings table
CREATE TABLE job_postings (
    id UUID PRIMARY KEY,
    date_updated BIGINT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    title TEXT NOT NULL,
    sponsorship TEXT,
    active BOOLEAN DEFAULT true,
    source TEXT,
    date_posted BIGINT,
    company_url TEXT,
    is_visible BOOLEAN DEFAULT true
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

-- Message tracking table (one-to-one relationship)
CREATE TABLE message_tracking (
    id UUID PRIMARY KEY REFERENCES job_postings(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id, channel_id)
);

-- Performance indexes for common query patterns
CREATE INDEX idx_job_postings_company ON job_postings(company_name);
CREATE INDEX idx_job_postings_active ON job_postings(active, is_visible);
CREATE INDEX idx_job_postings_date_posted ON job_postings(date_posted DESC);
CREATE INDEX idx_job_postings_url_hash ON job_postings USING hash(url);
CREATE INDEX idx_message_tracking_message_id ON message_tracking(message_id);
CREATE INDEX idx_job_locations_location ON job_locations(location);
CREATE INDEX idx_job_terms_term ON job_terms(term);

-- Create a view for human-readable timestamps (optional convenience)
CREATE VIEW job_postings_readable AS
SELECT 
    jp.*,
    to_timestamp(jp.date_posted) AT TIME ZONE 'UTC' as posted_timestamp,
    to_timestamp(jp.date_updated) AT TIME ZONE 'UTC' as updated_timestamp,
    ARRAY_AGG(DISTINCT jl.location) FILTER (WHERE jl.location IS NOT NULL) as locations,
    ARRAY_AGG(DISTINCT jt.term) FILTER (WHERE jt.term IS NOT NULL) as terms
FROM job_postings jp
LEFT JOIN job_locations jl ON jp.id = jl.id
LEFT JOIN job_terms jt ON jp.id = jt.id
GROUP BY jp.id, jp.date_updated, jp.url, jp.company_name, jp.title, 
         jp.sponsorship, jp.active, jp.source, jp.date_posted, 
         jp.company_url, jp.is_visible;

-- Insert a test record to verify schema works
INSERT INTO job_postings (id, date_updated, url, company_name, title, active, date_posted, is_visible) 
VALUES (
    uuid_generate_v4(),
    extract(epoch from now())::bigint,
    'https://example.com/test-job',
    'Test Company',
    'Test Software Engineer Intern',
    true,
    extract(epoch from now())::bigint,
    true
);

-- Add some test data to related tables
INSERT INTO job_locations (id, location) 
SELECT id, 'San Francisco, CA' FROM job_postings WHERE company_name = 'Test Company';

INSERT INTO job_terms (id, term) 
SELECT id, 'Summer 2026' FROM job_postings WHERE company_name = 'Test Company';

-- Verify the schema works with a test query
DO $$
DECLARE
    record_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO record_count FROM job_postings_readable;
    RAISE NOTICE 'Schema initialized successfully. Test records created: %', record_count;
END $$;