"""A plain, printable HTML page for one class's generated weekly
timetable — same server-rendered-HTML-with-a-print-button pattern as
card_render.py, not an SPA page, so it opens cleanly in its own tab and
prints without any app chrome."""
import html

_DAY_LABELS = {"MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday", "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday", "SUN": "Sunday"}
_ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _from_minutes(total: int) -> str:
    h = (total // 60) % 24
    m = total % 60
    return f"{h:02d}:{m:02d}"


def _format_clock(hhmm: str) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    period = "PM" if h >= 12 else "AM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {period}"


def _build_day_schedule(start_time: str, end_time: str, periods_per_day: int, breaks: list[dict]) -> list[dict] | None:
    total_minutes = _to_minutes(end_time) - _to_minutes(start_time)
    break_minutes = sum(b["duration_minutes"] for b in breaks)
    teaching_minutes = total_minutes - break_minutes
    if periods_per_day < 1 or teaching_minutes < periods_per_day:
        return None

    base = teaching_minutes // periods_per_day
    extra = teaching_minutes % periods_per_day
    breaks_by_after = {b["after_period"]: b for b in breaks}

    rows: list[dict] = []
    cursor = _to_minutes(start_time)
    for i in range(1, periods_per_day + 1):
        duration = base + (1 if i <= extra else 0)
        start = cursor
        cursor += duration
        rows.append({"kind": "period", "period": i, "label": f"Period {i}", "start": _from_minutes(start), "end": _from_minutes(cursor)})
        brk = breaks_by_after.get(i)
        if brk:
            b_start = cursor
            cursor += brk["duration_minutes"]
            rows.append({"kind": "break", "label": brk["label"], "start": _from_minutes(b_start), "end": _from_minutes(cursor)})
    return rows


_CSS = """
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#f6f8fb;font-family:'Hind','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a}
.bar{position:sticky;top:0;background:#fff;border-bottom:1px solid rgba(15,23,42,.12);padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.bar h1{font-size:1.05rem;margin:0}
.bar button{background:#1e3a8a;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-weight:600;font-size:.85rem;cursor:pointer}
.page{max-width:900px;margin:24px auto;background:#fff;padding:28px;border-radius:8px;box-shadow:0 1px 0 rgba(15,23,42,.05),0 8px 20px -6px rgba(15,23,42,.18)}
.school{text-align:center;font-size:1.3rem;font-weight:700;margin:0}
.class-name{text-align:center;font-size:1rem;color:#475569;margin:4px 0 20px}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th,td{border:1px solid rgba(15,23,42,.12);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#1e3a8a;color:#fff;font-size:.75rem}
th.time-col{background:#f6f8fb;color:#475569}
td.time-col{background:#f6f8fb;white-space:nowrap}
td.time-col .pname{font-weight:600;font-size:.8rem}
td.time-col .ptime{font-size:.72rem;color:#64748b}
.subject{font-weight:600;font-size:.8rem}
.teacher{font-size:.72rem;color:#64748b}
.break-row td{background:rgba(30,58,138,.08);text-align:center;font-style:italic;font-size:.75rem;color:#475569}
@media print{
  .noprint{display:none!important}
  body{background:#fff}
  .page{box-shadow:none;margin:0;max-width:none}
}
"""


def render_class_timetable_print(school_name: str, class_label: str, config: dict, entries: list[dict]) -> str:
    """`config` is the dict shape returned by repo.get_school_config
    (working_days, periods_per_day, start_time, end_time, breaks).
    `entries` is the dict shape returned by repo.get_timetable_entries."""
    schedule = _build_day_schedule(config["start_time"], config["end_time"], config["periods_per_day"], config["breaks"])
    working_days = [d for d in _ALL_DAYS if d in config["working_days"]]
    entry_by_slot = {(e["day"], e["period"]): e for e in entries}

    if schedule is None:
        body_html = "<p>This school's schedule isn't valid right now — fix the breaks under Schedule first.</p>"
    else:
        header_cells = "".join(f"<th>{_esc(_DAY_LABELS.get(d, d))}</th>" for d in working_days)
        rows_html = []
        for row in schedule:
            if row["kind"] == "break":
                rows_html.append(
                    f'<tr class="break-row"><td colspan="{len(working_days) + 1}">{_esc(row["label"])} · '
                    f'{_esc(_format_clock(row["start"]))} – {_esc(_format_clock(row["end"]))}</td></tr>'
                )
                continue
            cells = []
            for d in working_days:
                entry = entry_by_slot.get((d, row["period"]))
                if entry:
                    cells.append(
                        f'<td><div class="subject">{_esc(entry["subject_name"])}</div>'
                        f'<div class="teacher">{_esc(entry["teacher_name"] or "")}</div></td>'
                    )
                else:
                    cells.append("<td></td>")
            rows_html.append(
                f'<tr><td class="time-col"><div class="pname">{_esc(row["label"])}</div>'
                f'<div class="ptime">{_esc(_format_clock(row["start"]))} – {_esc(_format_clock(row["end"]))}</div></td>'
                f'{"".join(cells)}</tr>'
            )
        body_html = (
            f'<p class="school">{_esc(school_name)}</p>'
            f'<p class="class-name">{_esc(class_label)}</p>'
            f'<table><thead><tr><th class="time-col">Time</th>{header_cells}</tr></thead>'
            f'<tbody>{"".join(rows_html)}</tbody></table>'
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(class_label)} — Timetable</title>
<style>{_CSS}</style></head>
<body>
<div class="bar noprint">
  <h1>{_esc(school_name)} — {_esc(class_label)}</h1>
  <button onclick="window.print()">Print / Save as PDF</button>
</div>
<div class="page">{body_html}</div>
</body></html>"""
