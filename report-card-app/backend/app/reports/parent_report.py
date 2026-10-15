"""Renders the PARENT-facing report page — a completely different
presentation from card_render.py's dense printable card, built for a
parent (often in a rural area, sometimes unable to read comfortably) to
follow on a phone. Structure is fixed by design: one page per subject,
plus a final overall/conclusion page — (number of subjects + 1) pages
total — moved through via native vertical scroll-snap, one swipe up/down
per page, the same gesture as a reels/shorts feed rather than a labeled
Next/Back button. A floating "Listen" button narrates just the current
page's content, and each page's own script is self-contained (names the
student, the subject, and how many subjects remain) and ends by telling
the listener to swipe up — so the whole report can be understood by
listening alone, without ever needing to look at or read the screen.

Icon-led rather than a plain data table (circular mark-percentage rings,
a celebratory conclusion banner) so it's something a parent actually wants
to open, not just a readable one — but the palette itself is deliberately
restrained: white surfaces with the product's own navy as the one accent
color (matching the rest of the app), not a different gradient per page.
Color is still used where it carries real meaning — grade badges, the
pass/fail pill, the good/needs-attention commentary tint — just not as
page-to-page decoration.

The teacher-facing /batches/{id}/report route is untouched and keeps using
card_render.render_report_page — this module is only ever reached via
/api/public/report/{token}.
"""
from __future__ import annotations

import html
import re

from app.reports.numfmt import fmt_num
from app.reports.parent_subject import (
    build_conclusion_voice_romanized,
    build_conclusion_voice_telugu,
    build_subject_voice_romanized,
    build_subject_voice_telugu,
    compute_subject_facts,
    subject_commentary_telugu,
)
from app.reports.voice_script import _compute_facts

NAVY = "#1e3a8a"

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
html,body{margin:0;height:100%;overflow:hidden}
body{background:#f7f8fa;font:16px/1.55 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif;color:#0f172a;display:flex;flex-direction:column;height:100vh}
.topbar{position:sticky;top:0;z-index:3;background:#1e3a8a;color:#fff;padding:.7em 1em .6em}
.topbar .school{font-weight:700;font-size:1em;text-align:center;opacity:.9}
.topbar .student{text-align:center;font-size:1.2em;font-weight:800;margin-top:.1em}
.steps{display:flex;justify-content:center;gap:.3em;margin-top:.65em;flex-wrap:wrap;padding:0 .3em}
.step{width:1.6em;height:1.6em;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:.8em;transition:all .2s ease;filter:grayscale(.6);opacity:.65}
.step.active{background:#e9a400;transform:scale(1.18);filter:none;opacity:1}
.pagelabel{text-align:center;font-size:.8em;margin-top:.4em;opacity:.85;font-weight:600;letter-spacing:.3px}
main{flex:1;position:relative;overflow-y:auto;scroll-snap-type:y mandatory;scroll-behavior:smooth;-webkit-overflow-scrolling:touch}
.page{min-height:100%;display:flex;flex-direction:column;scroll-snap-align:start;scroll-snap-stop:always}
.hero{flex:none;padding:1.6em 1.2em 1.3em;text-align:center;background:#fff;border-bottom:1px solid #e7eaf0}
.hero-icon{width:3.2em;height:3.2em;margin:0 auto .6em;border-radius:12px;background:#1e3a8a;color:#fff;display:flex;align-items:center;justify-content:center;font-size:1.7em}
.hero h1{margin:0;font-size:1.5em;font-weight:800;letter-spacing:.2px;color:#0f172a}
.hero .sub{font-size:.85em;font-weight:600;color:#64748b;margin-top:.3em}
.body-pad{padding:1.1em 1.1em 8em;flex:1;display:flex;flex-direction:column}
.exam-rows{display:flex;flex-direction:column;gap:.7em;margin-top:1.1em}
.exam-row{background:#fff;border:1px solid #e7eaf0;border-radius:10px;padding:.7em .85em;display:flex;align-items:center;gap:.8em}
.ring{--pct:0%;width:3em;height:3em;border-radius:50%;flex:none;background:conic-gradient(var(--ring-color,#1e3a8a) var(--pct),#e7eaf0 0);display:flex;align-items:center;justify-content:center}
.ring-inner{width:2.25em;height:2.25em;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:.7em;font-weight:800;color:#1e293b}
.exam-meta{flex:1}
.exam-meta .exam-name{font-weight:800;color:#1e3a8a;font-size:1.05em}
.exam-meta .exam-marks{font-size:.85em;color:#64748b;font-weight:600;margin-top:.1em}
.gr{display:inline-block;min-width:2.3em;text-align:center;border-radius:6px;padding:.2em .5em;color:#fff;font-weight:800;font-size:.85em}
.ga{background:#16a34a}.gb{background:#1e3a8a}.gc{background:#d97706}.gd{background:#ea580c}.gf{background:#dc2626}
.stars{margin-top:.6em;text-align:center;font-size:1.3em;letter-spacing:.15em}
.commentary{margin-top:1.1em;border-radius:10px;padding:1em 1.05em;font-size:1.05em;font-weight:600;line-height:1.5;display:flex;gap:.7em;align-items:flex-start}
.commentary .bubble{flex:none;width:1.9em;height:1.9em;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.1em;background:rgba(255,255,255,.6)}
.commentary.good{background:#eafaf0;color:#166534;border:1px solid #bbf7d0}
.commentary.mid{background:#fef9e8;color:#854d0e;border:1px solid #fde68a}
.commentary.low{background:#fff4ea;color:#9a3412;border:1px solid #fed7aa}
.commentary.fail{background:#fdecec;color:#991b1b;border:1px solid #fecaca}
.summary-grid{display:grid;grid-template-columns:1fr 1fr;gap:.8em;margin-top:1.2em}
.summary-box{background:#fff;border:1px solid #e7eaf0;border-radius:10px;padding:1em .8em;text-align:center}
.summary-box .icon{font-size:1.5em;margin-bottom:.15em}
.summary-box .label{font-size:.76em;color:#64748b;text-transform:uppercase;letter-spacing:.5px;font-weight:700}
.summary-box .value{font-size:1.45em;font-weight:800;color:#0f172a;margin-top:.15em}
.result-pill{display:inline-block;border-radius:6px;padding:.25em 1em;font-weight:800;color:#fff;font-size:1.15em;margin-top:.2em}
.result-pill.pass{background:#16a34a}
.result-pill.fail{background:#dc2626}
.celebrate{margin-top:1.2em;text-align:center;background:#fff8e8;border:1px solid #fde68a;border-radius:10px;padding:1em 1em .9em}
.celebrate .emoji-row{font-size:1.8em;letter-spacing:.2em;margin-bottom:.15em}
.celebrate .msg{font-weight:800;color:#92400e;font-size:1.1em}
.recap{margin-top:1.2em;display:flex;flex-direction:column;gap:.55em}
.recap-line{background:#fff;border:1px solid #e7eaf0;border-radius:10px;padding:.65em .9em;font-size:.95em;display:flex;gap:.5em;align-items:flex-start}
.recap-line b{color:#1e3a8a}
.closing{margin-top:1.1em;background:#eef2fb;border:1px solid #dbe3f5;border-radius:10px;padding:1em 1.1em;font-size:1em;line-height:1.55}
.grow{flex:1 0 auto}
.bottom-fade{position:fixed;left:0;right:0;bottom:0;height:8.5em;background:linear-gradient(to bottom,rgba(247,248,250,0) 0%,#f7f8fa 65%);pointer-events:none;z-index:4}
.listen-fab{position:fixed;left:50%;bottom:1.3em;transform:translateX(-50%);z-index:5;border:0;font:inherit;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.5em;border-radius:99px;padding:.9em 1.6em;background:#1e3a8a;color:#fff;font-size:1em;box-shadow:3px 3px 0 0 #e9a400;transition:transform .12s ease}
.listen-fab:active{transform:translateX(-50%) scale(.97)}
.listen-fab.speaking{background:#dc2626;box-shadow:3px 3px 0 0 #fca5a5}
.swipe-hint{position:fixed;left:50%;bottom:6.3em;transform:translateX(-50%);z-index:5;font-size:.78em;font-weight:600;color:#475569;background:rgba(255,255,255,.92);padding:.35em .9em;border-radius:99px;box-shadow:0 1px 6px rgba(0,0,0,.1);display:flex;align-items:center;gap:.35em;animation:hintbob 1.6s ease-in-out infinite}
.swipe-hint.hidden{display:none}
@keyframes hintbob{0%,100%{transform:translateX(-50%) translateY(0)}50%{transform:translateX(-50%) translateY(-4px)}}
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

  var audioEl = null; // currently-playing real Bhashini audio, if any

  function stopSpeech(){
    if('speechSynthesis' in window) speechSynthesis.cancel();
    if(audioEl){ audioEl.pause(); audioEl.src = ''; audioEl = null; }
    if(speaking){ speaking.classList.remove('speaking'); speaking.textContent = speaking.dataset.label; speaking = null; }
  }

  // Falls back to the browser's own voice when real audio isn't available
  // (Bhashini not configured, a failed call, or no token on this page).
  function speakWithBrowser(page){
    if(!('speechSynthesis' in window)){ stopSpeech(); alert('Reading aloud is not supported in this browser.'); return; }
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
      if(!text){ stopSpeech(); return; }
      var utter = new SpeechSynthesisUtterance(text);
      utter.lang = lang;
      utter.onend = utter.onerror = function(){ stopSpeech(); };
      speechSynthesis.speak(utter);
    });
  }

  var main = document.querySelector('main');
  var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
  var steps = Array.prototype.slice.call(document.querySelectorAll('.step'));
  var current = 0;
  var speakBtn = document.getElementById('speakBtn');
  var pageLabel = document.getElementById('pageLabel');
  var swipeHint = document.getElementById('swipeHint');
  var publicToken = main.dataset.token || '';

  // Navigation is native vertical scroll-snap (swipe up/down, like a
  // reels/shorts feed) rather than click-driven — this just tracks which
  // page the scroll has landed on, for the dots/label/stopping audio.
  function setCurrent(i){
    if(i === current) return;
    stopSpeech();
    current = i;
    steps.forEach(function(d, idx){ d.classList.toggle('active', idx === i); });
    pageLabel.textContent = (i + 1) + ' / ' + pages.length;
    swipeHint.classList.toggle('hidden', i === pages.length - 1);
  }

  // Figures out which page is "current" from main's own scroll position
  // instead of IntersectionObserver — more predictable across mobile
  // browsers, especially right at the last page, where a dynamic address
  // bar changing the real viewport height can make 100vh-based
  // intersection thresholds miss entirely.
  function updateCurrentFromScroll(){
    var mid = main.scrollTop + main.clientHeight / 2;
    var idx = 0;
    for(var i = 0; i < pages.length; i++){
      if(pages[i].offsetTop <= mid) idx = i;
    }
    setCurrent(idx);
  }
  var scrollTimer = null;
  main.addEventListener('scroll', function(){
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(updateCurrentFromScroll, 100);
  });

  speakBtn.addEventListener('click', function(){
    if(speaking){ stopSpeech(); return; }
    var page = pages[current];
    var pageId = page.getAttribute('data-page-id');

    speakBtn.dataset.label = speakBtn.dataset.label || speakBtn.textContent;
    speakBtn.textContent = '\\u23f9 Stop';
    speakBtn.classList.add('speaking');
    speaking = speakBtn;

    if(!pageId || !publicToken){
      speakWithBrowser(page);
      return;
    }

    // Try real Telugu audio (Bhashini) first; any failure — not
    // configured, API error, network issue — falls back to the browser's
    // own voice so "Listen" always does something either way.
    fetch('/api/public/report/' + publicToken + '/voice/' + encodeURIComponent(pageId))
      .then(function(resp){
        if(!resp.ok) throw new Error('voice endpoint returned ' + resp.status);
        return resp.blob();
      })
      .then(function(blob){
        if(speaking !== speakBtn) return; // user already stopped/switched pages
        audioEl = new Audio(URL.createObjectURL(blob));
        audioEl.onended = audioEl.onerror = function(){ stopSpeech(); };
        audioEl.play();
      })
      .catch(function(){
        if(speaking === speakBtn) speakWithBrowser(page);
      });
  });

  pageLabel.textContent = '1 / ' + pages.length;
  swipeHint.classList.toggle('hidden', pages.length <= 1);
  window.addEventListener('beforeunload', function(){ try { speechSynthesis.cancel(); } catch(e){} });
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
<main data-token="{token}">{pages}</main>
<div class="bottom-fade"></div>
<div class="swipe-hint" id="swipeHint">⬆ తదుపరి కోసం పైకి స్వైప్ చేయండి</div>
<button type="button" class="listen-fab" id="speakBtn">\U0001f50a వినండి / Listen</button>
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


_GRADE_RING_COLOR = {"ga": "#16a34a", "gb": NAVY, "gc": "#d97706", "gd": "#ea580c", "gf": "#dc2626"}


def _render_grade_badge(g: str) -> str:
    if g == "-":
        return ""
    return f'<span class="gr {_grade_class(g)}">{_esc(g)}</span>'


def _render_marks_cell(v) -> str:
    return fmt_num(v) if isinstance(v, (int, float)) else str(v)


def _discover_subjects(student: dict, exam_defs: list[dict]) -> list[str]:
    exams_present = [e["key"] for e in exam_defs if e["key"] in student["exams"]]
    subjects: list[str] = []
    for key in exams_present:
        for x in student["exams"][key]["subjects"]:
            if x["name"] not in subjects:
                subjects.append(x["name"])
    return subjects


def _render_subject_page(student: dict, exam_defs: list[dict], settings, subject_name: str, index: int, total: int, school_name: str) -> str:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    exam_order = [e["key"] for e in exam_defs]
    facts = compute_subject_facts(student, exam_order, subject_name, max_marks)
    is_last = index == total - 1
    parent_name = (student.get("father") or "").strip()
    speech_te = build_subject_voice_telugu(facts, student["name"], index, total, is_last, school_name, parent_name)
    speech_roman = build_subject_voice_romanized(facts, student["name"], index, total, is_last, school_name, parent_name)
    icon = _subject_icon(subject_name)

    h = (
        '<div class="hero">'
        f'<div class="hero-icon">{icon}</div>'
        f'<h1>{_esc(subject_name)}</h1>'
        '<div class="sub">ఈ సబ్జెక్టులో ప్రదర్శన</div>'
        "</div>"
    )
    h += '<div class="body-pad"><div class="exam-rows">'
    for e in facts.history:
        ring_color = _GRADE_RING_COLOR.get(_grade_class(e.grade), NAVY) if e.grade != "-" else "#94a3b8"
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

    return f'<section class="page" data-page-id="{_esc(subject_name)}" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def _render_conclusion_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)
    speech_te = build_conclusion_voice_telugu(student, exam_order, class_strength, school_name)
    speech_roman = build_conclusion_voice_romanized(student, exam_order, class_strength, school_name)

    h = (
        '<div class="hero">'
        '<div class="hero-icon">\U0001f3c6</div>'
        "<h1>మొత్తం గ్రేడ్ &amp; ఫలితం</h1>"
        '<div class="sub">Overall Result</div>'
        "</div>"
    )
    h += '<div class="body-pad">'

    if facts is None:
        h += '<div class="grow"></div></div>'
        return f'<section class="page" data-page-id="conclusion" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'

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

    return f'<section class="page" data-page-id="conclusion" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def render_parent_report_page(
    student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, title: str = "Report Card", token: str = ""
) -> str:
    """`student` is the single student this link belongs to (parent links
    always resolve to exactly one student — see api/public.py). Builds
    (number of subjects + 1) pages: one per subject in discovery order,
    then a final overall/conclusion page. `token` is embedded for
    READ_ALOUD_SCRIPT to call the real-audio voice route."""
    subjects = _discover_subjects(student, exam_defs)

    pages_html = [_render_subject_page(student, exam_defs, settings, name, i, len(subjects), school_name) for i, name in enumerate(subjects)]
    pages_html.append(_render_conclusion_page(student, all_students, exam_defs, settings, school_name))

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
        token=_esc(token),
        pages="".join(pages_html),
        script=READ_ALOUD_SCRIPT,
    )


def get_speech_text(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, page: str) -> str | None:
    """Recomputes the Telugu narration for one page (`page` is a subject
    name, or the literal "conclusion") without rendering any HTML — used by
    the real-audio voice route so it always synthesizes exactly what that
    page would read aloud itself, never client-supplied text. Returns None
    if `page` isn't a real subject/conclusion for this student."""
    if page == "conclusion":
        exam_order = [e["key"] for e in exam_defs]
        class_strength = settings.class_strength_override or len(all_students)
        return build_conclusion_voice_telugu(student, exam_order, class_strength, school_name) or None

    subjects = _discover_subjects(student, exam_defs)
    if page not in subjects:
        return None
    index = subjects.index(page)
    is_last = index == len(subjects) - 1

    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    exam_order = [e["key"] for e in exam_defs]
    facts = compute_subject_facts(student, exam_order, page, max_marks)
    if not facts.history:
        return None
    parent_name = (student.get("father") or "").strip()
    return build_subject_voice_telugu(facts, student["name"], index, len(subjects), is_last, school_name, parent_name) or None
