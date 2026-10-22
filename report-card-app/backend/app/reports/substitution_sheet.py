"""A plain, printable HTML page listing every confirmed substitution
across the whole school for one date — the staff-noticeboard sheet,
same server-rendered-HTML-with-a-print-button pattern as
timetable_print.py, not an SPA page."""
import html

_CSS = """
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#f6f8fb;font-family:'Hind','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a}
.bar{position:sticky;top:0;background:#fff;border-bottom:1px solid rgba(15,23,42,.12);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.bar h1{font-size:1.05rem;margin:0}
.bar button{background:#1e3a8a;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-weight:600;font-size:.85rem;cursor:pointer}
.page{max-width:900px;margin:24px auto;background:#fff;padding:28px;border-radius:8px;box-shadow:0 1px 0 rgba(15,23,42,.05),0 8px 20px -6px rgba(15,23,42,.18)}
.school{text-align:center;font-size:1.3rem;font-weight:700;margin:0}
.date{text-align:center;font-size:1rem;color:#475569;margin:4px 0 20px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{border:1px solid rgba(15,23,42,.12);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#1e3a8a;color:#fff;font-size:.75rem}
.empty{text-align:center;color:#64748b;padding:2rem 0}
@media print{
  .noprint{display:none!important}
  body{background:#fff}
  .page{box-shadow:none;margin:0;max-width:none}
}
"""


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _class_label(row: dict) -> str:
    return f'Grade {row["grade"]} · {row["section"]}' if row["section"] else f'Grade {row["grade"]}'


def render_substitution_sheet(school_name: str, date: str, rows: list[dict]) -> str:
    """`rows` is the dict shape returned by repo.list_substitutions_for_account."""
    if rows:
        body_rows = "".join(
            f"<tr><td>{_esc(r['period'])}</td><td>{_esc(_class_label(r))}</td>"
            f"<td>{_esc(r['subject_name'] or '—')}</td>"
            f"<td>{_esc(r['original_teacher_name'] or '—')}</td>"
            f"<td>{_esc(r['substitute_teacher_name'])}</td></tr>"
            for r in rows
        )
        table_html = (
            "<table><thead><tr><th>Period</th><th>Class</th><th>Subject</th>"
            "<th>Absent teacher</th><th>Substitute</th></tr></thead>"
            f"<tbody>{body_rows}</tbody></table>"
        )
    else:
        table_html = '<p class="empty">No substitutions confirmed for this date.</p>'

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Substitutes — {_esc(date)}</title>
<style>{_CSS}</style></head>
<body>
<div class="bar noprint">
  <h1>{_esc(school_name)} — Substitutes for {_esc(date)}</h1>
  <button onclick="window.print()">Print / Save as PDF</button>
</div>
<div class="page">
  <p class="school">{_esc(school_name)}</p>
  <p class="date">Substitutes for {_esc(date)}</p>
  {table_html}
</div>
</body></html>"""
