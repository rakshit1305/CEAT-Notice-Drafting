"""The analysis step: read everything, fill what can be filled, invent nothing.

The model is given (a) the skill's golden rules, (b) the notice type's required
inputs from its reference file, (c) what the user has already answered, and
(d) every document. It returns strict JSON — values it actually found, with the
evidence, plus a list of what is missing. `null` is a legitimate answer and the
prompt says so; rules 02 and 04 are enforced here and re-checked in validate.py.

With no API key the module falls back to a deterministic reader that handles
ordinary ledgers and invoice text without any model at all.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field

from . import skill_loader as SK
from .config import llm_ready, llm_settings
from .extract import Doc
from .schema import LABELS, TABLE_COLS, label
from .words import find_amounts, find_dates, iso, to_float

SCALAR_KEYS = [k for k in LABELS if k not in TABLE_COLS]


@dataclass
class Found:
    values: dict = field(default_factory=dict)      # field key -> value
    evidence: dict = field(default_factory=dict)    # field key -> where it came from
    missing: list = field(default_factory=list)     # labels the model could not find
    notes: list = field(default_factory=list)
    used_model: bool = False
    error: str = ""


# --------------------------------------------------------------------------
def _client():
    from .models import make_client
    return make_client()


def _prompt(kind: str, case: dict, docs: list[Doc]) -> str:
    ref = SK.notice_ref(kind)
    rules = "\n".join(f"{r.n}. {r.title}. {r.body}" for r in SK.golden_rules())
    known = {k: v for k, v in case.items()
             if not k.startswith("_") and v not in (None, "", [], {})}
    wanted = [k for k in SCALAR_KEYS] + list(TABLE_COLS)

    doc_blocks = []
    for d in docs:
        if d.kind in ("tables", "text"):
            doc_blocks.append(f"===== DOCUMENT: {d.name} =====\n{d.as_prompt()}")
    documents = "\n\n".join(doc_blocks) or "(no readable documents attached)"

    cols = {t: [c[0] for c in TABLE_COLS[t]] for t in TABLE_COLS}

    return f"""You are the analysis step of CEAT Limited's legal notice drafting console.
You are preparing a {SK.notice_ref(kind).kind} — {ref.when_to_use or kind}.

THE RULES THAT BIND YOU (from CEAT's own skill definition):
{rules}

THE INPUTS THIS NOTICE TYPE NEEDS (from its approved reference file):
{chr(10).join('- ' + i for i in ref.required_inputs) or '- (see the template)'}

WHAT THE USER HAS ALREADY TOLD US — treat as authoritative, never contradict it,
never restate it back as if newly found:
{json.dumps(known, indent=2, default=str, ensure_ascii=False)}

THE ATTACHED DOCUMENTS:
{documents}

YOUR TASK
Work out for yourself which sheet, which header row, which columns and which rows
matter. Use what the user told you to find the right material — if they named the
dealer, keep only that dealer's rows and ignore the others. Read every document.
Then return the values you actually found.

ABSOLUTE CONSTRAINTS
- Never invent, round, estimate or infer a value that is not supported by the user's
  input or a document. If you cannot find it, omit the key and name it in "missing".
- Do not supply a statutory section, Act name or deadline from memory.
- Do not overwrite anything already present in the user's input above.
- Amounts: digits only, no commas or currency symbols. Dates: YYYY-MM-DD.
- For a total you computed by summing rows, say so in "evidence".

RETURN ONLY JSON, no prose, exactly this shape:
{{
  "values": {{ "<field key>": <value>, ... }},
  "evidence": {{ "<field key>": "<where in which document, in a few words>", ... }},
  "missing": ["<plain-English name of something this notice needs that you could not find>"],
  "notes": ["<anything a lawyer should know about how you read the documents>"]
}}

Valid scalar field keys: {", ".join(SCALAR_KEYS)}
Valid table field keys, each an array of objects with exactly these columns:
{json.dumps(cols, indent=1)}
"""


_GONE = ("decommissioned", "does not exist", "not found", "deprecated",
         "model_not_found", "no longer supported")


def _chat(client, role: str, **kw):
    """One chat call, retried once against a freshly discovered model if the
    pinned ID has been retired since the app started."""
    from . import models as MODELS
    model, _ = MODELS.pick(role)
    try:
        return client.chat.completions.create(model=model, **kw)
    except Exception as e:
        if not any(w in str(e).lower() for w in _GONE):
            raise
        MODELS.available(force=True)
        retry, _ = MODELS.pick(role)
        if retry == model:
            raise
        return client.chat.completions.create(model=retry, **kw)


def _call_text(kind: str, case: dict, docs: list[Doc]) -> Found:
    client, s = _client()
    out = Found(used_model=True)
    try:
        rsp = _chat(
            client, "text",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system",
                 "content": "You extract structured facts for legal drafting. "
                            "You never invent a value. You reply with JSON only."},
                {"role": "user", "content": _prompt(kind, case, docs)},
            ],
        )
        data = json.loads(rsp.choices[0].message.content or "{}")
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
        return out
    out.values = data.get("values") or {}
    out.evidence = data.get("evidence") or {}
    out.missing = [str(x) for x in (data.get("missing") or [])]
    out.notes = [str(x) for x in (data.get("notes") or [])]
    return out


def _call_vision(kind: str, case: dict, images: list[Doc]) -> Found:
    """Cheque photos, bank memos, scanned notices."""
    from . import models as MODELS
    client, s = _client()
    out = Found(used_model=True)
    content = [{"type": "text", "text": _prompt(kind, case, []) +
                "\n\nThe documents are the attached images. Read them."}]
    cap = MODELS.max_images(MODELS.pick("vision")[0])
    if len(images) > cap:
        out.notes.append(f"{len(images)} images attached; this vision model takes {cap} per "
                         f"request, so the first {cap} were read. Run again with the rest.")
    for im in images[:cap]:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{im.mime};base64,{im.b64}"}})
    try:
        rsp = _chat(
            client, "vision", temperature=0,
            messages=[{"role": "user", "content": content}],
        )
        raw = rsp.choices[0].message.content or "{}"
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else "{}")
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
        return out
    out.values = data.get("values") or {}
    out.evidence = data.get("evidence") or {}
    out.missing = [str(x) for x in (data.get("missing") or [])]
    out.notes = [str(x) for x in (data.get("notes") or [])]
    return out


# --------------------------------------------------------------------------
# deterministic fallback — works with no key at all
# --------------------------------------------------------------------------
def _looks_money(v) -> bool:
    s = re.sub(r"[,\s₹]|INR|Rs\.?", "", str(v or ""), flags=re.I)
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", s)) and abs(float(s or 0)) >= 1


def _looks_date(v) -> bool:
    return bool(iso(v))


def _header_row(rows: list[list]) -> int:
    best, best_score = 0, -1
    for i, r in enumerate(rows[:12]):
        filled = sum(1 for c in r if str(c).strip())
        if filled < 2:
            continue
        wordy = sum(1 for c in r if str(c).strip() and not _looks_money(c) and not _looks_date(c)
                    and re.search(r"[A-Za-z]", str(c)))
        nxt = rows[i + 1] if i + 1 < len(rows) else []
        data_like = sum(1 for c in nxt if _looks_money(c) or _looks_date(c))
        score = wordy * 2 + data_like * 3 + filled
        if score > best_score:
            best, best_score = i, score
    return best


def _sniff(header: list, body: list[list]) -> dict:
    n = len(header)
    cols = {}
    hints = dict(
        date=["date", "dated", "dt"],
        amt=["amount", "amt", "outstanding", "balance", "value", "total", "due", "debit", "net"],
        ref=["invoice", "inv", "bill", "ref", "document", "doc", "voucher"],
        party=["party", "dealer", "customer", "name", "account", "ledger", "distributor"],
    )
    tests = dict(date=_looks_date, amt=_looks_money, ref=lambda v: bool(re.search(r"\d", str(v))),
                 party=lambda v: bool(re.search(r"[A-Za-z]{3,}", str(v))) and not _looks_money(v))
    for role, words in hints.items():
        best, best_s = -1, 0.0
        for c in range(n):
            h = re.sub(r"[^a-z ]", " ", str(header[c]).lower())
            vals = [r[c] for r in body if c < len(r) and str(r[c]).strip()]
            hit = 3.0 if any(w in h for w in words) else 0.0
            frac = (sum(1 for v in vals if tests[role](v)) / len(vals)) * 2 if vals else 0
            if hit + frac > best_s:
                best, best_s = c, hit + frac
        cols[role] = best if best_s >= 1.2 else -1
    return cols


def _tokens(s: str) -> list[str]:
    stop = {"the", "and", "ltd", "limited", "pvt", "private", "mrs", "shri", "prop",
            "proprietor", "company", "messrs"}
    return [w for w in re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split()
            if len(w) > 2 and w not in stop]


def deterministic(kind: str, case: dict, docs: list[Doc]) -> Found:
    out = Found()
    known_party = case.get("noticee_name") or case.get("client_name") or ""
    table_key = "soa" if kind == "recovery" else ("prices" if kind == "price" else "invoices")

    for d in docs:
        if d.kind == "tables":
            for t in d.tables:
                rows = t["rows"]
                hi = _header_row(rows)
                header = [str(c).strip() for c in rows[hi]]
                body = [r for r in rows[hi + 1:] if any(str(c).strip() for c in r)]
                if not body:
                    continue
                cols = _sniff(header, body)

                want = _tokens(known_party)
                if want and cols["party"] >= 0:
                    hits = [r for r in body
                            if any(w in re.sub(r"[^a-z0-9]+", " ", str(r[cols['party']]).lower())
                                   for w in want)]
                    if hits and len(hits) < len(body):
                        out.notes.append(
                            f"{d.name}: kept {len(hits)} of {len(body)} rows matching “{known_party}”.")
                        body = hits

                spec = TABLE_COLS.get(table_key, [])
                built = []
                for r in body:
                    row = {}
                    for ck, _ in spec:
                        ci = {"date": cols["date"], "amt": cols["amt"], "old": cols["amt"]}.get(
                            ck, cols["ref"] if ck in ("ref", "no", "sku") else -1)
                        v = str(r[ci]).strip() if 0 <= ci < len(r) else ""
                        if ck == "date":
                            v = iso(v) or v
                        if ck in ("amt", "old", "nw"):
                            v = re.sub(r"[^\d.\-]", "", v)
                        row[ck] = v
                    if any(row.values()):
                        built.append(row)
                if built:
                    out.values[table_key] = built
                    out.evidence[table_key] = f"{d.name}, sheet “{t['sheet']}”, {len(built)} rows"

                if cols["amt"] >= 0:
                    total = sum(to_float(r[cols["amt"]]) or 0 for r in body if cols["amt"] < len(r))
                    if total:
                        out.values["amount"] = round(total, 2)
                        out.evidence["amount"] = f"{d.name}: sum of {len(body)} rows"
                pre = "\n".join(" ".join(str(c) for c in r) for r in rows[:hi])
                m = re.search(r"as\s*on\s*:?\s*([0-9][0-9.\-/]{6,12})", pre, re.I)
                if m and iso(m[1]):
                    out.values["as_on_date"] = iso(m[1])
                    out.evidence["as_on_date"] = f"{d.name}: stated in the sheet heading"
                elif cols["date"] >= 0:
                    ds = sorted(filter(None, (iso(r[cols["date"]]) for r in body if cols["date"] < len(r))))
                    if ds:
                        out.values["as_on_date"] = ds[-1]
                        out.evidence["as_on_date"] = f"{d.name}: latest document date"

        elif d.kind == "text":
            t = d.text
            dts, amts = find_dates(t), find_amounts(t)
            chq = re.search(r"(?:cheque|chq)\s*(?:no\.?|number|#)?\s*[:\-]?\s*(\d{5,10})", t, re.I)
            inv = re.search(r"(?:invoice|inv|bill)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{3,24})", t, re.I)
            bank = re.search(r"^.*\b[Bb]ank\b.*$", t, re.M)
            clause = re.search(r"clause\s*([0-9][0-9.()a-z]*)", t, re.I)
            if chq:
                out.values["cheques"] = [dict(no=chq[1], date=dts[0] if dts else "",
                                              amt=str(amts[0]) if amts else "",
                                              bank=(bank[0].strip()[:110] if bank else ""))]
                out.evidence["cheques"] = d.name
            if inv and kind != "recovery":
                out.values.setdefault("invoices", [dict(no=inv[1], date=dts[0] if dts else "",
                                                        amt=str(amts[0]) if amts else "")])
                out.evidence["invoices"] = d.name
            if clause:
                out.values["clause_no"] = clause[1]
                out.evidence["clause_no"] = d.name
            if amts:
                out.values.setdefault("amount", amts[0])
                out.evidence.setdefault("amount", f"{d.name}: largest amount found")
            if dts:
                out.values.setdefault("agreement_date", dts[0])
                out.evidence.setdefault("agreement_date", d.name)
            if kind == "consumer" and len(t) > 200:
                out.values.setdefault("incoming", t)
                out.evidence.setdefault("incoming", d.name)
                n = len(re.findall(r"(^|\n)\s*\(?\d{1,2}[.)]", t))
                if n:
                    out.values.setdefault(
                        "paras", [dict(n=str(i), stance="Deny", text="") for i in range(1, n + 1)])
                    out.evidence.setdefault("paras", f"{d.name}: {n} numbered paragraphs")

        elif d.kind == "image":
            out.notes.append(f"{d.name}: an image — no model key configured, so it was not read.")
        elif d.kind == "error":
            out.notes.append(f"{d.name}: {d.note}")
    return out


# --------------------------------------------------------------------------
def analyse(kind: str, case: dict, docs: list[Doc]) -> Found:
    """Model first when a key is present, deterministic reader as the floor.

    The two are merged, not alternatives: the deterministic pass supplies table
    rows and sums the model may not bother with, and never overwrites the model.
    """
    from .freetext import from_text, narrative

    story = str(case.get("_narrative") or "").strip()
    # The account goes to the model as context, but never through the
    # deterministic document reader — that one is built for files, and its
    # first-cheque-wins scan would beat the narrative parser's full reading.
    story_doc = Doc(name="What you told the console", kind="text", text=story,
                    digest="narrative") if story else None

    base = deterministic(kind, case, docs)
    ft_vals, ft_ev = from_text(kind, case)
    nv_vals, nv_ev, nv_notes = narrative(kind, story) if story else ({}, {}, [])

    def with_typed(found: Found) -> Found:
        """The user's own words are the floor under everything else: a field the
        documents and the model did not produce is still filled if the answer
        boxes plainly contain it. A specific answer beats the general account."""
        for vals, evs in ((ft_vals, ft_ev), (nv_vals, nv_ev)):
            for k, v in vals.items():
                if k not in found.values or found.values[k] in (None, "", [], {}):
                    found.values[k] = v
                    found.evidence.setdefault(k, evs.get(k, "read from what you typed"))
        for n in nv_notes:
            if n not in found.notes:
                found.notes.append(n)
        return found

    typed = story or any(str(v or "").strip() for k, v in case.items() if k.startswith("_raw_"))

    if not llm_ready():
        base.notes.append("No model key configured — your answers and any documents were read "
                          "directly. Set GROQ_API_KEY to have them actually reasoned over.")
        return with_typed(base)

    readable = [d for d in docs if d.kind in ("tables", "text")]
    if story_doc:
        readable = readable + [story_doc]
    images = [d for d in docs if d.kind == "image"]

    merged = Found(values=dict(base.values), evidence=dict(base.evidence),
                   notes=list(base.notes), missing=[], used_model=True)

    # The model is worth a call even with no attachment: the typed answers are
    # in the prompt, and it reads a messy sentence better than any regex.
    for got in ([_call_text(kind, case, readable)] if (readable or typed) else []) + \
               ([_call_vision(kind, case, images)] if images else []):
        if got.error:
            merged.notes.append(f"Model call failed ({got.error}) — deterministic reading kept.")
            continue
        for k, v in (got.values or {}).items():
            if v in (None, "", [], {}):
                continue
            merged.values[k] = v                      # the model wins over the regex floor
            if got.evidence.get(k):
                merged.evidence[k] = got.evidence[k]
        merged.missing += [m for m in got.missing if m not in merged.missing]
        merged.notes += [n for n in got.notes if n not in merged.notes]
    return with_typed(merged)
