-- CEAT Notice Drafting Console — schema v1
-- Database: ceat_notices. Same conventions as ceat_compintel/db/schema.sql:
-- lean tables, TEXT + CHECK for closed vocabularies, JSONB where the shape is
-- owned by the application, idempotent DDL. Later changes go in
-- db/migrations/002_*.sql onwards.
--
-- Nobody has to run this by hand: with DATABASE_URL set the app creates the
-- database if it is missing and applies this file, then every migration in
-- name order, each time it starts (core/db.py). It needs no extension, so it
-- applies on any Postgres 13+ without superuser rights.
--
-- What each table replaces in the file/session-based app:
--   offices           offices.json                       (core/offices.py)
--   matters           st.session_state.case[kind]        (app.py — lost on refresh today)
--   matter_documents  st.session_state.docs / .parsed    (uploads, parsed once per digest)
--   notices           the History tab and drafts/register.csv + .docx/.txt/.json
--                                                        (core/archive.py)
--   llm_calls         nothing — model calls are not recorded today
--   app_users/app_sessions   the single shared APP_PASSWORD
--
-- The rulebook itself (skill/SKILL.md and skill/references/*.md) stays in the
-- repo: it is versioned wording, read at runtime, not data.

BEGIN;

-- Login. Same shape as ceat_compintel's app_users/app_sessions (its migration
-- 015) so the same auth code can serve both; the accounts themselves are
-- separate, because the databases are.
CREATE TABLE IF NOT EXISTS app_users (
    id                   BIGSERIAL PRIMARY KEY,
    email                TEXT NOT NULL,
    password_hash        TEXT NOT NULL,          -- pbkdf2_sha256$<iters>$<b64salt>$<b64hash>
    role                 TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at        TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS app_users_email_key ON app_users(lower(email));

CREATE TABLE IF NOT EXISTS app_sessions (
    token_hash   TEXT PRIMARY KEY,               -- sha256 hex of the cookie value, never the value
    user_id      BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent   TEXT,
    ip           TEXT
);
CREATE INDEX IF NOT EXISTS app_sessions_user_idx    ON app_sessions(user_id);
CREATE INDEX IF NOT EXISTS app_sessions_expires_idx ON app_sessions(expires_at);

-- The offices a notice can be issued from (letterhead + registered office).
-- Row one is seeded by the app from skill/references/house-style.md, as today.
CREATE TABLE IF NOT EXISTS offices (
    id          TEXT PRIMARY KEY,                -- slug of the label, e.g. 'house-style'
    label       TEXT NOT NULL,
    name        TEXT NOT NULL DEFAULT '',
    address     TEXT NOT NULL DEFAULT '',
    meta        TEXT NOT NULL DEFAULT '',        -- CIN / phone / web line under the address
    reg_office  TEXT NOT NULL DEFAULT '',        -- one-line form used mid-sentence
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS offices_one_default_idx ON offices(is_default) WHERE is_default;

-- One matter = one notice type + the answers held against it. case_json is the
-- dict the app already keeps (scalar fields, the invoice/cheque/SOA tables,
-- _office, _notes, _defaults). It stays JSONB because the field list is read
-- out of the skill files and changes without a code edit; only what a list
-- screen needs is copied out into columns.
CREATE TABLE IF NOT EXISTS matters (
    id           BIGSERIAL PRIMARY KEY,
    notice_type  TEXT NOT NULL,                  -- s138 | recovery | consumer | breach | termination | renewal | fm | price | cnd | generic
    party        TEXT,                           -- noticee_name (client_name for a consumer reply)
    case_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','drafted','closed')),
    created_by   BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS matters_status_idx     ON matters(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS matters_type_idx       ON matters(notice_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS matters_owner_idx      ON matters(created_by, notice_type, updated_at DESC);

-- Everything attached to a matter: ledgers, cheque photos, the inbound notice,
-- Outlook messages. The original bytes are kept so a reopened matter can be
-- re-analysed; the extracted form is kept so it need not be re-parsed.
CREATE TABLE IF NOT EXISTS matter_documents (
    id                  BIGSERIAL PRIMARY KEY,
    matter_id           BIGINT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    parent_document_id  BIGINT REFERENCES matter_documents(id) ON DELETE CASCADE,  -- attachment of a .msg/.eml
    question_key        TEXT,                    -- the question it was attached against, if any
    file_name           TEXT NOT NULL,
    file_mime           TEXT,
    file_size           BIGINT,
    content_hash        TEXT NOT NULL,           -- sha256 of the bytes
    file_bytes          BYTEA,
    doc_kind            TEXT NOT NULL DEFAULT 'text' CHECK (doc_kind IN ('text','tables','image','error')),
    extracted_text      TEXT,
    extracted_tables    JSONB,                   -- [{sheet, rows:[[...]]}]
    extraction_note     TEXT,
    uploaded_by         BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (matter_id, content_hash)
);

-- Every notice drafted, exactly as it printed. The .docx and the text are
-- stored rather than regenerated: the wording comes from the skill files, which
-- change, and a notice already sent must stay what was sent.
--   specimen  still has [● …] blanks — carries the NOT READY TO ISSUE header
--   ready     no blanks left
-- Nothing is overwritten: a changed notice is a new row with the next version;
-- an identical one (same text_sha) is not saved twice.
CREATE TABLE IF NOT EXISTS notices (
    id            BIGSERIAL PRIMARY KEY,
    matter_id     BIGINT REFERENCES matters(id) ON DELETE SET NULL,   -- the register outlives the matter
    version       INTEGER NOT NULL DEFAULT 1,
    notice_type   TEXT NOT NULL,
    party         TEXT,
    subject       TEXT,
    notice_date   DATE,                          -- reply_date for a consumer reply
    amount        NUMERIC(16,2),                 -- s138 and recovery only
    status        TEXT NOT NULL CHECK (status IN ('specimen','ready')),
    blanks        INTEGER NOT NULL DEFAULT 0,
    review_notes  INTEGER NOT NULL DEFAULT 0,    -- flags raised at the time
    file_name     TEXT,                          -- CEAT_Section138_Notice_<party>_<date>[_vN].docx
    body_text     TEXT NOT NULL,
    text_sha      TEXT NOT NULL,
    docx_bytes    BYTEA,
    case_json     JSONB NOT NULL,                -- the answers behind it, to reopen
    report_json   JSONB,                         -- blockers / flags / checks / open items / annexures
    saved_by      BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
    saved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (text_sha),
    UNIQUE (matter_id, version)
);
CREATE INDEX IF NOT EXISTS notices_saved_idx      ON notices(saved_at DESC);
CREATE INDEX IF NOT EXISTS notices_type_idx       ON notices(notice_type, saved_at DESC);

-- Same columns as ceat_compintel.llm_calls (with its migration 016 actor
-- columns), plus the matter the call was made for.
CREATE TABLE IF NOT EXISTS llm_calls (
    id            BIGSERIAL PRIMARY KEY,
    model         TEXT NOT NULL,
    provider      TEXT,                          -- Groq | OpenAI-compatible | azure
    purpose       TEXT NOT NULL,                 -- extract_text | extract_vision | compose
    tokens_in     INTEGER,
    tokens_out    INTEGER,
    cost_usd      NUMERIC(10,6),
    latency_ms    INTEGER,
    request_hash  TEXT,
    meta          JSONB NOT NULL DEFAULT '{}'::jsonb,
    matter_id     BIGINT REFERENCES matters(id) ON DELETE SET NULL,
    user_id       BIGINT REFERENCES app_users(id) ON DELETE SET NULL,
    user_email    TEXT,                          -- kept after the account is deleted
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS llm_calls_purpose_idx      ON llm_calls(purpose, created_at DESC);
CREATE INDEX IF NOT EXISTS llm_calls_user_created_idx ON llm_calls(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS llm_calls_matter_idx       ON llm_calls(matter_id);

-- If the server has the read-only viewer role, it must never see credentials.
-- (Guarded: the role does not exist in local dev.)
DO $revoke$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ceat_ro') THEN
        EXECUTE 'REVOKE ALL ON TABLE app_users, app_sessions FROM ceat_ro';
    END IF;
EXCEPTION
    WHEN undefined_object THEN NULL;
END $revoke$;

COMMIT;
