-- Creates this app's role and database on a Postgres server. Run it once, as
-- the server's superuser. The tables are not created here: the app applies
-- db/schema.sql itself, as the owner, the first time it starts.
--
-- When it is needed: on the shared CEAT database server
-- (ceat-compintel/deploy/db-shared) roles and databases are made by an init
-- script that only ever runs on an empty data directory, and each project's
-- role is LOGIN-only — so neither the role nor the database for this app
-- appears by itself there. On the ceat-compintel dev stack the `ceat` role is
-- the superuser and the app creates its database on first start; this file is
-- then optional.
--
-- Same arrangement as that server's init/00-databases.sql: one database per
-- project, owned by the project's role, with the CONNECT that Postgres grants
-- everyone by default taken away. Notices carry party names, cheque numbers
-- and amounts; the read-only viewer role (ceat_ro) and the other projects'
-- roles must not be able to open this database at all.
--
-- Two names, matching the app's .env:
--   -v db=...      POSTGRES_DB      (default ceat_notices)
--   -v owner=...   POSTGRES_USER    (default ceat, the role ceat-compintel uses)
-- If the owner role does not exist yet it is created, with the password taken
-- from the environment variable APP_DB_PASSWORD (the app's POSTGRES_PASSWORD) —
-- read by psql, never written into this file. A role that already exists is
-- left exactly as it is, password included.
--
-- On the database server (the container is called ceat-pg there):
--   read -s APP_DB_PASSWORD && export APP_DB_PASSWORD      # type it; nothing is shown
--   docker exec -i -e APP_DB_PASSWORD ceat-pg \
--       psql -U postgres -d postgres -v db=legal -v owner=legal < db/bootstrap.sql
--
-- Safe to re-run.

\set ON_ERROR_STOP on

\if :{?db}
\else
    \set db ceat_notices
\endif
\if :{?owner}
\else
    \set owner ceat
\endif
\set owner_pw ''
\getenv owner_pw APP_DB_PASSWORD

SELECT NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'owner') AS need_role,
       (:'owner_pw' <> '') AS have_pw \gset

\if :need_role
    \if :have_pw
        -- LOGIN only: it may not create databases or other roles.
        SELECT format('CREATE ROLE %I WITH LOGIN PASSWORD %L', :'owner', :'owner_pw')\gexec
    \else
        DO $stop$ BEGIN
            RAISE EXCEPTION 'The owner role does not exist yet and APP_DB_PASSWORD is not set, so it cannot be created. Nothing was changed.';
        END $stop$;
    \endif
\endif

SELECT format('CREATE DATABASE %I OWNER %I', :'db', :'owner')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db')\gexec

SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'db')\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db', :'owner')\gexec
