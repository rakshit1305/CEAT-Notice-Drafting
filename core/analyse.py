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
from .freetext import _cheques, _directors, _invoices, _noticee_type
from .schema import LABELS, TABLE_COLS, label
from .words import find_amounts, find_dates, fmt_amount, iso, to_float

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

READING A LEDGER, AGEING REPORT OR STATEMENT
A file of this kind usually covers MANY counterparties. This notice concerns ONE.
- Keep only the rows whose party/customer/dealer column matches this notice's
  counterparty. Match on the substance of the name, not character-for-character:
  "M/s Highway Auto Spares Pvt Ltd" and "M/s Highway Auto Spares Private Limited"
  are the same party. Every other row belongs to a different customer and must not
  appear, be summed, or influence any figure.
- Putting another customer's rows into this notice discloses their data to a third
  party. Treat it as a hard error, not an untidiness.
- Where both an invoice-value column and an outstanding/balance column exist, the
  amount demanded is the OUTSTANDING/BALANCE column. Invoice value is what was
  billed; balance is what is still owed after payments. Never sum invoice value
  when a balance column is present.
- The total you return must equal the sum of the rows you return in the table. If
  they cannot be reconciled, omit the total and say so in "missing".
- In "evidence" for the total, state the counterparty filtered on, the column summed
  and the number of rows — e.g. "AR ageing, Highway Auto Spares, Balance O/s, 5 rows".

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
    # What is still owed beats what was billed. A ledger carrying both an
    # "Invoice Amt" and a "Balance O/s" column must be summed on the balance.
    owed = ["outstanding", "balance", "o/s", "os", "closing", "unpaid"]
    billed = ["invoice amt", "invoice amount", "invoice value", "gross", "billed"]
    tests = dict(date=_looks_date, amt=_looks_money, ref=lambda v: bool(re.search(r"\d", str(v))),
                 party=lambda v: bool(re.search(r"[A-Za-z]{3,}", str(v))) and not _looks_money(v))
    for role, words in hints.items():
        best, best_s = -1, 0.0
        for c in range(n):
            h = re.sub(r"[^a-z /]", " ", str(header[c]).lower())
            vals = [r[c] for r in body if c < len(r) and str(r[c]).strip()]
            hit = 3.0 if any(w in h for w in words) else 0.0
            if role == "amt" and hit:
                if any(w in h for w in owed):
                    hit += 2.5          # prefer the balance column
                elif any(w in h for w in billed):
                    hit -= 1.5          # demote gross invoice value
            frac = (sum(1 for v in vals if tests[role](v)) / len(vals)) * 2 if vals else 0
            if hit + frac > best_s:
                best, best_s = c, hit + frac
        cols[role] = best if best_s >= 1.2 else -1
    return cols


def _tokens(s: str) -> list[str]:
    # Constitution words carry no identity, and neither do the trade words that
    # half the dealers in a tyre ledger share. Matching on "auto" or "spares"
    # pulls in every other dealer; matching on "highway" finds the right one.
    stop = {"the", "and", "ltd", "limited", "pvt", "private", "mrs", "shri", "prop",
            "proprietor", "company", "messrs",
            "auto", "autos", "spare", "spares", "tyre", "tyres", "tube", "tubes",
            "motor", "motors", "wheel", "wheels", "trader", "traders", "trading",
            "enterprise", "enterprises", "agency", "agencies", "automobile",
            "automobiles", "sales", "service", "services", "centre", "center",
            "house", "depot", "store", "stores", "works", "india", "corporation"}
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
                    elif not hits:
                        # Better no figure than the whole ledger's figure.
                        out.notes.append(
                            f"{d.name}: no row matched “{known_party}”, so nothing was taken from this "
                            f"file. Check the name in the sheet against the name on the notice.")
                        continue
                elif want and cols["party"] < 0:
                    out.notes.append(
                        f"{d.name}: no party/customer column was found, so the rows could not be "
                        f"narrowed to “{known_party}”. Any total here would cover every counterparty "
                        f"in the file — check it before use.")
                elif not want and cols["party"] >= 0:
                    # The sheet has a party column, so it CAN be narrowed — but the
                    # counterparty is not known yet at this pass (it is likely still
                    # to be read out of another attached document, e.g. by the model
                    # later in this same analyse() call). Handing back every row here
                    # would silently pass off the whole ledger as this party's
                    # statement, which is exactly the failure this filter exists to
                    # stop. Leave the table alone; the later filtered-rows fallback
                    # (which does know how to look the name up) picks it up once the
                    # name is known.
                    out.notes.append(
                        f"{d.name}: the counterparty's name is not known yet, so its "
                        f"{len(body)} row(s) were not taken from this file at this pass — "
                        f"narrowing happens once the name is read.")
                    continue

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
                        # Name the column. "Outstanding", "Balance", "Debit" and "Net" are
                        # different figures in a real ledger and the sniffer cannot tell
                        # which one was meant — so the choice is stated, not hidden.
                        col_name = str(header[cols["amt"]]).strip() if cols["amt"] < len(header) else ""
                        col_name = col_name or f"column {cols['amt'] + 1}"
                        out.values["amount"] = round(total, 2)
                        out.evidence["amount"] = (f"{d.name}, sheet “{t['sheet']}”: sum of {len(body)} rows "
                                                  f"in column “{col_name}”")
                        out.notes.append(
                            f"{d.name}: no model key configured, so the amount column was chosen by "
                            f"keyword. It summed “{col_name}”. Confirm that is the figure you want — "
                            f"outstanding, balance, debit and net are not the same thing."
                        )
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
            clause = re.search(r"clause\s*([0-9][0-9.()a-z]*)", t, re.I)

            # Cheques: the same cue-anchored reader the typed answers use, so a
            # pasted sheet and a typed answer produce identical rows. The old
            # code took the first date and the first amount anywhere in the
            # file and pasted the whole line containing "Bank" into the bank
            # field, truncated at 110 characters.
            chqs = _cheques(t)
            if chqs:
                out.values["cheques"] = chqs
                out.evidence["cheques"] = d.name
                if len(chqs) == 1:
                    for col, key in (("dis", "dishonour_date"),
                                     ("reason", "dishonour_reason"),
                                     ("memo", "memo_date")):
                        if chqs[0].get(col):
                            out.values.setdefault(key, chqs[0][col])
                            out.evidence.setdefault(key, d.name)

            if kind != "recovery":
                invs = _invoices(t)
                if invs:
                    out.values.setdefault("invoices", invs)
                    out.evidence["invoices"] = d.name

            # A private limited company must never fall through to the
            # proprietorship wording because the choice widget was untouched.
            nt = _noticee_type(t)
            if nt:
                out.values.setdefault("noticee_type", nt)
                out.evidence.setdefault("noticee_type", d.name)
            if nt.startswith(("Company","Partnership")):
                dirs = _directors(t, out.values.get("noticee_address", ""))
                if dirs:
                    out.values.setdefault("directors", dirs)
                    out.evidence.setdefault("directors", d.name)
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
                        # Stance left blank deliberately: denying every paragraph
                        # is a legal position, not a default, and the app has no
                        # basis for taking it on the user's behalf.
                        "paras", [dict(n=str(i), stance="", text="") for i in range(1, n + 1)])
                    out.evidence.setdefault("paras", f"{d.name}: {n} numbered paragraphs")
                    out.notes.append(
                        f"{d.name}: {n} numbered paragraphs found. Set a stance for each — they are "
                        f"deliberately left blank rather than denied by default.")

        elif d.kind == "image":
            out.notes.append(f"{d.name}: an image — no model key configured, so it was not read.")
        elif d.kind == "error":
            out.notes.append(f"{d.name}: {d.note}")
    return out


_BAD_BANK = re.compile(r"cheque\s*no|dated|for\s*inr|drawn\s*on", re.I)


def _plausible(key: str, value) -> bool:
    """Is a model-returned value the right shape for its field?

    The model wins over the deterministic regex floor, which is usually right —
    but when it returns a fragment ("oices" for an invoice number) or swallows a
    whole sentence into a field ("drawn on Cheque No. 004521 dated ... issued"),
    that overwrites a correct parse with rubbish that then prints in the notice.
    Values failing this check are dropped, leaving the deterministic value.
    """
    if isinstance(value, list):
        return all(_plausible_row(r) for r in value if isinstance(r, dict))
    s = str(value or "").strip()
    if key in ("bank",) and (len(s) > 90 or _BAD_BANK.search(s)):
        return False
    return True


def _plausible_row(row: dict) -> bool:
    ref = str(row.get("no") or row.get("ref") or "").strip()
    # "oices" — the tail of "invoices" caught by a loose capture.
    if ref and (len(ref) < 4 or ref.lower() in ("oices", "voice", "nvoice", "oice")):
        return False
    bank = str(row.get("bank") or "")
    if bank and (len(bank) > 90 or _BAD_BANK.search(bank)):
        return False
    return True


# --------------------------------------------------------------------------
def _fix_noticees(case: dict, found: Found) -> Found:
    """Recover the company-and-directors shape from a collapsed name.

    draft.py already renders Noticee No. 1 / 2 / 3 blocks and says "jointly and
    severally" — but only when noticee_type says Company and directors[] is
    populated. The model path returns the names as one string ("Company; Mr A;
    Mrs B") and no directors, so none of that machinery ever fires and three
    addressees print on a single line. This puts the structure back.
    """
    v = found.values
    blob = "\n".join(x for x in [
        str(v.get("noticee_name") or ""),
        str(case.get("_narrative") or ""),
        *(str(case.get(k) or "") for k in case if str(k).startswith("_raw_")),
    ] if x.strip())
    if not blob.strip():
        return found

    if not str(v.get("noticee_type") or "").strip():
        t = _noticee_type(blob)
        if t:
            v["noticee_type"] = t
            found.evidence.setdefault("noticee_type", "inferred from the names you gave")

    if str(v.get("noticee_type") or "").startswith(("Company","Partnership")) and not v.get("directors"):
        dirs = _directors(blob, str(v.get("noticee_address") or ""))
        if dirs:
            v["directors"] = dirs
            found.evidence.setdefault("directors", f"{len(dirs)} director(s) named alongside the company")

    # With the directors held separately, noticee_name is the company alone.
    name = str(v.get("noticee_name") or "")
    if v.get("directors") and (";" in name or "\n" in name):
        first = re.split(r"[;\n]", name)[0].strip(" ,")
        taken = {str(d.get("name", "")).lower() for d in v["directors"]}
        if first and first.lower() not in taken:
            v["noticee_name"] = first

    # "Noticee No. 1:" is a label in the answer box, not part of anyone's name,
    # and a director's address must not swallow the rest of the list.
    # "Noticee No. 1: M/s Deccan Auto Tyres, a partnership firm registered
    # under..." — the address parser splits on the first comma and leaves the
    # descriptor clause as the name. Recover the actual name from the label.
    m = re.search(r"noticee\s*no\.?\s*1\s*[:.\-–]\s*([^,\n]+)", blob, re.I)
    if m:
        real = m.group(1).strip(" ,;")
        cur = str(v.get("noticee_name") or "")
        looks_descriptive = bool(re.match(r"^(a|an|the)\s|^(partnership|company|firm|sole)\b", cur, re.I))
        if real and (not cur or looks_descriptive):
            v["noticee_name"] = real
            found.evidence["noticee_name"] = "named after the Noticee No. 1 label"

    def _clean_addr(a: str) -> str:
        """The splitter can leave "1932, principal place of business at ..." —
        the tail of "Indian Partnership Act, 1932" plus a connective phrase."""
        a = str(a or "").strip(" ,;")
        a = re.sub(r"^\d{4}\s*,\s*", "", a)                       # stray year
        a = re.sub(r"^(?:having\s+(?:its|their)\s+)?"
                   r"(?:principal\s+place\s+of\s+business|registered\s+office|"
                   r"place\s+of\s+business|office)\s+(?:at\s+)?", "", a, flags=re.I)
        return a.strip(" ,;")

    lbl = re.compile(r"^\s*noticee\s*no\.?\s*\d+\s*[:.\-–]?\s*", re.I)
    cut = re.compile(r"\s*noticee\s*no\.?\s*\d+.*$", re.I | re.S)
    if v.get("noticee_name"):
        v["noticee_name"] = lbl.sub("", str(v["noticee_name"])).strip(" ,;")
    if v.get("noticee_address"):
        v["noticee_address"] = _clean_addr(cut.sub("", str(v["noticee_address"])))
    for d in v.get("directors") or []:
        d["name"] = lbl.sub("", str(d.get("name", ""))).strip(" ,;")
        addr = _clean_addr(cut.sub("", str(d.get("address", ""))))
        if not addr or re.search(r"same address", addr, re.I):
            addr = str(v.get("noticee_address") or "")
        d["address"] = addr
    return found


def _filter_from_docs(docs, party: str, key: str):
    """Filter the attached ledger to one party, independently of everything else.

    The substitution used to depend on the deterministic reader having produced
    rows. When that came back empty — no party column found, a name it could not
    match — there was no floor, the model's whole-ledger answer stood, and the
    user was stuck behind a blocker with no way forward. This goes back to the
    file and does the filtering itself.
    """
    want = _tokens(party)
    if not want or not docs:
        return [], None, ""
    for d in docs:
        if getattr(d, "kind", "") != "tables":
            continue
        for t in getattr(d, "tables", []) or []:
            rows_ = t["rows"]
            hi = _header_row(rows_)
            header = [str(c).strip() for c in rows_[hi]]
            body = [r for r in rows_[hi + 1:] if any(str(c).strip() for c in r)]
            if not body:
                continue
            cols = _sniff(header, body)
            if cols["party"] < 0 or cols["amt"] < 0:
                continue
            hits = [r for r in body
                    if any(w in re.sub(r"[^a-z0-9]+", " ", str(r[cols['party']]).lower())
                           for w in want)]
            if not hits or len(hits) == len(body):
                continue
            out_rows, total = [], 0.0
            for r in hits:
                amt = to_float(r[cols["amt"]]) if cols["amt"] < len(r) else None
                total += amt or 0.0
                row = {"amt": str(int(amt)) if amt is not None and amt == int(amt) else str(amt or "")}
                if cols["ref"] >= 0 and cols["ref"] < len(r):
                    row["ref"] = str(r[cols["ref"]]).strip()
                if cols["date"] >= 0 and cols["date"] < len(r):
                    row["date"] = iso(r[cols["date"]]) or ""
                out_rows.append(row)
            col_name = str(header[cols["amt"]]).strip() or f"column {cols['amt'] + 1}"
            ev = (f"{d.name}, sheet “{t['sheet']}”: {len(out_rows)} row(s) matching “{party}”, "
                  f"summed on “{col_name}”")
            return out_rows, round(total, 2), ev
    return [], None, ""


def _rows_total(rows_) -> float:
    t = 0.0
    for r in rows_ or []:
        if not isinstance(r, dict):
            continue
        v = to_float(r.get("amt") if r.get("amt") not in (None, "") else r.get("amount"))
        t += v or 0.0
    return round(t, 2)


def _consistent(vals: dict, key: str) -> bool:
    """Does the demanded total equal the sum of the rows the notice will list?"""
    rows_ = vals.get(key) or []
    amt = to_float(vals.get("amount"))
    if not rows_ or amt is None:
        return False
    return abs(_rows_total(rows_) - round(amt, 2)) <= 1


def _prefer_filtered_rows(base: Found, merged: Found, case: dict, docs=None, kind: str = "") -> Found:
    """Keep the deterministic filtered read when the merged one does not add up.

    Two ways this goes wrong. The model returns the whole ledger, or — worse,
    because it looks plausible — it returns a handful of rows while the total
    still comes from somewhere else entirely. Either way the rows and the figure
    disagree, and a demand whose total does not match the invoices listed under
    it is indefensible. The deterministic reader has already filtered on the
    party column and summed exactly the rows it kept, so where it is internally
    consistent and the merge is not, it is put back as a pair.
    """
    # Only the one table field this notice kind actually uses — matching
    # deterministic()'s own table_key. Checking the other field too (as this
    # used to) meant a "missing" floor for "soa" also stuffed identical rows
    # into "invoices" (or vice versa) on notice kinds that never asked for it.
    table_key = "soa" if kind == "recovery" else ("prices" if kind == "price" else "invoices")
    for key in (table_key,):
        m_rows = merged.values.get(key) or []
        b_rows = base.values.get(key) or []
        b_vals = base.values
        b_ev = base.evidence
        if not b_rows:
            # No floor from the deterministic pass — go back to the file itself.
            # The name may only exist because the model just read it out of an
            # attached document (e.g. a covering letter) rather than a typed
            # answer, so check what the merge has found so far before falling
            # back to the raw case dict.
            known = str(merged.values.get("noticee_name") or merged.values.get("client_name")
                        or case.get("noticee_name") or case.get("client_name") or "")
            f_rows, f_total, f_ev = _filter_from_docs(docs or [], known, key)
            if f_rows and f_total is not None:
                b_rows = f_rows
                b_vals = {key: f_rows, "amount": f_total}
                b_ev = {key: f_ev, "amount": f_ev}
        if not isinstance(m_rows, list) or not b_rows:
            continue

        whole_ledger = len(m_rows) > 40 and len(b_rows) * 3 < len(m_rows)
        mismatch = bool(m_rows) and not _consistent(merged.values, key)
        # The model may simply not have returned this field at all — e.g. it left
        # the ledger to the table reader, and that reader had no name to filter on
        # until this same merge established one. That is not a "bad answer" to
        # repair, it is a missing one to fill, and the floor is exactly what fills it.
        missing = not m_rows and bool(b_rows)
        if not (whole_ledger or mismatch or missing):
            continue
        if not _consistent(b_vals, key):
            continue                      # the floor is no better — leave the blocker

        old_amt = to_float(merged.values.get("amount")) or 0
        merged.values[key] = b_rows
        merged.values["amount"] = b_vals["amount"]
        for k in (key, "amount"):
            if b_ev.get(k):
                merged.evidence[k] = b_ev[k]
        if whole_ledger:
            why = (f"the model returned {len(m_rows)} rows — the whole ledger rather than "
                   f"{case.get('noticee_name') or 'this counterparty'}'s rows")
        elif mismatch:
            why = (f"the model's {len(m_rows)} row(s) totalled "
                   f"INR {fmt_amount(_rows_total(m_rows))} against a demand of "
                   f"INR {fmt_amount(old_amt)}, which do not agree")
        else:
            why = "no rows had been read for it yet"
        merged.notes.append(
            f"Statement of account: {why}. The filtered reading of {len(b_rows)} row(s) totalling "
            f"INR {fmt_amount(b_vals['amount'])} was used instead, so the figure demanded is the "
            f"sum of the invoices the notice lists.")
    return merged


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

    ft_vals, ft_ev = from_text(kind, case)
    nv_vals, nv_ev, nv_notes = narrative(kind, story) if story else ({}, {}, [])

    # The document reader filters a ledger down to this counterparty — so it has
    # to know who that is BEFORE it reads. When the name was only typed into the
    # answer box, reading first meant no filter and a whole-file total.
    seed = dict(case)
    for src in (ft_vals, nv_vals):
        for k in ("noticee_name", "firm_name", "client_name"):
            if not str(seed.get(k) or "").strip() and str(src.get(k) or "").strip():
                seed[k] = src[k]
    base = deterministic(kind, seed, docs)

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
        return _fix_noticees(case, with_typed(base))

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
            if not _plausible(k, v):
                merged.notes.append(
                    f"The model's value for “{k}” looked malformed and was discarded; the reading "
                    f"taken directly from your input was kept instead.")
                continue
            merged.values[k] = v                      # the model wins over the regex floor
            if got.evidence.get(k):
                merged.evidence[k] = got.evidence[k]
        merged.missing += [m for m in got.missing if m not in merged.missing]
        merged.notes += [n for n in got.notes if n not in merged.notes]
    return _fix_noticees(case, with_typed(_prefer_filtered_rows(base, merged, case, docs, kind)))
