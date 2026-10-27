"""A printable HTML page listing every confirmed substitution across the
whole school for one date — the staff-noticeboard sheet, same server-
rendered-HTML pattern as timetable_print.py, not an SPA page. The
substitute column is a live dropdown (reusing the same single-slot
substitute endpoints the Quick Substitution panel's "fix a slot" control
already calls) so a wrong auto-pick can be corrected right here before
printing, without going back into the app."""
import html
from datetime import date as date_cls

_CSS = """
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#f6f8fb;font-family:'Hind','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a}
.bar{position:sticky;top:0;background:#fff;border-bottom:1px solid rgba(15,23,42,.12);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.bar h1{font-size:1.05rem;margin:0}
.bar .actions{display:flex;gap:8px}
.bar button{background:#1e3a8a;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-weight:600;font-size:.85rem;cursor:pointer}
.bar button.secondary{background:#334155}
.page{max-width:900px;margin:24px auto;background:#fff;padding:28px;border-radius:8px;box-shadow:0 1px 0 rgba(15,23,42,.05),0 8px 20px -6px rgba(15,23,42,.18)}
.school{text-align:center;font-size:1.3rem;font-weight:700;margin:0;color:#166534}
.address{text-align:center;font-size:.85rem;color:#475569;margin:2px 0 0}
.title{text-align:center;font-size:1.05rem;font-weight:700;margin:14px 0 2px}
.date{text-align:center;font-size:.9rem;color:#475569;margin:0}
.summary{text-align:center;font-size:.82rem;color:#64748b;margin:4px 0 18px}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:10px}
th,td{border:1px solid rgba(15,23,42,.12);padding:8px 10px;text-align:left;vertical-align:middle}
th{background:#166534;color:#fff;font-size:.75rem}
tr.g-even td{background:#f8fafc}
select{width:100%;padding:4px 6px;border-radius:4px;border:1px solid #cbd5e1;font:inherit}
.save-status{font-size:.72rem;color:#64748b;margin-top:2px;min-height:1em}
.empty{text-align:center;color:#64748b;padding:2rem 0}
@media print{
  .noprint{display:none!important}
  body{background:#fff}
  .page{box-shadow:none;margin:0;max-width:none}
  select{border:none;appearance:none;background:transparent}
}
"""

_JS = """
<script>
const params = new URLSearchParams(window.location.search);
const token = params.get('token') || '';

function assignSubstitute(selectEl) {
  const statusEl = selectEl.parentElement.querySelector('.save-status');
  statusEl.textContent = 'Saving…';
  fetch(`/api/timetable/classes/${selectEl.dataset.classId}/substitutions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({
      date: selectEl.dataset.date,
      day: selectEl.dataset.day,
      period: Number(selectEl.dataset.period),
      substitute_teacher_id: Number(selectEl.value),
    }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not save');
      }
      statusEl.textContent = 'Saved';
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    })
    .catch((err) => { statusEl.textContent = err.message; });
}

async function downloadPdf() {
  const page = document.querySelector('.page');
  const canvas = await html2canvas(page, { scale: 2, backgroundColor: '#ffffff' });
  const imgData = canvas.toDataURL('image/png');
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const imgHeight = (canvas.height * pageWidth) / canvas.width;
  pdf.addImage(imgData, 'PNG', 0, 0, pageWidth, imgHeight);
  pdf.save('substitute-timetable.pdf');
}
</script>
"""


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _class_label(row: dict) -> str:
    return f'Grade {row["grade"]} · {row["section"]}' if row["section"] else f'Grade {row["grade"]}'


def _format_date(date: str) -> str:
    d = date_cls.fromisoformat(date)
    return f"{d.strftime('%d.%m.%Y')} ({d.strftime('%A')})"


def _format_absence_summary(summary: list[dict]) -> str:
    if not summary:
        return ""
    parts = []
    for s in summary:
        label = _esc(s["teacher_code"] or s["teacher_name"])
        if s["whole_day"]:
            parts.append(label)
        else:
            parts.append(f"{label} (P{', '.join(str(p) for p in s['periods'])})")
    return f"(Today: {', '.join(parts)})"


def render_substitution_sheet(
    school_name: str,
    school_address: str,
    date: str,
    rows: list[dict],
    absence_summary: list[dict],
    row_candidates: dict[tuple[int, int], list[dict]],
) -> str:
    """`rows` is the dict shape returned by repo.list_substitutions_for_account.
    `row_candidates` maps (class_id, period) -> ranked candidates for that
    exact row (see api/timetable.py's print_substitution_sheet, which
    always makes sure the row's currently-assigned substitute is included
    even if find_substitute_candidates would otherwise treat them as
    "busy" covering this very slot)."""
    if rows:
        body_rows = []
        last_period = None
        group_idx = -1
        for r in rows:
            if r["period"] != last_period:
                group_idx += 1
                last_period = r["period"]
            candidates = row_candidates.get((r["class_id"], r["period"]), [])
            options = "".join(
                f'<option value="{c["teacher_id"]}"{" selected" if c["teacher_id"] == r["substitute_teacher_id"] else ""}>{_esc(c["teacher_name"])}</option>'
                for c in candidates
            )
            body_rows.append(
                f'<tr class="g-{"even" if group_idx % 2 == 0 else "odd"}">'
                f'<td>{_esc(r["period"])}</td><td>{_esc(_class_label(r))}</td>'
                f'<td><select data-class-id="{r["class_id"]}" data-day="{_esc(r["day"])}" data-period="{r["period"]}" '
                f'data-date="{_esc(date)}" onchange="assignSubstitute(this)">{options}</select>'
                f'<div class="save-status"></div></td>'
                f"<td>&nbsp;</td></tr>"
            )
        table_html = (
            "<table><thead><tr><th>Period</th><th>Class</th><th>Substitute teacher</th><th>Signature</th></tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table>"
        )
    else:
        table_html = '<p class="empty">No substitutions confirmed for this date.</p>'

    address_html = f'<p class="address">{_esc(school_address)}</p>' if school_address else ""
    summary_text = _format_absence_summary(absence_summary)
    summary_html = f'<p class="summary">{summary_text}</p>' if summary_text else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Substitutes — {_esc(date)}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>{_CSS}</style></head>
<body>
<div class="bar noprint">
  <h1>{_esc(school_name)} — Substitutes for {_esc(date)}</h1>
  <div class="actions">
    <button class="secondary" onclick="downloadPdf()">Download PDF</button>
    <button onclick="window.print()">Print</button>
  </div>
</div>
<div class="page">
  <p class="school">{_esc(school_name)}</p>
  {address_html}
  <p class="title">Substitute Teacher Time Table</p>
  <p class="date">Date: {_format_date(date)}</p>
  {summary_html}
  {table_html}
</div>
{_JS}
</body></html>"""
