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


PARENT_CSS = """
:root{
  color-scheme:light;
  --navy:#1e3a8a;
  --ink:#0f172a;
  --muted:#64748b;
  --line:#e5e7eb;
  --good:#15803d;
  --warn:#b45309;
  --bad:#b91c1c;
  --gold:#b08a2e;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{background:#f6f7f9;font:16px/1.5 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif;color:var(--ink);display:flex;flex-direction:column;height:100vh;-webkit-font-smoothing:antialiased}
.topbar{position:sticky;top:0;z-index:3;background:var(--navy);color:#fff;padding:.85em 1.2em .75em}
.topbar .school{font-weight:600;font-size:.82em;text-align:center;opacity:.72;letter-spacing:.2px}
.topbar .student{text-align:center;font-size:1.1em;font-weight:600;margin-top:.15em;letter-spacing:.1px}
.progressbar{display:flex;gap:.3em;margin-top:.8em}
.seg{flex:1;height:3px;border-radius:2px;background:rgba(255,255,255,.22);overflow:hidden}
.seg .fill{height:100%;width:0;background:#fff;transition:width .25s ease}
.seg.active .fill{width:100%}
.seg.done .fill{width:100%;background:rgba(255,255,255,.6)}
.pagelabel{text-align:center;font-size:.72em;margin-top:.5em;opacity:.6;font-weight:500;letter-spacing:.4px}
main{flex:1;position:relative;overflow-y:auto;scroll-snap-type:y mandatory;scroll-behavior:smooth;-webkit-overflow-scrolling:touch}
.page{min-height:100%;display:flex;flex-direction:column;scroll-snap-align:start;scroll-snap-stop:always}
.hero{flex:none;padding:2em 1.3em 1.5em;text-align:center;background:#fff;border-bottom:1px solid var(--line)}
.eyebrow{font-size:.72em;font-weight:600;letter-spacing:1px;color:var(--muted);text-transform:uppercase}
.hero h1{margin:.3em 0 0;font-size:1.6em;font-weight:700;letter-spacing:.1px;color:var(--ink)}
.hero .sub{font-size:.85em;font-weight:400;color:var(--muted);margin-top:.35em}
.trend-note{margin-top:.7em;font-size:.82em;font-weight:500;color:var(--muted)}
.trend-note.up{color:var(--good)}
.trend-note.down{color:var(--bad)}
.body-pad{padding:1.3em 1.2em 8em;flex:1;display:flex;flex-direction:column}
.panel{background:#fff;border:1px solid var(--line);border-radius:14px;margin-top:1.3em}
.panel:first-child{margin-top:0}
.exam-row{padding:.95em 1.05em;display:flex;align-items:center;gap:.9em}
.exam-row+.exam-row{border-top:1px solid var(--line)}
.ring{--pct:0%;width:2.7em;height:2.7em;border-radius:50%;flex:none;background:conic-gradient(var(--ring-color,var(--navy)) var(--pct),var(--line) 0);display:flex;align-items:center;justify-content:center}
.ring-inner{width:2.05em;height:2.05em;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:.65em;font-weight:600;color:var(--ink)}
.exam-meta{flex:1}
.exam-meta .exam-name{font-weight:600;color:var(--ink);font-size:1em}
.exam-meta .exam-marks{font-size:.84em;color:var(--muted);margin-top:.1em}
.gr{display:inline-block;min-width:2.1em;text-align:center;border-radius:5px;padding:.2em .5em;color:#fff;font-weight:600;font-size:.8em}
.ga{background:var(--good)}.gb{background:var(--navy)}.gc{background:var(--warn)}.gd{background:#c2410c}.gf{background:var(--bad)}
.commentary{margin-top:1.3em;background:#fff;border:1px solid var(--line);border-left:3px solid var(--line);border-radius:10px;padding:1.05em 1.1em}
.commentary .ctitle{font-size:.7em;text-transform:uppercase;letter-spacing:.6px;font-weight:600;color:var(--muted)}
.commentary .ctext{margin-top:.4em;font-size:.98em;line-height:1.5;color:var(--ink)}
.commentary.good{border-left-color:var(--good)}
.commentary.mid{border-left-color:var(--warn)}
.commentary.low{border-left-color:var(--warn)}
.commentary.fail{border-left-color:var(--bad)}
.summary-grid{display:grid;grid-template-columns:1fr 1fr;padding:.3em}
.summary-box{padding:1em .7em;text-align:center}
.summary-box .label{font-size:.72em;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;font-weight:600}
.summary-box .value{font-size:1.4em;font-weight:600;color:var(--ink);margin-top:.25em}
.result-pill{display:inline-block;border-radius:5px;padding:.2em .85em;font-weight:600;color:#fff;font-size:1.05em;margin-top:.1em}
.result-pill.pass{background:var(--good)}
.result-pill.fail{background:var(--bad)}
.recap-line{padding:.8em 1.05em;font-size:.95em;line-height:1.5}
.recap-line+.recap-line{border-top:1px solid var(--line)}
.recap-line .tag{display:inline-block;font-size:.7em;font-weight:600;text-transform:uppercase;letter-spacing:.4px;color:var(--muted);margin-right:.5em}
.closing{margin-top:1.3em;padding:1em 0 0;font-size:.92em;line-height:1.55;color:var(--muted)}
.grow{flex:1 0 auto}

/* Finale page: a single deliberate departure from white — a solid navy
   band (no gradient, no decoration), distinguished by restraint rather
   than ornament. A thin gold rule is the only accent, used once. */
.hero.finale{background:var(--navy);border-bottom:none}
.hero.finale h1{color:#fff}
.hero.finale .sub{color:#c7d0e8}
.hero.finale .rule{width:2.4em;height:2px;background:var(--gold);margin:.9em auto 0;border-radius:1px}

.share-row{margin-top:1.4em;display:flex;justify-content:center}
.share-btn{border:1px solid var(--line);background:#fff;color:var(--ink);font:inherit;font-weight:500;font-size:.88em;border-radius:8px;padding:.6em 1.2em;cursor:pointer}
.share-btn:active{opacity:.7}

.bottom-fade{position:fixed;left:0;right:0;bottom:0;height:8.5em;background:linear-gradient(to bottom,rgba(246,247,249,0) 0%,#f6f7f9 65%);pointer-events:none;z-index:4}
.listen-fab{position:fixed;left:50%;bottom:1.3em;transform:translateX(-50%);z-index:5;border:0;font:inherit;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.5em;border-radius:99px;padding:.85em 1.6em;background:var(--navy);color:#fff;font-size:.96em;box-shadow:0 4px 14px rgba(30,58,138,.3);transition:transform .12s ease,background .2s ease}
.listen-fab:active{transform:translateX(-50%) scale(.97)}
.listen-fab.loading{background:#475569;cursor:wait}
.listen-fab.loading .spinner{width:1em;height:1em;border-radius:50%;border:.15em solid rgba(255,255,255,.35);border-top-color:#fff;animation:spin .7s linear infinite}
.listen-fab.speaking{background:var(--bad)}
.listen-fab.error{background:var(--warn)}
@keyframes spin{to{transform:rotate(360deg)}}
.swipe-hint{position:fixed;left:50%;bottom:6.3em;transform:translateX(-50%);z-index:5;font-size:.76em;font-weight:500;color:var(--muted);background:rgba(255,255,255,.95);padding:.35em .9em;border-radius:99px;box-shadow:0 1px 6px rgba(0,0,0,.08);transition:opacity .25s ease}
.swipe-hint.hidden{opacity:0;pointer-events:none}

/* Base state for content that fades/settles in once its page becomes
   current — never opacity:0 by default, so a page is always fully
   visible even if JS never runs (no-JS / slow-script fallback). The
   .enter class, added transiently by script, is what actually plays the
   motion; removing this class (or JS not running) just leaves it visible. */
.hero,.body-pad{opacity:1}
.hero.enter,.body-pad.enter{animation:content-in .4s ease both}
@keyframes content-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}

@media (prefers-reduced-motion: reduce){
  .ring,.listen-fab,.swipe-hint,.hero.enter,.body-pad.enter,.seg .fill{animation:none!important;transition:none!important}
}
"""

READ_ALOUD_SCRIPT = """
<script>
(function(){
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // speakState: null (idle) | 'loading' (request/synthesis in flight,
  // nothing audible yet) | 'speaking' (actually playing) | 'error'
  // (both the real-audio fetch and the browser fallback failed).
  var speakState = null;
  var speakBtn = document.getElementById('speakBtn');
  var idleLabel = speakBtn.textContent;
  var errorTimer = null;

  function setSpeakState(state){
    speakState = state;
    clearTimeout(errorTimer);
    speakBtn.classList.remove('loading', 'speaking', 'error');
    if(state === 'loading'){
      speakBtn.innerHTML = '<span class="spinner"></span> లోడ్ అవుతోంది…';
      speakBtn.classList.add('loading');
    } else if(state === 'speaking'){
      speakBtn.textContent = '\\u23f9 Stop';
      speakBtn.classList.add('speaking');
    } else if(state === 'error'){
      speakBtn.textContent = '\\u26a0\\ufe0f వినలేకపోయాం';
      speakBtn.classList.add('error');
      errorTimer = setTimeout(function(){ if(speakState === 'error') setSpeakState(null); }, 2200);
    } else {
      speakBtn.textContent = idleLabel;
    }
  }

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
  var speakToken = 0; // bumped on every stop/new request so stale async callbacks are ignored

  function stopSpeech(){
    speakToken += 1;
    if('speechSynthesis' in window) speechSynthesis.cancel();
    if(audioEl){ audioEl.pause(); audioEl.src = ''; audioEl = null; }
    setSpeakState(null);
  }

  // Falls back to the browser's own voice when real audio isn't available
  // (Bhashini not configured, a failed call, or no token on this page).
  function speakWithBrowser(page, myToken){
    if(!('speechSynthesis' in window)){ setSpeakState('error'); return; }
    getVoicesAsync().then(function(voices){
      if(myToken !== speakToken) return; // superseded by a stop/new request
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
      if(!text){ setSpeakState('error'); return; }
      var utter = new SpeechSynthesisUtterance(text);
      utter.lang = lang;
      utter.onstart = function(){ if(myToken === speakToken) setSpeakState('speaking'); };
      utter.onend = function(){ if(myToken === speakToken) setSpeakState(null); };
      utter.onerror = function(){ if(myToken === speakToken) setSpeakState('error'); };
      speechSynthesis.speak(utter);
    });
  }

  var main = document.querySelector('main');
  var pages = Array.prototype.slice.call(document.querySelectorAll('.page'));
  var segs = Array.prototype.slice.call(document.querySelectorAll('.seg'));
  var current = 0;
  var hasSwiped = false;
  var pageLabel = document.getElementById('pageLabel');
  var swipeHint = document.getElementById('swipeHint');
  var publicToken = main.dataset.token || '';

  function animateRing(ring){
    var target = parseFloat(ring.getAttribute('data-pct') || '0');
    var inner = ring.querySelector('.ring-inner');
    if(reduceMotion){ ring.style.setProperty('--pct', target + '%'); return; }
    ring.style.setProperty('--pct', '0%');
    if(inner) inner.textContent = '0%';
    var start = null, duration = 700;
    function step(ts){
      if(start === null) start = ts;
      var p = Math.min(1, (ts - start) / duration);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = target * eased;
      ring.style.setProperty('--pct', val + '%');
      if(inner) inner.textContent = Math.round(val) + '%';
      if(p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // Plays a page's entrance once (ring fill, content settle-in). Guarded
  // by data-animated so revisiting an already-seen page by scrolling back
  // up doesn't replay the animation every time.
  function activatePage(page){
    if(page.dataset.animated) return;
    page.dataset.animated = '1';
    var hero = page.querySelector('.hero');
    var body = page.querySelector('.body-pad');
    if(!reduceMotion){
      if(hero){ hero.classList.add('enter'); hero.addEventListener('animationend', function(){ hero.classList.remove('enter'); }, { once: true }); }
      if(body){ body.classList.add('enter'); body.addEventListener('animationend', function(){ body.classList.remove('enter'); }, { once: true }); }
    }
    Array.prototype.forEach.call(page.querySelectorAll('.ring'), animateRing);
  }

  // Navigation is native vertical scroll-snap (swipe up/down, like a
  // reels/shorts feed) rather than click-driven — this just tracks which
  // page the scroll has landed on, for the progress bar/label/stopping audio.
  function setCurrent(i){
    if(i === current){ activatePage(pages[i]); return; }
    stopSpeech();
    if(current !== i) hasSwiped = true;
    current = i;
    segs.forEach(function(s, idx){
      s.classList.toggle('active', idx === i);
      s.classList.toggle('done', idx < i);
    });
    pageLabel.textContent = (i + 1) + ' / ' + pages.length;
    swipeHint.classList.toggle('hidden', hasSwiped || i === pages.length - 1);
    activatePage(pages[i]);
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
    if(speakState === 'loading' || speakState === 'speaking'){ stopSpeech(); return; }
    var myToken = ++speakToken;
    var page = pages[current];
    var pageId = page.getAttribute('data-page-id');

    setSpeakState('loading');

    if(!pageId || !publicToken){
      speakWithBrowser(page, myToken);
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
        if(myToken !== speakToken) return; // user already stopped/switched pages/pages
        audioEl = new Audio(URL.createObjectURL(blob));
        audioEl.onended = function(){ if(myToken === speakToken) stopSpeech(); };
        audioEl.onerror = function(){ if(myToken === speakToken) speakWithBrowser(page, myToken); };
        // The play() Promise resolving is the reliable cross-browser signal
        // that playback actually started — the 'playing' event alone isn't
        // consistently fired for a freshly created Audio() in every engine.
        audioEl.play().then(function(){
          if(myToken === speakToken) setSpeakState('speaking');
        }).catch(function(){
          if(myToken === speakToken) speakWithBrowser(page, myToken);
        });
      })
      .catch(function(){
        if(myToken === speakToken) speakWithBrowser(page, myToken);
      });
  });

  var shareBtn = document.getElementById('shareBtn');
  if(shareBtn){
    shareBtn.addEventListener('click', function(){
      var text = shareBtn.getAttribute('data-share-text') || '';
      if(navigator.share){
        navigator.share({ text: text }).catch(function(){});
      } else if(navigator.clipboard){
        navigator.clipboard.writeText(text).then(function(){
          var label = shareBtn.textContent;
          shareBtn.textContent = '\\u2705 కాపీ అయ్యింది';
          setTimeout(function(){ shareBtn.textContent = label; }, 1600);
        }).catch(function(){});
      }
    });
  }

  pageLabel.textContent = '1 / ' + pages.length;
  swipeHint.classList.toggle('hidden', pages.length <= 1);
  activatePage(pages[0]);
  window.addEventListener('beforeunload', function(){ try { speechSynthesis.cancel(); } catch(e){} });
})();
</script>
"""

PAGE_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700;800&family=Noto+Sans+Telugu:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body>
<div class="topbar">
  <div class="school">{school}</div>
  <div class="student">{student_name}</div>
  <div class="progressbar">{steps}</div>
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


_GRADE_RING_COLOR = {"ga": "#15803d", "gb": NAVY, "gc": "#b45309", "gd": "#c2410c", "gf": "#b91c1c"}

_TREND_NOTE = {
    "up": "▲ మెరుగుపడింది",
    "down": "▼ తగ్గింది",
    "flat": "స్థిరంగా ఉంది",
}


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

    h = (
        '<div class="hero">'
        f'<div class="eyebrow">Subject {index + 1} of {total}</div>'
        f'<h1>{_esc(subject_name)}</h1>'
        '<div class="sub">ఈ సబ్జెక్టులో ప్రదర్శన</div>'
    )
    if facts.trend:
        h += f'<div class="trend-note {facts.trend}">{_TREND_NOTE[facts.trend]}</div>'
    h += "</div>"
    h += '<div class="body-pad"><div class="panel">'
    for e in facts.history:
        ring_color = _GRADE_RING_COLOR.get(_grade_class(e.grade), NAVY) if e.grade != "-" else "#94a3b8"
        pct = 0.0
        if isinstance(e.marks, (int, float)) and e.max_marks:
            pct = max(0.0, min(100.0, e.marks * 100 / e.max_marks))
        h += (
            '<div class="exam-row">'
            f'<div class="ring" data-pct="{pct:.0f}" style="--pct:{pct:.0f}%;--ring-color:{ring_color}">'
            f'<div class="ring-inner">{round(pct)}%</div></div>'
            '<div class="exam-meta">'
            f'<div class="exam-name">{_esc(e.exam_key)}</div>'
            f'<div class="exam-marks">{_render_marks_cell(e.marks)} / {_render_marks_cell(e.max_marks)} marks</div>'
            "</div>"
            f"{_render_grade_badge(e.grade)}"
            "</div>"
        )
    h += "</div>"
    h += (
        f'<div class="commentary {facts.classification}">'
        '<div class="ctitle">How they did</div>'
        f'<div class="ctext">{_esc(subject_commentary_telugu(facts))}</div>'
        "</div>"
    )
    h += '<div class="grow"></div></div>'

    return f'<section class="page" data-page-id="{_esc(subject_name)}" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def _render_finale_hero() -> str:
    return (
        '<div class="hero finale">'
        "<h1>మొత్తం గ్రేడ్ &amp; ఫలితం</h1>"
        '<div class="sub">Overall Result</div>'
        '<div class="rule"></div>'
        "</div>"
    )


def _render_conclusion_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)
    speech_te = build_conclusion_voice_telugu(student, exam_order, class_strength, school_name)
    speech_roman = build_conclusion_voice_romanized(student, exam_order, class_strength, school_name)

    if facts is None:
        h = _render_finale_hero() + '<div class="body-pad"><div class="grow"></div></div>'
        return f'<section class="page" data-page-id="conclusion" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'

    is_pass = facts.grade not in ("D2", "-") or bool(re.search(r"PASS", facts.result_text or "", re.I))
    if facts.grade == "D2" or re.search(r"FAIL", facts.result_text or "", re.I):
        is_pass = False
        result_html = '<span class="result-pill fail">FAIL</span>'
    elif facts.grade != "-" or re.search(r"PASS", facts.result_text or "", re.I):
        result_html = '<span class="result-pill pass">PASS</span>'
    else:
        result_html = "-"

    h = _render_finale_hero()
    h += '<div class="body-pad">'
    h += '<div class="panel"><div class="summary-grid">'
    h += f'<div class="summary-box"><div class="label">Marks</div><div class="value">{_render_marks_cell(facts.total)}</div></div>'
    h += f'<div class="summary-box"><div class="label">Grade</div><div class="value">{_render_grade_badge(facts.grade) or "-"}</div></div>'
    h += f'<div class="summary-box"><div class="label">Result</div><div class="value">{result_html}</div></div>'
    if facts.last_rank is not None:
        h += f'<div class="summary-box"><div class="label">Rank</div><div class="value">{fmt_num(facts.last_rank)} / {facts.class_strength}</div></div>'
    if facts.attendance_pct is not None:
        h += f'<div class="summary-box"><div class="label">Attendance</div><div class="value">{facts.attendance_pct}%</div></div>'
    h += "</div></div>"

    if facts.good or facts.fail or facts.low:
        h += '<div class="panel">'
        if facts.good:
            h += f'<div class="recap-line"><span class="tag">Strong</span>{_esc(", ".join(facts.good))}</div>'
        if facts.fail:
            h += f'<div class="recap-line"><span class="tag">Failed</span>{_esc(", ".join(facts.fail))}</div>'
        if facts.low:
            h += f'<div class="recap-line"><span class="tag">Needs attention</span>{_esc(", ".join(facts.low))}</div>'
        h += "</div>"

    if facts.attendance_pct is not None and facts.attendance_pct < 75:
        h += '<div class="closing">హాజరు తక్కువగా ఉంది; దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.</div>'
    h += '<div class="closing">పూర్తి వివరాల కోసం పైన వివరాలను వినండి, మీ పిల్లవాడి భవిష్యత్తు కోసం శుభాకాంక్షలు!</div>'

    # Share text intentionally carries only what's already shown on this
    # page — the student's own name and these same facts — never the
    # private report link itself, so forwarding it can't hand someone
    # else access to the report.
    share_parts = [student["name"]]
    if isinstance(facts.total, (int, float)):
        share_parts.append(f"{fmt_num(facts.total)} marks")
    if facts.grade != "-":
        share_parts.append(f"Grade {facts.grade}")
    share_parts.append("PASS" if is_pass else "FAIL")
    if facts.last_rank is not None:
        share_parts.append(f"Rank {fmt_num(facts.last_rank)}/{facts.class_strength}")
    if facts.attendance_pct is not None:
        share_parts.append(f"Attendance {facts.attendance_pct}%")
    share_text = " · ".join(share_parts)
    h += (
        '<div class="share-row">'
        f'<button type="button" class="share-btn" id="shareBtn" data-share-text="{_esc(share_text)}">'
        "షేర్ / Share</button>"
        "</div>"
    )

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

    total_pages = len(subjects) + 1
    segs = "".join(f'<div class="seg{" active" if i == 0 else ""}"><div class="fill"></div></div>' for i in range(total_pages))

    return PAGE_SHELL.format(
        title=_esc(title),
        css=PARENT_CSS,
        school=_esc(school_name or "School"),
        student_name=_esc(student["name"]),
        steps=segs,
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
