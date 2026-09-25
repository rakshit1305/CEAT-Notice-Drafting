"""Small compatibility helpers for the Streamlit UI.

Streamlit changes widget keyword arguments between releases, and
requirements.txt deliberately has no upper pin, so Streamlit Cloud installs
whatever is current. Rather than guess, ask the installed version what it takes.
"""
from __future__ import annotations
from functools import lru_cache
from inspect import signature


@lru_cache(maxsize=None)
def _fit_kw(name: str) -> tuple:
    import streamlit as st
    return _probe(st, name)


def _probe(mod, name: str) -> tuple:
    fn = getattr(mod, name, None)
    if fn is None:
        return ()
    try:
        params = signature(fn).parameters
    except (TypeError, ValueError):
        return (("use_container_width", True),)
    if "use_container_width" in params:
        return (("use_container_width", True),)
    if "width" in params:                    # 1.49+ replacement
        return (("width", "stretch"),)
    return ()


def fit(name: str, mod=None) -> dict:
    """Keyword(s) that make a widget fill its container on this Streamlit.

    `use_container_width` was deprecated in 1.49 in favour of width="stretch"
    and is being removed element by element; passing it to a version that has
    dropped it raises TypeError and kills the page. `mod` is for tests.
    """
    return dict(_probe(mod, name) if mod is not None else _fit_kw(name))


def clean_rows(rows, cols: list[str]) -> list[dict]:
    """Table data as the editor needs it: a list of dicts of plain strings.

    The model can return a table as a list of strings, a dict, rows with nested
    values or numbers instead of text. Newer Arrow/Streamlit versions are
    stricter about mixed types than older ones, so normalise before display.
    """
    if isinstance(rows, dict):
        rows = [rows]
    if isinstance(rows, str):
        rows = []
    out = []
    for r in rows or []:
        if not isinstance(r, dict):
            r = {cols[0]: r}
        row = {}
        for c in cols:
            v = r.get(c, "")
            if v is None:
                v = ""
            elif isinstance(v, (list, tuple)):
                v = ", ".join(str(x) for x in v)
            elif isinstance(v, dict):
                v = ", ".join(f"{k}: {x}" for k, x in v.items())
            elif isinstance(v, float) and v.is_integer():
                v = str(int(v))
            row[c] = str(v)
        out.append(row)
    return out
