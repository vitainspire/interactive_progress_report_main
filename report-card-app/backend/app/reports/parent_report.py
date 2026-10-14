"""Renders the PARENT-facing report page — a completely different
presentation from card_render.py's dense printable card, built for a
parent (often in a rural area, sometimes unable to read comfortably) to
follow on a phone. Structure is fixed by design: one page per subject,
plus a final overall/conclusion page — (number of subjects + 1) pages
total — moved through one at a time (tap Next/Back or swipe), with a
"Listen" button on every page that narrates just that page's content, so
the whole report can be understood by listening alone.

The teacher-facing /batches/{id}/report route is untouched and keeps using
card_render.render_report_page — this module is only ever reached via
/api/public/report/{token}.
"""
from __future__ import annotations

import html
import re

from app.reports.numfmt import fmt_num
from app.reports.parent_subject import (
    build_subject_voice_romanized,
    build_subject_voice_telugu,
    compute_subject_facts,
    subject_commentary_telugu,
)
from app.reports.voice_script import build_voice_script_romanized, build_voice_script_telugu, _compute_facts

PARENT_CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:#eef2f9;font:16px/1.5 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a;display:flex;flex-direction:column;min-height:100vh}
.topbar{position:sticky;top:0;z-index:3;background:linear-gradient(120deg,#1e3a8a,#2563eb 60%,#0e7490);color:#fff;padding:.7em 1em .6em;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.topbar .school{font-weight:700;font-size:1em;text-align:center;opacity:.95}
.topbar .student{text-align:center;font-size:1.15em;font-weight:700;margin-top:.1em}
.dots{display:flex;justify-content:center;gap:.3em;margin-top:.55em;flex-wrap:wrap}
.dot{width:.55em;height:.55em;border-radius:50%;background:rgba(255,255,255,.35)}
.dot.active{background:#f5b700;width:.7em;height:.7em}
.pagelabel{text-align:center;font-size:.8em;margin-top:.3em;opacity:.9}
main{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative}
.page{display:none;flex:1;overflow-y:auto;padding:1.1em 1.1em 1.6em;animation:fade .25s ease}
.page.active{display:flex;flex-direction:column}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.subject-title{font-size:1.6em;font-weight:800;color:#1e3a8a;text-align:center;margin:.2em 0 .1em}
.subject-title small{display:block;font-size:.55em;font-weight:600;color:#64748b;margin-top:.15em}
.exam-rows{display:flex;flex-direction:column;gap:.6em;margin-top:.9em}
.exam-row{background:#fff;border:1px solid #c7d6f5;border-left:.3em solid #2563eb;border-radius:.6em;padding:.7em .9em;display:flex;align-items:center;justify-content:space-between;box-shadow:0 1px 4px rgba(30,58,138,.08)}
.exam-row .exam-name{font-weight:700;color:#1e3a8a;font-size:1.05em}
.exam-row .marks{font-size:1.3em;font-weight:800}
.exam-row .marks small{font-size:.55em;font-weight:600;color:#64748b}
.gr{display:inline-block;margin-left:.5em;min-width:2.3em;text-align:center;border-radius:99px;padding:.15em .5em;color:#fff;font-weight:700;font-size:.85em}
.ga{background:#16a34a}.gb{background:#2563eb}.gc{background:#d97706}.gd{background:#ea580c}.gf{background:#dc2626}
.commentary{margin-top:1.1em;border-radius:.8em;padding:.9em 1em;font-size:1.05em;font-weight:600;line-height:1.5}
.commentary.good{background:#dcfce7;color:#166534;border:1px solid #86efac}
.commentary.mid{background:#fef9c3;color:#854d0e;border:1px solid #fde047}
.commentary.low{background:#ffedd5;color:#9a3412;border:1px solid #fdba74}
.commentary.fail{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5}
.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:.7em;margin-top:.8em}
.summary-box{background:#fff;border:1px solid #c7d6f5;border-radius:.7em;padding:.8em;text-align:center;box-shadow:0 1px 4px rgba(30,58,138,.08)}
.summary-box .label{font-size:.78em;color:#64748b;text-transform:uppercase;letter-spacing:.5px}
.summary-box .value{font-size:1.4em;font-weight:800;color:#0f172a;margin-top:.15em}
.result-pill{display:inline-block;border-radius:99px;padding:.25em .9em;font-weight:800;color:#fff;font-size:1.2em;margin-top:.3em}
.result-pill.pass{background:#16a34a}.result-pill.fail{background:#dc2626}
.recap{margin-top:1em;display:flex;flex-direction:column;gap:.5em}
.recap-line{background:#fff;border:1px solid #c7d6f5;border-radius:.6em;padding:.6em .9em;font-size:.95em}
.recap-line b{color:#1e3a8a}
.closing{margin-top:1.1em;background:#eff6ff;border:1px dashed #93c5fd;border-radius:.8em;padding:.9em 1em;font-size:1em;line-height:1.55}
.grow{flex:1 0 auto}
.navbar{position:sticky;bottom:0;z-index:3;background:#fff;border-top:1px solid #dbe4f3;display:flex;align-items:stretch;box-shadow:0 -2px 8px rgba(0,0,0,.08)}
.navbar button{flex:1;border:0;background:none;padding:.95em .4em;font:inherit;font-size:1em;font-weight:700;color:#1e3a8a;display:flex;align-items:center;justify-content:center;gap:.35em}
.navbar button:disabled{opacity:.3}
.navbar button.listen{color:#0e7490;flex:1.3}
.navbar button.listen.speaking{color:#dc2626}
.navbar button.nav{flex:1}
"""

READ_ALOUD_SCRIPT = """
<script>
(function(){
  var speaking = null;

  function getVoicesAsync(){
    return new Promise(function(resolve){
      var voices = speechSynthesis.getVoices();
      if(voices && voices.length){ resolve(voices); return; }
      var done = false;
      speechSynthesis.onvoiceschanged = function(){ if(done) return; done = true; resolve(speechSynthesis.getVoices()); };
      setTimeout(function(){ if(done) return; done = true; resolve(speechSynthesis.getVoices()); }, 1000);
    });
  }

  function stopSpeech(){
    if('speechSynthesis' in window) speechSynthesis.cancel();
    if(speaking){ speaking.classList.remove('speaking'); speaking.textContent = speaking.dataset.label; speaking = null; }
  }

  var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
  var dots = Array.prototype.slice.call(document.querySelectorAll('.dot'));
  var current = 0;
  var prevBtn = document.getElementById('prevBtn');
  var nextBtn = document.getElementById('nextBtn');
  var speakBtn = document.getElementById('speakBtn');
  var pageLabel = document.getElementById('pageLabel');

  function show(i){
    stopSpeech();
    pages.forEach(function(p, idx){ p.classList.toggle('active', idx === i); });
    dots.forEach(function(d, idx){ d.classList.toggle('active', idx === i); });
    current = i;
    prevBtn.disabled = i === 0;
    nextBtn.style.visibility = i === pages.length - 1 ? 'hidden' : 'visible';
    pageLabel.textContent = (i + 1) + ' / ' + pages.length;
    window.scrollTo(0, 0);
  }

  prevBtn.addEventListener('click', function(){ if(current > 0) show(current - 1); });
  nextBtn.addEventListener('click', function(){ if(current < pages.length - 1) show(current + 1); });

  speakBtn.addEventListener('click', function(){
    if(!('speechSynthesis' in window)){ alert('Reading aloud is not supported in this browser.'); return; }
    if(speaking){ stopSpeech(); return; }
    var page = pages[current];
    getVoicesAsync().then(function(voices){
      var teluguVoice = voices.filter(function(v){ return /^te/i.test(v.lang); })[0];
      var text, lang;
      if(teluguVoice){
        text = page.getAttribute('data-speech-te') || '';
        lang = teluguVoice.lang;
      } else {
        text = page.getAttribute('data-speech-roman') || '';
        var enInVoice = voices.filter(function(v){ return /^en-in/i.test(v.lang); })[0];
        lang = enInVoice ? enInVoice.lang : 'en-US';
      }
      if(!text) return;
      var utter = new SpeechSynthesisUtterance(text);
      utter.lang = lang;
      utter.onend = utter.onerror = function(){ stopSpeech(); };
      speakBtn.dataset.label = speakBtn.dataset.label || speakBtn.textContent;
      speakBtn.textContent = '\\u23f9 Stop';
      speakBtn.classList.add('speaking');
      speaking = speakBtn;
      speechSynthesis.speak(utter);
    });
  });

  var touchStartX = null;
  document.querySelector('main').addEventListener('touchstart', function(e){ touchStartX = e.changedTouches[0].clientX; });
  document.querySelector('main').addEventListener('touchend', function(e){
    if(touchStartX === null) return;
    var dx = e.changedTouches[0].clientX - touchStartX;
    touchStartX = null;
    if(Math.abs(dx) < 60) return;
    if(dx < 0 && current < pages.length - 1) show(current + 1);
    if(dx > 0 && current > 0) show(current - 1);
  });

  window.addEventListener('beforeunload', function(){ try { speechSynthesis.cancel(); } catch(e){} });
  show(0);
})();
</script>
"""

PAGE_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700;800&family=Noto+Sans+Telugu:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<div class="topbar">
  <div class="school">{school}</div>
  <div class="student">{student_name}</div>
  <div class="dots">{dots}</div>
  <div class="pagelabel" id="pageLabel"></div>
</div>
<main>{pages}</main>
<div class="navbar">
  <button type="button" class="nav" id="prevBtn">⬅ వెనుకకి</button>
  <button type="button" class="listen" id="speakBtn">\U0001f50a వినండి / Listen</button>
  <button type="button" class="nav" id="nextBtn">తరువాత ➡</button>
</div>
{script}
</body></html>
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


def _render_grade_badge(g: str) -> str:
    if g == "-":
        return ""
    return f'<span class="gr {_grade_class(g)}">{_esc(g)}</span>'


def _render_marks_cell(v) -> str:
    return fmt_num(v) if isinstance(v, (int, float)) else str(v)


def _render_subject_page(student: dict, exam_defs: list[dict], settings, subject_name: str) -> str:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    exam_order = [e["key"] for e in exam_defs]
    facts = compute_subject_facts(student, exam_order, subject_name, max_marks)
    speech_te = build_subject_voice_telugu(facts, student["name"])
    speech_roman = build_subject_voice_romanized(facts, student["name"])

    h = f'<h1 class="subject-title">{_esc(subject_name)}<small>ఈ సబ్జెక్టులో ప్రదర్శన</small></h1>'
    h += '<div class="exam-rows">'
    for e in facts.history:
        h += (
            '<div class="exam-row">'
            f'<span class="exam-name">{_esc(e.exam_key)}</span>'
            f'<span class="marks">{_render_marks_cell(e.marks)}<small> / {_render_marks_cell(e.max_marks)}</small>{_render_grade_badge(e.grade)}</span>'
            "</div>"
        )
    h += "</div>"
    h += f'<div class="commentary {facts.classification}">{_esc(subject_commentary_telugu(facts))}</div>'
    h += '<div class="grow"></div>'

    return f'<section class="page" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def _render_conclusion_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)
    speech_te = build_voice_script_telugu(student, exam_order, class_strength, school_name)
    speech_roman = build_voice_script_romanized(student, exam_order, class_strength, school_name)

    h = '<h1 class="subject-title">మొత్తం గ్రేడ్ &amp; ఫలితం<small>Overall Result</small></h1>'

    if facts is None:
        h += '<div class="grow"></div>'
        return f'<section class="page" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'

    if facts.grade == "D2" or re.search(r"FAIL", facts.result_text or "", re.I):
        result_html = '<span class="result-pill fail">FAIL</span>'
    elif facts.grade != "-" or re.search(r"PASS", facts.result_text or "", re.I):
        result_html = '<span class="result-pill pass">PASS</span>'
    else:
        result_html = "-"

    h += '<div class="summary-grid">'
    h += f'<div class="summary-box"><div class="label">మార్కులు / Marks</div><div class="value">{_render_marks_cell(facts.total)}</div></div>'
    h += f'<div class="summary-box"><div class="label">గ్రేడ్ / Grade</div><div class="value">{_render_grade_badge(facts.grade) or "-"}</div></div>'
    h += f'<div class="summary-box"><div class="label">ఫలితం / Result</div><div class="value">{result_html}</div></div>'
    if facts.last_rank is not None:
        h += f'<div class="summary-box"><div class="label">ర్యాంకు / Rank</div><div class="value">{fmt_num(facts.last_rank)} / {facts.class_strength}</div></div>'
    if facts.attendance_pct is not None:
        h += f'<div class="summary-box"><div class="label">హాజరు / Attendance</div><div class="value">{facts.attendance_pct}%</div></div>'
    h += "</div>"

    h += '<div class="recap">'
    if facts.good:
        h += f'<div class="recap-line">✅ <b>బలం (Strong):</b> {_esc(", ".join(facts.good))}</div>'
    if facts.fail:
        h += f'<div class="recap-line">❌ <b>ఫెయిల్ (Failed):</b> {_esc(", ".join(facts.fail))}</div>'
    if facts.low:
        h += f'<div class="recap-line">⚠️ <b>గమనిక (Needs attention):</b> {_esc(", ".join(facts.low))}</div>'
    h += "</div>"

    if facts.attendance_pct is not None and facts.attendance_pct < 75:
        h += '<div class="closing">హాజరు తక్కువగా ఉంది; దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.</div>'
    h += '<div class="closing">పూర్తి వివరాల కోసం పైన వివరాలను వినండి, మీ పిల్లవాడి భవిష్యత్తు కోసం శుభాకాంక్షలు!</div>'
    h += '<div class="grow"></div>'

    return f'<section class="page" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def render_parent_report_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, title: str = "Report Card") -> str:
    """`student` is the single student this link belongs to (parent links
    always resolve to exactly one student — see api/public.py). Builds
    (number of subjects + 1) pages: one per subject in discovery order,
    then a final overall/conclusion page."""
    exams_present = [e["key"] for e in exam_defs if e["key"] in student["exams"]]
    subjects: list[str] = []
    for key in exams_present:
        for x in student["exams"][key]["subjects"]:
            if x["name"] not in subjects:
                subjects.append(x["name"])

    pages_html = [_render_subject_page(student, exam_defs, settings, name) for name in subjects]
    pages_html.append(_render_conclusion_page(student, all_students, exam_defs, settings, school_name))

    # Mark the very first page active up front so there is no flash of
    # unstyled/empty content before READ_ALOUD_SCRIPT's show(0) runs.
    if pages_html:
        pages_html[0] = pages_html[0].replace('class="page"', 'class="page active"', 1)

    dots = "".join(f'<span class="dot{" active" if i == 0 else ""}"></span>' for i in range(len(pages_html)))

    return PAGE_SHELL.format(
        title=_esc(title),
        css=PARENT_CSS,
        school=_esc(school_name or "School"),
        student_name=_esc(student["name"]),
        dots=dots,
        pages="".join(pages_html),
        script=READ_ALOUD_SCRIPT,
    )
