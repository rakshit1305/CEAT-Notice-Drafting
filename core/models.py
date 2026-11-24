"""Which model to actually call.

Hosted model IDs get retired on a schedule — `llama-3.3-70b-versatile` was shut
down in August 2026, and whatever is current today will go the same way. So the
app asks the provider what it has rather than trusting a constant, and picks the
first workable ID from a preference order. A pinned ID in .env always wins; if
the list can't be fetched the configured default is used unchanged.
"""
from __future__ import annotations
import time

from . import config as CFG
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
# OpenAI-compatible accounts. Before this list existed, an unavailable configured
# model on an OpenAI key fell through to "the alphabetically first model the key
# can see" — which could be a tiny or retired model.
OPENAI_TEXT_PREF = ["gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o"]
OPENAI_VISION_PREF = ["gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o"]
VISION_LIMITS = {"qwen/qwen3.6-27b": 5, "qwen/qwen3.8-27b": 3}
_WEAK = ("mini", "nano", "8b", "20b", "instant", "small", "lite")


def weak(model_id: str) -> bool:
    """A small/fast tier — fine for chat, not for legal drafting."""
    m = str(model_id or "").lower()
    return any(w in m for w in _WEAK)
DEFAULT_MAX_IMAGES = 3

_cache: dict = {"at": 0.0, "ids": None, "error": ""}
TTL = 600          # seconds; a restart or ten minutes re-checks


def _client_args(s: dict) -> tuple:
    """(client class, its keyword arguments) for the configured provider.

    Azure has two API surfaces and they need different clients:
      * v1 — the endpoint ends in /openai/v1. The PLAIN OpenAI client with that
        as base_url; no API version. Giving this URL to AzureOpenAI would be
        wrong: that class appends /openai/ itself and the path 404s.
      * classic — the bare resource host. AzureOpenAI plus an API version; it
        builds the /openai/deployments/<name>/ path.
    Either way `model=` is the deployment name. (Same detection, and the same
    variables, as ceat-compintel's llm/client.py.)
    """
    from openai import OpenAI
    if not s.get("azure"):
        return OpenAI, dict(api_key=s["key"], base_url=s["base"])
    if CFG.azure_is_v1(s["base"]):
        # The SDK sends Authorization: Bearer; a gateway in front of the v1
        # surface may still expect api-key. Sending both saves a confusing 401.
        return OpenAI, dict(api_key=s["key"], base_url=s["base"],
                            default_headers={"api-key": s["key"]})
    from openai import AzureOpenAI
    return AzureOpenAI, dict(api_key=s["key"], azure_endpoint=s["base"],
                             api_version=CFG.AZURE_API_VERSION)


def make_client(timeout: int | None = None):
    """A client for the configured provider that survives the openai/httpx
    version clash.

    httpx 0.28 removed the `proxies` argument; openai SDKs before 1.55.3 still
    pass it, so constructing a client raises
        TypeError: Client.__init__() got an unexpected keyword argument 'proxies'
    Handing the SDK a client we built ourselves skips the code that does it, so
    the app works on either combination rather than demanding an upgrade.
    """
    s = llm_settings()
    timeout = timeout or CFG.LLM_TIMEOUT_SECONDS
    cls, kw = _client_args(s)
    try:
        return cls(timeout=timeout, max_retries=1, **kw), s
    except TypeError as e:
        if "proxies" not in str(e):
            raise
        import httpx
        return cls(max_retries=1, http_client=httpx.Client(timeout=timeout), **kw), s


def available(force: bool = False) -> set[str]:
    """Model IDs this key can actually call. Empty set means 'could not ask'.

    On Azure the list is the resource's model catalogue, not its deployments —
    so there it only shows that the endpoint and key work; pick() never chooses
    from it.
    """
    s = llm_settings()
    if not s["key"] or (s.get("azure") and not s["base"]):
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
    if s.get("azure"):
        # A deployment is addressed by the name it was given in the portal and
        # nothing else. Swapping in a model id from a preference list — right
        # on Groq, where ids get retired — is a 404 DeploymentNotFound here.
        if not configured:
            return "", "no Azure deployment named in .env"
        return configured, "Azure deployment named in .env"
    if s["name"] == "Groq":
        pref = TEXT_PREF if role == "text" else VISION_PREF
    else:
        pref = OPENAI_TEXT_PREF if role == "text" else OPENAI_VISION_PREF
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
    # Never guess an arbitrary model: keep the configured one and say so. If it
    # really is unavailable the call fails visibly instead of silently running
    # on whatever happens to sort first.
    return configured, (f"“{configured}” is not in this account's model list and none of the "
                        "preferred models are either — calls will use it and may fail")


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
    missing = CFG.llm_missing()
    return dict(provider=s["name"], key=not missing, missing=missing,
                azure=bool(s.get("azure")), reachable=bool(available()) if not missing else False,
                text=t, text_why=twhy, vision=v, vision_why=vwhy, weak=weak(t),
                images=max_images(v), error=last_error(), versions=versions())
