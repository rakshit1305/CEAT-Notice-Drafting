"""Configuration. Everything that varies by deployment lives here."""
from __future__ import annotations
import os
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
AUTO_SAVE = _secret("NOTICE_AUTO_SAVE", "1").strip().lower() not in ("0", "false", "no", "off")

# --- provider -------------------------------------------------------------
# Groq is OpenAI-compatible, so the same client speaks to either.
PROVIDER = _secret("LLM_PROVIDER", "groq").lower()

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


def llm_settings() -> dict:
    """Which endpoint, key and models to use. Empty key => deterministic mode."""
    if PROVIDER == "groq":
        return dict(key=GROQ_KEY, base=GROQ_BASE,
                    text=GROQ_TEXT_MODEL, vision=GROQ_VISION_MODEL, name="Groq")
    return dict(key=OPENAI_KEY, base=OPENAI_BASE,
                text=OPENAI_TEXT_MODEL, vision=OPENAI_VISION_MODEL, name="OpenAI-compatible")


def llm_ready() -> bool:
    return bool(llm_settings()["key"])


# --- limits ---------------------------------------------------------------
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_SHEET_ROWS = int(os.getenv("MAX_SHEET_ROWS", "400"))   # rows sent to the model
MAX_DOC_CHARS = int(os.getenv("MAX_DOC_CHARS", "24000"))   # text sent to the model

# The marker used wherever a detail is genuinely unknown. Never a guess.
BLANK = "[● {}]"          # -> "[● amount demanded]"


def blank(label: str) -> str:
    return BLANK.format(label)
