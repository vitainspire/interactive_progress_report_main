"""Renders the printable report-card HTML page — a straight port of the
original tool's `.card` markup/CSS, so the printed output the teacher gets
looks exactly like the one they already use."""
from __future__ import annotations

import html
import re

from app.reports.analysis import build_analysis
from app.reports.numfmt import fmt_num
from app.reports.voice_script import build_voice_script_romanized, build_voice_script_telugu

CARD_CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
html,body{margin:0}
body{background:#f4f6f9;font:15px/1.5 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif}
#pvw{overflow-x:auto}#pv{width:210mm;margin:auto}
.card{--fs:10px;font-size:var(--fs);position:relative;width:210mm;height:296mm;background:radial-gradient(circle at 0 0,#e8f0ff 0,transparent 40%),radial-gradient(circle at 100% 100%,#fff3d1 0,transparent 38%),#fff;color:#111;box-shadow:0 2px 12px rgba(0,0,0,.25);padding:11mm 11mm 10mm;margin:0 auto 14px;overflow:hidden;display:flex;flex-direction:column;gap:2.8mm;page-break-after:always;break-after:page;font-family:'Noto Sans','Noto Sans Telugu',sans-serif;line-height:1.35}
.card:last-child{page-break-after:auto;break-after:auto}.card>*{flex:none}.card>.grow{flex:1 0 auto}.card::before{content:"";position:absolute;inset:5mm;border:.5mm solid #1e3a8a;border-radius:2.5mm;pointer-events:none;box-shadow:0 0 0 .5mm #fff,0 0 0 1mm #e9a400}
.card h2{margin:0;text-align:center;font-size:1.8em;letter-spacing:.6px;background:linear-gradient(120deg,#1e3a8a,#2563eb 55%,#0e7490);color:#fff;border-radius:2mm;padding:.35em .5em;box-shadow:0 .6mm 1.6mm rgba(30,58,138,.3);text-shadow:0 1px 2px rgba(0,0,0,.3)}
.card h3{margin:-1mm auto 0;text-align:center;font-size:1.05em;background:linear-gradient(90deg,#f5b700,#e9a400);color:#1b1b1b;border-radius:99px;width:56%;padding:.2em;letter-spacing:2px;box-shadow:0 .4mm 1.2mm rgba(233,164,0,.35)}
.info{display:grid;grid-template-columns:1.6fr .9fr .9fr 1.5fr;gap:1.8mm}.info>div{background:#fff;border:1px solid #c7d6f5;border-top:.8mm solid #2563eb;border-radius:1.5mm;padding:.3em .6em}.info small{display:block;font-size:.72em;color:#64748b;letter-spacing:.8px;text-transform:uppercase}.info b{font-size:1em;color:#0f172a}
.blk{display:flex;flex-direction:column;gap:1.3mm}
.sec{display:flex;align-items:center;gap:.6em;font-weight:700;font-size:1em;color:#1e3a8a;letter-spacing:.8px}.sec::before{content:"";flex:none;width:.95em;height:.95em;border-radius:.25em;background:linear-gradient(135deg,#f5b700,#e9a400);box-shadow:0 0 0 .5mm #fff3d1}.sec::after{content:"";flex:1;height:.35mm;background:linear-gradient(90deg,#9db4e8,transparent)}.sec small{font-weight:600;color:#64748b;letter-spacing:0;font-size:.85em}
.tw{border:1px solid #9db4e8;border-radius:1.8mm;overflow:hidden;background:#fff;box-shadow:0 .4mm 1.2mm rgba(30,58,138,.1)}
.card table{width:100%;border-collapse:collapse;border-style:hidden;text-align:center;table-layout:auto}.card th,.card td{border:1px solid #c7d6f5;padding:.2em .25em;font-size:.88em}.card th{background:linear-gradient(#2a4fb5,#1e3a8a);color:#fff;border-color:#4466c4}.card th.fa{background:linear-gradient(#14a3b3,#0e7490)}.card th.sa{background:linear-gradient(#8b5cf6,#6d28d9)}.card td.l,.card th.l{text-align:left;padding-left:.6em}.card td.l{font-weight:600;color:#1e3a8a}.card tr:nth-child(even) td{background:#f3f7ff}
.card .t,.card tr.t td{font-weight:700;background:#fff1c9}.f,.pass{color:#fff;border-radius:99px;padding:0 .7em;font-weight:700}.f{background:#dc2626}.pass{background:#16a34a}.gr{display:inline-block;min-width:2.1em;border-radius:99px;padding:0 .3em;color:#fff;font-weight:700}.ga{background:#16a34a}.gb{background:#2563eb}.gc{background:#d97706}.gd{background:#ea580c}.gf{background:#dc2626}
.rk{display:inline-block;font-size:1.2em;font-weight:700;color:#1e3a8a;min-width:2em;border-radius:99px;padding:0 .5em}.rk.m1,.rk.m2,.rk.m3{color:#fff}.rk.m1{background:linear-gradient(#fcd34d,#d97706)}.rk.m2{background:linear-gradient(#cbd5e1,#64748b)}.rk.m3{background:linear-gradient(#fdba74,#b45309)}
.ai{flex:1 1 auto;display:flex;flex-direction:column;border:1px solid #9fd3de;border-radius:1.8mm;overflow:hidden;line-height:1.55;background:linear-gradient(#f0fafc,#fff);box-shadow:0 .4mm 1.2mm rgba(14,116,144,.1)}.ab{flex:1;display:flex;flex-direction:column;gap:.6em;padding:.7em .8em}.ai p{margin:0}
.ai p.in{font-size:.95em;color:#1e3a8a;font-weight:700;padding-bottom:.35em;border-bottom:1px dashed #9db4e8}
.ai p.pt{flex:1 1 auto;display:flex;align-items:center;gap:.75em;padding:.45em .85em;font-size:.98em;font-weight:700;color:#1f2937;background:#fff;border:1px solid #cfe7ee;border-left:1.1mm solid #0e7490;border-radius:1.4mm;box-shadow:0 .3mm .8mm rgba(14,116,144,.08)}
.ai p.pt:nth-child(odd){background:#f5fbfd;border-left-color:#2563eb}.ai p.pt:nth-child(odd) i{background:linear-gradient(#3b82f6,#1e3a8a)}
.ai p.pt i{flex:none;font-style:normal;width:1.8em;height:1.8em;border-radius:50%;background:linear-gradient(#14a3b3,#0e7490);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;line-height:1;box-shadow:0 .3mm .8mm rgba(0,0,0,.2)}
.sig{display:flex;justify-content:space-between;padding-top:9mm;font-weight:700;font-size:.95em;color:#1e3a8a}.sig span{border-top:1.2px solid #1e3a8a;width:28%;text-align:center;padding-top:.3em;letter-spacing:.5px}
body.out .card{margin:0;box-shadow:none}
.speak-btn{position:absolute;top:4mm;right:4mm;z-index:2;display:inline-flex;align-items:center;gap:.4em;background:#0e7490;color:#fff;border:0;border-radius:99px;padding:.4em .9em;font:inherit;font-size:.85em;font-weight:700;cursor:pointer;box-shadow:0 .3mm 1mm rgba(0,0,0,.25)}
.speak-btn.speaking{background:#dc2626}
@page{size:A4;margin:0}
@media print{body{background:#fff}#pvw{overflow:visible}#pv{margin:0}.card{margin:0;box-shadow:none}.speak-btn{display:none}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""

READ_ALOUD_SCRIPT = """
<script>
(function(){
  var current = null;

  function getVoicesAsync(){
    return new Promise(function(resolve){
      var voices = speechSynthesis.getVoices();
      if(voices && voices.length){ resolve(voices); return; }
      var done = false;
      speechSynthesis.onvoiceschanged = function(){
        if(done) return;
        done = true;
        resolve(speechSynthesis.getVoices());
      };
      setTimeout(function(){
        if(done) return;
        done = true;
        resolve(speechSynthesis.getVoices());
      }, 1000);
    });
  }

  window.__speakCard = function(btn){
    if(!('speechSynthesis' in window)){ alert('Reading aloud is not supported in this browser.'); return; }
    var card = btn.closest('.card');
    if(current){
      speechSynthesis.cancel();
      current.btn.classList.remove('speaking');
      current.btn.textContent = current.btn.dataset.label;
      var wasSameCard = current.btn === btn;
      current = null;
      if(wasSameCard) return;
    }
    getVoicesAsync().then(function(voices){
      var teluguVoice = voices.filter(function(v){ return /^te/i.test(v.lang); })[0];
      var text, lang;
      if(teluguVoice){
        text = card.getAttribute('data-speech-te') || '';
        lang = teluguVoice.lang;
      } else {
        text = card.getAttribute('data-speech-roman') || '';
        var enInVoice = voices.filter(function(v){ return /^en-in/i.test(v.lang); })[0];
        lang = enInVoice ? enInVoice.lang : 'en-US';
      }
      if(!text) return;
      var utter = new SpeechSynthesisUtterance(text);
      utter.lang = lang;
      utter.onend = utter.onerror = function(){
        btn.classList.remove('speaking');
        btn.textContent = btn.dataset.label;
        current = null;
      };
      btn.dataset.label = btn.dataset.label || btn.textContent;
      btn.textContent = '\\u23f9 Stop';
      btn.classList.add('speaking');
      current = { btn: btn };
      speechSynthesis.speak(utter);
    });
  };
  window.addEventListener('beforeunload', function(){ try { speechSynthesis.cancel(); } catch(e){} });
})();
</script>
"""

PAGE_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Telugu:wght@400;600;700&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body class="out"><div id="pvw"><div id="pv">{cards}</div></div>{script}</body></html>
"""


def _esc(v) -> str:
    return html.escape(str(v), quote=True)


def _grade_class(g: str) -> str:
    if g == "D2":
        return "gf"
    if g == "D1":
        return "gd"
    if re.match(r"^A", g):
        return "ga"
    if re.match(r"^B", g):
        return "gb"
    return "gc"


def _render_grade(g: str) -> str:
    if g == "-":
        return "-"
    return f'<b class="gr {_grade_class(g)}">{_esc(g)}</b>'


def _render_result(total_grade: str, result_text: str) -> str:
    if total_grade == "D2":
        r = "FAIL"
    elif total_grade != "-":
        r = "PASS"
    elif re.search(r"FAIL", result_text or "", re.I):
        r = "FAIL"
    elif re.search(r"PASS", result_text or "", re.I):
        r = "PASS"
    else:
        r = "-"
    if r == "FAIL":
        return '<span class="f">FAIL</span>'
    if r == "PASS":
        return '<span class="pass">PASS</span>'
    return "-"


def _render_marks_cell(v) -> str:
    return fmt_num(v) if isinstance(v, (int, float)) else str(v)


def render_card(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    """`student` and each of `all_students` are parsed-sheet rows (see
    sheet_parser.parse_worksheet); `exam_defs` is the batch's full exam
    list in discovery order: [{"key", "is_fa"}, ...]. `all_students` (every
    student in the batch, not just the ones being printed) is needed for
    the duplicate-rank "*" marker and the class-strength count, exactly as
    in the original tool — selecting a subset of cards to print never
    changes what those reflect."""
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    exams_present = [e["key"] for e in exam_defs if e["key"] in student["exams"]]

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    def exam_total(key: str) -> float:
        return settings.fa_total if is_fa_by_key[key] else settings.sa_total

    subjects: list[str] = []
    for key in exams_present:
        for x in student["exams"][key]["subjects"]:
            if x["name"] not in subjects:
                subjects.append(x["name"])

    def find_subject(key: str, name: str) -> dict:
        for x in student["exams"][key]["subjects"]:
            if x["name"] == name:
                return x
        return {"marks": "-", "grade": "-"}

    class_strength = settings.class_strength_override or len(all_students)
    analysis = build_analysis(student, [e["key"] for e in exam_defs], class_strength)
    speech_text_te = build_voice_script_telugu(student, [e["key"] for e in exam_defs], class_strength, school_name)
    speech_text_roman = build_voice_script_romanized(student, [e["key"] for e in exam_defs], class_strength, school_name)

    h = f'<h2>{_esc(school_name or "School Name")}</h2><h3>STUDENT AI REPORT CARD</h3>'
    if speech_text_te:
        h += f'<button type="button" class="speak-btn" onclick="window.__speakCard(this)">\U0001f50a Read aloud</button>'
    h += (
        '<div class="info">'
        f'<div><small>Student Name</small><b>{_esc(student["name"])}</b></div>'
        f'<div><small>Class</small><b>{_esc(student["section"] or "-")}</b></div>'
        f'<div><small>Roll No</small><b>{_esc(student["roll"] or "-")}</b></div>'
        f'<div><small>Father\'s Name</small><b>{_esc(student["father"] or "-")}</b></div>'
        "</div>"
    )

    h += '<div class="blk"><div class="sec">MARKS &amp; GRADES <small>(మార్కులు, గ్రేడ్లు)</small></div><div class="tw"><table>'
    h += '<tr><th rowspan="2" class="l">SUBJECT</th>' + "".join(
        f'<th colspan="3" class="{"fa" if is_fa_by_key[k] else "sa"}">{_esc(k)}</th>' for k in exams_present
    ) + "</tr>"
    h += "<tr>" + "".join('<th>Total</th><th>Marks</th><th>Grade</th>' for _ in exams_present) + "</tr>"
    for name in subjects:
        h += f'<tr><td class="l">{_esc(name)}</td>'
        for key in exams_present:
            x = find_subject(key, name)
            h += f"<td>{_render_marks_cell(max_marks(key))}</td><td>{_render_marks_cell(x['marks'])}</td><td>{_render_grade(x['grade'])}</td>"
        h += "</tr>"
    h += '<tr class="t"><td class="l">TOTAL</td>'
    for key in exams_present:
        e = student["exams"][key]
        h += f"<td>{_render_marks_cell(exam_total(key))}</td><td>{_render_marks_cell(e['total_marks'])}</td><td>{_render_grade(e['total_grade'])}</td>"
    h += "</tr><tr><td class=\"l\">RESULT</td>"
    for key in exams_present:
        e = student["exams"][key]
        h += f'<td colspan="3">{_render_result(e["total_grade"], e["result"])}</td>'
    h += "</tr></table></div></div>"

    def is_dup_rank(key: str, rank) -> bool:
        return sum(1 for o in all_students if key in o["exams"] and o["exams"][key]["rank"] == rank) > 1

    h += f'<div class="blk"><div class="sec">CLASS RANK <small>(ర్యాంకు · out of {class_strength} students)</small></div><div class="tw"><table>'
    h += "<tr>" + "".join(f'<th class="{"fa" if is_fa_by_key[k] else "sa"}">{_esc(k)}</th>' for k in exams_present) + "</tr>"
    h += "<tr>"
    for key in exams_present:
        rank = student["exams"][key]["rank"]
        if isinstance(rank, (int, float)):
            cls = f" m{int(rank)}" if rank <= 3 else ""
            marker = " *" if is_dup_rank(key, rank) else ""
            h += f'<td><span class="rk{cls}">{fmt_num(rank)}</span>{marker}</td>'
        else:
            h += f"<td>{rank}</td>"
    h += "</tr></table></div></div>"

    att = student.get("attendance")
    if att:
        months = att["months"]
        h += '<div class="blk"><div class="sec">ATTENDANCE <small>(హాజరు)</small></div><div class="tw"><table>'
        h += '<tr><th class="l">Month</th>' + "".join(f"<th>{_esc(m['month'][:3])}</th>" for m in months) + "<th>TOTAL</th></tr>"
        h += '<tr><td class="l">Working days</td>' + "".join(f"<td>{fmt_num(m['working_days']) if m['working_days'] else '-'}</td>" for m in months) + f'<td class="t">{fmt_num(att["total_working"]) if att["total_working"] else "-"}</td></tr>'
        h += '<tr><td class="l">Attended</td>' + "".join(f"<td>{fmt_num(m['attended'])}</td>" for m in months) + f'<td class="t">{fmt_num(att["total_present"])}</td></tr>'
        h += "</table></div></div>"

    h += '<div class="blk grow"><div class="sec">AI ANALYSIS <small>(విశ్లేషణ)</small></div><div class="ai"><div class="ab">'
    if analysis["points"]:
        h += f'<p class="in">{_esc(analysis["intro"])}</p>'
        h += "".join(f'<p class="pt"><i>{i + 1}</i><span>{_esc(pt)}</span></p>' for i, pt in enumerate(analysis["points"]))
    h += "</div></div></div>"
    h += '<div class="sig"><span>Parent</span><span>Class Teacher</span><span>Head Master</span></div>'

    return f'<div class="card" data-speech-te="{_esc(speech_text_te)}" data-speech-roman="{_esc(speech_text_roman)}">{h}</div>'


def render_report_page(students: list[dict], all_students: list[dict], exam_defs: list[dict], settings, school_name: str, title: str = "Report Cards") -> str:
    cards = "".join(render_card(s, all_students, exam_defs, settings, school_name) for s in students) or "<p>No students selected.</p>"
    return PAGE_SHELL.format(title=_esc(title), css=CARD_CSS, cards=cards, script=READ_ALOUD_SCRIPT)
