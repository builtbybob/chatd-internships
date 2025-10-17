-- Schema version tracking table
-- This table tracks which migrations have been applied to maintain database state consistency

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    applied_by TEXT DEFAULT CURRENT_USER,
    description TEXT
);

-- Insert records for current schema versions
INSERT INTO schema_migrations (version, description) VALUES 
    ('V1__initial_schema', 'Initial database schema with job postings, locations, terms, degrees, and message tracking')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_migrations (version, description) VALUES 
    ('V2__add_soft_delete_and_apps', 'Add soft delete support and student applications table')
ON CONFLICT (version) DO NOTHING;