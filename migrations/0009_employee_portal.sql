-- Phase 4: employee self-service credentials.
ALTER TABLE employees ADD COLUMN password_hash TEXT;
