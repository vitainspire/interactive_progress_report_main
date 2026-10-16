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
import math
import re

from app.reports.analysis import build_analysis
from app.reports.greeting import time_greeting_telugu
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

# Optional per-subject background image for the hero section — faded behind
# a near-opaque white wash (see .hero.themed) so it never competes with the
# heading or the marks table underneath. Matched by exact subject name
# (upper-cased); a subject with no match just keeps the plain white hero.
# Served from /static (see main.py's StaticFiles mount) — a decorative,
# non-sensitive asset path, never one that touches student data.
SUBJECT_BACKGROUNDS = {
    "TELUGU": "/static/backgrounds/telugu.jpg",
    "HINDI": "/static/backgrounds/hindi.jpg",
    "ENGLISH": "/static/backgrounds/english.jpg",
    "MATHS": "/static/backgrounds/maths.jpg",
    "MATHEMATICS": "/static/backgrounds/maths.jpg",
    "PHYSICAL SCIENCE": "/static/backgrounds/physical_science.jpg",
    "SOCIAL": "/static/backgrounds/social.jpg",
    "SOCIAL STUDIES": "/static/backgrounds/social.jpg",
}


def _subject_background(name: str) -> str | None:
    return SUBJECT_BACKGROUNDS.get((name or "").strip().upper())


PARENT_CSS = """
:root{
  color-scheme:light;
  --navy:#1e3a8a;
  --navy-deep:#0e1b4d;
  --ink:#0f172a;
  --muted:#64748b;
  --line:#e5e7eb;
  --good:#15803d;
  --warn:#b45309;
  --bad:#b91c1c;
  --gold:#e9a400;
  --gold-soft:#f0c75e;
  --ivory:#fbf8f2;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden}
body{background:#f6f7f9;font:16px/1.5 'Noto Sans','Noto Sans Telugu',system-ui,sans-serif;color:var(--ink);display:flex;flex-direction:column;height:100vh;-webkit-font-smoothing:antialiased}
.topbar{position:sticky;top:0;z-index:3;background:var(--navy-deep);color:#fff;padding:.85em 1.2em .75em}
.topbar .school{font-weight:600;font-size:.8em;text-align:center;opacity:.65;letter-spacing:.3px}
.topbar .student{text-align:center;font-size:1.08em;font-weight:600;margin-top:.15em;letter-spacing:.1px}
.progressbar{display:flex;gap:.3em;margin-top:.8em}
.seg{flex:1;height:3px;border-radius:2px;background:rgba(255,255,255,.18);overflow:hidden}
.seg .fill{height:100%;width:0;background:var(--gold);transition:width .3s ease}
.seg.active .fill{width:100%}
.seg.done .fill{width:100%;background:rgba(255,255,255,.55)}
.pagelabel{text-align:center;font-size:.7em;margin-top:.5em;opacity:.55;font-weight:500;letter-spacing:.4px}
main{flex:1;position:relative;overflow-y:auto;scroll-snap-type:y mandatory;scroll-behavior:smooth;-webkit-overflow-scrolling:touch}
.page{min-height:100%;display:flex;flex-direction:column;scroll-snap-align:start;scroll-snap-stop:always}

/* ---- Hero: a real editorial moment, not a header bar. Dark by default
   (navy, or a navy-duotone photo when a subject has one), with the score
   ring as the dominant visual element — this is the "score as hero" the
   brief asked for, and the dark-to-light handoff into .body-pad is the
   one recurring piece of visual drama every subject page shares. ---- */
.hero{position:relative;flex:none;padding:1.7em 1.4em 1.6em;text-align:center;background:linear-gradient(165deg,var(--navy) 0%,var(--navy-deep) 100%);color:#fff;overflow:hidden}
.hero.themed{background-size:cover;background-position:center}
.hero-welcome{font-size:.78em;color:var(--gold-soft);font-weight:600;margin-bottom:.7em;letter-spacing:.2px;line-height:1.35}
.eyebrow{font-size:.7em;font-weight:600;letter-spacing:2px;color:var(--gold-soft);text-transform:uppercase}
.hero h1{margin:.3em 0 0;font-size:1.9em;font-weight:700;letter-spacing:.2px;color:#fff;line-height:1.1}
.hero .sub{font-size:.8em;font-weight:400;color:rgba(255,255,255,.6);margin-top:.3em}
.trend-note{display:inline-block;margin-top:.6em;font-size:.76em;font-weight:600;color:rgba(255,255,255,.75);background:rgba(255,255,255,.1);padding:.28em .75em;border-radius:99px}
.trend-note.up{color:#86efac}
.trend-note.down{color:#fca5a5}

/* Score ring: real SVG, not a CSS hack — lets the fill animate smoothly
   via stroke-dashoffset and carry a genuine gold gradient stroke. */
.score-wrap{position:relative;width:7.6em;height:7.6em;margin:1em auto 0}
.score-ring{width:100%;height:100%;transform:rotate(-90deg)}
.score-ring .track{fill:none;stroke:rgba(255,255,255,.14);stroke-width:7}
.score-ring .fill{fill:none;stroke:url(#scoreGoldGrad);stroke-width:7;stroke-linecap:round;transition:stroke-dashoffset 1.1s cubic-bezier(.16,.84,.26,1)}
.score-num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.score-num .big{font-size:2em;font-weight:700;color:#fff;line-height:1}
.score-num .big sup{font-size:.42em;font-weight:600;margin-left:.05em;opacity:.85}
.score-num .exam{font-size:.65em;color:rgba(255,255,255,.6);margin-top:.25em;font-weight:600;letter-spacing:.3px}
.hero-grade{margin-top:.7em;display:flex;align-items:center;justify-content:center;gap:.6em;flex-wrap:wrap}
.hero-grade .gr{font-size:1.05em;padding:.3em 1em}
.hero-marks{font-size:.85em;font-weight:600;color:rgba(255,255,255,.75)}

/* ---- Exam history: collapsed by default — the hero above already fully
   covers the current/latest exam, so the page opens showing just that,
   not a wall of every exam at once. "View previous exams" reveals the
   rest on demand, as a single row of chips (never wraps — see .timeline,
   same one-row-always reasoning as before, now just hidden until asked
   for). ---- */
.body-pad{padding:1.1em 1.2em 8em;flex:1;display:flex;flex-direction:column;background:var(--ivory)}
.history-toggle{display:flex;align-items:center;justify-content:center;gap:.4em;width:100%;border:1px solid var(--line);background:#fff;color:var(--navy);font:inherit;font-weight:600;font-size:.85em;border-radius:10px;padding:.7em 1em;cursor:pointer}
.history-toggle .chev{transition:transform .2s ease;font-size:.85em}
.history-toggle.open .chev{transform:rotate(180deg)}
.timeline{display:flex;flex-wrap:nowrap;gap:.6em;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;margin-top:.8em}
.timeline.collapsed{display:none}
.timeline::-webkit-scrollbar{display:none}
.chip{flex:1 1 auto;min-width:6.4em;background:#fff;border:1px solid var(--line);border-radius:12px;padding:.85em .9em;box-shadow:0 1px 2px rgba(15,23,42,.03)}
.chip .exam-name{font-size:.72em;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.chip .exam-marks{font-size:1.15em;font-weight:700;color:var(--ink);margin-top:.3em}
.chip .gr{margin-top:.5em}
.gr{display:inline-block;min-width:2.1em;text-align:center;border-radius:5px;padding:.2em .5em;color:#fff;font-weight:600;font-size:.8em}
.ga{background:var(--good)}.gb{background:var(--navy)}.gc{background:var(--warn)}.gd{background:#c2410c}.gf{background:var(--bad)}

/* Commentary styled as a personal note, not a dashboard tile — a large
   quote glyph and serif-leaning italic give it a written, human voice. */
.commentary{margin-top:1.2em;position:relative;padding:.3em 0 0 1.4em}
.commentary::before{content:'\\201C';position:absolute;left:-.1em;top:-.25em;font-size:3em;font-weight:700;color:var(--navy);opacity:.18;line-height:1}
.commentary .ctitle{font-size:.7em;text-transform:uppercase;letter-spacing:.8px;font-weight:700;color:var(--muted)}
.commentary .ctext{margin-top:.5em;font-size:1.08em;line-height:1.6;color:var(--ink);font-style:italic}
.commentary.good .ctitle{color:var(--good)}
.commentary.low .ctitle,.commentary.mid .ctitle{color:var(--warn)}
.commentary.fail .ctitle{color:var(--bad)}
.grow{flex:1 0 auto}

/* ---- Finale: the payoff. Full dark stage, oversized typography, gold
   light instead of a boxed stat grid. ---- */
.hero.finale{min-height:100%;flex:1;padding:3.2em 1.5em 3em;display:flex;flex-direction:column;justify-content:center;background:radial-gradient(120% 90% at 50% -10%,#24409e 0%,var(--navy-deep) 60%)}
.finale-eyebrow{font-size:.74em;font-weight:700;letter-spacing:3px;color:var(--gold-soft);text-transform:uppercase}
.finale-name{margin-top:.5em;font-size:1.3em;font-weight:600;color:#fff}
.finale-total{margin-top:.5em;font-size:4em;font-weight:700;color:#fff;line-height:1;letter-spacing:-.01em}
.finale-total .unit{font-size:.28em;font-weight:600;color:rgba(255,255,255,.55);margin-left:.15em}
.finale-grade-row{margin-top:1em;display:flex;gap:.6em;align-items:center;justify-content:center;flex-wrap:wrap}
.result-tag{display:inline-block;border-radius:5px;padding:.25em .9em;font-weight:700;color:#fff;font-size:.95em;letter-spacing:.3px}
.result-tag.pass{background:var(--good)}
.result-tag.fail{background:var(--bad)}
.finale-stat{margin-top:1.8em;display:flex;justify-content:center;gap:2em;flex-wrap:wrap}
.finale-stat .item{text-align:center}
.finale-stat .n{font-size:1.5em;font-weight:700;color:#fff}
.finale-stat .l{font-size:.68em;color:rgba(255,255,255,.55);text-transform:uppercase;letter-spacing:.5px;margin-top:.2em}
.finale-msg{margin-top:1.8em;font-size:1em;line-height:1.6;color:rgba(255,255,255,.85);max-width:28em;margin-left:auto;margin-right:auto}
.finale-recap{margin-top:1.4em;font-size:.88em;line-height:1.6;color:rgba(255,255,255,.65)}
.finale-recap b{color:#fff;font-weight:600}

.spark{position:absolute;width:5px;height:5px;background:var(--gold-soft);opacity:0;border-radius:1px;transform:rotate(45deg)}
.spark:nth-child(1){top:14%;left:18%}
.spark:nth-child(2){top:22%;right:16%}
.spark:nth-child(3){top:62%;left:10%}
.spark:nth-child(4){top:70%;right:14%}
.spark:nth-child(5){top:40%;left:50%}
.hero.finale.sparkle .spark{animation:spark-glint 1.6s ease-out forwards}
.hero.finale.sparkle .spark:nth-child(2){animation-delay:.15s}
.hero.finale.sparkle .spark:nth-child(3){animation-delay:.3s}
.hero.finale.sparkle .spark:nth-child(4){animation-delay:.45s}
.hero.finale.sparkle .spark:nth-child(5){animation-delay:.6s}
@keyframes spark-glint{0%{opacity:0;transform:rotate(45deg) scale(.4)}40%{opacity:1;transform:rotate(45deg) scale(1.3)}100%{opacity:0;transform:rotate(45deg) scale(.6)}}

.action-row{margin-top:2em;display:flex;gap:.7em;justify-content:center}
.action-btn{border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.06);color:#fff;font:inherit;font-weight:600;font-size:.88em;border-radius:99px;padding:.7em 1.4em;cursor:pointer}
.action-btn:active{opacity:.7}
.action-btn.primary{background:var(--gold);border-color:var(--gold);color:var(--navy-deep)}

/* Full-analysis bottom sheet — its own scroll container (overflow-y:auto
   on .analysis-sheet), completely independent of main's scroll-snap, so
   this can be as long as the real analysis text needs to be without ever
   risking content past an unreachable snap boundary. */
.analysis-modal{position:fixed;inset:0;z-index:10;background:rgba(14,27,77,.72);display:flex;align-items:flex-end;justify-content:center}
.analysis-modal[hidden]{display:none}
.analysis-sheet{position:relative;background:#fff;color:var(--ink);width:100%;max-width:480px;max-height:80vh;overflow-y:auto;border-radius:18px 18px 0 0;padding:1.6em 1.4em 2.2em;box-shadow:0 -8px 30px rgba(0,0,0,.25)}
.analysis-sheet h2{margin:0 0 .9em;font-size:1.15em;color:var(--navy);padding-right:2em}
.analysis-sheet p{font-size:.95em;line-height:1.6;margin:0 0 1em;color:var(--ink)}
.analysis-sheet p.intro{font-weight:600;color:var(--navy)}
.analysis-sheet p:last-child{margin-bottom:0}
.analysis-close{position:absolute;top:1.1em;right:1.2em;width:2em;height:2em;border-radius:50%;border:none;background:var(--line);color:var(--ink);font-size:1em;line-height:1;cursor:pointer}

/* Final page: the exact same dense card the teacher sees, embedded via
   <iframe> so its own CARD_CSS/scripts stay fully isolated from this
   page's styles (both define classes like .gr/.ga.. with different
   rules — sharing one stylesheet would make them collide). The parent
   can still pinch-zoom the iframe like any other page content since the
   outer viewport meta never disables scaling. */
.full-report-page{flex:1;display:flex;flex-direction:column;min-height:100%;background:var(--ivory)}
.full-report-head{flex:none;padding:1.3em 1.2em .9em;text-align:center}
.full-report-eyebrow{font-size:.7em;font-weight:700;letter-spacing:1.5px;color:var(--navy);text-transform:uppercase}
.full-report-title{margin:.3em 0 0;font-size:1.15em;font-weight:700;color:var(--ink)}
.full-report-sub{margin-top:.3em;font-size:.82em;color:var(--muted)}
.full-report-frame{flex:1 1 auto;width:100%;border:0;background:#fff}

/* ---- Landing/choice screen: the first thing a parent sees before
   picking a path. A real photo up top (not an emoji) gives it the warmth
   of an actual school rather than a generic app screen, while the two
   options sit side by side as equal, calm choices — not one loud button
   next to an afterthought — which is what reads as "designed" rather
   than a default template stack. ---- */
html.landing-html,body.landing-body-root{height:auto;overflow:visible;background:#fff}
.landing-hero{position:relative;overflow:hidden;min-height:6em}
.landing-hero img{width:100%;height:auto;display:block}
.landing-hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(14,27,77,.1) 0%,rgba(14,27,77,.85) 100%)}
.landing-hero-caption{position:absolute;left:0;right:0;bottom:.9em;z-index:1;text-align:center;padding:0 1.2em}
.landing-hero-caption .eyebrow{font-size:.68em;font-weight:700;letter-spacing:1.6px;color:var(--gold-soft);text-transform:uppercase}
.landing-hero-caption .name{margin-top:.25em;font-size:1.15em;font-weight:700;color:#fff}
.landing-body{flex:1;background:#fff;padding:1.5em 1.3em 2.6em;max-width:30em;margin:0 auto;width:100%}
.landing-intro{text-align:center;font-size:.86em;color:var(--muted);margin-bottom:1.1em;line-height:1.5}
.landing-options{display:grid;grid-template-columns:1fr 1fr;gap:.8em}
.landing-card{display:flex;flex-direction:column;align-items:center;text-align:center;gap:.55em;text-decoration:none;border-radius:14px;padding:1.3em .9em 1.1em;border:1px solid var(--line);background:#fff;transition:transform .12s ease,border-color .15s ease,box-shadow .15s ease}
.landing-card:active{transform:scale(.97)}
.landing-card .lc-icon{flex:none;width:2.9em;height:2.9em;border-radius:12px;display:flex;align-items:center;justify-content:center;background:#eef1f8;color:var(--navy)}
.landing-card .lc-icon svg{width:1.5em;height:1.5em}
.landing-card .lc-title{font-size:.86em;font-weight:700;color:var(--ink);line-height:1.3}
.landing-card .lc-sub{font-size:.72em;color:var(--muted);line-height:1.4}
.landing-card.primary{border-color:var(--navy);box-shadow:0 2px 10px rgba(14,27,77,.1)}
.landing-card.primary .lc-icon{background:var(--navy);color:#fff}
.landing-card.soon{color:inherit}
.landing-card.soon .lc-icon{background:#f1f2f4;color:var(--muted)}
.landing-card .lc-badge{font-size:.62em;font-weight:600;letter-spacing:.3px;color:var(--muted);background:#f1f2f4;border-radius:99px;padding:.25em .65em;margin-top:.1em}

.about-placeholder{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2em 1.5em;gap:.6em}
.about-placeholder .ap-icon{width:3.2em;height:3.2em;border-radius:50%;background:#eef1f8;color:var(--navy);display:flex;align-items:center;justify-content:center}
.about-placeholder .ap-icon svg{width:1.7em;height:1.7em}
.about-placeholder h1{font-size:1.2em;margin:.2em 0 0;color:var(--ink)}
.about-placeholder p{font-size:.92em;color:var(--muted);max-width:22em;line-height:1.55;margin:.2em 0 0}
.about-back{margin-top:1.2em;display:inline-block;font-size:.88em;font-weight:600;color:var(--navy);text-decoration:none;border:1px solid var(--line);border-radius:99px;padding:.6em 1.3em}

/* ---- "Know About Student" chat ---- */
.chat-head{text-align:center;padding:0 0 1em}
.chat-head .eyebrow{font-size:.7em;font-weight:700;letter-spacing:1.5px;color:var(--navy);text-transform:uppercase}
.chat-head h1{margin:.3em 0 0;font-size:1.15em;color:var(--ink)}
.chat-head p{margin-top:.3em;font-size:.82em;color:var(--muted)}
.chat-box{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.chat-messages{height:min(56vh,440px);overflow-x:hidden;overflow-y:auto;padding:1em;display:flex;flex-direction:column;gap:.6em;-webkit-overflow-scrolling:touch}
.chat-bubble{max-width:82%;padding:.6em .85em;border-radius:14px;font-size:.92em;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
.chat-bubble.assistant{align-self:flex-start;background:var(--ivory);color:var(--ink);border-bottom-left-radius:4px}
.chat-bubble.user{align-self:flex-end;background:var(--navy);color:#fff;border-bottom-right-radius:4px}
.chat-bubble.error{align-self:flex-start;background:#fef2f2;color:var(--bad);border-bottom-left-radius:4px}
.chat-bubble.typing{align-self:flex-start;background:var(--ivory);color:var(--muted);display:flex;gap:.3em;align-items:center;padding:.75em .9em}
.chat-dot{width:.4em;height:.4em;border-radius:50%;background:var(--muted);animation:chat-dot-bounce 1s ease-in-out infinite}
.chat-dot:nth-child(2){animation-delay:.15s}
.chat-dot:nth-child(3){animation-delay:.3s}
@keyframes chat-dot-bounce{0%,100%{opacity:.3;transform:translateY(0)}50%{opacity:1;transform:translateY(-2px)}}
.chat-suggestions{display:flex;flex-wrap:wrap;gap:.5em;padding:.2em 1em .9em;border-top:1px solid var(--line)}
.chat-chip{font-size:.78em;font-weight:500;color:var(--navy);background:var(--ivory);border:1px solid var(--line);border-radius:99px;padding:.5em .9em;cursor:pointer;text-align:left}
.chat-chip:active{transform:scale(.97)}
.chat-input-row{display:flex;gap:.5em;padding:.7em;border-top:1px solid var(--line)}
.chat-input-row input{flex:1;border:1px solid var(--line);border-radius:99px;padding:.65em 1em;font:inherit;font-size:.9em;color:var(--ink);background:#fff}
.chat-input-row input:focus{outline:none;border-color:var(--navy)}
.chat-send{flex:none;width:2.6em;height:2.6em;border-radius:50%;border:none;background:var(--navy);color:#fff;font-size:1em;cursor:pointer;display:flex;align-items:center;justify-content:center}
.chat-send:disabled{opacity:.5;cursor:default}
@media (prefers-reduced-motion: reduce){.chat-dot{animation:none}}

.bottom-fade{position:fixed;left:0;right:0;bottom:0;height:8.5em;background:linear-gradient(to bottom,rgba(246,247,249,0) 0%,#f6f7f9 65%);pointer-events:none;z-index:4}
.listen-fab{position:fixed;left:50%;bottom:1.3em;transform:translateX(-50%);z-index:5;border:1px solid rgba(233,164,0,.55);font:inherit;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.6em;border-radius:99px;padding:.85em 1.6em;background:var(--navy-deep);color:#fff;font-size:.96em;box-shadow:0 6px 18px rgba(14,27,77,.35);transition:transform .12s ease,background .2s ease}
.listen-fab:active{transform:translateX(-50%) scale(.97)}
.listen-fab.loading{background:#334155;border-color:rgba(255,255,255,.2);cursor:wait}
.listen-fab.loading .spinner{width:1em;height:1em;border-radius:50%;border:.15em solid rgba(255,255,255,.35);border-top-color:#fff;animation:spin .7s linear infinite}
.listen-fab.speaking{background:var(--navy-deep);border-color:var(--gold)}
.listen-fab.error{background:var(--warn);border-color:var(--warn)}
.listen-fab.hidden,.bottom-fade.hidden{display:none}
@keyframes spin{to{transform:rotate(360deg)}}
.wave{display:inline-flex;align-items:center;gap:.16em;height:1em}
.wave span{display:block;width:.16em;background:var(--gold);border-radius:1px;animation:wave-bounce .9s ease-in-out infinite}
.wave span:nth-child(1){animation-delay:0s}
.wave span:nth-child(2){animation-delay:.15s}
.wave span:nth-child(3){animation-delay:.3s}
.wave span:nth-child(4){animation-delay:.45s}
@keyframes wave-bounce{0%,100%{height:.3em}50%{height:1em}}
.swipe-hint{position:fixed;left:50%;bottom:6.3em;transform:translateX(-50%);z-index:5;font-size:.76em;font-weight:500;color:var(--muted);background:rgba(255,255,255,.95);padding:.35em .9em;border-radius:99px;box-shadow:0 1px 6px rgba(0,0,0,.08);transition:opacity .25s ease}
.swipe-hint.hidden{opacity:0;pointer-events:none}

/* Base state for content that fades/settles in once its page becomes
   current — never opacity:0 by default, so a page is always fully
   visible even if JS never runs (no-JS / slow-script fallback). The
   .enter class, added transiently by script, is what actually plays the
   motion; removing this class (or JS not running) just leaves it visible. */
.hero,.body-pad{opacity:1}
.hero.enter{animation:content-in .5s ease both}
.body-pad.enter{animation:content-in .5s ease .08s both}
.hero.enter .hero-grade,.hero.enter .trend-note{animation:content-in .5s ease .25s both}
@keyframes content-in{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}

@media (prefers-reduced-motion: reduce){
  .score-ring .fill,.listen-fab,.swipe-hint,.hero.enter,.body-pad.enter,.hero.enter .hero-grade,.hero.enter .trend-note,.seg .fill,.wave span,.spark{animation:none!important;transition:none!important}
}

/* Shorter phones (common budget Android, iPhone SE, anything under ~720px
   tall) can't absorb the full hero without pushing the commentary past
   the last scroll-snap boundary, where it becomes unreachable — vertical
   space is compacted specifically, not just scaled down uniformly. */
@media (max-height: 720px){
  .hero-welcome{font-size:.72em;margin-bottom:.45em}
  .hero{padding:1.1em 1.3em 1em}
  .eyebrow{font-size:.64em}
  .hero h1{font-size:1.5em;margin-top:.2em}
  .hero .sub{font-size:.72em;margin-top:.2em}
  .trend-note{margin-top:.4em;font-size:.68em;padding:.2em .6em}
  .score-wrap{width:5.6em;height:5.6em;margin-top:.6em}
  .score-num .big{font-size:1.5em}
  .score-num .exam{font-size:.55em;margin-top:.1em}
  .hero-grade{margin-top:.45em}
  .body-pad{padding:.7em 1.2em 6.6em}
  .history-toggle{padding:.55em 1em;font-size:.8em}
  .timeline{gap:.4em;margin-top:.5em}
  .chip{padding:.45em .6em}
  .commentary{margin-top:.6em}
  .finale-total{font-size:3em}
  .finale-stat{margin-top:1.2em}
  .finale-msg{margin-top:1.1em}
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
      speakBtn.innerHTML = '<span class="wave"><span></span><span></span><span></span><span></span></span> Stop';
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
  var bottomFade = document.querySelector('.bottom-fade');
  var publicToken = main.dataset.token || '';

  // The ring's fill circle already carries its real, correct
  // stroke-dashoffset from the server (so it's right even if this script
  // never runs). To animate it, the trick is just: briefly force it to
  // the fully-unfilled offset, then — on the next frame, so the browser
  // registers that as a real style change — set it back to the real
  // value. The CSS transition on stroke-dashoffset does the rest.
  function animateRing(ring){
    if(reduceMotion) return;
    var fill = ring.querySelector('.fill');
    if(!fill) return;
    var target = fill.getAttribute('data-offset');
    var circumference = fill.getAttribute('data-circumference');
    fill.style.transition = 'none';
    fill.style.strokeDashoffset = circumference;
    // Force a reflow so the "none" transition + reset value actually commits
    // before re-enabling the transition and setting the real target.
    void fill.getBoundingClientRect();
    fill.style.transition = '';
    requestAnimationFrame(function(){ fill.style.strokeDashoffset = target; });
  }

  // Plays a page's entrance once (ring fill, content settle-in, and — on
  // the finale page, only for a pass — a brief gold sparkle). Guarded by
  // data-animated so revisiting an already-seen page by scrolling back up
  // doesn't replay the animation every time.
  function activatePage(page){
    if(page.dataset.animated) return;
    page.dataset.animated = '1';
    var hero = page.querySelector('.hero');
    var body = page.querySelector('.body-pad');
    if(!reduceMotion){
      if(hero){ hero.classList.add('enter'); hero.addEventListener('animationend', function(){ hero.classList.remove('enter'); }, { once: true }); }
      if(body){ body.classList.add('enter'); body.addEventListener('animationend', function(){ body.classList.remove('enter'); }, { once: true }); }
    }
    Array.prototype.forEach.call(page.querySelectorAll('.score-ring'), animateRing);
    if(hero && hero.classList.contains('finale') && hero.dataset.pass === '1' && !reduceMotion){
      hero.classList.add('sparkle');
      setTimeout(function(){ hero.classList.remove('sparkle'); }, 2200);
    }
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
    // The full-report page has its own "Read aloud" button inside the
    // embedded card (a different narration system entirely), so the
    // page-by-page Listen FAB and its bottom fade don't apply there.
    var isFullReport = pages[i].getAttribute('data-page-id') === 'full-report';
    speakBtn.classList.toggle('hidden', isFullReport);
    if(bottomFade) bottomFade.classList.toggle('hidden', isFullReport);
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

  // Delegated (not per-button) since every subject page has its own
  // independent "View previous exams" toggle — one listener handles them
  // all, each only ever affecting its own adjacent .timeline.
  main.addEventListener('click', function(e){
    var btn = e.target.closest('.history-toggle');
    if(!btn) return;
    var timeline = btn.nextElementSibling;
    var open = btn.classList.toggle('open');
    if(timeline) timeline.classList.toggle('collapsed', !open);
    var label = btn.querySelector('.label');
    if(label) label.textContent = open
      ? 'దాచండి / Hide'
      : 'మునుపటి పరీక్షలు చూడండి / View previous exams';
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

  var analysisToggle = document.getElementById('analysisToggle');
  var analysisModal = document.getElementById('analysisModal');
  var analysisClose = document.getElementById('analysisClose');
  if(analysisToggle && analysisModal){
    analysisToggle.addEventListener('click', function(){ analysisModal.hidden = false; });
    if(analysisClose) analysisClose.addEventListener('click', function(){ analysisModal.hidden = true; });
    // Tapping the dimmed backdrop (not the sheet itself) also closes it.
    analysisModal.addEventListener('click', function(e){ if(e.target === analysisModal) analysisModal.hidden = true; });
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

# A plain, non-scrolling-trick page — unlike PAGE_SHELL, content here is
# normal document flow (the body can be taller than one viewport and just
# scrolls), since neither the landing choice screen nor the "about student"
# placeholder need the swipe/scroll-snap machinery built for the report
# itself.
SIMPLE_SHELL = """<!doctype html>
<html lang="en" class="landing-html"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700;800&family=Noto+Sans+Telugu:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body class="landing-body-root">
{header}
{content}
</body></html>
"""

TOPBAR_HEADER = """<div class="topbar">
  <div class="school">{school}</div>
  <div class="student">{student_name}</div>
</div>"""


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


_TREND_NOTE = {
    "up": "▲ మెరుగుపడింది",
    "down": "▼ తగ్గింది",
    "flat": "స్థిరంగా ఉంది",
}


def _render_grade_badge(g: str) -> str:
    if g == "-":
        return ""
    return f'<span class="gr {_grade_class(g)}">{_esc(g)}</span>'


_RING_R = 50
_RING_CIRCUMFERENCE = 2 * math.pi * _RING_R


def _render_score_ring(pct: float, exam_label: str) -> str:
    """A real SVG ring (not the old conic-gradient trick) — correct,
    static stroke-dashoffset by default (so it reads right even with no
    JS), animated by script.js briefly resetting it to fully-unfilled and
    letting the CSS transition carry it back to this value."""
    pct = max(0.0, min(100.0, pct))
    offset = _RING_CIRCUMFERENCE * (1 - pct / 100)
    return (
        '<div class="score-wrap">'
        '<svg class="score-ring" viewBox="0 0 120 120" aria-hidden="true">'
        '<defs><linearGradient id="scoreGoldGrad" x1="0" y1="1" x2="1" y2="0">'
        '<stop offset="0%" stop-color="#e9a400"/><stop offset="100%" stop-color="#f6d97a"/>'
        "</linearGradient></defs>"
        f'<circle class="track" cx="60" cy="60" r="{_RING_R}"></circle>'
        f'<circle class="fill" cx="60" cy="60" r="{_RING_R}" '
        f'stroke-dasharray="{_RING_CIRCUMFERENCE:.2f}" stroke-dashoffset="{offset:.2f}" '
        f'data-circumference="{_RING_CIRCUMFERENCE:.2f}" data-offset="{offset:.2f}"></circle>'
        "</svg>"
        '<div class="score-num">'
        f'<div class="big">{round(pct)}<sup>%</sup></div>'
        f'<div class="exam">{_esc(exam_label)}</div>'
        "</div></div>"
    )


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

    bg = _subject_background(subject_name)
    if bg:
        # Darkened toward navy, not washed toward white — the photo stays
        # genuinely visible (the earlier near-opaque white wash made it
        # look like it was barely there), while staying dark enough for
        # white text to sit on top of it cleanly.
        hero_style = (
            " style=\"background-image:linear-gradient(165deg,rgba(30,58,138,.55) 0%,rgba(14,27,77,.88) 100%),"
            f"url('{_esc(bg)}')\""
        )
        h = f'<div class="hero themed"{hero_style}>'
    else:
        h = '<div class="hero">'

    if index == 0:
        h += (
            f'<div class="hero-welcome">{_esc(time_greeting_telugu())} '
            f'{_esc(student["name"])} యొక్క ప్రోగ్రెస్ కార్డ్‌కు స్వాగతం</div>'
        )
    h += (
        f'<div class="eyebrow">Subject {index + 1} of {total}</div>'
        f'<h1>{_esc(subject_name)}</h1>'
        '<div class="sub">ఈ సబ్జెక్టులో ప్రదర్శన</div>'
    )
    if facts.trend:
        h += f'<div class="trend-note {facts.trend}">{_TREND_NOTE[facts.trend]}</div>'
    if facts.history:
        latest = facts.history[-1]
        pct = 0.0
        if isinstance(latest.marks, (int, float)) and latest.max_marks:
            pct = latest.marks * 100 / latest.max_marks
        h += _render_score_ring(pct, latest.exam_key)
        h += (
            '<div class="hero-grade">'
            f"{_render_grade_badge(latest.grade)}"
            f'<span class="hero-marks">{_render_marks_cell(latest.marks)} / {_render_marks_cell(latest.max_marks)} marks</span>'
            "</div>"
        )
    h += "</div>"

    h += '<div class="body-pad">'
    if len(facts.history) > 1:
        # The hero above already fully covers the latest exam — this only
        # ever needs to render when there's actually more history to show
        # behind the toggle, not for a subject with just one exam on record.
        h += (
            '<button type="button" class="history-toggle">'
            '<span class="label">మునుపటి పరీక్షలు చూడండి / View previous exams</span>'
            '<span class="chev">▾</span>'
            "</button>"
        )
        h += '<div class="timeline collapsed">'
        for e in facts.history:
            h += (
                '<div class="chip">'
                f'<div class="exam-name">{_esc(e.exam_key)}</div>'
                f'<div class="exam-marks">{_render_marks_cell(e.marks)}/{_render_marks_cell(e.max_marks)}</div>'
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


def _render_conclusion_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str) -> str:
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)
    speech_te = build_conclusion_voice_telugu(student, exam_order, class_strength, school_name)
    speech_roman = build_conclusion_voice_romanized(student, exam_order, class_strength, school_name)

    if facts is None:
        h = (
            '<div class="hero finale" data-pass="0">'
            '<div class="finale-eyebrow">Overall Result</div>'
            f'<div class="finale-name">{_esc(student["name"])}</div>'
            "</div>"
        )
        return f'<section class="page" data-page-id="conclusion" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'

    is_pass = facts.grade not in ("D2", "-") or bool(re.search(r"PASS", facts.result_text or "", re.I))
    if facts.grade == "D2" or re.search(r"FAIL", facts.result_text or "", re.I):
        is_pass = False
        result_html = '<span class="result-tag fail">FAIL</span>'
    elif facts.grade != "-" or re.search(r"PASS", facts.result_text or "", re.I):
        result_html = '<span class="result-tag pass">PASS</span>'
    else:
        result_html = ""

    h = f'<div class="hero finale" data-pass="{1 if is_pass else 0}">'
    if is_pass:
        h += '<span class="spark"></span><span class="spark"></span><span class="spark"></span><span class="spark"></span><span class="spark"></span>'
    h += '<div class="finale-eyebrow">Overall Result</div>'
    h += f'<div class="finale-name">{_esc(student["name"])}</div>'
    if isinstance(facts.total, (int, float)):
        h += f'<div class="finale-total">{fmt_num(facts.total)}<span class="unit">marks</span></div>'
    h += '<div class="finale-grade-row">'
    if facts.grade != "-":
        h += _render_grade_badge(facts.grade)
    h += result_html
    h += "</div>"

    stats = []
    if facts.last_rank is not None:
        stats.append(("n", fmt_num(facts.last_rank) + " / " + str(facts.class_strength), "Rank"))
    if facts.attendance_pct is not None:
        stats.append(("n", f"{facts.attendance_pct}%", "Attendance"))
    if stats:
        h += '<div class="finale-stat">'
        for _, value, label in stats:
            h += f'<div class="item"><div class="n">{value}</div><div class="l">{_esc(label)}</div></div>'
        h += "</div>"

    if facts.attendance_pct is not None and facts.attendance_pct < 75:
        h += '<div class="finale-msg">హాజరు తక్కువగా ఉంది; దయచేసి మీ పిల్లలను ప్రతిరోజూ పాఠశాలకు పంపించండి.</div>'
    h += '<div class="finale-msg">పూర్తి వివరాల కోసం పైన వివరాలను వినండి, మీ పిల్లవాడి భవిష్యత్తు కోసం శుభాకాంక్షలు!</div>'

    if facts.good or facts.fail or facts.low:
        h += '<div class="finale-recap">'
        parts = []
        if facts.good:
            parts.append(f'<b>Strong:</b> {_esc(", ".join(facts.good))}')
        if facts.fail:
            parts.append(f'<b>Failed:</b> {_esc(", ".join(facts.fail))}')
        if facts.low:
            parts.append(f'<b>Needs attention:</b> {_esc(", ".join(facts.low))}')
        h += " &nbsp;&middot;&nbsp; ".join(parts)
        h += "</div>"

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
    h += '<div class="action-row">'
    h += f'<button type="button" class="action-btn primary" id="shareBtn" data-share-text="{_esc(share_text)}">షేర్ / Share</button>'

    # The full written analysis (same rule-based text already shown on the
    # teacher's printed card — see analysis.py) is long enough that inlining
    # it on this page, even collapsed-then-expanded, would risk pushing
    # content past a scroll-snap boundary where it can't be reached (the
    # exact bug already hit twice with shorter content). A bottom-sheet
    # modal sidesteps that entirely — it scrolls on its own, independent of
    # the page's scroll-snap, so arbitrarily long text is always reachable.
    analysis = build_analysis(student, exam_order, class_strength)
    if analysis["points"]:
        h += '<button type="button" class="action-btn" id="analysisToggle">పూర్తి విశ్లేషణ / Full analysis</button>'
    h += "</div>"
    h += "</div>"

    if analysis["points"]:
        h += '<div class="analysis-modal" id="analysisModal" hidden>'
        h += '<div class="analysis-sheet">'
        h += '<button type="button" class="analysis-close" id="analysisClose" aria-label="Close">✕</button>'
        h += '<h2>పూర్తి విశ్లేషణ / Full Analysis</h2>'
        if analysis["intro"]:
            h += f'<p class="intro">{_esc(analysis["intro"])}</p>'
        for point in analysis["points"]:
            h += f"<p>{_esc(point)}</p>"
        h += "</div></div>"

    return f'<section class="page" data-page-id="conclusion" data-speech-te="{_esc(speech_te)}" data-speech-roman="{_esc(speech_roman)}">{h}</section>'


def _render_full_report_page(token: str) -> str:
    """Final page: the exact same dense report card the teacher sees in the
    app (every exam, class rank, attendance, full AI analysis), embedded
    via <iframe src="/api/public/report/{token}/full"> — that route reuses
    card_render.render_report_page unchanged, so this is a byte-for-byte
    match of the teacher's view for this one student, not a re-implementation
    that could drift from it. No speech data: this page has its own "Read
    aloud" button inside the card itself (a separate, pre-existing system —
    see card_render.READ_ALOUD_SCRIPT), so the page-by-page Listen FAB hides
    itself here instead (see setCurrent in READ_ALOUD_SCRIPT above)."""
    h = (
        '<div class="full-report-page">'
        '<div class="full-report-head">'
        '<div class="full-report-eyebrow">Full Report</div>'
        '<div class="full-report-title">పూర్తి రిపోర్ట్ కార్డ్ / Complete report card</div>'
        '<div class="full-report-sub">ఉపాధ్యాయులు చూసేది సరిగ్గా ఇదే — ప్రతి పరీక్ష, ర్యాంకు, హాజరు వివరాలు</div>'
        "</div>"
        f'<iframe class="full-report-frame" id="fullReportFrame" src="/api/public/report/{_esc(token)}/full" title="Full report card"></iframe>'
        "</div>"
        "<script>"
        "(function(){"
        "var frame=document.getElementById('fullReportFrame');"
        "function fit(){"
        "var doc=frame.contentDocument;var pv=doc&&doc.getElementById('pv');var pvw=doc&&doc.getElementById('pvw');"
        "if(!pv||!pvw)return;"
        # The card is a fixed-size print layout (210mm wide) — never
        # reflowed for phones. Rather than leave it horizontally
        # scrollable (cutting the table off mid-row on a phone, which is
        # what this fit() replaces), it's scaled down to the iframe's own
        # width via a CSS transform, then pvw/the iframe itself are resized
        # to the resulting visual size — transforms don't affect layout
        # sizing, so without this the page would still report (and leave
        # scrollable) its full unscaled box despite painting smaller.
        "var scale=frame.clientWidth/pv.scrollWidth;"
        "pv.style.transformOrigin='top left';"
        "pv.style.transform='scale('+scale+')';"
        "pvw.style.overflow='hidden';"
        "pvw.style.width=frame.clientWidth+'px';"
        "var scaledHeight=Math.ceil(pv.scrollHeight*scale);"
        "pvw.style.height=scaledHeight+'px';"
        "frame.style.flex='none';"
        "frame.style.height=scaledHeight+'px';"
        "}"
        "frame.addEventListener('load',fit);"
        "window.addEventListener('resize',fit);"
        "})();"
        "</script>"
    )
    return f'<section class="page" data-page-id="full-report">{h}</section>'


def render_parent_report_page(
    student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, title: str = "Report Card", token: str = ""
) -> str:
    """`student` is the single student this link belongs to (parent links
    always resolve to exactly one student — see api/public.py). Builds
    (number of subjects + 2) pages: one per subject in discovery order,
    an overall/conclusion page, then the full teacher-style report as a
    final page. `token` is embedded for READ_ALOUD_SCRIPT to call the
    real-audio voice route, and for the final page's embedded iframe."""
    subjects = _discover_subjects(student, exam_defs)

    pages_html = [_render_subject_page(student, exam_defs, settings, name, i, len(subjects), school_name) for i, name in enumerate(subjects)]
    pages_html.append(_render_conclusion_page(student, all_students, exam_defs, settings, school_name))
    pages_html.append(_render_full_report_page(token))

    segs = "".join(f'<div class="seg{" active" if i == 0 else ""}"><div class="fill"></div></div>' for i in range(len(pages_html)))

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


# Simple line icons (not emoji — emoji render inconsistently across devices
# and read as a toy/chat-app register rather than a school document).
_ICON_REPORT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>'
    "</svg>"
)
_ICON_STUDENT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.6 3.1-6.5 7-6.5s7 2.9 7 6.5"/>'
    "</svg>"
)


def render_report_landing_page(student_name: str, school_name: str, token: str) -> str:
    """The first thing a parent sees when they open the link — a choice
    between the full swipeable report (_render_full_report_page and friends,
    now served from /view) and a not-yet-built "know about student" page
    (/about, currently a placeholder). A real classroom photo stands in for
    the usual flat topbar here, so the choice itself feels less like a
    settings screen and more like opening a school document."""
    header = (
        '<div class="landing-hero">'
        '<img src="/static/landing/school.jpg" alt="" loading="eager">'
        '<div class="landing-hero-caption">'
        f'<div class="eyebrow">{_esc(school_name or "School")}</div>'
        f'<div class="name">{_esc(student_name)}</div>'
        "</div></div>"
    )
    content = (
        '<div class="landing-body">'
        '<p class="landing-intro">మీరు ఏమి చూడాలనుకుంటున్నారో ఎంచుకోండి<br>Choose what you\'d like to see</p>'
        '<div class="landing-options">'
        f'<a class="landing-card primary" href="/api/public/report/{_esc(token)}/view">'
        f'<div class="lc-icon">{_ICON_REPORT}</div>'
        '<div class="lc-title">రిపోర్ట్ చూడండి<br>View Report</div>'
        '<div class="lc-sub">Marks, rank &amp; attendance</div>'
        "</a>"
        f'<a class="landing-card" href="/api/public/report/{_esc(token)}/about">'
        f'<div class="lc-icon">{_ICON_STUDENT}</div>'
        '<div class="lc-title">విద్యార్థి గురించి<br>Know About Student</div>'
        '<div class="lc-sub">Ask a question, get an answer</div>'
        "</a>"
        "</div></div>"
    )
    return SIMPLE_SHELL.format(
        title=_esc(f"{student_name} — Report"),
        css=PARENT_CSS,
        header=header,
        content=content,
    )


# The fixed set of starter questions offered as tappable chips before a
# parent has typed anything — kept in Telugu exactly as specified, not
# derived from this student's own data, since they're meant as generic
# conversation starters that work for any student.
_DEFAULT_CHAT_QUESTIONS = [
    "మొత్తం ప్రగతి ఎలా ఉంది?",
    "ఏ సబ్జెక్టులు మెరుగుపడాలి?",
    "ర్యాంకు గురించి చెప్పండి",
    "హాజరు ఎలా ఉంది?",
    "ఇంకా బాగా చదవాలంటే ఏం చేయాలి?",
]


def render_report_about_page(student_name: str, school_name: str, token: str) -> str:
    """The "Know About Student" chat: a parent types a free-form question
    and gets an answer grounded in this one student's own report data (see
    app/reports/chat_context.py + app/integrations/chat.py, called via
    POST .../ask). Keeps no server-side conversation state — the page's own
    script resends the growing `history` array with every question, same
    statelessness as the rest of this API."""
    header = TOPBAR_HEADER.format(school=_esc(school_name or "School"), student_name=_esc(student_name))
    chips = "".join(f'<button type="button" class="chat-chip" data-q="{_esc(q)}">{_esc(q)}</button>' for q in _DEFAULT_CHAT_QUESTIONS)
    content = (
        f'<div class="landing-body" id="chatRoot" data-token="{_esc(token)}">'
        '<div class="chat-head">'
        '<div class="eyebrow">Know About Student</div>'
        f'<h1>{_esc(student_name)} గురించి అడగండి / Ask about {_esc(student_name)}</h1>'
        '<p>మార్కులు, ర్యాంకు, హాజరు గురించి ఏదైనా అడగండి. / Ask anything about their marks, rank, or attendance.</p>'
        "</div>"
        '<div class="chat-box">'
        '<div class="chat-messages" id="chatMessages">'
        f'<div class="chat-bubble assistant">నమస్కారం! {_esc(student_name)} చదువు గురించి ఏదైనా అడగండి. / Hello! Ask me anything about {_esc(student_name)}\'s studies.</div>'
        "</div>"
        f'<div class="chat-suggestions" id="chatSuggestions">{chips}</div>'
        '<form class="chat-input-row" id="chatForm">'
        '<input type="text" id="chatInput" placeholder="మీ ప్రశ్న టైప్ చేయండి... / Type your question..." autocomplete="off">'
        '<button type="submit" class="chat-send" id="chatSend" aria-label="Send">➤</button>'
        "</form></div>"
        f'<a class="about-back" href="/api/public/report/{_esc(token)}">← వెనక్కి / Back</a>'
        "</div>"
        "<script>"
        "(function(){"
        "var root=document.getElementById('chatRoot');"
        "var token=root.dataset.token;"
        "var messages=document.getElementById('chatMessages');"
        "var suggestions=document.getElementById('chatSuggestions');"
        "var form=document.getElementById('chatForm');"
        "var input=document.getElementById('chatInput');"
        "var sendBtn=document.getElementById('chatSend');"
        "var history=[];"
        "var busy=false;"
        "function addBubble(cls,text){"
        "var div=document.createElement('div');"
        "div.className='chat-bubble '+cls;"
        "div.textContent=text;"
        "messages.appendChild(div);"
        "messages.scrollTop=messages.scrollHeight;"
        "return div;"
        "}"
        "function addTyping(){"
        "var div=document.createElement('div');"
        "div.className='chat-bubble typing';"
        "div.innerHTML='<span class=\"chat-dot\"></span><span class=\"chat-dot\"></span><span class=\"chat-dot\"></span>';"
        "messages.appendChild(div);"
        "messages.scrollTop=messages.scrollHeight;"
        "return div;"
        "}"
        "function send(question){"
        "question=(question||'').trim();"
        "if(busy||!question)return;"
        "busy=true;sendBtn.disabled=true;"
        "if(suggestions)suggestions.style.display='none';"
        "addBubble('user',question);"
        "var typing=addTyping();"
        "var priorHistory=history.slice();"
        "history.push({role:'user',content:question});"
        "fetch('/api/public/report/'+token+'/ask',{"
        "method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({question:question,history:priorHistory})"
        "}).then(function(r){return r.json().then(function(data){return {ok:r.ok,data:data};});})"
        ".then(function(res){"
        "typing.remove();"
        "if(res.ok){"
        "addBubble('assistant',res.data.answer);"
        "history.push({role:'assistant',content:res.data.answer});"
        "}else{"
        "addBubble('error',res.data.detail||'సమాధానం పొందలేకపోయాం. / Could not get an answer. Please try again.');"
        "}"
        "}).catch(function(){"
        "typing.remove();"
        "addBubble('error','నెట్‌వర్క్ సమస్య. / Network error — please try again.');"
        "}).finally(function(){"
        "busy=false;sendBtn.disabled=false;"
        "});"
        "}"
        "form.addEventListener('submit',function(e){"
        "e.preventDefault();"
        "var q=input.value;input.value='';"
        "send(q);"
        "});"
        "Array.prototype.forEach.call(document.querySelectorAll('.chat-chip'),function(btn){"
        "btn.addEventListener('click',function(){send(btn.getAttribute('data-q'));});"
        "});"
        "})();"
        "</script>"
    )
    return SIMPLE_SHELL.format(
        title=_esc(f"{student_name} — Know About Student"),
        css=PARENT_CSS,
        header=header,
        content=content,
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
