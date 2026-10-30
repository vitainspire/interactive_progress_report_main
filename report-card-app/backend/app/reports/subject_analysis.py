"""Teacher-facing, whole-class, per-subject analysis — ported from a
standalone HTML tool the teacher already uses (same marks-Excel layout,
same AP SSC blueprint data), rebuilt here to run off data already sitting
in Postgres from the original upload instead of re-parsing a freshly
re-uploaded file. Two printable A4 pages per subject:

  Page 1: exam-by-exam grade-distribution donuts and pass-rate trend,
  class KPIs, a "Shining Stars" (top performers) and "Rising Stars"
  (students needing attention, fails flagged) breakdown for the latest
  exam, and the absentee list.

  Page 2: a grade-distribution table across every exam, an exam-to-exam
  most-improved/most-declined comparison, and the official SSC exam
  blueprint's chapter-weightage action plan (subject_blueprint /
  subject_exam_info — see app/db/subject_blueprint_seed.py) — which
  chapters are worth the most marks, plus curated exam-technique tips.

Entirely rule-based arithmetic + one DB lookup for the blueprint data, no
LLM call — same philosophy as class_stats.py. The donut/bar charts are
plain CSS (conic-gradient), not canvas, so the page prints correctly with
no JavaScript dependency beyond the print button itself.
"""
from __future__ import annotations

import html
import json
import re

import psycopg

from app.reports.numfmt import fmt_num

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}
GROUP_OF = {"A1": "A", "A2": "A", "B1": "B", "B2": "B", "C1": "C", "C2": "C", "D1": "D1", "D2": "D2"}
GROUPS = [("A", "A1, A2", "#1d8f50"), ("B", "B1, B2", "#2f74d0"), ("C", "C1, C2", "#e8a20c"), ("D1", "D1 (అంచున పాస్)", "#e46a1e"), ("D2", "D2 (ఫెయిల్)", "#cf3a3a")]
GCOL = {g[0]: g[2] for g in GROUPS}

# Some sheets carry a stray non-subject column (an overall grade/percentage
# label) that the core parser stores as if it were a subject — excluded
# here the same way the reference tool this was ported from already did,
# rather than silently showing a bogus "GRADE" button in the picker.
_NOT_A_SUBJECT = re.compile(r"^(grade|grades|grd|gr|gpa|%|percent(age)?|గ్రేడ్|గ్రేడు)\.?$", re.I)

_SUBJECT_PATTERNS = [
    ("MATHS", re.compile(r"mat|గణిత|లెక్క", re.I)),
    ("PHYSICAL SCIENCE", re.compile(r"phy|^p\.?\s?s\b|భౌతిక", re.I)),
    ("BIOLOGY", re.compile(r"bio|^b\.?\s?s\b|^n\.?\s?s\b|జీవ", re.I)),
    ("SOCIAL", re.compile(r"soc|^s\.?\s?s\b|సాంఘిక", re.I)),
    ("ENGLISH", re.compile(r"eng|ఇంగ్లీ|ఆంగ్ల", re.I)),
    ("HINDI", re.compile(r"hin|హిందీ", re.I)),
    ("TELUGU", re.compile(r"tel|తెలుగు", re.I)),
]
_SUBJECT_SORT = [p for _canon, p in _SUBJECT_PATTERNS[::-1]] + [re.compile(r"sci|సైన్స్", re.I)]

_DISPLAY = {
    "TELUGU": ("తెలుగు", "Telugu", "#b3264f"),
    "HINDI": ("హిందీ", "Hindi", "#cf6a0a"),
    "ENGLISH": ("ఇంగ్లీష్", "English", "#2453c4"),
    "MATHS": ("గణితం", "Mathematics", "#1d8a4e"),
    "PHYSICAL SCIENCE": ("భౌతిక రసాయన శాస్త్రం", "Physical Science", "#6a3fb5"),
    "BIOLOGY": ("జీవశాస్త్రం", "Biological Science", "#0d8580"),
    "SOCIAL": ("సాంఘిక శాస్త్రం", "Social Studies", "#8a5528"),
}

GENERAL_TIPS = [
    "ప్రత్యేక తరగతి: వారానికి 4 రోజులు, సాయంత్రం 45 నిమిషాలు (Rising Stars కు)",
    "ప్రతి శనివారం 20 మార్కుల స్లిప్ టెస్ట్: ఆ వారం చాప్టర్ నుంచి, మార్కులు రిజిస్టర్‌లో",
    "గత 3 సంవత్సరాల ప్రశ్నాపత్రాలు, మోడల్ పేపర్ల సాధన",
    "D1, D2 గ్రేడ్ పిల్లల తల్లిదండ్రులతో నెలకోసారి మాట్లాడటం",
    "ముందు బెంచీలో కూర్చోబెట్టి తరగతిలో తరచూ ప్రశ్నలు అడగడం",
]


def _esc(v) -> str:
    return html.escape(str(v), quote=True)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def classify_subject(name: str) -> str | None:
    for canon, pat in _SUBJECT_PATTERNS:
        if pat.search((name or "").strip()):
            return canon
    return None


def normalize_subject_key(name: str) -> str:
    """The canonical storage/lookup key for a subject — one of the 7 built-in
    AP/Telangana SSC subjects when recognized, otherwise the raw name
    trimmed and uppercased. This is what lets a school teaching something
    outside that fixed list (Sanskrit, Computer Science, a differently-named
    subject) still have its own syllabus/blueprint confirmed and looked up
    consistently, instead of being rejected outright."""
    return classify_subject(name) or (name or "").strip().upper()


def subject_sort_key(name: str) -> int:
    for i, pat in enumerate(_SUBJECT_SORT):
        if pat.search((name or "").strip()):
            return i
    return 99


def discover_subjects(all_students: list[dict]) -> list[str]:
    """Every distinct subject name appearing in any student's any exam —
    the raw text as it appears in the sheet, not the canonical/classified
    name, since that's what the picker needs to show and what a lookup
    into a student's own exams uses."""
    seen: list[str] = []
    for s in all_students:
        for ex in s["exams"].values():
            for x in ex["subjects"]:
                if x["name"] not in seen and not _NOT_A_SUBJECT.match(x["name"].strip()):
                    seen.append(x["name"])
    seen.sort(key=subject_sort_key)
    return seen


# Fallback colors for a subject outside the 7 built-in ones (e.g. Sanskrit,
# Computer Science) — picked deterministically by name so the same subject
# always gets the same color, and two different unlisted subjects on one
# report don't collide on the single old fixed color.
_FALLBACK_COLORS = ["#3b4a7a", "#7a3b63", "#3b7a5e", "#7a6a3b", "#5e3b7a", "#7a3b3b"]


def _display_info(subject_name: str) -> tuple[str, str, str]:
    canon = classify_subject(subject_name)
    if canon and canon in _DISPLAY:
        return _DISPLAY[canon]
    color = _FALLBACK_COLORS[sum(normalize_subject_key(subject_name).encode()) % len(_FALLBACK_COLORS)]
    return (subject_name, subject_name, color)


def compute_exam_stats(all_students: list[dict], exam_defs: list[dict], settings, subject_name: str) -> list[dict]:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    out = []
    for e in exam_defs:
        key = e["key"]
        max_marks = settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject
        rows = []
        for s in all_students:
            ex = s["exams"].get(key)
            if not ex:
                continue
            match = next((x for x in ex["subjects"] if x["name"] == subject_name), None)
            if not match:
                continue
            rows.append({"student": s, "marks": match["marks"], "grade": match["grade"]})
        nums = []
        for r in rows:
            if not _is_num(r["marks"]):
                continue
            group = GROUP_OF.get(r["grade"])
            if not group:
                continue
            pct = r["marks"] * 100 / max_marks if max_marks else 0
            nums.append({**r, "pct": pct, "group": group})
        if not nums:
            continue
        pass_n = sum(1 for r in nums if r["grade"] != "D2")
        avg = sum(r["marks"] for r in nums) / len(nums)
        hi = max(r["marks"] for r in nums)
        top = [r for r in nums if r["marks"] == hi]
        cnt = {g[0]: sum(1 for r in nums if r["group"] == g[0]) for g in GROUPS}
        sc = {g: sum(1 for r in nums if r["grade"] == g) for g in GRADE_POINTS}
        absentees = [r for r in rows if r["marks"] == "AB"]
        out.append({
            "key": key, "max": max_marks, "nums": nums, "pass": pass_n,
            "pass_pct": pass_n * 100 / len(nums), "avg": avg,
            "avg_pct": avg * 100 / max_marks if max_marks else 0,
            "hi": hi, "top": top, "cnt": cnt, "sc": sc, "absentees": absentees,
        })
    return out


def get_blueprint(conn: psycopg.Connection, account_id: int, class_level: str, subject_name: str) -> list[dict]:
    """Only ever this account's own confirmed blueprint (see
    app/db/reference_documents.py) — never another school's data."""
    canon = normalize_subject_key(subject_name)
    if not canon:
        return []
    return list(
        conn.execute(
            "SELECT topic_name, marks, choice_marks FROM subject_blueprint WHERE account_id = %s AND class_level = %s AND subject = %s ORDER BY marks DESC",
            (account_id, class_level, canon),
        ).fetchall()
    )


def get_exam_info(conn: psycopg.Connection, account_id: int, class_level: str, subject_name: str) -> tuple[str, list[str]]:
    canon = normalize_subject_key(subject_name)
    if not canon:
        return "", []
    row = conn.execute(
        "SELECT exam_format, tips FROM subject_exam_info WHERE account_id = %s AND class_level = %s AND subject = %s",
        (account_id, class_level, canon),
    ).fetchone()
    if not row:
        return "", []
    return row["exam_format"] or "", json.loads(row["tips"] or "[]")


# ---------------------------------------------------------------- render --

_CSS = """
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact;color-adjust:exact}
body{margin:0;background:#eceff5;color:#18213a;font-family:'Noto Sans Telugu','Noto Sans',system-ui,sans-serif}
.bar{position:sticky;top:0;z-index:5;display:flex;gap:10px;align-items:center;background:#fff;border-bottom:1px solid #d3d9e6;padding:10px 16px}
#pv{zoom:var(--z,1)}
.bar h1{margin:0;flex:1;font-size:16px}
.bar button{border:0;border-radius:10px;padding:9px 16px;font-weight:700;cursor:pointer;background:#18213a;color:#fff;font:inherit}
.pvw{overflow-x:auto;padding:16px 0 40px}
.pg{--fs:12px;--c:#333;--cl:#f3f3f3;font-size:var(--fs);width:210mm;min-height:296mm;background:#fff;color:#1a2140;margin:0 auto 16px;padding:9mm 11mm 9mm 13mm;display:flex;flex-direction:column;gap:1.05em;box-shadow:0 2px 14px rgba(0,0,0,.22);position:relative;font-weight:700;-webkit-font-smoothing:antialiased}
.pg>*{flex:none}
.pg::after{content:"";position:absolute;left:0;top:0;bottom:0;width:4.5mm;background:var(--c)}
.hd::before{content:"";position:absolute;left:0;right:0;top:0;height:1.6mm;background:linear-gradient(90deg,#b3264f 0 14.3%,#cf6a0a 14.3% 28.6%,#2453c4 28.6% 42.9%,#1d8a4e 42.9% 57.1%,#6a3fb5 57.1% 71.4%,#0d8580 71.4% 85.7%,#8a5528 85.7%)}
.hd{text-align:center;padding:3mm 4mm 3.2mm;border-radius:2.5mm;background:#fff6ea;border:.35mm solid #f3d9b5;position:relative;overflow:hidden}
.hd h1{margin:1.2mm 0 0;font-weight:800;font-size:26px;line-height:1.3;color:#a3123a;overflow-wrap:anywhere}
.hd p{margin:1mm 0 0;font-size:16px;font-weight:800;line-height:1.3;color:#1d2f7a}
.ti{display:flex;align-items:stretch;border-radius:2mm;overflow:hidden;background:var(--c);color:#fff}
.ti .tn{padding:.55em 1.1em .65em;flex:1;min-width:0}
.ti .tl{font-size:.95em;font-weight:700;opacity:.9}
.ti .tb{font-size:2.6em;line-height:1.05;margin-top:.1em}
.ti .te{font-size:1.05em;font-weight:700;opacity:.9}
.ti .tf{background:rgba(0,0,0,.16);padding:.7em 1.1em;display:flex;flex-direction:column;justify-content:center;gap:.25em;font-size:.95em;font-weight:700;min-width:38%}
.ti .tf b{font-weight:800}
.sec h4{margin:0 0 .55em;font-size:1.22em;font-weight:800;color:var(--c);display:flex;align-items:baseline;gap:.5em;border-bottom:.3mm solid var(--cl);padding-bottom:.2em}
.sec h4 small{font-size:.72em;color:#3a4362;font-weight:700}
.dash{background:linear-gradient(180deg,var(--cl),#fff 70%);border-radius:2.5mm;padding:.9em 1em 1em}
.rings{display:flex;justify-content:space-evenly;align-items:center;gap:.4em;flex-wrap:wrap}
.rg{display:flex;flex-direction:column;align-items:center;text-align:center;min-width:0}
.donut{width:38mm;height:38mm;border-radius:50%;display:flex;align-items:center;justify-content:center}
.donut .hole{width:66%;height:66%;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.1}
.donut .hole b{font-size:2em;font-weight:800;color:#1a2140}
.donut .hole span{font-size:.82em;font-weight:700;color:#3a4362}
.rg .en{font-weight:800;font-size:1.25em;margin-top:.3em;color:#fff;background:var(--c);border-radius:99px;padding:0 .9em}
.rg .sm{font-size:.86em;color:#3a4362;font-weight:700;margin-top:.15em}
.mvc{display:flex;flex-direction:column;align-items:center;gap:.35em;font-size:.86em;font-weight:700;color:#3a4362;text-align:center}
.mvc .ar{font-size:1.8em;line-height:1;color:var(--c)}
.dl{font-weight:800;font-size:.95em;padding:.15em .6em;border-radius:99px;white-space:nowrap}
.dl.u{background:#e3f5ea;color:#167443}.dl.d{background:#fde7e5;color:#b03024}.dl.z{background:#eef0f5;color:#3a4362}
.lgd{display:flex;justify-content:center;gap:1.1em;flex-wrap:wrap;font-size:.86em;color:#3a4362;font-weight:700;margin-top:.7em}
.lgd span::before{content:"";display:inline-block;width:.85em;height:.85em;border-radius:50%;margin-right:.3em;vertical-align:-.05em;background:var(--g)}
.kp{display:grid;grid-template-columns:repeat(4,1fr);gap:.6em;margin-top:.9em}
.kp div{background:#fff;border-radius:1.6mm;padding:.45em .7em;border:.3mm solid var(--cl);border-left:1.2mm solid var(--c)}
.kp b{display:block;font-size:1.4em;font-weight:800;color:#1a2140;line-height:1.15}
.kp b small{font-size:.6em}
.kp span{font-size:.84em;color:#2e3654;font-weight:700}
.gt{width:100%;border-collapse:collapse;font-size:.88em;text-align:center}
.gt th,.gt td{border:.25mm solid #dde1ec;padding:.18em .2em}
.gt th{background:#f2f4f9;font-weight:800}
.gt th.f{background:#fde7e5;color:#b03024}
.gt td:first-child,.gt th:first-child{text-align:left;font-weight:800;padding-left:.5em}
.two{display:grid;grid-template-columns:1fr 1fr;gap:1.1em}
.lst{border-radius:2mm;padding:.6em .7em .7em;border:.35mm solid}
.lst.sh{background:#fffaf0;border-color:#f1d79a}.lst.rs{background:#f4fbf6;border-color:#bfe3cb}
.lst h5{margin:0 0 .45em;font-size:1.1em;font-weight:800;display:flex;align-items:baseline;gap:.4em;flex-wrap:wrap}
.lst.sh h5{color:#9a6a00}.lst.rs h5{color:#167443}
.lst h5 small{font-size:.7em;color:#3a4362;font-weight:700}
.more{margin:.45em 0 0;font-size:.84em;font-weight:700;color:#3a4362}
.note{font-size:.86em;color:#2e3654;font-weight:700;margin:.4em 0 0}
.ab{font-size:.86em;color:#2e3654;font-weight:700}
.ph{display:flex;justify-content:space-between;align-items:center;font-weight:700;color:#2e3654;font-size:.92em;border-bottom:.35mm solid #c9cfdf;padding-bottom:.4em}
.ph b{color:var(--c);font-weight:800;font-size:1.15em}
.mv{display:flex;height:2em;border-radius:1mm;overflow:hidden;margin-bottom:.8em;font-weight:800;font-size:.86em}
.mv i{display:flex;align-items:center;justify-content:center;font-style:normal;color:#fff;white-space:nowrap;overflow:hidden}
.chg h5{margin:0 0 .4em;font-size:1.05em;font-weight:800}
.chg.up h5{color:#167443}.chg.dn h5{color:#b03024}
.cr{background:#fff;border:.3mm solid #e2e5ee;border-radius:1.6mm;padding:.35em .55em;margin-bottom:.4em;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.1em .6em}
.chg.up .cr{border-left:1.3mm solid #1d8f50}.chg.dn .cr{border-left:1.3mm solid #cf3a3a}
.cr .nm{font-weight:800;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cr .ft{font-size:.84em;font-weight:700;color:#3a4362;white-space:nowrap}
.cr .br{grid-column:1/-1;display:flex;align-items:center;gap:.4em}
.cr .br i{display:block;height:.75em;border-radius:99px;flex:none}
.chg.up .br i{background:linear-gradient(90deg,#9fd8b4,#1d8f50)}.chg.dn .br i{background:linear-gradient(90deg,#f1aaa2,#cf3a3a)}
.cr .br b{font-size:.9em;font-weight:800;white-space:nowrap}
.chg.up .br b{color:#167443}.chg.dn .br b{color:#b03024}
.cr .br .ft{margin-left:auto}
.tip{margin:.55em 0 0;padding:.45em .7em .45em 1.6em;border-radius:1.4mm;font-size:.84em;font-weight:700;color:#33405f}
.chg.up .tip{background:#eaf7ef}.chg.dn .tip{background:#fdf0ee}
.tip li{margin:.1em 0}
.bp{display:grid;grid-template-columns:1fr 1fr;gap:.25em 1.2em}
.bpr{display:grid;grid-template-columns:minmax(0,1fr) 9em;gap:.5em;align-items:center;font-size:.86em;font-weight:700}
.bpr .nm{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bpr .bb{display:flex;align-items:center;gap:.3em}
.bpr .bb i{display:block;height:1em;border-radius:.5mm;background:var(--c);opacity:.35}
.bpr.hot .bb i{opacity:1}
.bpr.hot .nm{font-weight:800;color:#1a2140}
.bpr .bb span{font-weight:800;font-size:.9em;white-space:nowrap}
.sub{font-weight:800;font-size:1em;margin:.8em 0 .35em;color:#1a2140}
.ez{margin:0;padding-left:1.3em;font-weight:700;font-size:.88em}
.ez li{margin:.12em 0}
.msn{margin-top:.9em;border:.4mm solid var(--c);border-radius:2mm;overflow:hidden;background:var(--cl)}
.msn .mh{background:var(--c);color:#fff;font-weight:800;font-size:1.1em;padding:.35em .8em}
.msn ol{margin:.5em 0 .3em;padding-left:2.2em;font-weight:700;font-size:.92em}
.msn li{margin:.18em 0}
.msn p{margin:0 .8em .55em;font-weight:800;color:#167443;font-size:.92em}
.sig{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;gap:2em;font-size:.9em;font-weight:700;color:#3a4362;padding-top:2em}
.sig div{border-top:.3mm solid #6a7190;padding-top:.3em;min-width:32%;text-align:center}
.sig small{font-weight:700;color:#2e3654;font-size:.82em}
.tg{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.5em}
.tile{background:#fff;border:.3mm solid #e2e5ee;border-top:1.3mm solid var(--g);border-radius:1.6mm;padding:.35em .45em .45em;display:flex;flex-direction:column;gap:.25em}
.tile .tt{display:flex;align-items:center;gap:.35em}
.tile .no{width:1.6em;height:1.6em;border-radius:50%;display:grid;place-items:center;font-size:.78em;font-weight:800;color:#fff;background:#8a92a8;flex:none}
.tile .gr{font-size:.8em;font-weight:800;color:#fff;border-radius:.8mm;padding:0 .4em;background:var(--g)}
.tile .mk{margin-left:auto;font-size:1.1em;font-weight:800;color:#0f1530}
.tile .mk small{font-size:.65em;color:#3a4362}
.tile .nm{font-size:.84em;font-weight:800;line-height:1.25;height:2.5em;overflow:hidden;overflow-wrap:anywhere;color:#0f1530}
.tile .pb{height:.45em;border-radius:99px;background:#eceef4;overflow:hidden}
.tile .pb i{display:block;height:100%;border-radius:99px;background:var(--g)}
.tile.fl{background:#fff1ef;border-color:#f3c3bc}
.tile.fl .nm{color:#b03024}
@media print{
 @page{size:A4;margin:0}
 body{background:#fff}
 .noprint{display:none!important}
 .pvw{padding:0;overflow:visible}
 #pv{zoom:1!important}
 .pg{margin:0;box-shadow:none}
}
"""


def _donut(e: dict) -> str:
    total = sum(e["cnt"].values()) or 1
    stops = []
    acc = 0.0
    for g, _label, color in GROUPS:
        n = e["cnt"][g]
        if not n:
            continue
        start, acc = acc, acc + n * 100 / total
        stops.append(f"{color} {start:.2f}% {acc:.2f}%")
    bg = f"conic-gradient({', '.join(stops)})" if stops else "#eceef4"
    return (
        f'<div class="donut" style="background:{bg}"><div class="hole">'
        f'<b>{round(e["pass_pct"])}%</b><span>పాస్</span></div></div>'
    )


def _delta(a: float, b: float, suf: str = "") -> str:
    d = b - a
    cls = "u" if d > 0.05 else "d" if d < -0.05 else "z"
    arrow = "▲" if d > 0.05 else "▼" if d < -0.05 else "="
    return f'<span class="dl {cls}">{arrow} {abs(round(d, 1))}{suf}</span>'


def _fm(v: float) -> str:
    return fmt_num(round(v, 1))


def _grade_row(r: dict, j: int, fail_flag: bool) -> str:
    warn = "⚠ " if fail_flag and r["grade"] == "D2" else ""
    return (
        f'<div class="row{" fl" if fail_flag and r["grade"] == "D2" else ""}">'
        f'<span class="no">{j + 1}</span><span class="nm">{warn}{_esc(r["student"]["name"])}</span>'
        f'<span class="gr g{r["group"]}">{_esc(r["grade"])}</span><span class="mk">{_fm(r["marks"])}</span></div>'
    )


def _tile(r: dict, j: int, max_marks: float, flag_fail: bool) -> str:
    fl = flag_fail and r["grade"] == "D2"
    warn = "⚠ " if fl else ""
    pct = max(3, r["pct"])
    return (
        f'<div class="tile{" fl" if fl else ""}" style="--g:{GCOL[r["group"]]}">'
        f'<div class="tt"><span class="no">{j + 1}</span><span class="gr">{_esc(r["grade"])}</span>'
        f'<b class="mk">{_fm(r["marks"])}<small>/{fmt_num(max_marks)}</small></b></div>'
        f'<div class="nm">{warn}{_esc(r["student"]["name"])}</div>'
        f'<div class="pb"><i style="width:{pct}%"></i></div></div>'
    )


def render_subject_analysis(
    conn: psycopg.Connection,
    account_id: int,
    all_students: list[dict],
    exam_defs: list[dict],
    settings,
    class_level: str,
    school_name: str,
    batch_name: str,
    subject_name: str,
) -> str | None:
    """Returns the full printable HTML page for one subject, or None if
    this subject has no numeric marks recorded in any exam yet."""
    te, en, color = _display_info(subject_name)
    exam_format, easy_tips = get_exam_info(conn, account_id, class_level, subject_name)
    blueprint = get_blueprint(conn, account_id, class_level, subject_name)

    X = compute_exam_stats(all_students, exam_defs, settings, subject_name)
    if not X:
        return None
    L = X[-1]
    P = X[-2] if len(X) > 1 else None

    css_vars = f"--c:{color};--cl:{color}1f"
    shine_all = sorted([r for r in L["nums"] if r["group"] in ("A", "B")], key=lambda r: -r["marks"])
    rise_all = sorted([r for r in L["nums"] if r["group"] in ("C", "D1", "D2")], key=lambda r: r["marks"])
    shine, rise = shine_all[:10], rise_all[:10]
    fail_n = L["cnt"]["D2"]

    head_html = f'<div class="hd"><h1>{_esc(school_name or "పాఠశాల పేరు")}</h1></div>'

    # ---- page 1 ----
    h = f'<div class="pg" style="{css_vars}">{head_html}'
    h += (
        f'<div class="ti"><div class="tn"><div class="tl">సబ్జెక్ట్ విశ్లేషణ / Subject Analysis</div>'
        f'<div class="tb">{_esc(te)}</div><div class="te">{_esc(en)}{", " + _esc(batch_name) if batch_name else ""}</div></div>'
        f'<div class="tf"><span>పరీక్షలు: <b>{", ".join(_esc(e["key"]) for e in X)}</b></span>'
        f'<span>విద్యార్థులు: <b>{len(all_students)}</b></span>'
        f'{f"<span>పబ్లిక్ పరీక్ష: <b>{_esc(exam_format)}</b></span>" if exam_format else ""}</div></div>'
    )
    h += '<div class="sec dash"><h4>పరీక్షల వారీగా ఫలితాలు <small>వృత్తంలో రంగులు = గ్రేడ్ల వాటా, మధ్యలో పాస్ శాతం</small></h4><div class="rings">'
    for j, e in enumerate(X):
        if j:
            q = X[j - 1]
            h += f'<div class="mvc"><span class="ar">➜</span>{_delta(q["pass_pct"], e["pass_pct"], "%")}<span>పాస్</span>{_delta(q["avg_pct"], e["avg_pct"], "%")}<span>సగటు</span></div>'
        h += (
            f'<div class="rg">{_donut(e)}<div class="en">{_esc(e["key"])}</div>'
            f'<div class="sm">{len(e["nums"])} లో {e["pass"]} పాస్</div>'
            f'<div class="sm">సగటు {_fm(e["avg"])}/{fmt_num(e["max"])} ({round(e["avg_pct"])}%)</div></div>'
        )
    h += "</div>"
    legend_items = "".join(f'<span style="--g:{g[2]}">{_esc(g[1])}</span>' for g in GROUPS)
    h += f'<div class="lgd">{legend_items}</div>'
    top_names = ", ".join(_esc(r["student"]["name"]) for r in L["top"][:2])
    extra = f" +{len(L['top']) - 2}" if len(L["top"]) > 2 else ""
    absent_suffix = f', గైర్హాజరు {len(L["absentees"])}' if L["absentees"] else ""
    fail_color = "#cf3a3a" if fail_n else "#1d8f50"
    h += (
        '<div class="kp">'
        f'<div><b>{_fm(L["avg"])}<small>/{fmt_num(L["max"])}</small></b><span>{_esc(L["key"])} తరగతి సగటు</span></div>'
        f'<div><b>{_fm(L["hi"])}<small>/{fmt_num(L["max"])}</small></b><span>అత్యధికం: {top_names}{extra}</span></div>'
        f'<div><b>{L["cnt"]["A"]}</b><span>A1, A2 గ్రేడ్లు</span></div>'
        f'<div><b style="color:{fail_color}">{fail_n}</b>'
        f'<span>D2 (ఫెయిల్){absent_suffix}</span></div></div></div>'
    )
    h += (
        f'<div class="lst sh"><h5>⭐ Shining Stars <small>{_esc(L["key"])}, టాప్ {len(shine)}</small></h5>'
        + (f'<div class="tg">{"".join(_tile(r, j, L["max"], False) for j, r in enumerate(shine))}</div>' if shine else '<p class="note">ఈ పరీక్షలో A, B గ్రేడ్లు ఎవరికీ రాలేదు.</p>')
        + (f'<p class="more">ఇంకా {len(shine_all) - len(shine)} మంది A, B గ్రేడ్లలో ఉన్నారు (మొత్తం {len(shine_all)}).</p>' if len(shine_all) > len(shine) else "")
        + "</div>"
    )
    h += (
        '<div class="lst rs"><h5>🌱 Rising Stars <small>ప్రత్యేక శ్రద్ధ అవసరం, తక్కువ మార్కుల నుంచి</small></h5>'
        + (f'<div class="tg">{"".join(_tile(r, j, L["max"], True) for j, r in enumerate(rise))}</div>' if rise else '<p class="note">C, D గ్రేడ్లలో ఎవరూ లేరు.</p>')
        + (f'<p class="more">ఇంకా {len(rise_all) - len(rise)} మంది C1, C2, D1 గ్రేడ్లలో ఉన్నారు (మొత్తం {len(rise_all)}).</p>' if len(rise_all) > len(rise) else "")
        + ('<p class="more" style="color:#b03024">⚠ ఎరుపు టైల్ = D2, ఫెయిల్. వీరితో వెంటనే మొదలుపెట్టండి.</p>' if fail_n else "")
        + "</div>"
    )
    if L["absentees"]:
        h += f'<div class="ab">గైర్హాజరు ({_esc(L["key"])}): {", ".join(_esc(r["student"]["name"]) for r in L["absentees"])}</div>'
    h += "</div>"

    # ---- page 2 ----
    h += f'<div class="pg" style="{css_vars}"><div class="ph"><span>{_esc(school_name or "")}</span><span><b>{_esc(te)}</b> విశ్లేషణ, పేజీ 2</span></div>'
    grade_keys = list(GRADE_POINTS.keys())
    h += (
        '<div class="sec"><h4>🎯 గ్రేడ్ల వారీగా విద్యార్థుల సంఖ్య</h4><table class="gt"><tr><th>పరీక్ష</th>'
        + "".join(f'<th class="f">{g}</th>' if g == "D2" else f"<th>{g}</th>" for g in grade_keys)
        + "<th>గైర్హాజరు</th><th>పాస్ %</th></tr>"
        + "".join(
            f'<tr><td>{_esc(e["key"])}</td>' + "".join(f'<td>{e["sc"].get(g) or "–"}</td>' for g in grade_keys)
            + f'<td>{len(e["absentees"]) or "–"}</td><td><b>{_fm(e["pass_pct"])}</b></td></tr>'
            for e in X
        )
        + "</table></div>"
    )
    if P:
        both = []
        p_by_id = {r["student"]["id"]: r for r in P["nums"]}
        for r in L["nums"]:
            q = p_by_id.get(r["student"]["id"])
            if q:
                both.append({"student": r["student"], "a": q["marks"], "b": r["marks"], "ga": q["grade"], "gb": r["grade"], "d": r["pct"] - q["pct"], "dm": r["marks"] - q["marks"]})
        same_max = P["max"] == L["max"]
        up_all = sorted([x for x in both if x["d"] > 0], key=lambda x: -x["d"])
        dn_all = sorted([x for x in both if x["d"] < 0], key=lambda x: x["d"])
        steady = len(both) - len(up_all) - len(dn_all)
        n = len(both) or 1
        up, dn = up_all[:5], dn_all[:5]
        mx = max(1.0, *(abs(x["d"]) for x in (up + dn))) if (up + dn) else 1.0

        def dv(x: dict) -> str:
            if same_max:
                return f'{"+" if x["dm"] > 0 else "−"}{_fm(abs(x["dm"]))}'
            return f'{"+" if x["d"] > 0 else "−"}{round(abs(x["d"]))}%'

        def cr(x: dict, is_down: bool) -> str:
            att = None
            a = x["student"].get("attendance")
            if a and a.get("total_working"):
                att = round(a["total_present"] * 100 / a["total_working"])
            bar_w = abs(x["d"]) * 45 / mx
            att_html = f'<span class="ft">హాజరు {att}%</span>' if is_down and att is not None else ""
            return (
                f'<div class="cr"><span class="nm">{_esc(x["student"]["name"])}</span>'
                f'<span class="ft">{_esc(P["key"])} {_fm(x["a"])} ({_esc(x["ga"])}) ➜ {_esc(L["key"])} {_fm(x["b"])} ({_esc(x["gb"])})</span>'
                f'<div class="br"><i style="width:{bar_w}%"></i><b>{"▼" if is_down else "▲"} {dv(x)} మార్కులు</b>{att_html}</div></div>'
            )

        h += f'<div class="sec"><h4>📊 పరీక్ష నుంచి పరీక్షకు మార్పు <small>{_esc(P["key"])} ➜ {_esc(L["key"])}, {len(both)} మంది</small></h4><div class="mv">'
        if up_all:
            label = f"▲ పెరిగినవారు {len(up_all)}" if len(up_all) * 100 / n >= 10 else str(len(up_all))
            h += f'<i style="width:{len(up_all) * 100 / n}%;background:#1d8f50">{label}</i>'
        if steady:
            label = f"= మార్పు లేదు {steady}" if steady * 100 / n >= 12 else str(steady)
            h += f'<i style="width:{steady * 100 / n}%;background:#9aa1b5">{label}</i>'
        if dn_all:
            label = f"▼ తగ్గినవారు {len(dn_all)}" if len(dn_all) * 100 / n >= 10 else str(len(dn_all))
            h += f'<i style="width:{len(dn_all) * 100 / n}%;background:#cf3a3a">{label}</i>'
        h += "</div>"
        h += (
            '<div class="two"><div class="chg up"><h5>📈 ఎక్కువ మెరుగుపడిన ' + str(len(up)) + " మంది</h5>"
            + ("".join(cr(x, False) for x in up) if up else '<p class="note">ఎవరి మార్కులూ పెరగలేదు.</p>')
            + '<ul class="tip"><li>ప్రార్థనా సమావేశంలో పేర్లు చెప్పి అభినందించండి</li><li>తదుపరి పరీక్షకు ఒక గ్రేడ్ పైకి లక్ష్యం ఇవ్వండి</li></ul></div>'
            + '<div class="chg dn"><h5>📉 ఎక్కువ తగ్గిన ' + str(len(dn)) + " మంది</h5>"
            + ("".join(cr(x, True) for x in dn) if dn else '<p class="note">ఎవరి మార్కులూ తగ్గలేదు.</p>')
            + '<ul class="tip"><li>విడిగా మాట్లాడి కారణం తెలుసుకోండి: ఆరోగ్యం, హాజరు, ఇంటి పరిస్థితి</li><li>హాజరు తక్కువ ఉంటే తల్లిదండ్రులకు తెలియజేయండి</li><li>తగ్గిన చాప్టర్లు మళ్ళీ చెప్పి చిన్న టెస్ట్ పెట్టండి</li></ul></div></div></div>'
        )
    else:
        h += (
            '<div class="sec"><h4>📊 పరీక్ష నుంచి పరీక్షకు మార్పు</h4>'
            f'<p class="note">ఇప్పటివరకు ఒక్క పరీక్ష ({_esc(L["key"])}) మార్కులు మాత్రమే ఉన్నాయి. '
            "రెండో పరీక్ష మార్కులు చేర్చిన తర్వాత ఎక్కువ మెరుగుపడిన, ఎక్కువ తగ్గిన విద్యార్థులు ఇక్కడ వస్తారు.</p></div>"
        )

    hot = {b["topic_name"] for b in blueprint[:3]}
    mx_bp = max([b["marks"] + (b["choice_marks"] or 0) for b in blueprint], default=1)
    h += f'<div class="sec"><h4>🌱 Rising Stars కోసం కార్యాచరణ ప్రణాళిక <small>{len(rise_all)} మంది{f", వీరిలో D2 {fail_n}" if fail_n else ""}; AP SSC బ్లూప్రింట్ ఆధారంగా</small></h4>'
    if blueprint:
        h += '<div class="sub" style="margin-top:0">చాప్టర్ల వారీ వెయిటేజ్ (మార్కులు): ముదురు రంగు ఉన్నవి ముందు చదివించండి</div><div class="bp">'
        for b in blueprint:
            total = b["marks"] + (b["choice_marks"] or 0)
            extra = f' (+{b["choice_marks"]})' if b["choice_marks"] else ""
            h += (
                f'<div class="bpr{" hot" if b["topic_name"] in hot else ""}"><span class="nm">{_esc(b["topic_name"])}</span>'
                f'<span class="bb"><i style="width:{total * 6 / mx_bp}em"></i><span>{b["marks"]}{extra}</span></span></div>'
            )
        h += "</div>"
        if any(b["choice_marks"] for b in blueprint):
            h += '<p class="note">(+ ) = ఛాయిస్ ప్రశ్నల అదనపు మార్కులు</p>'
    h += '<div class="two" style="margin-top:.4em"><div><div class="sub">✅ సులభంగా మార్కులు వచ్చే భాగాలు</div><ul class="ez">'
    h += "".join(f"<li>{_esc(t)}</li>" for t in (easy_tips or ["తరచూ వచ్చే 1 మార్కు ప్రశ్నలు, నిర్వచనాలు", "గత ప్రశ్నాపత్రాల్లో పదేపదే వచ్చిన ప్రశ్నలు", "చిత్రాలు, పట్టికలు, ముఖ్య సూత్రాలు"]))
    h += '</ul></div><div><div class="sub">🏫 ప్రత్యేక శిక్షణ</div><ul class="ez">'
    h += "".join(f"<li>{_esc(t)}</li>" for t in GENERAL_TIPS)
    h += "</ul></div></div>"
    top3 = ", ".join(_esc(b["topic_name"]) for b in blueprint[:3])
    h += (
        '<div class="msn"><div class="mh">🎯 కార్యాచరణ ప్రణాళిక</div><ol>'
        f"<li>ప్రభుత్వం విడుదల చేసిన {_esc(te)} బ్లూప్రింట్‌పై విద్యార్థులకు అవగాహన కల్పించడం</li>"
        f"<li>{_esc(te)} మోడల్ పేపర్లు క్రమం తప్పకుండా సాధన చేయించడం</li>"
        f'<li>ఎక్కువ వెయిటేజ్ ఉన్న చాప్టర్లపై ప్రత్యేక శ్రద్ధ{": " + top3 if top3 else ""}</li></ol>'
        "<p>ఈ విధంగా Rising Stars ను Shining Stars గా మార్చడానికి అవకాశం ఉంటుంది.</p></div></div>"
    )
    h += (
        '<div class="sig"><div>సబ్జెక్ట్ ఉపాధ్యాయుని సంతకం</div>'
        f'<small>తేదీ: _______________</small><div>ప్రధానోపాధ్యాయుని సంతకం</div></div></div>'
    )

    return f"""<!doctype html>
<html lang="te"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(te)} — Subject Analysis</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700;800&family=Noto+Sans+Telugu:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{_CSS}</style></head>
<body>
<div class="bar noprint"><h1>{_esc(te)} — Subject Analysis</h1><button onclick="window.print()">\U0001f5a8 Print / Save as PDF</button></div>
<div class="pvw"><div id="pv">{h}</div></div>
<script>
(function(){{
  // Each .pg page is a fixed A4 width (210mm ≈ 794px) — on a phone-width
  // screen that's wider than the viewport, so it's shrunk to fit here via
  // CSS zoom (affects layout size, unlike transform:scale, so no leftover
  // blank space below). Printing always resets zoom to 1 (see @media print)
  // so the saved PDF is always full quality regardless of what the on-screen
  // preview happened to be shrunk to.
  var pvw = document.querySelector('.pvw');
  var pv = document.getElementById('pv');
  if(!pvw || !pv || !('zoom' in document.documentElement.style)) return;
  function fit(){{
    var natural = 794;
    var z = Math.min(1, (pvw.clientWidth - 4) / natural);
    pv.style.zoom = z > 0 ? z : 1;
  }}
  fit();
  window.addEventListener('resize', fit);
}})();
</script>
</body></html>"""
