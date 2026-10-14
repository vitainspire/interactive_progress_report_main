"""Renders the PARENT-facing report page — a completely different
presentation from card_render.py's dense printable card, built for a
parent (often in a rural area, sometimes unable to read comfortably) to
follow on a phone. Structure is fixed by design: one page per subject,
plus a final overall/conclusion page — (number of subjects + 1) pages
total — moved through one at a time (tap Next/Back or swipe), with a
"Listen" button on every page that narrates just that page's content, so
the whole report can be understood by listening alone.

Deliberately colorful and icon-led (gradient header per subject, circular
mark-percentage rings, celebratory conclusion banner) rather than a plain
data table — the goal is something a parent actually wants to open and
look at, not just a readable one.

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

# Cycled by page index so each subject page gets its own distinct, cheerful
# header color instead of every page looking identical.
PAGE_THEMES = [
    ("#2563eb", "#0ea5e9"),
    ("#7c3aed", "#c026d3"),
    ("#0d9488", "#22c55e"),
    ("#ea580c", "#f59e0b"),
    ("#db2777", "#f43f5e"),
    ("#4f46e5", "#06b6d4"),
    ("#16a34a", "#84cc16"),
    ("#9333ea", "#4f46e5"),
]
CONCLUSION_THEME = ("#1e3a8a", "#0e7490")

SUBJECT_ICONS = {
    "TELUGU": "\U0001f4d6", "HINDI": "\U0001f5e3️", "ENGLISH": "\U0001f524",
    "MATHS": "➕", "MATHEMATICS": "➕",
    "PHYSICAL SCIENCE": "\U0001f52c", "PHYSICS": "\U0001f52c", "CHEMISTRY": "\U0001f9ea",
    "BIOLOGY": "\U0001f331", "BIOLOGICAL SCIENCE": "\U0001f331", "SCIENCE": "\U0001f52c",
    "SOCIAL": "\U0001f30d", "SOCIAL STUDIES": "\U0001f30d", "SANSKRIT": "\U0001f549️",
    "URDU": "\U0001f5e3️", "COMPUTER SCIENCE": "\U0001f4bb", "COMPUTERS": "\U0001f4bb",
    "IT": "\U0001f4bb", "EVS": "\U0001f33f", "VALUE EDUCATION": "\U0001f31f",
}
DEFAULT_SUBJECT_ICON = "\U0001f4d8"


def _subject_icon(name: str) -> str:
    return SUBJECT_ICONS.get((name or "").strip().upper(), DEFAULT_SUBJECT_ICON)


PARENT_CSS = """
:root{color-scheme:light}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:#eef2f9;font:16px/1.55 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a;display:flex;flex-direction:column;min-height:100vh}
.topbar{position:sticky;top:0;z-index:3;background:linear-gradient(120deg,#1e3a8a,#2563eb 60%,#0e7490);color:#fff;padding:.7em 1em .6em;box-shadow:0 2px 10px rgba(0,0,0,.22)}
.topbar .school{font-weight:700;font-size:1em;text-align:center;opacity:.95}
.topbar .student{text-align:center;font-size:1.2em;font-weight:800;margin-top:.1em;text-shadow:0 1px 3px rgba(0,0,0,.25)}
.steps{display:flex;justify-content:center;gap:.3em;margin-top:.65em;flex-wrap:wrap;padding:0 .3em}
.step{width:1.6em;height:1.6em;border-radius:50%;background:rgba(255,255,255,.22);display:flex;align-items:center;justify-content:center;font-size:.8em;transition:all .2s ease;filter:grayscale(.6);opacity:.65}
.step.active{background:#f5b700;transform:scale(1.22);filter:none;opacity:1;box-shadow:0 2px 6px rgba(0,0,0,.3)}
.pagelabel{text-align:center;font-size:.8em;margin-top:.4em;opacity:.9;font-weight:600;letter-spacing:.3px}
main{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative}
.page{display:none;flex:1;overflow-y:auto;animation:pop .32s cubic-bezier(.2,.8,.3,1)}
.page.active{display:flex;flex-direction:column}
@keyframes pop{from{opacity:0;transform:scale(.97) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}
.hero{flex:none;padding:1.5em 1.2em 1.9em;text-align:center;color:#fff;border-radius:0 0 1.6em 1.6em;box-shadow:0 6px 16px rgba(0,0,0,.12);position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 85% -10%,rgba(255,255,255,.25),transparent 55%),radial-gradient(circle at -10% 110%,rgba(255,255,255,.18),transparent 50%)}
.hero-icon{position:relative;width:3.4em;height:3.4em;margin:0 auto .5em;border-radius:50%;background:rgba(255,255,255,.92);display:flex;align-items:center;justify-content:center;font-size:1.9em;box-shadow:0 4px 12px rgba(0,0,0,.25)}
.hero h1{position:relative;margin:0;font-size:1.6em;font-weight:800;letter-spacing:.3px;text-shadow:0 1px 3px rgba(0,0,0,.2)}
.hero .sub{position:relative;font-size:.85em;font-weight:600;opacity:.92;margin-top:.25em}
.body-pad{padding:1.1em 1.1em 1.6em;flex:1;display:flex;flex-direction:column}
.exam-rows{display:flex;flex-direction:column;gap:.7em;margin-top:1.1em}
.exam-row{background:#fff;border-radius:1em;padding:.7em .85em;display:flex;align-items:center;gap:.8em;box-shadow:0 2px 8px rgba(30,58,138,.1)}
.ring{--pct:0%;width:3.1em;height:3.1em;border-radius:50%;flex:none;background:conic-gradient(var(--ring-color,#2563eb) var(--pct),#e7ecf7 0);display:flex;align-items:center;justify-content:center}
.ring-inner{width:2.3em;height:2.3em;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:.72em;font-weight:800;color:#1e293b}
.exam-meta{flex:1}
.exam-meta .exam-name{font-weight:800;color:#1e3a8a;font-size:1.05em}
.exam-meta .exam-marks{font-size:.85em;color:#64748b;font-weight:600;margin-top:.1em}
.gr{display:inline-block;min-width:2.3em;text-align:center;border-radius:99px;padding:.2em .55em;color:#fff;font-weight:800;font-size:.85em;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.ga{background:#16a34a}.gb{background:#2563eb}.gc{background:#d97706}.gd{background:#ea580c}.gf{background:#dc2626}
.stars{margin-top:.6em;text-align:center;font-size:1.3em;letter-spacing:.15em}
.commentary{margin-top:1.1em;border-radius:1em;padding:1em 1.05em;font-size:1.05em;font-weight:600;line-height:1.5;display:flex;gap:.7em;align-items:flex-start;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.commentary .bubble{flex:none;width:1.9em;height:1.9em;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1em;background:rgba(255,255,255,.7)}
.commentary.good{background:linear-gradient(135deg,#dcfce7,#bbf7d0);color:#166534}
.commentary.mid{background:linear-gradient(135deg,#fef9c3,#fef08a);color:#854d0e}
.commentary.low{background:linear-gradient(135deg,#ffedd5,#fed7aa);color:#9a3412}
.commentary.fail{background:linear-gradient(135deg,#fee2e2,#fecaca);color:#991b1b}
.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:.8em;margin-top:1.2em}
.summary-box{background:#fff;border-radius:1em;padding:1em .8em;text-align:center;box-shadow:0 2px 8px rgba(30,58,138,.1)}
.summary-box .icon{font-size:1.5em;margin-bottom:.15em}
.summary-box .label{font-size:.76em;color:#64748b;text-transform:uppercase;letter-spacing:.5px;font-weight:700}
.summary-box .value{font-size:1.45em;font-weight:800;color:#0f172a;margin-top:.15em}
.result-pill{display:inline-block;border-radius:99px;padding:.25em 1em;font-weight:800;color:#fff;font-size:1.15em;margin-top:.2em;box-shadow:0 2px 6px rgba(0,0,0,.2)}
.result-pill.pass{background:linear-gradient(135deg,#22c55e,#16a34a)}
.result-pill.fail{background:linear-gradient(135deg,#f87171,#dc2626)}
.celebrate{margin-top:1.2em;text-align:center;background:linear-gradient(135deg,#fff7ed,#fef3c7);border-radius:1.1em;padding:1em 1em .9em;box-shadow:0 2px 10px rgba(217,119,6,.15)}
.celebrate .emoji-row{font-size:1.8em;letter-spacing:.2em;margin-bottom:.15em}
.celebrate .msg{font-weight:800;color:#92400e;font-size:1.1em}
.recap{margin-top:1.2em;display:flex;flex-direction:column;gap:.55em}
.recap-line{background:#fff;border-radius:.8em;padding:.65em .9em;font-size:.95em;box-shadow:0 1px 5px rgba(30,58,138,.08);display:flex;gap:.5em;align-items:flex-start}
.recap-line b{color:#1e3a8a}
.closing{margin-top:1.1em;background:linear-gradient(135deg,#eff6ff,#e0f2fe);border-radius:1.1em;padding:1em 1.1em;font-size:1em;line-height:1.55;box-shadow:0 1px 6px rgba(14,116,144,.1)}
.grow{flex:1 0 auto}
.navbar{position:sticky;bottom:0;z-index:3;background:#fff;border-top:1px solid #dbe4f3;display:flex;align-items:center;gap:.5em;padding:.6em .7em;box-shadow:0 -3px 10px rgba(0,0,0,.1)}
.navbar button{border:0;font:inherit;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4em;border-radius:99px;transition:transform .15s ease}
.navbar button:active{transform:scale(.95)}
.navbar button.nav{flex:1;padding:.85em .3em;background:#eef2f9;color:#1e3a8a;font-size:.95em}
.navbar button.nav:disabled{opacity:.3}
.navbar button.listen{flex:1.5;padding:.85em .3em;background:linear-gradient(135deg,#14b8c4,#0e7490);color:#fff;font-size:1em;box-shadow:0 3px 10px rgba(14,116,144,.35)}
.navbar button.listen.speaking{background:linear-gradient(135deg,#f87171,#dc2626);box-shadow:0 3px 10px rgba(220,38,38,.35)}
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
  var steps = Array.prototype.slice.call(document.querySelectorAll('.step'));
  var current = 0;
  var prevBtn = document.getElementById('prevBtn');
  var nextBtn = document.getElementById('nextBtn');
  var speakBtn = document.getElementById('speakBtn');
  var pageLabel = document.getElementById('pageLabel');

  function show(i){
    stopSpeech();
    pages.forEach(function(p, idx){ p.classList.toggle('active', idx === i); });
    steps.forEach(function(d, idx){ d.classList.toggle('active', idx === i); });
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
  <div class="steps">{steps}</div>
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


_GRADE_RING_COLOR = {"ga": "#16a34a", "gb": "#2563eb", "gc": "#d97706", "gd": "#ea580c", "gf": "#dc2626"}


def _render_grade_badge(g: str) -> str:
    if g == "-":
        return ""
    return f'<span class="gr {_grade_class(g)}">{_esc(g)}</span>'


def _render_marks_cell(v) -> str:
    return fmt_num(v) if isinstance(v, (int, float)) else str(v)


def _gradient_style(theme: tuple[str, str]) -> str:
    return f"background:linear-gradient(135deg,{theme[0]},{theme[1]})"


def _render_subject_page(student: dict, exam_defs: list[dict], settings, subject_name: str, theme: tuple[str, str]) -> str:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    exam_order = [e["key"] for e in exam_defs]
    facts = compute_subject_facts(student, exam_order, subject_name, max_marks)
    speech_te = build_subject_voice_telugu(facts, student["name"])
    speech_roman = build_subject_voice_romanized(facts, student["name"])
    icon = _subject_icon(subject_name)

    h = (
        f'<div class="hero" style="{_gradient_style(theme)}">'
        f'<div class="hero-icon">{icon}</div>'
        f'<h1>{_esc(subject_name)}</h1>'
        '<div class="sub">ఈ సబ్జెక్టులో ప్రదర్శన</div>'
        "</div>"
    )
    h += '<div class="body-pad"><div class="exam-rows">'
    for e in facts.history:
        ring_color = _GRADE_RING_COLOR.get(_grade_class(e.grade), "#2563eb") if e.grade != "-" else "#94a3b8"
        pct = 0.0
        if isinstance(e.marks, (int, float)) and e.max_marks:
            pct = max(0.0, min(100.0, e.marks * 100 / e.max_marks))
        h += (
            '<div class="exam-row">'
            f'<div class="ring" style="--pct:{pct:.0f}%;--ring-color:{ring_color}">'
            f'<div class="ring-inner">{round(pct)}%</div></div>'
            '<div class="exam-meta">'
            f'<div class="exam-name">{_esc(e.exam_key)}</div>'
            f'<div class="exam-marks">{_render_marks_cell(e.marks)} / {_render_marks_cell(e.max_marks)} marks</div>'
            "</div>"
            f"{_render_grade_badge(e.grade)}"
            "</div>"
        )
    h += "</div>"
    if facts.classification == "good":
        h += '<div class="stars">⭐⭐⭐</div>'
    h += f'<div class="commentary {facts.classification}"><span class="bubble">{icon}</span><span>{_esc(subject_commentary_telugu(facts))}</span></div>'
    h += '<div class="grow"></div></div>'

    return f'<section class="page" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def _render_conclusion_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)
    speech_te = build_voice_script_telugu(student, exam_order, class_strength, school_name)
    speech_roman = build_voice_script_romanized(student, exam_order, class_strength, school_name)

    h = (
        f'<div class="hero" style="{_gradient_style(CONCLUSION_THEME)}">'
        '<div class="hero-icon">\U0001f3c6</div>'
        "<h1>మొత్తం గ్రేడ్ &amp; ఫలితం</h1>"
        '<div class="sub">Overall Result</div>'
        "</div>"
    )
    h += '<div class="body-pad">'

    if facts is None:
        h += '<div class="grow"></div></div>'
        return f'<section class="page" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'

    is_pass = facts.grade not in ("D2", "-") or bool(re.search(r"PASS", facts.result_text or "", re.I))
    if facts.grade == "D2" or re.search(r"FAIL", facts.result_text or "", re.I):
        is_pass = False
        result_html = '<span class="result-pill fail">FAIL</span>'
    elif facts.grade != "-" or re.search(r"PASS", facts.result_text or "", re.I):
        result_html = '<span class="result-pill pass">PASS</span>'
    else:
        result_html = "-"

    h += '<div class="summary-grid">'
    h += f'<div class="summary-box"><div class="icon">\U0001f4ca</div><div class="label">మార్కులు / Marks</div><div class="value">{_render_marks_cell(facts.total)}</div></div>'
    h += f'<div class="summary-box"><div class="icon">\U0001f396️</div><div class="label">గ్రేడ్ / Grade</div><div class="value">{_render_grade_badge(facts.grade) or "-"}</div></div>'
    result_icon = "\U0001f389" if is_pass else "\U0001f4aa"
    h += f'<div class="summary-box"><div class="icon">{result_icon}</div><div class="label">ఫలితం / Result</div><div class="value">{result_html}</div></div>'
    if facts.last_rank is not None:
        rank_icon = "\U0001f3c6" if facts.last_rank <= 3 else "\U0001f396️"
        h += f'<div class="summary-box"><div class="icon">{rank_icon}</div><div class="label">ర్యాంకు / Rank</div><div class="value">{fmt_num(facts.last_rank)} / {facts.class_strength}</div></div>'
    if facts.attendance_pct is not None:
        att_icon = "\U0001f4c5" if facts.attendance_pct >= 75 else "⚠️"
        h += f'<div class="summary-box"><div class="icon">{att_icon}</div><div class="label">హాజరు / Attendance</div><div class="value">{facts.attendance_pct}%</div></div>'
    h += "</div>"

    if is_pass:
        h += (
            '<div class="celebrate"><div class="emoji-row">\U0001f389\U0001f38a\U0001f389</div>'
            '<div class="msg">అభినందనలు! Congratulations!</div></div>'
        )

    h += '<div class="recap">'
    if facts.good:
        h += f'<div class="recap-line">✅ <span><b>బలం (Strong):</b> {_esc(", ".join(facts.good))}</span></div>'
    if facts.fail:
        h += f'<div class="recap-line">❌ <span><b>ఫెయిల్ (Failed):</b> {_esc(", ".join(facts.fail))}</span></div>'
    if facts.low:
        h += f'<div class="recap-line">⚠️ <span><b>గమనిక (Needs attention):</b> {_esc(", ".join(facts.low))}</span></div>'
    h += "</div>"

    if facts.attendance_pct is not None and facts.attendance_pct < 75:
        h += '<div class="closing">⚠️ హాజరు తక్కువగా ఉంది; దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.</div>'
    h += '<div class="closing">❤️ పూర్తి వివరాల కోసం పైన వివరాలను వినండి, మీ పిల్లవాడి భవిష్యత్తు కోసం శుభాకాంక్షలు!</div>'
    h += '<div class="grow"></div></div>'

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

    pages_html = [
        _render_subject_page(student, exam_defs, settings, name, PAGE_THEMES[i % len(PAGE_THEMES)])
        for i, name in enumerate(subjects)
    ]
    pages_html.append(_render_conclusion_page(student, all_students, exam_defs, settings, school_name))

    # Mark the very first page active up front so there is no flash of
    # unstyled/empty content before READ_ALOUD_SCRIPT's show(0) runs.
    if pages_html:
        pages_html[0] = pages_html[0].replace('class="page"', 'class="page active"', 1)

    step_icons = [_subject_icon(name) for name in subjects] + ["\U0001f3c1"]
    steps = "".join(
        f'<span class="step{" active" if i == 0 else ""}">{icon}</span>' for i, icon in enumerate(step_icons)
    )

    return PAGE_SHELL.format(
        title=_esc(title),
        css=PARENT_CSS,
        school=_esc(school_name or "School"),
        student_name=_esc(student["name"]),
        steps=steps,
        pages="".join(pages_html),
        script=READ_ALOUD_SCRIPT,
    )
