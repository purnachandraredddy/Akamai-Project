-- Initialize Rick & Morty database
-- This script runs when the PostgreSQL container starts for the first time

-- Create database if it doesn't exist (this is usually handled by POSTGRES_DB env var)
-- CREATE DATABASE IF NOT EXISTS rickmorty;

-- Use the rickmorty database
\c rickmorty;

-- Create extension for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- You can add any additional initialization SQL here
-- For example, creating tables, indexes, or inserting initial data

-- Example: Create a simple health check table
CREATE TABLE IF NOT EXISTS health_check (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'healthy',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert initial health check record
INSERT INTO health_check (status) VALUES ('initialized') ON CONFLICT DO NOTHING;

-- Add any other initialization queries below
-- Tables will be created by Alembic migrations when the API starts
