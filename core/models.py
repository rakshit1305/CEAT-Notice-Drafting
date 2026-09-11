"""Which model to actually call.

Hosted model IDs get retired on a schedule — `llama-3.3-70b-versatile` was shut
down in August 2026, and whatever is current today will go the same way. So the
app asks the provider what it has rather than trusting a constant, and picks the
first workable ID from a preference order. A pinned ID in .env always wins; if
the list can't be fetched the configured default is used unchanged.
"""
from __future__ import annotations
import time

from .config import llm_settings

# Best first. Anything not offered by the account is skipped.
TEXT_PREF = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
VISION_PREF = [
    "qwen/qwen3.6-27b",          # 5 images per request
    "qwen/qwen3.8-27b",          # 3 images per request
]
VISION_LIMITS = {"qwen/qwen3.6-27b": 5, "qwen/qwen3.8-27b": 3}
DEFAULT_MAX_IMAGES = 3

_cache: dict = {"at": 0.0, "ids": None, "error": ""}
TTL = 600          # seconds; a restart or ten minutes re-checks


def make_client(timeout: int = 40):
    """An OpenAI-protocol client that survives the openai/httpx version clash.

    httpx 0.28 removed the `proxies` argument; openai SDKs before 1.55.3 still
    pass it, so constructing a client raises
        TypeError: Client.__init__() got an unexpected keyword argument 'proxies'
    Handing the SDK a client we built ourselves skips the code that does it, so
    the app works on either combination rather than demanding an upgrade.
    """
    from openai import OpenAI
    s = llm_settings()
    try:
        return OpenAI(api_key=s["key"], base_url=s["base"], timeout=timeout, max_retries=1), s
    except TypeError as e:
        if "proxies" not in str(e):
            raise
        import httpx
        return OpenAI(api_key=s["key"], base_url=s["base"], max_retries=1,
                      http_client=httpx.Client(timeout=timeout)), s


def available(force: bool = False) -> set[str]:
    """Model IDs this key can actually call. Empty set means 'could not ask'."""
    s = llm_settings()
    if not s["key"]:
        return set()
    now = time.time()
    if not force and _cache["ids"] is not None and now - _cache["at"] < TTL:
        return _cache["ids"]
    ids: set[str] = set()
    err = ""
    try:
        client, _ = make_client(timeout=12)
        ids = {m.id for m in client.models.list().data}
    except Exception as e:                       # offline, bad key, provider down
        err = f"{type(e).__name__}: {e}"[:180]
    _cache.update(at=now, ids=ids, error=err)
    return ids


def last_error() -> str:
    return _cache.get("error", "")


def pick(role: str = "text") -> tuple[str, str]:
    """(model id, one line saying why). role is 'text' or 'vision'."""
    s = llm_settings()
    configured = s["text"] if role == "text" else s["vision"]
    pref = TEXT_PREF if role == "text" else VISION_PREF
    have = available()

    if not have:
        why = ("could not reach the provider's model list — using the configured default"
               if s["key"] else "no key set")
        return configured, why
    if configured in have:
        return configured, "configured in .env and available"
    for m in pref:
        if m in have:
            return m, (f"“{configured}” is not available on this account — "
                       f"fell back to the best one that is")
    any_left = sorted(have)
    if any_left:
        return any_left[0], f"none of the preferred models are available; using “{any_left[0]}”"
    return configured, "the provider returned no models"


def max_images(model_id: str) -> int:
    return VISION_LIMITS.get(model_id, DEFAULT_MAX_IMAGES)


def versions() -> str:
    """What is actually installed in the interpreter Streamlit is running."""
    import sys
    out = []
    for name in ("openai", "httpx"):
        try:
            out.append(f"{name} {__import__(name).__version__}")
        except Exception:
            out.append(f"{name} not installed")
    return " · ".join(out) + f" · {sys.executable}"


def status() -> dict:
    """Everything the sidebar needs, in one call."""
    s = llm_settings()
    t, twhy = pick("text")
    v, vwhy = pick("vision")
    return dict(provider=s["name"], key=bool(s["key"]), reachable=bool(available()),
                text=t, text_why=twhy, vision=v, vision_why=vwhy,
                images=max_images(v), error=last_error(), versions=versions())
