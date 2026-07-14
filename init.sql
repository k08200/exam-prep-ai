-- PostgreSQL bootstrap only.
--
-- The application owns its schema through Alembic migrations. Keeping table
-- definitions here as well would let fresh databases drift from migrations.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
