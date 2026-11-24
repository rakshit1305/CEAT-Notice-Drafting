"""Configuration. Everything that varies by deployment lives here."""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    # Look for .env beside app.py first, then wherever the process was started.
    load_dotenv(ROOT / ".env")
    load_dotenv()
except Exception:                                   # dotenv is optional
    pass


def _secret(name: str, default: str = "") -> str:
    """Environment first, then .streamlit/secrets.toml if one happens to exist.

    Reading st.secrets when no secrets.toml is present raises in current
    Streamlit, so it is never allowed to escape. The app runs on .env alone.
    """
    v = os.getenv(name)
    if v:
        return v
    try:
        import streamlit as st
        return str(st.secrets[name])
    except Exception:
        return default
SKILL_DIR = ROOT / "skill"
REFERENCES = SKILL_DIR / "references"
OUTPUT_DIR = ROOT / "drafts"
OUTPUT_DIR.mkdir(exist_ok=True)

# --- saved notices ----------------------------------------------------------
# Where every drafted notice is kept (.docx + .txt + the case behind it, and a
# register). Defaults to drafts/ beside app.py, which .gitignore already keeps
# off GitHub. Point it at a OneDrive / SharePoint / Google Drive sync folder
# or a shared network drive and the notices land there directly.
SAVE_DIR = Path(_secret("NOTICE_SAVE_DIR", str(OUTPUT_DIR))).expanduser()

# Saving is OFF unless someone turns it on. It used to default ON, which on a
# public URL with no login meant every drafted notice — real party names,
# cheque numbers, amounts — sat in one shared folder that the Saved notices tab
# showed to any visitor. Notices are personal data; keeping them is a decision
# the deployment makes deliberately, not a default.
SAVE_NOTICES = _secret("NOTICE_SAVE", "0").strip().lower() in ("1", "true", "yes", "on")
AUTO_SAVE = SAVE_NOTICES and _secret("NOTICE_AUTO_SAVE", "1").strip().lower() \
    not in ("0", "false", "no", "off")

# A shared password for the whole app. Set it whenever the app is reachable from
# the internet: Streamlit Community Cloud has no accounts of its own.
# Only used when no database is configured — with one, people sign in by name.
APP_PASSWORD = _secret("APP_PASSWORD", "").strip()

# --- database -------------------------------------------------------------
# Configured, the app keeps matters, attachments, drafted notices and the
# office list in Postgres and asks everyone to sign in. Not configured, it runs
# exactly as it did before: in the browser session, with the shared password
# above. Two ways to configure it, the same two ceat-compintel has:
#
#   one address   DATABASE_URL=postgresql://user:password@host:5432/ceat_notices
#                 (DATABASE_URL_LOCAL is read as well)
#   the pieces    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, and the server
#                 as DB_HOST/DB_PORT (or POSTGRES_HOST/POSTGRES_PORT), plus the
#                 optional DB_SSL_PARAMS and DB_WAN_PARAMS query strings
#
# The address wins when both are given. The server and the role may be the ones
# ceat-compintel uses; the DATABASE must be this app's own (core/db.py refuses
# one that already holds another application's tables).
DEFAULT_DATABASE = "ceat_notices"


def _either(own: str, shared: str, default: str = "") -> str:
    """This app's own setting, else the name ceat-compintel uses for the same
    thing, else the default — so one .env block can serve both projects and
    either spelling works."""
    return _secret(own) or _secret(shared) or default


def _database_url() -> str:
    url = _either("DATABASE_URL", "DATABASE_URL_LOCAL").strip()
    if url:
        # postgresql+psycopg://… is how SQLAlchemy (and ceat-compintel's .env)
        # writes the same address; the driver here wants it without "+driver".
        return re.sub(r"^(postgres(?:ql)?)\+\w+://", r"\1://", url)
    host = _either("DB_HOST", "POSTGRES_HOST").strip()
    user = _secret("POSTGRES_USER").strip()
    if not (host and user):
        return ""
    from urllib.parse import quote
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"                                   # a bare IPv6 address
    port = _either("DB_PORT", "POSTGRES_PORT", "5432").strip()
    name = _secret("POSTGRES_DB").strip() or DEFAULT_DATABASE
    password = _secret("POSTGRES_PASSWORD")
    login = quote(user, safe="") + (":" + quote(password, safe="") if password else "")
    params = "&".join(p for p in (_secret(k).strip().strip("?&")
                                  for k in ("DB_SSL_PARAMS", "DB_WAN_PARAMS")) if p)
    return f"postgresql://{login}@{host}:{port}/{quote(name, safe='')}" + (f"?{params}" if params else "")


DATABASE_URL = _database_url()

# The first account, created once when the user table is empty. Whoever signs
# in with it is made to choose a new password before anything else opens.
DEFAULT_ADMIN_PASSWORD = "ChangeMe@123"
ADMIN_EMAIL = _either("ADMIN_EMAIL", "SEED_ADMIN_EMAIL", "admin@ceat.com").strip()
ADMIN_PASSWORD = _either("ADMIN_PASSWORD", "SEED_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
SESSION_HOURS = int(_either("SESSION_HOURS", "SESSION_TTL_HOURS", "12") or 12)

# --- provider -------------------------------------------------------------
# LLM_PROVIDER picks one of three, per machine:
#   groq    Groq's hosted models                                  (the default)
#   openai  any OpenAI-compatible endpoint (OPENAI_BASE_URL)
#   azure   an Azure OpenAI resource — same variables as ceat-compintel
# Groq is OpenAI-compatible, so the same client speaks to the first two. Azure
# is not merely another base URL: see models.make_client().
PROVIDER = _secret("LLM_PROVIDER", "groq").strip().lower()

GROQ_KEY = _secret("GROQ_API_KEY")
GROQ_BASE = "https://api.groq.com/openai/v1"
GROQ_TEXT_MODEL = _secret("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
GROQ_VISION_MODEL = _secret("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")

OPENAI_KEY = _secret("OPENAI_API_KEY")
OPENAI_BASE = _secret("OPENAI_BASE_URL", "https://api.openai.com/v1")
# The fallback used to be gpt-4o-mini — a "mini" tier, which .env.example itself
# warns against. The model now also writes and proof-reads wording, so the
# default is a full-size model.
OPENAI_TEXT_MODEL = _secret("OPENAI_TEXT_MODEL", "gpt-5.1")
OPENAI_VISION_MODEL = _secret("OPENAI_VISION_MODEL", "gpt-5.1")


# --- Azure OpenAI (LLM_PROVIDER=azure) --------------------------------------
# Azure addresses DEPLOYMENT names created in the portal, not model ids:
# "gpt-4.1" is only a valid target if a deployment was given that name. The
# endpoint may be either surface Azure offers —
#   https://<resource>.openai.azure.com/            classic; needs the API version
#   https://<resource>.openai.azure.com/openai/v1   OpenAI-compatible v1
# — and which one it is, is read from the URL, so only one variable is set.
AZURE_ENDPOINT = _secret("AZURE_OPENAI_ENDPOINT").strip().rstrip("/")
AZURE_KEY = _secret("AZURE_OPENAI_API_KEY").strip()
AZURE_API_VERSION = _secret("AZURE_OPENAI_API_VERSION", "2024-10-21").strip()
# This app has two jobs for a model: reading and writing text, and reading
# images. ceat-compintel names its deployments by tier, so its block can be
# pasted in as it is — the tier-2 (stronger) deployment does the text work here,
# tier-1 if that is all there is. AZURE_TEXT_DEPLOYMENT overrides both.
AZURE_TEXT_DEPLOYMENT = (_secret("AZURE_TEXT_DEPLOYMENT") or _secret("AZURE_TIER2_DEPLOYMENT")
                         or _secret("AZURE_TIER1_DEPLOYMENT")).strip()
AZURE_VISION_DEPLOYMENT = (_secret("AZURE_VISION_DEPLOYMENT").strip() or AZURE_TEXT_DEPLOYMENT)


def azure_is_v1(endpoint: str = "") -> bool:
    """True for Azure's OpenAI-compatible surface (the endpoint ends /openai/v1)."""
    e = (endpoint or AZURE_ENDPOINT).rstrip("/")
    return e.endswith("/openai/v1") or "/openai/v1/" in e


# --- waiting out rate limits ------------------------------------------------
# Azure meters tokens per minute per deployment, so a 429 is ordinary traffic
# there rather than a fault: wait as long as it says and try again. On Groq and
# OpenAI-compatible endpoints the behaviour is what it always was (the SDK's
# single retry) unless LLM_MAX_RETRIES is set.
_retries = _secret("LLM_MAX_RETRIES").strip()
LLM_MAX_RETRIES = int(_retries) if _retries.isdigit() else (5 if PROVIDER == "azure" else 0)
LLM_RETRY_BASE_SECONDS = float(_secret("LLM_RETRY_BASE_SECONDS", "2") or 2)
LLM_RETRY_MAX_SECONDS = float(_secret("LLM_RETRY_MAX_SECONDS", "90") or 90)
_timeout = _secret("LLM_TIMEOUT_SECONDS").strip()
LLM_TIMEOUT_SECONDS = int(_timeout) if _timeout.isdigit() else (120 if PROVIDER == "azure" else 40)

# Azure returns token counts but never a price, so llm_calls.cost_usd would stay
# empty. JSON: {"<deployment or model>": [usd_per_1k_input, usd_per_1k_output]}
LLM_PRICE_TABLE = _secret("LLM_PRICE_TABLE").strip()


def llm_settings() -> dict:
    """Which endpoint, key and models to use. Empty key => deterministic mode."""
    if PROVIDER == "groq":
        return dict(key=GROQ_KEY, base=GROQ_BASE, text=GROQ_TEXT_MODEL,
                    vision=GROQ_VISION_MODEL, name="Groq", azure=False)
    if PROVIDER == "azure":
        return dict(key=AZURE_KEY, base=AZURE_ENDPOINT, text=AZURE_TEXT_DEPLOYMENT,
                    vision=AZURE_VISION_DEPLOYMENT, name="Azure OpenAI", azure=True)
    return dict(key=OPENAI_KEY, base=OPENAI_BASE, text=OPENAI_TEXT_MODEL,
                vision=OPENAI_VISION_MODEL, name="OpenAI-compatible", azure=False)


def llm_missing() -> list[str]:
    """The settings still needed before a model can be called — named, because
    on Azure a missing or wrong one otherwise surfaces as an opaque 404."""
    if PROVIDER == "groq":
        return [] if GROQ_KEY else ["GROQ_API_KEY"]
    if PROVIDER == "azure":
        return [name for name, val in (("AZURE_OPENAI_ENDPOINT", AZURE_ENDPOINT),
                                       ("AZURE_OPENAI_API_KEY", AZURE_KEY),
                                       ("AZURE_TEXT_DEPLOYMENT", AZURE_TEXT_DEPLOYMENT)) if not val]
    return [] if OPENAI_KEY else ["OPENAI_API_KEY"]


def llm_ready() -> bool:
    return not llm_missing()


# --- limits ---------------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_SHEET_ROWS = int(os.getenv("MAX_SHEET_ROWS", "400"))   # rows sent to the model
MAX_DOC_CHARS = int(os.getenv("MAX_DOC_CHARS", "24000"))   # text sent to the model

# The marker used wherever a detail is genuinely unknown. Never a guess.
BLANK = "[● {}]"          # -> "[● amount demanded]"


def blank(label: str) -> str:
    return BLANK.format(label)
