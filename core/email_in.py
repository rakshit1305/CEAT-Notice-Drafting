"""Read an Outlook message as it comes, without anyone re-typing it first.

Two formats arrive in practice. `.eml` is MIME and the standard library parses
it. `.msg` is Outlook's own container — a Compound File holding MAPI property
streams — which `olefile` opens and the decoding below turns back into text.

Both paths return the same two things: the message rendered as text (headers,
body, and the quoted chain underneath, which is usually where the dates and
figures actually are), and the attachments as raw bytes so extract.py can read
each one as a document of its own. A dealer's mail with the ledger attached has
to give up both in a single drag, or the time this was meant to save is still
being spent.

The decoding of a .msg is split in two on purpose: `_msg_streams` does the
container plumbing and needs a real file, `_msg_from_streams` does all the
interpretation and is pure, so the part that can be wrong is the part the tests
can reach.
"""
from __future__ import annotations

import email
import email.policy
import html as _html
import io
import re
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

# MAPI property tags, as they appear in a .msg stream name. The four hex digits
# are the property id; the four after are the type (001F unicode, 001E 8-bit,
# 0102 binary).
_P_SUBJECT = "0037"
_P_SENDER_NAME = "0C1A"
_P_SENDER_MAIL = "0C1F"
_P_SENT_REPR_NAME = "0042"
_P_DISPLAY_TO = "0E04"
_P_DISPLAY_CC = "0E03"
_P_BODY = "1000"
_P_HEADERS = "007D"
_P_ATTACH_LONG = "3707"
_P_ATTACH_SHORT = "3704"
_P_ATTACH_DATA = "3701"
_P_ATTACH_MIME = "370E"

MAX_ATTACHMENTS = 12
MAX_BODY_CHARS = 60000

# Boilerplate that carries no information about the matter. Each pattern is
# matched against a whole paragraph, and only that paragraph goes.
_NOISE_PARA = re.compile(
    r"""^(?:\s*)(?:
        (?:this\s+(?:e-?mail|message)\s+(?:and\s+any\s+attachments?\s+)?
           (?:is|are|may\s+be)\s+(?:confidential|intended|privileged)) |
        (?:the\s+information\s+contained\s+in\s+this\s+(?:e-?mail|message)) |
        (?:if\s+you\s+(?:are\s+not\s+the\s+intended\s+recipient|have\s+received\s+this
           \s+(?:e-?mail|message)\s+in\s+error)) |
        (?:please\s+consider\s+the\s+environment\s+before\s+printing) |
        (?:any\s+views\s+or\s+opinions\s+presented\s+in\s+this\s+e-?mail) |
        (?:disclaimer\s*:) |
        (?:p\.?\s*s\.?\s*save\s+(?:paper|trees))
    )""",
    re.I | re.X | re.S,
)

_NOISE_LINE = re.compile(
    r"^\s*(?:sent\s+from\s+my\s+\w+|get\s+outlook\s+for\s+(?:ios|android)"
    r"|sent\s+from\s+(?:mail\s+for\s+windows|outlook))\s*\.?\s*$", re.I)

# Outlook writes an inline image as a cid reference. It reads as noise and it
# hides nothing.
_CID = re.compile(r"\[\s*(?:cid:|image:)[^\]]*\]", re.I)
_CID_BARE = re.compile(r"\bcid:[\w.@$-]+", re.I)

# Both of Outlook's reply separators, and the one Gmail writes.
_SEP = re.compile(
    r"^\s*(?:-{2,}\s*original\s+message\s*-{2,}|_{10,}|-{10,}|"
    r"={10,}|\*{10,}|from:.{0,200}sent:.{0,200})\s*$", re.I)


# ---------------------------------------------------------------- helpers ----
def _decode(raw) -> str:
    """A header value, with any RFC 2047 encoding unwound."""
    if raw is None:
        return ""
    try:
        return str(make_header(decode_header(str(raw)))).strip()
    except Exception:
        return str(raw).strip()


def html_to_text(src: str) -> str:
    """HTML body to text, keeping the table structure.

    A ledger pasted into the body of a mail arrives as an HTML table. Flatten
    it to `a | b | c` rows rather than a smear of numbers, because the analyser
    reads rows and the smear is what made people re-type it into Excel.
    """
    if not src:
        return ""
    t = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", src)
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|h[1-6]|li|blockquote)\s*>", "\n", t)
    t = re.sub(r"(?i)<li\b[^>]*>", "\n• ", t)
    t = re.sub(r"(?i)</t[dh]\s*>\s*(?=<t[dh]\b)", " | ", t)
    t = re.sub(r"(?i)</tr\s*>", "\n", t)
    t = re.sub(r"(?i)<t[dh]\b[^>]*>", "", t)
    t = re.sub(r"(?i)<(table|tr)\b[^>]*>", "\n", t)
    t = re.sub(r"(?i)<hr\s*/?>", "\n----\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = _html.unescape(t)
    t = t.replace("\xa0", " ").replace("​", "")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def tidy_body(body: str) -> str:
    """Strip what carries nothing, keep everything that might.

    The quoted chain stays. It is tempting to cut at the first `From:` because
    it reads like clutter, but in a dispute the invoice number and the date the
    dealer admitted the dues are three replies down.
    """
    if not body:
        return ""
    t = _CID.sub("", body)
    t = _CID_BARE.sub("", t)
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    # A separator becomes one readable marker, so the chain is still visible as
    # a chain without 60 underscores across the page.
    out_lines = []
    for ln in t.split("\n"):
        if _SEP.match(ln) and not re.match(r"(?i)^\s*from:", ln):
            if out_lines and out_lines[-1] == "--- previous message ---":
                continue
            out_lines.append("--- previous message ---")
            continue
        if _NOISE_LINE.match(ln):
            continue
        out_lines.append(ln.rstrip())
    t = "\n".join(out_lines)
    # A signature after the "-- " convention is the sender's own block.
    t = re.split(r"\n-- \n", t)[0] if "\n-- \n" in t else t
    paras = re.split(r"\n\s*\n", t)
    keep = [p for p in paras if p.strip() and not _NOISE_PARA.match(p)]
    t = "\n\n".join(keep)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:MAX_BODY_CHARS]


def render(headers: dict, body: str, attachments: list[str]) -> str:
    """The message as the analyser sees it: who, when, what it said."""
    lines = []
    for label in ("From", "To", "Cc", "Date", "Subject"):
        v = (headers.get(label) or "").strip()
        if v:
            lines.append(f"{label}: {v}")
    if attachments:
        lines.append("Attachments: " + ", ".join(attachments))
    head = "\n".join(lines)
    body = tidy_body(body)
    return (head + ("\n\n" + body if body else "")).strip()


def _safe_name(name: str, fallback: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", (name or "").strip())
    name = name.strip(". ")
    return name or fallback


# -------------------------------------------------------------------- eml ----
def read_eml(data: bytes) -> tuple[str, list[tuple[str, bytes]], str]:
    """A MIME message: rendered text, attachments, and a note if anything odd."""
    msg = email.message_from_bytes(data, policy=email.policy.default)

    headers = dict(
        From=_decode(msg.get("From")),
        To=_decode(msg.get("To")),
        Cc=_decode(msg.get("Cc")),
        Subject=_decode(msg.get("Subject")),
    )
    raw_date = msg.get("Date")
    if raw_date:
        try:
            headers["Date"] = parsedate_to_datetime(str(raw_date)).strftime("%d.%m.%Y %H:%M")
        except Exception:
            headers["Date"] = _decode(raw_date)

    plain, rich, attachments, notes = [], [], [], []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disp = (part.get_content_disposition() or "").lower()
        ctype = part.get_content_type()
        fname = _decode(part.get_filename())
        if disp == "attachment" or (fname and ctype not in ("text/plain", "text/html")):
            try:
                payload = part.get_payload(decode=True) or b""
            except Exception:
                payload = b""
            if payload:
                attachments.append((_safe_name(fname, f"attachment-{len(attachments) + 1}"),
                                    payload))
            continue
        try:
            text = part.get_content() if hasattr(part, "get_content") else \
                (part.get_payload(decode=True) or b"").decode(
                    part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            text = (part.get_payload(decode=True) or b"").decode("utf-8", errors="replace")
        if ctype == "text/html":
            rich.append(html_to_text(str(text)))
        elif ctype == "text/plain":
            plain.append(str(text))

    body = "\n\n".join(x for x in plain if x.strip()) or "\n\n".join(x for x in rich if x.strip())
    if len(attachments) > MAX_ATTACHMENTS:
        notes.append(f"{len(attachments)} attachments; the first {MAX_ATTACHMENTS} were read.")
        attachments = attachments[:MAX_ATTACHMENTS]
    if not body.strip():
        notes.append("the message body was empty — only the headers and any attachments were read.")
    return render(headers, body, [n for n, _ in attachments]), attachments, " ".join(notes)


# -------------------------------------------------------------------- msg ----
def _msg_streams(data: bytes) -> dict[str, bytes]:
    """Every stream in the .msg container, keyed by its path with '/' joins."""
    try:
        import olefile
    except Exception as e:                       # pragma: no cover - env dependent
        raise RuntimeError(
            "reading .msg needs the 'olefile' package (pip install olefile). "
            "Until then, save the mail as .eml or paste the text in."
        ) from e
    if not olefile.isOleFile(io.BytesIO(data)):
        raise ValueError("not an Outlook .msg file")
    out: dict[str, bytes] = {}
    with olefile.OleFileIO(io.BytesIO(data)) as ole:
        for entry in ole.listdir(streams=True, storages=False):
            path = "/".join(entry)
            try:
                out[path] = ole.openstream(entry).read()
            except Exception:
                continue
    return out


def _mapi_text(streams: dict[str, bytes], prefix: str, tag: str) -> str:
    """One string property, whichever of the two string types it was stored as."""
    for suffix, codec in (("001F", "utf-16-le"), ("001E", "cp1252")):
        raw = streams.get(f"{prefix}__substg1.0_{tag}{suffix}")
        if raw:
            try:
                return raw.decode(codec, errors="replace").replace("\x00", "").strip()
            except Exception:
                continue
    return ""


def _msg_date(streams: dict[str, bytes], headers_blob: str) -> str:
    """The sent date: from the transport headers if they survived, otherwise
    from PR_CLIENT_SUBMIT_TIME in the properties stream."""
    m = re.search(r"^Date:\s*(.+)$", headers_blob or "", re.I | re.M)
    if m:
        try:
            return parsedate_to_datetime(m.group(1).strip()).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return m.group(1).strip()
    blob = streams.get("__properties_version1.0") or b""
    # 32-byte header on a top-level message, then 16-byte entries:
    # tag (4) | flags (4) | value (8).
    for off in range(32, max(32, len(blob) - 15), 16):
        entry = blob[off:off + 16]
        if len(entry) < 16:
            break
        ptype = int.from_bytes(entry[0:2], "little")
        pid = int.from_bytes(entry[2:4], "little")
        if pid == 0x0039 and ptype == 0x0040:            # PR_CLIENT_SUBMIT_TIME
            ticks = int.from_bytes(entry[8:16], "little")
            if ticks:
                import datetime
                try:
                    dt = (datetime.datetime(1601, 1, 1)
                          + datetime.timedelta(microseconds=ticks // 10))
                    return dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    return ""
    return ""


def _msg_from_streams(streams: dict[str, bytes]) -> tuple[str, list[tuple[str, bytes]], str]:
    """Everything that turns MAPI streams into a message. Pure, so it is tested."""
    notes = []
    headers_blob = _mapi_text(streams, "", _P_HEADERS)

    sender = _mapi_text(streams, "", _P_SENDER_NAME) or _mapi_text(streams, "", _P_SENT_REPR_NAME)
    mail = _mapi_text(streams, "", _P_SENDER_MAIL)
    frm = f"{sender} <{mail}>" if sender and mail else (sender or mail)
    if not frm:
        m = re.search(r"^From:\s*(.+)$", headers_blob, re.I | re.M)
        frm = m.group(1).strip() if m else ""

    headers = dict(
        From=frm,
        To=_mapi_text(streams, "", _P_DISPLAY_TO),
        Cc=_mapi_text(streams, "", _P_DISPLAY_CC),
        Subject=_mapi_text(streams, "", _P_SUBJECT),
        Date=_msg_date(streams, headers_blob),
    )

    body = _mapi_text(streams, "", _P_BODY)
    if not body:
        rich = streams.get("__substg1.0_10130102") or b""
        if rich:
            body = html_to_text(rich.decode("utf-8", errors="replace"))
    if not body:
        body = html_to_text(_mapi_text(streams, "", "1013"))

    # Attachments live in their own storages: __attach_version1.0_#00000000/...
    groups: dict[str, dict[str, bytes]] = {}
    for path, blob in streams.items():
        if not path.startswith("__attach_version1.0_"):
            continue
        folder, _, leaf = path.partition("/")
        if leaf:
            groups.setdefault(folder, {})[leaf] = blob

    attachments: list[tuple[str, bytes]] = []
    for i, folder in enumerate(sorted(groups), 1):
        inner = {f"__{k.split('__', 1)[1]}" if k.startswith("__") else k: v
                 for k, v in groups[folder].items()}
        name = (_mapi_text(inner, "", _P_ATTACH_LONG)
                or _mapi_text(inner, "", _P_ATTACH_SHORT))
        blob = inner.get(f"__substg1.0_{_P_ATTACH_DATA}0102")
        if blob is None:
            # An attached message rather than a file; its own streams are nested
            # and are not read as a document.
            notes.append(f"attachment {i} is an embedded message and was not read.")
            continue
        attachments.append((_safe_name(name, f"attachment-{i}"), blob))

    if len(attachments) > MAX_ATTACHMENTS:
        notes.append(f"{len(attachments)} attachments; the first {MAX_ATTACHMENTS} were read.")
        attachments = attachments[:MAX_ATTACHMENTS]
    if not body.strip():
        notes.append("the message body was empty — only the headers and any attachments were read.")
    return render(headers, body, [n for n, _ in attachments]), attachments, " ".join(notes)


def read_msg(data: bytes) -> tuple[str, list[tuple[str, bytes]], str]:
    """An Outlook .msg: rendered text, attachments, and a note if anything odd.

    `extract_msg` is used when it happens to be installed, because it handles
    the rarer encodings; otherwise the streams are read directly.
    """
    try:
        import extract_msg                                  # pragma: no cover
        m = extract_msg.Message(io.BytesIO(data))           # pragma: no cover
        headers = dict(                                     # pragma: no cover
            From=(m.sender or "").strip(),
            To=(m.to or "").strip(),
            Cc=(m.cc or "").strip(),
            Subject=(m.subject or "").strip(),
            Date=(m.date.strftime("%d.%m.%Y %H:%M") if getattr(m, "date", None)
                  else str(getattr(m, "date", "") or "")),
        )
        body = m.body or html_to_text(getattr(m, "htmlBody", "") or "")   # pragma: no cover
        atts = []                                           # pragma: no cover
        for i, a in enumerate(getattr(m, "attachments", []) or [], 1):
            blob = getattr(a, "data", None)
            if isinstance(blob, bytes) and blob:
                atts.append((_safe_name(getattr(a, "longFilename", "")
                                        or getattr(a, "shortFilename", ""),
                                        f"attachment-{i}"), blob))
        atts = atts[:MAX_ATTACHMENTS]                       # pragma: no cover
        return render(headers, body, [n for n, _ in atts]), atts, ""   # pragma: no cover
    except ImportError:
        pass
    return _msg_from_streams(_msg_streams(data))
