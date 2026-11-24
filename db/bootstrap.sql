-- Creates this app's database on a Postgres server. Run it once, as a role
-- that may create databases (the superuser on the shared CEAT database server).
--
-- When it is needed: on the shared server (ceat-compintel/deploy/db-shared)
-- each project signs in with a LOGIN-only role that cannot create databases,
-- so the app cannot make ceat_notices for itself there. On the ceat-compintel
-- dev stack the `ceat` role is the superuser and the app creates the database
-- on first start — this file is then optional.
--
-- Same arrangement as that server's init/00-databases.sql: one database per
-- project, owned by the project's role, with the CONNECT that Postgres grants
-- everyone by default taken away. Notices carry party names, cheque numbers
-- and amounts; the read-only viewer role (ceat_ro) and the other projects'
-- roles must not be able to open this database at all.
--
--   shared server    docker exec -i ceat-pg psql -U postgres -d postgres < db/bootstrap.sql
--   dev stack        docker compose exec -T postgres psql -U ceat -d postgres < db/bootstrap.sql
--
-- The owner defaults to `ceat` (the role ceat-compintel uses). To give this app
-- a role of its own, create it first and pass its name:
--   CREATE ROLE notices WITH LOGIN PASSWORD '...';
--   psql ... -v owner=notices < db/bootstrap.sql
--
-- The tables are not created here: the app applies db/schema.sql itself, as the
-- owner, the first time it starts. Safe to re-run.

\set ON_ERROR_STOP on

\if :{?owner}
\else
    \set owner ceat
\endif

SELECT format('CREATE DATABASE ceat_notices OWNER %I', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ceat_notices')\gexec

REVOKE CONNECT ON DATABASE ceat_notices FROM PUBLIC;
SELECT format('GRANT CONNECT ON DATABASE ceat_notices TO %I', :'owner')\gexec
