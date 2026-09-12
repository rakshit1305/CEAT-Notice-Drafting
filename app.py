"""CEAT Notice Drafting Console — Streamlit.

State discipline, since this is where Streamlit apps usually come apart:
  * every mutable thing lives in one dict, st.session_state.case[<type>]
  * every widget has an explicit, stable key
  * widget values are read back from st.session_state, never assigned into it
    after the widget exists
  * uploads are parsed once and cached by file digest, so a rerun does not
    re-read a 5 MB workbook
  * nothing is drafted until the button is pressed and the checks pass
"""
from __future__ import annotations
import copy
import datetime as dt
import html as _h
import re as _re

import streamlit as st

from core import draft as DRAFT
from core import models as MODELS
from core import skill_loader as SK
from core.analyse import analyse
from core.config import MAX_UPLOAD_MB
from core.extract import extract
from core.schema import (CRITICAL, LABELS, TABLE_COLS, TYPES, is_filled, label, questions)
from core.validate import missing_critical, missing_optional, validate
from core.words import fmt_amount, fmt_date

st.set_page_config(page_title="CEAT Notice Drafting Console",
                   page_icon="⚖️", layout="wide",
                   initial_sidebar_state="expanded")

# ---------------------------------------------------------------- style ----
# Glass over a deep gradient ground. One exception, deliberate: the notice
# itself is opaque paper. A legal document rendered on frosted glass is a
# document nobody can read.
CSS = """
<style>
:root{
  --ink:#E9EDF8; --dim:#A7B2CC; --faint:#7E89A6;
  --glass:rgba(255,255,255,.055);
  --glass-2:rgba(255,255,255,.085);
  --edge:rgba(255,255,255,.13);
  --edge-2:rgba(255,255,255,.22);
  --brass:#D8B14A; --brass-2:#F0D98A;
  --crit:#FF9587; --warn:#F6CE74; --ok:#7FE3B6; --info:#8FB8FF;
  --paper:#FAF7EF; --paper-ink:#22252B;
  --serif:Georgia,'Iowan Old Style','Palatino Linotype','Times New Roman',serif;
  --sans:system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
}

/* ---- the ground ------------------------------------------------------- */
.stApp{
  background:
    radial-gradient(1200px 780px at 10% -10%, rgba(86,120,255,.26), transparent 58%),
    radial-gradient(1000px 640px at 92% 0%,  rgba(216,177,74,.17), transparent 56%),
    radial-gradient(900px 900px at 62% 116%, rgba(129,71,214,.24), transparent 60%),
    linear-gradient(165deg,#060A14 0%,#0B1224 46%,#080D1C 100%);
  background-attachment:fixed;
}
.stApp, .stApp p, .stApp li, .stApp label{font-family:var(--sans);}
h1,h2,h3,h4{font-family:var(--serif) !important;
  letter-spacing:-.005em; color:var(--ink) !important;}
/* Streamlit draws its icons as ligature text — they must keep their own font */
span[data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons,
span[class*="material-symbols"]{font-family:'Material Symbols Rounded',
  'Material Symbols Outlined','Material Icons' !important;}
.block-container{padding-top:3.4rem; padding-bottom:3rem; max-width:1560px;}
hr{border-color:var(--edge) !important;}
/* Streamlit's own top bar floats over the page — let the ground show through
   it, and keep the hero clear of it. */
header[data-testid="stHeader"]{background:transparent !important;}
div[data-testid="stToolbar"]{right:.6rem;}

/* ---- glass cards ------------------------------------------------------ */
/* Containers created with key="glass…" — Streamlit renders that key as an
   st-key-* class, which is the only stable hook it gives for one container. */
div[class*="st-key-glass"], div[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--glass);
  backdrop-filter:blur(22px) saturate(160%);
  -webkit-backdrop-filter:blur(22px) saturate(160%);
  border:1px solid var(--edge) !important;
  border-radius:16px !important;
  box-shadow:0 12px 38px rgba(2,6,16,.46), inset 0 1px 0 rgba(255,255,255,.10);
  padding:16px 18px;
}
@supports not ((backdrop-filter:blur(2px)) or (-webkit-backdrop-filter:blur(2px))){
  div[class*="st-key-glass"], div[data-testid="stVerticalBlockBorderWrapper"]{
    background:rgba(19,27,48,.92);
  }
  section[data-testid="stSidebar"]{background:#0C1428 !important;}
}

/* ---- the output column follows you down the questions ----------------- */
/* the column must stretch to the row's height or sticky has nowhere to travel */
div[data-testid="stColumn"]{align-self:stretch;}
div[data-testid="stColumn"]:last-of-type > div[data-testid="stVerticalBlock"]{
  position:sticky; top:14px;
  max-height:calc(100vh - 46px); overflow-y:auto; overflow-x:hidden;
  padding-right:6px;
}
@media (max-width:1200px){
  div[data-testid="stColumn"]:last-of-type > div[data-testid="stVerticalBlock"]{
    position:static; max-height:none; overflow:visible;
  }
}

/* ---- sidebar ---------------------------------------------------------- */
section[data-testid="stSidebar"]{
  background:rgba(8,13,26,.62);
  backdrop-filter:blur(26px) saturate(170%);
  -webkit-backdrop-filter:blur(26px) saturate(170%);
  border-right:1px solid var(--edge);
}
section[data-testid="stSidebar"] *{color:var(--ink);}
section[data-testid="stSidebar"] .stRadio label{font-size:.86rem;}

/* ---- hero ------------------------------------------------------------- */
.hero{display:flex; align-items:flex-start; justify-content:space-between;
  gap:24px; flex-wrap:wrap; margin-bottom:.3rem;}
.hero h1{font-size:1.86rem; margin:0 0 .25rem;}
.hero .sub{color:var(--dim); font-size:.88rem; max-width:60ch; line-height:1.6;}
.tier{display:inline-block; padding:4px 12px; border-radius:999px; font-size:.7rem;
  font-weight:600; letter-spacing:.06em; text-transform:uppercase; margin-bottom:.5rem;
  border:1px solid var(--edge-2);}
.tier.ok{background:rgba(127,227,182,.13); color:var(--ok);}
.tier.ns{background:rgba(246,206,116,.13); color:var(--warn);}

/* ---- readiness meter -------------------------------------------------- */
.meter{min-width:290px; background:var(--glass-2); border:1px solid var(--edge);
  border-radius:14px; padding:14px 16px;
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);}
.meter .top{display:flex; justify-content:space-between; align-items:baseline;
  font-size:.74rem; color:var(--dim); letter-spacing:.04em; text-transform:uppercase;}
.meter .big{font-family:var(--serif); font-size:1.5rem; color:var(--ink);}
.bar{height:7px; border-radius:99px; background:rgba(255,255,255,.09);
  overflow:hidden; margin:9px 0 8px;}
.bar > i{display:block; height:100%; border-radius:99px;
  background:linear-gradient(90deg,var(--brass),var(--brass-2));
  box-shadow:0 0 16px rgba(216,177,74,.5);}
.meter .legend{font-size:.74rem; color:var(--faint); line-height:1.6;}

/* ---- question cards --------------------------------------------------- */
.q-ask{font-family:var(--serif); font-size:1.03rem; font-weight:600;
  margin:.1rem 0 .3rem; line-height:1.45; color:var(--ink);}
.q-hint{font-size:.78rem; color:var(--faint); margin-bottom:.5rem; line-height:1.55;}
.dot{display:inline-block; width:7px; height:7px; border-radius:99px; margin-right:7px;
  vertical-align:middle;}
.dot.done{background:var(--ok); box-shadow:0 0 9px rgba(127,227,182,.65);}
.dot.part{background:var(--warn); box-shadow:0 0 9px rgba(246,206,116,.6);}
.dot.open{background:rgba(255,255,255,.22);}
.ev{font-size:.74rem; color:var(--faint); font-family:ui-monospace,'SF Mono',monospace;
  line-height:1.6;}

/* ---- pills ------------------------------------------------------------ */
.pill{display:inline-block; padding:3px 11px; border-radius:999px; font-size:.71rem;
  font-weight:600; margin:0 6px 6px 0; border:1px solid transparent; letter-spacing:.02em;}
.pill.crit{background:rgba(255,149,135,.14); color:var(--crit); border-color:rgba(255,149,135,.3);}
.pill.warn{background:rgba(246,206,116,.13); color:var(--warn); border-color:rgba(246,206,116,.28);}
.pill.ok  {background:rgba(127,227,182,.13); color:var(--ok);   border-color:rgba(127,227,182,.28);}
.pill.info{background:rgba(143,184,255,.13); color:var(--info); border-color:rgba(143,184,255,.28);}

/* ---- the notice: paper, not glass ------------------------------------- */
.sheet{background:var(--paper); color:var(--paper-ink);
  border:1px solid #E0D9C6; border-left:3px solid var(--brass);
  padding:34px 40px; border-radius:6px;
  font-family:var(--serif); font-size:.94rem; line-height:1.74;
  white-space:pre-wrap;
  box-shadow:0 20px 52px rgba(2,6,16,.55);}
.lh{text-align:center; border-bottom:2px solid var(--brass);
  padding-bottom:11px; margin-bottom:19px;}
.lh b{font-size:1.24rem; letter-spacing:.02em;}
.blank{background:#FBEFD8; color:#8A5A06; border-bottom:1px solid #C49A3C;
  padding:0 4px; border-radius:3px;
  font-family:ui-monospace,monospace; font-size:.85em;}

/* ---- rule cards ------------------------------------------------------- */
.rule{background:var(--glass); border:1px solid var(--edge); border-radius:13px;
  padding:13px 16px 13px 52px; margin-bottom:9px; position:relative;
  backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);}
.rule b{color:var(--brass-2); font-family:var(--serif); font-size:.98rem;}
.rule p{margin:.25rem 0 0; font-size:.83rem; color:var(--dim); line-height:1.62;}
.rule .n{position:absolute; left:15px; top:13px; width:25px; height:25px;
  border-radius:8px; display:flex; align-items:center; justify-content:center;
  background:linear-gradient(135deg,rgba(216,177,74,.9),rgba(240,217,138,.75));
  color:#201804; font-weight:700; font-size:.78rem;
  font-family:var(--sans);}

/* ---- history ---------------------------------------------------------- */
.hist{background:var(--glass); border:1px solid var(--edge); border-radius:12px;
  padding:11px 14px; margin-bottom:8px;}
.hist .t{font-size:.72rem; color:var(--faint); font-family:ui-monospace,monospace;}
.hist .s{font-size:.85rem; color:var(--ink); line-height:1.5; margin-top:2px;}

/* ---- inputs ----------------------------------------------------------- */
.stTextInput input, .stTextArea textarea, .stDateInput input,
div[data-baseweb="select"] > div, div[data-baseweb="input"]{
  background:rgba(255,255,255,.05) !important;
  border:1px solid var(--edge) !important;
  color:var(--ink) !important; border-radius:11px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus{
  border-color:rgba(216,177,74,.62) !important;
  box-shadow:0 0 0 3px rgba(216,177,74,.14) !important;
}
.stTextArea textarea::placeholder, .stTextInput input::placeholder{
  color:rgba(167,178,204,.5) !important;
}
div[data-testid="stFileUploaderDropzone"]{
  background:rgba(255,255,255,.035) !important;
  border:1px dashed rgba(255,255,255,.20) !important;
  border-radius:12px; padding:.55rem 1rem; min-height:0;
}
div[data-testid="stFileUploaderDropzone"]:hover{
  border-color:rgba(216,177,74,.5) !important; background:rgba(216,177,74,.05) !important;
}

/* radios rendered as pills */
.stRadio [role="radiogroup"]{gap:7px; flex-wrap:wrap;}
.stRadio [role="radiogroup"] > label{
  background:rgba(255,255,255,.05); border:1px solid var(--edge);
  border-radius:999px; padding:5px 14px; margin:0;
  transition:border-color .14s, background .14s;
}
.stRadio [role="radiogroup"] > label:hover{border-color:var(--edge-2);}
.stRadio [role="radiogroup"] > label:has(input:checked){
  background:rgba(216,177,74,.16); border-color:rgba(216,177,74,.55);
}
.stRadio [role="radiogroup"] > label > div:first-child{display:none;}

/* buttons */
.stButton > button{
  background:rgba(255,255,255,.06); border:1px solid var(--edge);
  color:var(--ink); border-radius:11px; font-weight:500;
  transition:border-color .14s, background .14s, transform .08s;
}
.stButton > button:hover{border-color:var(--edge-2); background:rgba(255,255,255,.10);}
.stButton > button:active{transform:translateY(1px);}
.stButton > button[kind="primary"]{
  background:linear-gradient(135deg,rgba(216,177,74,.95),rgba(240,217,138,.88));
  color:#1C1505 !important; border:1px solid rgba(255,255,255,.3); font-weight:650;
  box-shadow:0 8px 26px rgba(216,177,74,.30);
}
.stButton > button[kind="primary"]:hover{box-shadow:0 10px 32px rgba(216,177,74,.44);}
.stDownloadButton > button{
  background:rgba(255,255,255,.06); border:1px solid var(--edge);
  color:var(--ink); border-radius:11px;
}
.stDownloadButton > button:hover{border-color:rgba(216,177,74,.5);}

/* tabs — Streamlit renders each tab as a div[role=tab], not a button */
.stTabs [role="tablist"]{
  gap:5px; border-bottom:1px solid var(--edge); flex-wrap:wrap;
}
.stTabs [role="tab"]{
  background:rgba(255,255,255,.04); border:1px solid var(--edge);
  border-bottom:none; border-radius:11px 11px 0 0; padding:6px 11px;
  color:var(--dim) !important; font-size:.78rem; white-space:nowrap;
  transition:background .14s, color .14s;
}
.stTabs [role="tab"]:hover{background:rgba(255,255,255,.08); color:var(--ink) !important;}
.stTabs [role="tab"][aria-selected="true"]{
  background:var(--glass-2) !important; color:var(--ink) !important;
  border-color:var(--edge-2); box-shadow:inset 0 2px 0 var(--brass);
}
.stTabs [role="tab"] p{font-size:.78rem !important; margin:0;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none;}
.stTabs [role="tabpanel"]{padding-top:14px;}

/* expanders, metrics, tables, alerts */
div[data-testid="stExpander"] details{
  background:var(--glass); border:1px solid var(--edge) !important; border-radius:13px;
  backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
}
div[data-testid="stExpander"] summary{color:var(--ink); font-size:.86rem;}
div[data-testid="stMetricValue"]{font-family:var(--serif);}
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"]{
  border:1px solid var(--edge); border-radius:12px; overflow:hidden;
}
div[data-testid="stNotification"], .stAlert{
  background:var(--glass-2) !important; border:1px solid var(--edge) !important;
  border-radius:12px; backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
}
.stCode, pre{border-radius:12px !important;}
::-webkit-scrollbar{width:10px; height:10px;}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14); border-radius:99px;}
::-webkit-scrollbar-track{background:transparent;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------- state ----
def default_case(kind: str) -> dict:
    name, desig = SK.signatory_default()
    c: dict = {"notice_date": dt.date.today().isoformat(),
               "mode": "BY SPEED POST",
               "signatory_name": name, "signatory_desig": desig,
               "authority_confirmed": False, "prior": "No"}
    if kind == "recovery":
        c["interest"] = "8"
    if kind == "consumer":
        c["reply_date"] = dt.date.today().isoformat()
        c.update(blk_a=True, blk_b=True, blk_c=True)
    return c


def boot():
    ss = st.session_state
    ss.setdefault("kind", "s138")
    ss.setdefault("case", {})                  # kind -> dict of field values
    ss.setdefault("docs", {})                  # kind -> {digest: Doc}
    ss.setdefault("drafted", {})               # kind -> bool
    ss.setdefault("report", {})                # kind -> analysis report
    ss.setdefault("parsed", {})                # digest -> Doc  (parse-once cache)
    ss.setdefault("tver", {})                  # "kind:table" -> int, bumps the editor's key
    ss.setdefault("history", [])               # drafts produced this session
    ss.setdefault("qfilter", "Everything")
    for k in TYPES:
        ss.case.setdefault(k, default_case(k))
        ss.docs.setdefault(k, {})
        ss.drafted.setdefault(k, False)


boot()
KIND = st.session_state.kind
CASE = st.session_state.case[KIND]
DOCS = st.session_state.docs[KIND]
QS = questions(KIND)


def touch():
    """Any edit invalidates the draft — it must be re-checked before it reappears."""
    st.session_state.drafted[KIND] = False


def _key(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()[:16]


def party_of(kind: str, case: dict) -> str:
    v = case.get("client_name") if kind == "consumer" else case.get("noticee_name")
    return str(v or "unnamed party")


def push_history(kind: str, case: dict, rep) -> None:
    h = st.session_state.history
    snap = copy.deepcopy(case)
    if h and h[0]["kind"] == kind and h[0]["case"] == snap:
        return                                     # same draft, re-checked
    h.insert(0, dict(
        when=dt.datetime.now(),
        kind=kind,
        party=party_of(kind, case),
        subject=DRAFT.build(kind, case)[0],
        case=snap,
        flags=len(rep.flags),
        open_items=list(rep.open_items),
    ))
    del h[20:]


# ------------------------------------------------------------ readiness ----
def readiness():
    """Recomputed rather than cached: the meter must reflect the current edit,
    not the state the script started this run with."""
    crit_keys = set(CRITICAL.get(KIND, []))
    rows = []
    for q in QS:
        keys = [k for k in q.fills if not k.startswith("_")]
        filled = [k for k in keys if is_filled(CASE, k)]
        state = "done" if keys and len(filled) == len(keys) else ("part" if filled else "open")
        rows.append(dict(q=q, keys=keys, filled=filled,
                         crit=bool(crit_keys & set(keys)), state=state))
    answered = sum(1 for r in rows if r["state"] == "done")
    return rows, answered, int(round(100 * answered / max(len(rows), 1)))


ROWS, ANSWERED, PCT = readiness()


# -------------------------------------------------------------- sidebar ----
with st.sidebar:
    st.markdown("### CEAT Legal")
    st.caption("Notice Drafting Console")

    approved = [k for k, v in TYPES.items() if v["tier"] == "approved"]
    nonstd = [k for k, v in TYPES.items() if v["tier"] == "ns"]
    order = approved + nonstd
    choice = st.radio("Notice type", order, index=order.index(KIND),
                      format_func=lambda k: ("🟢 " if TYPES[k]["tier"] == "approved" else "🟡 ")
                      + TYPES[k]["name"],
                      key="kind_radio", label_visibility="collapsed")
    if choice != KIND:
        st.session_state.kind = choice
        st.rerun()
    st.caption("🟢 approved — CEAT samples  ·  🟡 non-standard — no sample yet")

    st.divider()
    S = MODELS.status()
    if not S["key"]:
        st.warning("No model key — deterministic reading only", icon="⚠️")
        st.caption("Set `GROQ_API_KEY` in `.env` (beside `app.py`) to have documents reasoned "
                   "over, including cheque photos and scans.")
    elif not S["reachable"]:
        st.error(f"{S['provider']} key set, but the model list could not be fetched", icon="🔌")
        st.caption(f"`{S['error'] or 'no detail'}` — falling back to the configured IDs. "
                   "Analysis will still try; documents are read deterministically either way.")
        st.caption(f"Running: `{S.get('versions', '')}`")
    else:
        st.success(f"{S['provider']} connected", icon="✅")
        st.caption(f"text · `{S['text']}`  \nvision · `{S['vision']}` · up to {S['images']} images")
        if "fell back" in S["text_why"] or "fell back" in S["vision_why"]:
            st.caption("⚠️ A model named in `.env` is not available on this account; "
                       "the best available one is being used instead.")
    if st.button("Re-check models", use_container_width=True, key="recheck"):
        MODELS.available(force=True)
        st.rerun()

    st.divider()
    if st.button("Clear this case", use_container_width=True, key="clear"):
        st.session_state.case[KIND] = default_case(KIND)
        st.session_state.docs[KIND] = {}
        st.session_state.drafted[KIND] = False
        st.session_state.report.pop(KIND, None)
        st.rerun()
    st.caption("Case details stay in this session only. Clear it when the matter is done — "
               "notices carry personal data.")


# ------------------------------------------------------------- widgets ----
def uploader(q):
    up = st.file_uploader(
        "Alternative: attach the supporting document",
        type=["csv", "xlsx", "xls", "xlsm", "pdf", "docx", "txt",
              "jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key=f"up_{KIND}_{q.id}",
        label_visibility="collapsed",
        help="Excel · CSV · PDF · Word · JPG · PNG. Read when you press the analyse button.",
    )
    for f in up or []:
        if f.size > MAX_UPLOAD_MB * 1024 * 1024:
            st.error(f"{f.name} is over {MAX_UPLOAD_MB} MB.")
            continue
        data = f.getvalue()
        doc = st.session_state.parsed.get(_key(data))
        if doc is None:
            doc = extract(f.name, data)
            st.session_state.parsed[_key(data)] = doc
        if doc.digest not in DOCS:
            DOCS[doc.digest] = doc
            touch()


def ask(row):
    q, state = row["q"], row["state"]
    st.markdown(f'<div class="q-ask"><span class="dot {state}"></span>{_h.escape(q.ask)}</div>',
                unsafe_allow_html=True)
    if q.hint:
        st.markdown(f'<div class="q-hint">{_h.escape(q.hint)}</div>', unsafe_allow_html=True)
    if q.attach:
        uploader(q)

    wk = f"w_{KIND}_{q.id}"

    if q.kind in ("choice", "chips"):
        vals = [o[0] for o in q.options]
        cur = CASE.get(q.fills[0])
        idx = vals.index(cur) if cur in vals else None
        # Analysis may have supplied this after the widget first rendered empty.
        # Seeding the key *before* the widget is built is the one safe moment.
        if cur in vals and st.session_state.get(wk) is None:
            st.session_state[wk] = cur
        picked = st.radio("", vals, index=idx, key=wk, horizontal=True,
                          format_func=lambda v: next(o[1] for o in q.options if o[0] == v),
                          label_visibility="collapsed")
        # An unselected radio reports None. Writing that back would erase a value
        # analysis had just supplied, and silently un-draft the notice.
        if picked is not None and picked != CASE.get(q.fills[0]):
            CASE[q.fills[0]] = picked
            touch()

    elif q.kind == "date":
        cur = CASE.get(q.fills[0])
        d = dt.date.fromisoformat(cur) if cur else None
        got = st.date_input("", value=d, key=wk, format="DD.MM.YYYY",
                            label_visibility="collapsed")
        if got and got.isoformat() != CASE.get(q.fills[0]):
            CASE[q.fills[0]] = got.isoformat()
            touch()

    elif q.kind == "table":
        cols = TABLE_COLS[q.table]
        rows = CASE.get(q.table) or []
        import pandas as pd
        df = pd.DataFrame(rows if rows else [{c[0]: "" for c in cols}])
        df = df.reindex(columns=[c[0] for c in cols], fill_value="")
        # When analysis replaces the rows, the editor must be rebuilt rather than
        # replay its old edits onto different data.
        wk = f"{wk}_v{st.session_state.tver.get(f'{KIND}:{q.table}', 0)}"
        edited = st.data_editor(df, key=wk, num_rows="dynamic",
                                use_container_width=True, hide_index=True,
                                column_config={c[0]: st.column_config.TextColumn(c[1])
                                               for c in cols})
        new = [r for r in edited.fillna("").to_dict("records")
               if any(str(v).strip() for v in r.values())]
        if new != rows:
            CASE[q.table] = new
            touch()

    elif q.kind == "text":
        got = st.text_input("", value=CASE.get(q.fills[0], "") or "", key=wk,
                            placeholder=q.ph, label_visibility="collapsed")
        if got != (CASE.get(q.fills[0]) or ""):
            CASE[q.fills[0]] = got
            touch()

    else:
        raw_key = f"_raw_{q.id}"
        got = st.text_area("", value=CASE.get(raw_key, "") or "", key=wk, height=q.rows * 34,
                           placeholder=q.ph, label_visibility="collapsed")
        if got != (CASE.get(raw_key) or ""):
            CASE[raw_key] = got
            # A single-fill box writes straight through — unless the field is a
            # table, in which case the text is only raw material for analysis.
            if len(q.fills) == 1 and q.fills[0] not in TABLE_COLS:
                CASE[q.fills[0]] = got
            touch()

    bits = []
    for k in [k for k in row["keys"] if is_filled(CASE, k)]:
        v = CASE[k]
        if isinstance(v, list):
            bits.append(f"{label(k)}: {len(v)} rows")
        else:
            s = str(v)
            if k.endswith("_date") or k in ("notice_date", "reply_date"):
                s = fmt_date(v)
            elif k in ("amount", "dues", "principal", "tax"):
                s = "INR " + fmt_amount(v)
            bits.append(f"{label(k)}: {s[:44]}")
    if bits:
        st.markdown(f'<div class="ev">held · {_h.escape("  ·  ".join(bits))}</div>',
                    unsafe_allow_html=True)


def sheet_html(text: str) -> str:
    lh = SK.letterhead()
    body = (text.split(lh["meta"], 1)[-1]).strip()
    shown = _re.sub(r"\[●([^\]]*)\]", r"<span class='blank'>[●\1]</span>", _h.escape(body))
    return (f"<div class='sheet'><div class='lh'><b>{lh['name']}</b><br>"
            f"<span style='font-size:.8rem'>{lh['address'].replace(chr(10), '<br>')}</span><br>"
            f"<span style='font-size:.72rem;font-family:ui-monospace,monospace'>{lh['meta']}</span>"
            f"</div>{shown}</div>")


# ---------------------------------------------------------------- hero ----
# Filled in after the question column has run, so the meter shows the edit the
# user just made rather than the state this run started with.
HERO = st.empty()


def paint_hero(rows, answered, pct, crit_open):
    tier = TYPES[KIND]["tier"]
    ref = SK.notice_ref(KIND)
    legend = (f"{len(crit_open)} still needed before it can be drafted"
              if crit_open else "nothing essential outstanding")
    HERO.markdown(
        f"""<div class="hero">
          <div>
            <span class="tier {'ok' if tier == 'approved' else 'ns'}">
              {'Approved — CEAT sample wording' if tier == 'approved'
                 else 'Non-standard — no CEAT sample'}
            </span>
            <h1>{_h.escape(TYPES[KIND]['name'])}</h1>
            <div class="sub">{_h.escape(ref.when_to_use or TYPES[KIND]['blurb'])}</div>
          </div>
          <div class="meter">
            <div class="top"><span>Readiness</span><span class="big">{pct}%</span></div>
            <div class="bar"><i style="width:{pct}%"></i></div>
            <div class="legend">{answered} of {len(rows)} questions answered ·
              {len(DOCS)} document{'' if len(DOCS) == 1 else 's'} attached{
                ' · account given' if str(CASE.get('_narrative') or '').strip() else ''}<br>
              {_h.escape(legend)}</div>
          </div>
        </div>""",
        unsafe_allow_html=True)


paint_hero(ROWS, ANSWERED, PCT, missing_critical(KIND, CASE))
st.write("")

left, right = st.columns([1.04, 1], gap="large")

# ----------------------------------------------------------- the questions --
with left:
    with st.container(border=True, key=f"glass_story_{KIND}"):
        st.markdown('<div class="q-ask">Or just tell it the whole matter, in your own words'
                    '</div>', unsafe_allow_html=True)
        st.markdown('<div class="q-hint">Brief it the way you would brief a colleague — who, '
                    'what, the cheques or invoices, the dates, what you want demanded. It reads '
                    'this first and fills in the questions below; correct anything it got wrong. '
                    'You can use this, the questions, attachments, or all three.</div>',
                    unsafe_allow_html=True)
        story = st.text_area("", value=CASE.get("_narrative", "") or "",
                             key=f"w_{KIND}_narrative", height=150, label_visibility="collapsed",
                             placeholder="e.g. Our Pune dealer Om Enterprises, proprietor Suresh "
                                         "Patil at 8 Market Yard, gave us three cheques against "
                                         "dealership dues. Cheque no. 220145 dated 02.05.2026 for "
                                         "INR 1,50,000 drawn on Bank of Baroda, Pune, returned "
                                         "06.05.2026 for “Funds Insufficient”, memo dated "
                                         "06.05.2026 …")
        if story != (CASE.get("_narrative") or ""):
            CASE["_narrative"] = story
            touch()
        if story.strip():
            st.markdown(f"<div class='ev'>held · {len(story.split())} words — read when you press "
                        f"the button</div>", unsafe_allow_html=True)

    st.write("")
    f1, f2 = st.columns([2.1, 1])
    with f1:
        st.radio("Show", ["Everything", "Not yet answered", "Essential only"],
                 key="qfilter", horizontal=True, label_visibility="collapsed")
    with f2:
        st.markdown(f"<div class='ev' style='text-align:right;padding-top:8px'>"
                    f"{ANSWERED} done · {len(ROWS) - ANSWERED} open</div>",
                    unsafe_allow_html=True)

    mode = st.session_state.qfilter
    shown = [r for r in ROWS
             if mode == "Everything"
             or (mode == "Not yet answered" and r["state"] != "done")
             or (mode == "Essential only" and r["crit"])]

    if not shown:
        st.success("Nothing left under this filter." if mode != "Everything"
                   else "No questions for this type.", icon="✅")

    for r in shown:
        with st.container(border=True, key=f"glass_q_{KIND}_{r['q'].id}"):
            ask(r)

    st.caption("Nothing here is compulsory. Answer what you know, attach what you have — "
               "anything still open is either asked for below or left as [● …] in the notice.")

    with st.container(border=True, key=f"glass_docs_{KIND}"):
        st.markdown("**Documents attached**")
        if not DOCS:
            st.caption("None yet. Attach against any question above — Excel, CSV, PDF, Word, "
                       "JPG or PNG. They are read together, not one at a time.")
        for dg, d in list(DOCS.items()):
            c1, c2 = st.columns([5, 1])
            icon = {"tables": "📊", "text": "📄", "image": "🖼️", "error": "⚠️"}.get(d.kind, "📄")
            c1.markdown(f"{icon} `{d.name}`" + (f" — {d.note}" if d.note else ""))
            if c2.button("remove", key=f"rm_{KIND}_{dg}"):
                DOCS.pop(dg, None)
                touch()
                st.rerun()
        if DOCS:
            st.caption("Every file listed is carried into the annexure list.")

    st.write("")
    go = st.button("Analyse everything and draft the notice"
                   if not st.session_state.drafted[KIND] else "Re-check and update the notice",
                   type="primary", use_container_width=True, key=f"go_{KIND}")
    st.caption("Nothing is drafted until this is pressed. The console reads your answers and "
               "every attachment together, checks the matter, and drafts only if the notice "
               "can properly be made out.")

# The questions have now run and may have changed the case, so the meter and the
# "still needed" list are recomputed before anything else reads them.
ROWS, ANSWERED, PCT = readiness()
CRIT_OPEN = missing_critical(KIND, CASE)
paint_hero(ROWS, ANSWERED, PCT, CRIT_OPEN)

# ------------------------------------------------------------ the action ---
if go:
    with st.spinner("Reading the documents and checking the matter…"):
        found = analyse(KIND, CASE, list(DOCS.values()))
        applied, evidence = [], {}
        for k, v in (found.values or {}).items():
            if k not in LABELS and k not in TABLE_COLS:
                continue
            if is_filled(CASE, k):            # never overwrite the user
                continue
            if v in (None, "", [], {}):
                continue
            CASE[k] = v
            applied.append(k)
            evidence[k] = found.evidence.get(k, "")
            if k in TABLE_COLS:
                tk = f"{KIND}:{k}"
                st.session_state.tver[tk] = st.session_state.tver.get(tk, 0) + 1
        rep = validate(KIND, CASE, list(DOCS.values()))
        st.session_state.report[KIND] = dict(applied=applied, evidence=evidence,
                                             notes=found.notes, used_model=found.used_model,
                                             rep=rep)
        st.session_state.drafted[KIND] = rep.ok
        if rep.ok:
            push_history(KIND, CASE, rep)
    st.rerun()

# ------------------------------------------------------------- the output --
with right:
    R = st.session_state.report.get(KIND)
    drafted = st.session_state.drafted[KIND]
    rep = R["rep"] if R else None
    n_flag = len(rep.flags) if rep else 0
    n_pass = sum(1 for c in rep.checks if c.state == "pass") if rep else 0
    n_tot = sum(1 for c in rep.checks if c.state != "na") if rep else 0

    tabs = st.tabs(["Draft",
                    f"Review notes{f' ({n_flag})' if n_flag else ''}",
                    f"Checklist{f' ({n_pass}/{n_tot})' if rep else ''}",
                    "All fields",
                    f"History{f' ({len(st.session_state.history)})' if st.session_state.history else ''}",
                    "Rules"])

    # ---- 1. draft ---------------------------------------------------------
    with tabs[0]:
        if R and R["applied"]:
            with st.expander(f"Read from the documents — {len(R['applied'])} field(s) filled",
                             expanded=not drafted):
                for k in R["applied"]:
                    v = CASE.get(k)
                    shown_v = f"{len(v)} rows" if isinstance(v, list) else str(v)[:70]
                    st.markdown(f"**{label(k)}** — {_h.escape(shown_v)}  \n"
                                f"<span class='ev'>{_h.escape(R['evidence'].get(k) or 'from the attachment')}</span>",
                                unsafe_allow_html=True)
                for n in R["notes"]:
                    st.caption(n)

        if not drafted:
            if R is None:
                st.info("**No notice drafted yet.** Answer what you can on the left and attach any "
                        "supporting documents, then press the button. The console reads everything "
                        "together, checks it, and drafts only once it has what this notice must "
                        "assert.", icon="📄")
                if CRIT_OPEN:
                    st.markdown("Still needed for this notice type: "
                                + " ".join(f"<span class='pill warn'>{_h.escape(m)}</span>"
                                           for m in CRIT_OPEN), unsafe_allow_html=True)
            elif not rep.blockers:
                st.info("**The case has changed since it was last checked.** Press the button "
                        "again and the notice will be re-checked and redrafted.", icon="🔄")
            else:
                st.error("**Not drafted — the matter does not check out yet.** Nothing has been "
                         "assumed in place of what is missing.", icon="🚫")
                for b in rep.blockers:
                    st.markdown(f"<span class='pill crit'>blocked</span> {_h.escape(b)}",
                                unsafe_allow_html=True)
                opt = missing_optional(KIND, CASE)
                if opt:
                    st.caption("Separately, these are open and would show as [● …] in the draft — "
                               "they do not block it: " + "; ".join(opt) + ".")
        else:
            specimen = st.toggle("Fill-in specimen", key=f"spec_{KIND}",
                                 help="Marks the file as a specimen not ready to issue.")
            fname = DRAFT.filename(KIND, CASE, specimen)
            text = DRAFT.to_text(KIND, CASE)

            if rep.open_items:
                st.warning("Open and shown as [● …] in the notice, nothing assumed: "
                           + "; ".join(rep.open_items), icon="⚪")

            st.markdown(sheet_html(text), unsafe_allow_html=True)
            st.caption(f"Save as  `{fname}`")

            c1, c2 = st.columns(2)
            c1.download_button("Download .docx", DRAFT.to_docx(KIND, CASE), fname,
                               "application/vnd.openxmlformats-officedocument."
                               "wordprocessingml.document",
                               use_container_width=True, key=f"dl_{KIND}")
            c2.download_button("Download .txt", text, fname.replace(".docx", ".txt"),
                               "text/plain", use_container_width=True, key=f"dlt_{KIND}")
            with st.expander("Plain text — copy it straight out"):
                st.code(text, language=None)

    # ---- 2. review notes --------------------------------------------------
    with tabs[1]:
        if not rep:
            st.caption("Nothing checked yet. Press the button on the left.")
        else:
            st.caption("Chat notes — these never go inside the document.")
            for sev, t in rep.flags:
                cls = {"crit": "crit", "warn": "warn"}.get(sev, "info")
                tag = {"crit": "action", "warn": "verify"}.get(sev, "note")
                st.markdown(f"<span class='pill {cls}'>{tag}</span> {_h.escape(t)}",
                            unsafe_allow_html=True)
            if rep.annexures:
                st.markdown("**Annexures to attach before sending**")
                for a in rep.annexures:
                    st.markdown(f"- {a}")
            st.info(SK.review_banner(), icon="⚖️")

        st.divider()
        nk = f"w_{KIND}_notes"
        note = st.text_area("Your own notes on this matter", value=CASE.get("_notes", "") or "",
                            key=nk, height=120,
                            placeholder="Anything you want to remember about this matter. "
                                        "Kept in this session, never written into the notice.")
        if note != (CASE.get("_notes") or ""):
            CASE["_notes"] = note

    # ---- 3. checklist -----------------------------------------------------
    with tabs[2]:
        if not rep:
            st.caption("Nothing checked yet.")
        else:
            for c in rep.checks:
                mark = {"pass": "✓", "fail": "✗"}.get(c.state, "—")
                cls = {"pass": "ok", "fail": "crit"}.get(c.state, "info")
                st.markdown(f"<span class='pill {cls}'>{mark}</span> {_h.escape(c.text)}",
                            unsafe_allow_html=True)
            st.caption("Wording comes from CEAT's approved templates. Verify provisions against "
                       "India Code or India Kanoon — this app does not fetch live statutes.")

            if rep.skill_checklist:
                st.divider()
                st.markdown("**Mandatory validation checklist (verbatim from the skill)**")
                st.caption("Unlike the checks above, this list is read live from the reference "
                           "file — it always matches SKILL.md, with no code change needed.")
                for item in rep.skill_checklist:
                    st.markdown(f"- {_h.escape(item)}", unsafe_allow_html=True)

    # ---- 4. everything held -----------------------------------------------
    with tabs[3]:
        st.caption("Every field this notice can carry, and what the console holds right now. "
                   "Nothing here is inferred — a blank is a blank.")
        crit_keys = set(CRITICAL.get(KIND, []))
        seen, lines = set(), []
        for r in ROWS:
            for k in r["keys"]:
                if k in seen:
                    continue
                seen.add(k)
                v = CASE.get(k)
                if isinstance(v, list) and v:
                    shown_v = f"{len(v)} rows"
                elif is_filled(CASE, k):
                    shown_v = fmt_date(v) if (k.endswith("_date") or k in ("notice_date", "reply_date")) \
                        else ("INR " + fmt_amount(v) if k in ("amount", "dues", "principal", "tax")
                              else str(v))
                else:
                    shown_v = ""
                lines.append((k, shown_v, k in crit_keys))
        done = [x for x in lines if x[1]]
        open_ = [x for x in lines if not x[1]]
        st.markdown(f"**Held — {len(done)}**")
        for k, v, c in done:
            st.markdown(f"<span class='pill ok'>✓</span> **{label(k)}** — "
                        f"{_h.escape(v[:110])}", unsafe_allow_html=True)
        st.markdown(f"**Open — {len(open_)}**")
        for k, v, c in open_:
            st.markdown(f"<span class='pill {'warn' if c else 'info'}'>"
                        f"{'needed' if c else 'optional'}</span> {label(k)}",
                        unsafe_allow_html=True)

    # ---- 5. history -------------------------------------------------------
    with tabs[4]:
        H = st.session_state.history
        if not H:
            st.caption("Every notice drafted in this session is kept here — restore one to pick "
                       "it back up, or take the text without leaving the page.")
        for i, e in enumerate(H):
            with st.container(border=True, key=f"glass_h_{i}"):
                st.markdown(
                    f"<div class='hist'><div class='t'>{e['when']:%d.%m.%Y  %H:%M}  ·  "
                    f"{_h.escape(TYPES[e['kind']]['name'])}  ·  {_h.escape(e['party'])}</div>"
                    f"<div class='s'>{_h.escape(e['subject'][:150])}</div></div>",
                    unsafe_allow_html=True)
                meta = []
                if e["flags"]:
                    meta.append(f"{e['flags']} review note(s)")
                if e["open_items"]:
                    meta.append(f"{len(e['open_items'])} left as [● …]")
                if meta:
                    st.markdown(f"<div class='ev'>{' · '.join(meta)}</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("Restore this case", key=f"rest_{i}", use_container_width=True):
                    st.session_state.kind = e["kind"]
                    st.session_state.case[e["kind"]] = copy.deepcopy(e["case"])
                    st.session_state.drafted[e["kind"]] = False
                    st.session_state.report.pop(e["kind"], None)
                    st.toast("Restored — press the button to re-check it.")
                    st.rerun()
                c2.download_button("Download .txt",
                                   DRAFT.to_text(e["kind"], e["case"]),
                                   DRAFT.filename(e["kind"], e["case"]).replace(".docx", ".txt"),
                                   "text/plain", key=f"hdl_{i}", use_container_width=True)
        if H and st.button("Clear history", key="clr_hist"):
            st.session_state.history = []
            st.rerun()

    # ---- 6. the rules -----------------------------------------------------
    with tabs[5]:
        st.caption("Read live out of `skill/SKILL.md`. Edit the skill and this list changes — "
                   "the rules are the backend, not a copy of it.")
        for r in SK.golden_rules():
            st.markdown(
                f"<div class='rule'><div class='n'>{r.n}</div>"
                f"<b>{_h.escape(r.title)}</b><p>{_h.escape(r.body)}</p></div>",
                unsafe_allow_html=True)
        st.info(SK.review_banner(), icon="⚖️")
