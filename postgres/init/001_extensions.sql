-- Baseline Postgres extensions for application bootstrap.
-- Safe to re-run: all statements are idempotent.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
