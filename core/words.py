"""Indian-format numbers, dates and amounts-in-words.

House style requires every amount in figures AND words, dates as DD.MM.YYYY,
and grouping in the Indian system (lakh, crore).
"""
from __future__ import annotations
import re
from datetime import date, datetime

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
        "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _u100(n: int) -> str:
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _u1000(n: int) -> str:
    h, r = divmod(n, 100)
    out = (ONES[h] + " Hundred" if h else "")
    if r:
        out += (" " if out else "") + _u100(r)
    return out


def to_words(value) -> str:
    """7,50,400 -> 'Rupees Seven Lakh Fifty Thousand Four Hundred Only'"""
    n = to_float(value)
    if n is None:
        return ""
    whole = int(n)
    paise = int(round((n - whole) * 100))
    if whole == 0 and paise == 0:
        return ""
    parts: list[str] = []
    crore, whole = divmod(whole, 10_000_000)
    lakh, whole = divmod(whole, 100_000)
    thou, whole = divmod(whole, 1_000)
    if crore:
        parts.append(_u1000(crore) + " Crore")
    if lakh:
        parts.append(_u1000(lakh) + " Lakh")
    if thou:
        parts.append(_u1000(thou) + " Thousand")
    if whole:
        parts.append(_u1000(whole))
    s = "Rupees " + " ".join(p for p in parts if p).strip()
    if paise:
        s += " and Paise " + _u100(paise)
    return s + " Only"


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"[^\d.\-]", "", str(value))
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fmt_amount(value) -> str:
    """8,42,150.00 in the Indian grouping."""
    n = to_float(value)
    if n is None:
        return ""
    neg = n < 0
    n = abs(n)
    whole = int(n)
    dec = f"{n - whole:.2f}"[2:]
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = head + "," + tail
    return ("-" if neg else "") + s + "." + dec


def inr(value) -> str:
    a = fmt_amount(value)
    return f"INR {a}/-" if a else ""


# --------------------------------------------------------------------------
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(value):
    """Anything date-ish -> a datetime.date, or None. Day-first, as in India."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})$", s)
    if m:
        d_, mo, y = int(m[1]), int(m[2]), int(m[3])
        if y < 100:
            y += 2000 if y < 50 else 1900
        try:
            return date(y, mo, d_)
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})$", s)
    if m and m[2][:3].lower() in MONTHS:
        try:
            return date(int(m[3]), MONTHS[m[2][:3].lower()], int(m[1]))
        except ValueError:
            return None
    return None


def fmt_date(value) -> str:
    d = parse_date(value)
    return d.strftime("%d.%m.%Y") if d else (str(value) if value else "")


def iso(value) -> str:
    d = parse_date(value)
    return d.isoformat() if d else ""


def find_dates(text: str) -> list[str]:
    """Every date in a blob of text, in order of appearance, as ISO strings."""
    out: list[str] = []
    for m in re.finditer(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b", text or ""):
        d = parse_date(f"{m[1]}.{m[2]}.{m[3]}")
        if d and d.isoformat() not in out:
            out.append(d.isoformat())
    for m in re.finditer(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b", text or ""):
        d = parse_date(f"{m[1]} {m[2]} {m[3]}")
        if d and d.isoformat() not in out:
            out.append(d.isoformat())
    return out


def find_amounts(text: str) -> list[float]:
    out: list[float] = []
    for m in re.finditer(r"(?:INR|Rs\.?|₹)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", text or "", re.I):
        v = to_float(m[1])
        if v is not None and v not in out:
            out.append(v)
    return sorted(out, reverse=True)
