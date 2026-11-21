-- Optional. The app creates its own database on first start (core/db.py), so
-- this is only for a server where the app's role may not CREATE DATABASE, or
-- for setting the database up before the app is deployed.
--
-- The console gets a separate logical database (ceat_notices) on the Postgres
-- server that already hosts ceat_compintel — the same arrangement that server
-- uses for ceat_compintel_prefect — so notices, party names and cheque details
-- never share tables, grants or dumps with the competition-intelligence data.
--
-- Run connected to any existing database on that server, as a role that may
-- create databases; schema.sql can be applied the same way or left to the app:
--   docker compose exec -T postgres psql -U ceat -d postgres     < db/bootstrap.sql
--   docker compose exec -T postgres psql -U ceat -d ceat_notices < db/schema.sql
--
-- Safe to re-run: the database is only created when it is missing.

SELECT 'CREATE DATABASE ceat_notices'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ceat_notices')\gexec
