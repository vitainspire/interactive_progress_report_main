"""Renders the PARENT-facing report page — a completely different
presentation from card_render.py's dense printable card, built for a
parent (often in a rural area, sometimes unable to read comfortably) to
follow on a phone. A single scrolling page, matching a "Digital Progress
Card" presentation style the teacher asked to match exactly: an overall
summary (ring, marks, grade, rank, attendance) at top, a "listen to full
analysis" action, every subject listed as its own card, a monthly
attendance table, then the same Teacher's Advice cards shown on the Know
About Student page (see render_report_about_page) — inline here rather
than behind a toggle, since the page already scrolls. The free-form
question chat intentionally isn't repeated here; it has its own page.

Icon-led rather than a plain data table (circular mark-percentage rings,
numbered advice cards) so it's something a parent actually wants to open,
not just a readable one — but the palette stays the product's own navy/
ivory, not a different theme per section. Color still carries real
meaning — grade badges, the pass/fail pill, the good/needs-attention
commentary tint — never as page-to-page decoration.

The teacher-facing /batches/{id}/report route is untouched and keeps using
card_render.render_report_page — this module is only ever reached via
/api/public/report/{token}.
"""
from __future__ import annotations

import html
import math
import re

from app.reports.analysis import build_analysis
from app.reports.chat_canned import answer_canned_question
from app.reports.numfmt import fmt_num
from app.reports.parent_subject import (
    build_conclusion_voice_telugu,
    build_subject_voice_telugu,
    compute_subject_facts,
    subject_commentary_telugu,
)
from app.reports.voice_script import _compute_facts


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
/* Score ring: real SVG, not a CSS hack — lets the fill animate smoothly
   via stroke-dashoffset and carry a genuine gold gradient stroke. Sized
   down via descendant selectors for the summary card (.summary-head) and
   each subject card (.subject-card) — see the View Report section below. */
.score-wrap{position:relative;width:7.6em;height:7.6em;margin:0 auto}
.score-ring{width:100%;height:100%;transform:rotate(-90deg)}
.score-ring .track{fill:none;stroke:rgba(30,58,138,.12);stroke-width:7}
.score-ring .fill{fill:none;stroke:url(#scoreGoldGrad);stroke-width:7;stroke-linecap:round;transition:stroke-dashoffset 1.1s cubic-bezier(.16,.84,.26,1)}
.score-num{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.score-num .big{font-size:2em;font-weight:700;color:var(--ink);line-height:1}
.score-num .big sup{font-size:.42em;font-weight:600;margin-left:.05em;opacity:.85}
.score-num .exam{font-size:.65em;color:var(--muted);margin-top:.25em;font-weight:600;letter-spacing:.3px}

.timeline{display:flex;flex-wrap:nowrap;gap:.6em;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none}
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

.result-tag{display:inline-block;border-radius:5px;padding:.25em .9em;font-weight:700;color:#fff;font-size:.95em;letter-spacing:.3px}
.result-tag.pass{background:var(--good)}
.result-tag.fail{background:var(--bad)}

/* Full-analysis bottom sheet — also reused as-is by the Teacher's Advice
   modal on the Know About Student page (see .advice-* further down). */
.analysis-modal{position:fixed;inset:0;z-index:10;background:rgba(14,27,77,.72);display:flex;align-items:flex-end;justify-content:center}
.analysis-modal[hidden]{display:none}
.analysis-sheet{position:relative;background:#fff;color:var(--ink);width:100%;max-width:480px;max-height:80vh;overflow-y:auto;border-radius:18px 18px 0 0;padding:1.6em 1.4em 2.2em;box-shadow:0 -8px 30px rgba(0,0,0,.25)}
.analysis-sheet h2{margin:0 0 .9em;font-size:1.15em;color:var(--navy);padding-right:2em}
.analysis-sheet p{font-size:.95em;line-height:1.6;margin:0 0 1em;color:var(--ink)}
.analysis-sheet p.intro{font-weight:600;color:var(--navy)}
.analysis-sheet p:last-child{margin-bottom:0}
.analysis-close{position:absolute;top:1.1em;right:1.2em;width:2em;height:2em;border-radius:50%;border:none;background:var(--line);color:var(--ink);font-size:1em;line-height:1;cursor:pointer}

/* ---- Landing/choice screen: the first thing a parent sees before
   picking a path. A real photo up top (not an emoji) gives it the warmth
   of an actual school rather than a generic app screen, while the two
   options sit side by side as equal, calm choices — not one loud button
   next to an afterthought — which is what reads as "designed" rather
   than a default template stack. ---- */
html.scroll-html,body.scroll-body-root{height:auto;overflow:visible;background:#fff}
html.landing-html,body.landing-body-root{height:auto;overflow:visible;background:#16271c}
.landing-hero{position:relative;overflow:hidden;min-height:6em;z-index:0}
.landing-hero img{width:100%;height:auto;display:block}
.landing-hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(14,27,77,.1) 0%,rgba(14,27,77,.85) 100%)}
.landing-hero-caption{position:absolute;left:0;right:0;bottom:.9em;z-index:1;text-align:center;padding:0 1.2em}
.landing-hero-caption .eyebrow{font-size:.68em;font-weight:700;letter-spacing:1.6px;color:var(--gold-soft);text-transform:uppercase}
.landing-hero-caption .name{margin-top:.25em;font-size:1.15em;font-weight:700;color:#fff}
/* A chalkboard backdrop for the choice screen (classroom-themed, like a
   school noticeboard) — the radial gradient gives it depth instead of a
   flat fill, and the faint repeating diagonal lines read as chalk dust
   without needing an image asset (keeps this page light to load on a
   parent's mobile data). Pulled up over the photo as a rounded "sheet"
   (negative margin + radius) instead of a hard color seam. */
.landing-body{position:relative;z-index:1;flex:1;background:radial-gradient(ellipse at 50% -10%,#2b4a37 0%,#1c3226 55%,#16271c 100%);padding:2em 1.3em 1.6em;max-width:30em;margin:-1.1em auto 0;width:100%;overflow:hidden;border-radius:22px 22px 0 0;box-shadow:0 -6px 18px rgba(0,0,0,.2)}
.landing-body::before{content:"";position:absolute;inset:0;opacity:.05;background-image:repeating-linear-gradient(135deg,#fff 0 1px,transparent 1px 16px);pointer-events:none}
.landing-body::after{content:"";position:absolute;top:.55em;left:50%;transform:translateX(-50%);width:2.6em;height:4px;border-radius:99px;background:rgba(255,255,255,.22)}
.landing-body>*{position:relative}
.landing-badge{display:block;margin:0 auto 1em;width:fit-content;border:1.5px dashed var(--gold-soft);border-radius:8px;padding:.4em 1em;color:#fdfdf6;background:rgba(255,255,255,.04);box-shadow:0 0 22px -4px rgba(240,199,94,.35)}
.landing-greeting{text-align:center;font-size:1em;font-weight:600;color:#fdfdf6;margin-bottom:.3em;line-height:1.55;text-shadow:0 1px 2px rgba(0,0,0,.3)}
.landing-intro{text-align:center;font-size:.86em;color:rgba(255,255,255,.72);margin-bottom:1.3em;line-height:1.5}
.landing-privacy{text-align:center;font-size:.76em;color:rgba(255,255,255,.55);margin-top:1.4em;padding-top:1em;border-top:1px dashed rgba(255,255,255,.14)}
.landing-options{display:grid;grid-template-columns:1fr 1fr;gap:.9em}
.landing-card{display:flex;flex-direction:column;align-items:center;text-align:center;gap:.55em;text-decoration:none;border-radius:12px;padding:1.3em .9em 1.1em;border:1px solid rgba(0,0,0,.06);background:#fffdf7;box-shadow:0 6px 16px rgba(0,0,0,.28);transition:transform .12s ease,box-shadow .15s ease}
.landing-card:nth-child(1){transform:rotate(-1deg)}
.landing-card:nth-child(2){transform:rotate(1deg)}
.landing-card:active{transform:scale(.97)}
.landing-card .lc-icon{flex:none;width:2.9em;height:2.9em;border-radius:12px;display:flex;align-items:center;justify-content:center;background:#eef1f8;color:var(--navy)}
.landing-card .lc-icon svg{width:1.5em;height:1.5em}
.landing-card .lc-title{font-size:.86em;font-weight:700;color:var(--ink);line-height:1.3}
.landing-card .lc-sub{font-size:.72em;color:var(--muted);line-height:1.4}
.landing-card.primary{box-shadow:0 4px 16px rgba(233,164,0,.25),0 4px 14px rgba(0,0,0,.25)}
.landing-card.primary .lc-icon{background:var(--gold);color:#fff}
.landing-card.soon{color:inherit}
.landing-card.soon .lc-icon{background:#f1f2f4;color:var(--muted)}
.landing-card .lc-badge{font-size:.62em;font-weight:600;letter-spacing:.3px;color:var(--muted);background:#f1f2f4;border-radius:99px;padding:.25em .65em;margin-top:.1em}

.about-placeholder{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:2em 1.5em;gap:.6em}
.about-placeholder .ap-icon{width:3.2em;height:3.2em;border-radius:50%;background:#eef1f8;color:var(--navy);display:flex;align-items:center;justify-content:center}
.about-placeholder .ap-icon svg{width:1.7em;height:1.7em}
.about-placeholder h1{font-size:1.2em;margin:.2em 0 0;color:var(--ink)}
.about-placeholder p{font-size:.92em;color:var(--muted);max-width:22em;line-height:1.55;margin:.2em 0 0}
.about-back{flex:none;align-self:center;display:inline-block;font-size:.82em;font-weight:600;color:var(--navy);text-decoration:none;border:1px solid var(--line);border-radius:99px;padding:.45em 1.1em}

/* ---- "Know About Student" chat ----
   A fixed app-shell, not a scrolling page: the chat's own <html>/<body>
   classes (see render_report_about_page) skip the landing page's
   height:auto override, so the base body{height:100vh;overflow:hidden}
   rule applies — everything here has to fit in one screen by
   construction. .chat-box flexes to fill whatever's left after the
   header/head/back-link's natural height, and .chat-messages is the only
   thing that ever scrolls, same as any real chat app. */
.chat-shell{display:flex;flex-direction:column;gap:.7em;background:#fff;padding:1em 1.1em 2em;max-width:30em;margin:0 auto;width:100%}
.chat-head{flex:none;text-align:center}
.chat-head .eyebrow{font-size:.7em;font-weight:700;letter-spacing:1.5px;color:var(--navy);text-transform:uppercase}
.chat-head h1{margin:.3em 0 0;font-size:1.05em;color:var(--ink)}
.chat-head p{margin-top:.25em;font-size:.78em;color:var(--muted)}
.chat-box{height:65vh;max-height:32em;min-height:19em;flex:none;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.chat-messages{flex:1;min-height:0;overflow-x:hidden;overflow-y:auto;padding:1em;display:flex;flex-direction:column;gap:.6em;-webkit-overflow-scrolling:touch}
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

/* Teacher's Advice: a compact entry banner (keeps the chat shell fitting
   one screen, same constraint as the rest of this page) that opens the
   full numbered breakdown in the existing analysis-sheet bottom modal —
   reusing that pattern rather than a new one. Its five cards are each
   just one of the already-built canned chat answers (chat_canned.py),
   re-presented here instead of re-derived, so this can never drift out of
   sync with what the chat itself would say for the same question. */
.advice-banner{flex:none;display:flex;align-items:center;gap:.7em;width:100%;text-align:left;border:1px solid var(--line);background:#fff;border-radius:14px;padding:.75em .9em;font:inherit;cursor:pointer}
.advice-banner .ab-icon{flex:none;width:2.3em;height:2.3em;border-radius:10px;background:linear-gradient(165deg,#2f6b45 0%,#173823 100%);display:flex;align-items:center;justify-content:center;font-size:1.1em}
.advice-banner .ab-text{flex:1;min-width:0;display:flex;flex-direction:column;gap:.15em}
.advice-banner .ab-title{display:block;font-size:.86em;font-weight:700;color:var(--ink)}
.advice-banner .ab-sub{display:block;font-size:.72em;color:var(--muted)}
.advice-banner .ab-chev{flex:none;color:var(--muted);font-size:.85em}
.advice-greeting{font-size:.95em;font-weight:700;color:var(--ink);margin:0 0 1em}
.advice-card{display:flex;gap:.8em;border:1px solid var(--line);border-radius:14px;padding:.9em 1em;margin-bottom:.7em;background:#fff}
.advice-card:last-child{margin-bottom:0}
.advice-num{flex:none;width:1.8em;height:1.8em;border-radius:50%;background:#173823;color:#fff;font-weight:700;font-size:.82em;display:flex;align-items:center;justify-content:center}
.advice-body{flex:1;min-width:0}
.advice-title{font-size:.87em;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:.4em}
.advice-text{font-size:.87em;color:var(--ink);line-height:1.55;margin-top:.35em}

@keyframes spin{to{transform:rotate(360deg)}}
.wave{display:inline-flex;align-items:center;gap:.16em;height:1em}
.wave span{display:block;width:.16em;background:var(--gold);border-radius:1px;animation:wave-bounce .9s ease-in-out infinite}
.wave span:nth-child(1){animation-delay:0s}
.wave span:nth-child(2){animation-delay:.15s}
.wave span:nth-child(3){animation-delay:.3s}
.wave span:nth-child(4){animation-delay:.45s}
@keyframes wave-bounce{0%,100%{height:.3em}50%{height:1em}}

@media (prefers-reduced-motion: reduce){
  .score-ring .fill,.listen-static,.wave span{animation:none!important;transition:none!important}
}

/* ---- View Report: a single scrolling page (matching a "Digital Progress
   Card" presentation style the teacher asked to match) instead of the
   earlier one-subject-per-swipe design — overall summary, one listen
   action, every subject as its own card, a monthly attendance table, then
   the same Teacher's Advice cards as the Know About Student page. ---- */
.view-shell{max-width:30em;margin:0 auto;width:100%;padding:1.1em 1.1em 3em;display:flex;flex-direction:column;gap:1.1em}

.summary-card{border:1px solid var(--line);border-radius:16px;background:#fff;padding:1.2em 1.1em;box-shadow:0 1px 2px rgba(15,23,42,.05)}
.summary-info-row{display:flex;gap:.8em;margin-bottom:1.1em;padding-bottom:1.1em;border-bottom:1px solid var(--line)}
.summary-info-row .si{flex:1;min-width:0}
.summary-info-row .si-label{font-size:.64em;font-weight:700;letter-spacing:.5px;color:var(--muted);text-transform:uppercase}
.summary-info-row .si-value{font-size:.88em;font-weight:600;color:var(--ink);margin-top:.25em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.summary-head{display:flex;align-items:center;gap:1.2em}
.summary-head .score-wrap{width:5.6em;height:5.6em;flex:none;margin:0}
.summary-head .score-num .big{font-size:1.5em}
.summary-head .score-num .exam{font-size:.58em}
.summary-result{flex:1;min-width:0}
.summary-eyebrow{font-size:.7em;font-weight:700;letter-spacing:1px;color:var(--navy);text-transform:uppercase}
.summary-grade-row{margin-top:.5em;display:flex;align-items:center;gap:.6em;flex-wrap:wrap}
.summary-grade-row .gr{font-size:1.05em;padding:.3em 1em}
.summary-stats{margin-top:1.1em;display:grid;grid-template-columns:repeat(2,1fr);gap:.7em}
.stat-tile{border:1px solid var(--line);border-radius:12px;padding:.7em .8em;background:var(--ivory)}
.stat-tile.wide{grid-column:1 / -1}
.stat-tile .st-label{font-size:.66em;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}
.stat-tile .st-value{font-size:1.05em;font-weight:700;color:var(--ink);margin-top:.25em}

.listen-static{display:flex;align-items:center;justify-content:center;gap:.6em;width:100%;border:2px dashed rgba(245,239,222,.55);font:inherit;font-weight:700;cursor:pointer;border-radius:14px;padding:.9em 1.2em;background:linear-gradient(165deg,#2f6b45 0%,#173823 100%);color:#fdfbf3;font-size:.96em;letter-spacing:.2px;box-shadow:0 6px 18px rgba(12,38,22,.3),inset 0 0 0 3px rgba(255,255,255,.06);transition:transform .12s ease}
.listen-static:active{transform:scale(.98)}
.listen-static.loading{background:#334155;border-color:rgba(255,255,255,.2);cursor:wait}
.listen-static.loading .spinner{width:1em;height:1em;border-radius:50%;border:.15em solid rgba(255,255,255,.35);border-top-color:#fff;animation:spin .7s linear infinite}
.listen-static.speaking{border-color:var(--gold)}
.listen-static.error{background:var(--warn);border-color:var(--warn)}

.section-heading{font-size:.78em;font-weight:700;letter-spacing:.8px;color:var(--navy);text-transform:uppercase;display:flex;align-items:center;gap:.4em}
.subjects-section{display:flex;flex-direction:column;gap:.9em}
.subject-card{border:1px solid var(--line);border-radius:14px;background:#fff;padding:1em 1.1em;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.subject-card-top{display:flex;align-items:center;gap:1em}
.subject-card .score-wrap{width:4em;height:4em;flex:none;margin:0}
.subject-card .score-num .big{font-size:1.05em}
.subject-card .score-num .exam{font-size:.5em}
.subject-card .sc-name{flex:1;min-width:0;font-size:1em;font-weight:700;color:var(--ink)}
.subject-card .timeline{margin-top:.9em}
.subject-card .commentary{margin-top:.8em;padding-left:1.2em}
.subject-card .commentary::before{font-size:2.4em}
.subject-card .commentary .ctext{font-size:.92em}

.attendance-card{border:1px solid var(--line);border-radius:14px;background:#fff;padding:1.1em}
.attendance-total{display:flex;align-items:center;justify-content:space-between;margin-bottom:.9em}
.attendance-total .at-pct{font-size:1.4em;font-weight:700;color:var(--navy)}
.attendance-table{width:100%;border-collapse:collapse;font-size:.76em}
.attendance-table th,.attendance-table td{padding:.4em .25em;text-align:center;border-bottom:1px solid var(--line)}
.attendance-table th{color:var(--muted);font-weight:600;font-size:.82em}
.attendance-note{margin-top:.9em;font-size:.87em;line-height:1.55;color:var(--ink)}

.view-advice-card{border:1px solid var(--line);border-radius:16px;background:#fff;padding:1.1em}

.view-footer{text-align:center;padding-top:.6em;display:flex;flex-direction:column;align-items:center;gap:.6em}
.view-footer .vf-school{font-size:.84em;font-weight:600;color:var(--ink)}
.view-footer .vf-privacy{font-size:.76em;color:var(--muted)}
"""


# A page shell shared by every parent-facing page — the landing choice
# screen, the chat, and the single-scroll report. `html_class`/`body_class`
# pick which body behavior a given page gets: "landing-html"/"landing-body-root"
# or "scroll-html"/"scroll-body-root" both mean normal document flow (the
# page just scrolls, see that selector in PARENT_CSS); the chat passes ""
# for both, which falls through to the base body{height:100vh;overflow:hidden}
# rule instead, so it's a fixed one-screen app shell where only its own
# message list scrolls (see .chat-shell/.chat-box/.chat-messages in PARENT_CSS).
SIMPLE_SHELL = """<!doctype html>
<html lang="en" class="{html_class}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700;800&family=Noto+Sans+Telugu:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body class="{body_class}">
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


def _class_average_pct(all_students: list[dict], exam_key: str, max_total: float) -> float | None:
    """Average of every OTHER student's own total-marks percentage for the
    same exam — rank already tells a parent their position, this gives the
    number behind it ("74% vs a class average of 68%") without exposing any
    other student's name or individual marks."""
    if not max_total:
        return None
    vals = []
    for s in all_students:
        exam = s.get("exams", {}).get(exam_key)
        if not exam:
            continue
        total = exam.get("total_marks")
        if isinstance(total, (int, float)):
            vals.append(total * 100 / max_total)
    return sum(vals) / len(vals) if vals else None


def _subject_class_average_pct(all_students: list[dict], exam_key: str, subject_name: str, max_marks: float) -> float | None:
    if not max_marks:
        return None
    vals = []
    for s in all_students:
        exam = s.get("exams", {}).get(exam_key)
        if not exam:
            continue
        for x in exam.get("subjects", []):
            if x["name"] == subject_name and isinstance(x.get("marks"), (int, float)):
                vals.append(x["marks"] * 100 / max_marks)
                break
    return sum(vals) / len(vals) if vals else None


def _render_summary_card(student: dict, all_students: list[dict], exam_defs: list[dict], settings, facts) -> str:
    """Top-of-page overview: father's name/roll as a two-column info row
    (matching the reference's FATHER'S NAME / CHILD ID header), the latest
    exam's score ring, grade + pass/fail tag, then stat tiles for total
    marks, grade, rank, attendance and a class-average comparison — all
    from the same _Facts (voice_script._compute_facts) the old conclusion
    page used."""
    father = (student.get("father") or "").strip()
    roll = str(student.get("roll") or "").strip()
    info_row = ""
    if father or roll:
        info_row = (
            '<div class="summary-info-row">'
            f'<div class="si"><div class="si-label">Father’s Name</div><div class="si-value">{_esc(father) if father else "&mdash;"}</div></div>'
            f'<div class="si"><div class="si-label">Roll No</div><div class="si-value">{_esc(roll) if roll else "&mdash;"}</div></div>'
            "</div>"
        )

    if facts is None:
        return f'<div class="summary-card">{info_row}<div class="summary-eyebrow">మొత్తం ఫలితం / Overall Result</div></div>'

    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}
    max_total = settings.fa_total if is_fa_by_key.get(facts.last_key) else settings.sa_total
    pct = 0.0
    if isinstance(facts.total, (int, float)) and max_total:
        pct = facts.total * 100 / max_total

    is_pass = facts.grade not in ("D2", "-") or bool(re.search(r"PASS", facts.result_text or "", re.I))
    if facts.grade == "D2" or re.search(r"FAIL", facts.result_text or "", re.I):
        is_pass = False
        result_html = '<span class="result-tag fail">FAIL</span>'
    elif facts.grade != "-" or re.search(r"PASS", facts.result_text or "", re.I):
        result_html = '<span class="result-tag pass">PASS</span>'
    else:
        result_html = ""

    h = info_row
    h += '<div class="summary-head">'
    h += _render_score_ring(pct, facts.last_key)
    h += '<div class="summary-result">'
    h += '<div class="summary-eyebrow">మొత్తం ఫలితం / Overall Result</div>'
    h += '<div class="summary-grade-row">'
    if facts.grade != "-":
        h += _render_grade_badge(facts.grade)
    h += result_html
    h += "</div></div></div>"

    stats: list[tuple[str, str, bool]] = []
    if isinstance(facts.total, (int, float)):
        max_label = fmt_num(max_total) if max_total else "-"
        stats.append(("మొత్తం మార్కులు / Total Marks", f"{fmt_num(facts.total)}/{max_label}", False))
    if facts.grade != "-":
        stats.append(("గ్రేడ్ / Grade", facts.grade, False))
    if facts.last_rank is not None:
        stats.append(("ర్యాంకు / Rank", f"{fmt_num(facts.last_rank)} / {facts.class_strength}", False))
    if facts.attendance_pct is not None:
        stats.append(("హాజరు / Attendance", f"{facts.attendance_pct}%", False))

    class_avg = _class_average_pct(all_students, facts.last_key, max_total)
    if class_avg is not None and isinstance(facts.total, (int, float)):
        diff = round(pct - class_avg)
        comp_color = "var(--good)" if diff >= 0 else "var(--warn)"
        arrow = "▲" if diff >= 0 else "▼"
        stats.append((
            "తరగతి సగటుతో పోలిక / vs Class Average",
            f'మీరు {round(pct)}% <span style="color:{comp_color};font-weight:700">{arrow} {abs(diff)}</span>'
            f" &nbsp;·&nbsp; తరగతి సగటు {round(class_avg)}%",
            True,
        ))

    if stats:
        h += '<div class="summary-stats">'
        for label, value, wide in stats:
            tile_class = "stat-tile wide" if wide else "stat-tile"
            value_html = value if wide else _esc(value)
            h += f'<div class="{tile_class}"><div class="st-label">{_esc(label)}</div><div class="st-value">{value_html}</div></div>'
        h += "</div>"

    if facts.attendance_pct is not None and facts.attendance_pct < 75:
        h += '<p style="margin-top:1em;font-size:.86em;color:var(--bad)">హాజరు తక్కువగా ఉంది; దయచేసి ప్రతిరోజూ పాఠశాలకు పంపించండి.</p>'

    return f'<div class="summary-card">{h}</div>'


def _render_listen_section(student: dict, all_students: list[dict], exam_defs: list[dict], settings) -> str:
    """One "listen to full analysis" action for the whole page, replacing
    the old page-by-page Listen FAB — speaks the same rule-based analysis
    text already shown to the teacher (see analysis.py) via the browser's
    own voice. The real-audio (Bhashini) system stays wired to
    get_speech_text/the /voice route for any future reuse; this simpler
    single-button page just uses the always-available browser voice."""
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    analysis = build_analysis(student, exam_order, class_strength)
    parts = [analysis["intro"]] if analysis.get("intro") else []
    parts.extend(analysis.get("points") or [])
    speech = " ".join(p for p in parts if p)
    if not speech:
        return ""
    return (
        f'<button type="button" class="listen-static" id="viewListenBtn" data-speech-te="{_esc(speech)}">'
        "\U0001f50a మొత్తం విశ్లేషణ వినండి"
        "</button>"
    )


def _render_subject_card(student: dict, all_students: list[dict], exam_defs: list[dict], settings, subject_name: str) -> str:
    is_fa_by_key = {e["key"]: e["is_fa"] for e in exam_defs}

    def max_marks(key: str) -> float:
        return settings.fa_marks_per_subject if is_fa_by_key[key] else settings.sa_marks_per_subject

    exam_order = [e["key"] for e in exam_defs]
    facts = compute_subject_facts(student, exam_order, subject_name, max_marks)
    if not facts.history:
        return ""

    latest = facts.history[-1]
    pct = 0.0
    if isinstance(latest.marks, (int, float)) and latest.max_marks:
        pct = latest.marks * 100 / latest.max_marks

    h = '<div class="subject-card">'
    h += '<div class="subject-card-top">'
    h += _render_score_ring(pct, latest.exam_key)
    h += f'<div class="sc-name">{_esc(subject_name)}</div>'
    h += "</div>"
    h += '<div class="timeline">'
    for e in facts.history:
        h += (
            '<div class="chip">'
            f'<div class="exam-name">{_esc(e.exam_key)}</div>'
            f'<div class="exam-marks">{_render_marks_cell(e.marks)}/{_render_marks_cell(e.max_marks)}</div>'
            f"{_render_grade_badge(e.grade)}"
            "</div>"
        )
    h += "</div>"

    class_avg = _subject_class_average_pct(all_students, latest.exam_key, subject_name, latest.max_marks)
    if class_avg is not None and isinstance(latest.marks, (int, float)):
        diff = round(pct - class_avg)
        comp_color = "var(--good)" if diff >= 0 else "var(--warn)"
        arrow = "▲" if diff >= 0 else "▼"
        h += (
            '<div style="margin-top:.7em;font-size:.78em;color:var(--muted)">'
            f'తరగతి సగటు ({_esc(latest.exam_key)}): {round(class_avg)}% '
            f'<span style="color:{comp_color};font-weight:700">{arrow} {abs(diff)}</span>'
            "</div>"
        )

    h += (
        f'<div class="commentary {facts.classification}">'
        f'<div class="ctext">{_esc(subject_commentary_telugu(facts))}</div>'
        "</div>"
    )
    h += "</div>"
    return h


def _render_subjects_section(student: dict, all_students: list[dict], exam_defs: list[dict], settings) -> str:
    subjects = _discover_subjects(student, exam_defs)
    cards = [c for c in (_render_subject_card(student, all_students, exam_defs, settings, name) for name in subjects) if c]
    if not cards:
        return ""
    return (
        "<div>"
        '<div class="section-heading">\U0001f4da సబ్జెక్టుల వారీగా / Subject-wise</div>'
        f'<div class="subjects-section" style="margin-top:.8em">{"".join(cards)}</div>'
        "</div>"
    )


def _render_attendance_section(student: dict) -> str:
    att = student.get("attendance")
    if not att or not att.get("months"):
        return ""
    total_working = att.get("total_working") or 0
    total_present = att.get("total_present") or 0
    pct = round(total_present * 100 / total_working) if total_working else 0

    h = '<div class="attendance-card">'
    h += '<div class="section-heading">\U0001f4c5 నెలవారీ హాజరు / Monthly Attendance</div>'
    h += '<div class="attendance-total" style="margin-top:.8em">'
    h += f"<span>{fmt_num(total_present)} / {fmt_num(total_working)} రోజులు</span>"
    h += f'<span class="at-pct">{pct}%</span>'
    h += "</div>"
    h += '<div style="overflow-x:auto"><table class="attendance-table"><thead><tr><th>నెల</th>'
    for m in att["months"]:
        h += f'<th>{_esc(m["month"])}</th>'
    h += "</tr></thead><tbody>"
    h += "<tr><td>పని దినాలు</td>"
    for m in att["months"]:
        h += f'<td>{_render_marks_cell(m["working_days"])}</td>'
    h += "</tr><tr><td>హాజరైనవి</td>"
    for m in att["months"]:
        attended = m.get("attended")
        working = m.get("working_days")
        cell = _render_marks_cell(attended)
        if isinstance(attended, (int, float)) and isinstance(working, (int, float)) and working:
            cell += f'<br><span style="color:var(--muted);font-size:.85em">{round(attended * 100 / working)}%</span>'
        h += f"<td>{cell}</td>"
    h += "</tr></tbody></table></div>"
    if pct < 75:
        h += '<p class="attendance-note" style="color:var(--bad)">హాజరు తక్కువగా ఉంది; దయచేసి ప్రతిరోజూ పాఠశాలకు పంపించండి.</p>'
    else:
        h += f'<p class="attendance-note">మొత్తం {fmt_num(total_working)} పని దినాలలో {fmt_num(total_present)} రోజులు ({pct}%) హాజరయ్యారు.</p>'
    h += "</div>"
    return h


def _render_view_footer(school_name: str, student_name: str, token: str) -> str:
    return (
        '<div class="view-footer">'
        f'<div class="vf-school">{_esc(school_name or "School")}</div>'
        f'<a class="about-back" href="/api/public/report/{_esc(token)}/full" target="_blank" rel="noopener">\U0001f4c4 పూర్తి రిపోర్ట్ కార్డ్ / Full report card</a>'
        f'<a class="about-back" href="/api/public/report/{_esc(token)}">← వెనక్కి / Back</a>'
        f'<div class="vf-privacy">\U0001f512 ఈ రిపోర్ట్ {_esc(student_name)} తల్లిదండ్రుల కోసం మాత్రమే.</div>'
        "</div>"
    )


VIEW_REPORT_SCRIPT = """
<script>
(function(){
  var shell = document.getElementById('viewShell');
  var studyPlanCard = document.getElementById('studyPlanCard');
  if(shell && studyPlanCard){
    var token = shell.dataset.token;
    fetch('/api/public/report/' + token + '/study-plan').then(function(r){ return r.json(); }).then(function(data){
      if(data && data.available){
        document.getElementById('studyPlanText').textContent = data.plan;
        studyPlanCard.hidden = false;
      }
    }).catch(function(){});
  }
})();
(function(){
  var btn = document.getElementById('viewListenBtn');
  if(!btn) return;
  var idleLabel = btn.textContent;
  var speaking = false;

  function getVoicesAsync(){
    return new Promise(function(resolve){
      var voices = speechSynthesis.getVoices();
      if(voices && voices.length){ resolve(voices); return; }
      var done = false;
      speechSynthesis.onvoiceschanged = function(){ if(done) return; done = true; resolve(speechSynthesis.getVoices()); };
      setTimeout(function(){ if(done) return; done = true; resolve(speechSynthesis.getVoices()); }, 1000);
    });
  }

  function setState(state){
    btn.classList.remove('loading', 'speaking', 'error');
    if(state === 'loading'){
      btn.innerHTML = '<span class="spinner"></span> లోడ్ అవుతోంది…';
      btn.classList.add('loading');
    } else if(state === 'speaking'){
      btn.innerHTML = '<span class="wave"><span></span><span></span><span></span><span></span></span> Stop';
      btn.classList.add('speaking');
    } else if(state === 'error'){
      btn.textContent = '\\u26a0\\ufe0f వినలేకపోయామ్';
      btn.classList.add('error');
      setTimeout(function(){ setState(null); }, 2200);
    } else {
      btn.textContent = idleLabel;
    }
  }

  btn.addEventListener('click', function(){
    if(speaking){ speechSynthesis.cancel(); speaking = false; setState(null); return; }
    if(!('speechSynthesis' in window)){ setState('error'); return; }
    setState('loading');
    getVoicesAsync().then(function(voices){
      var teluguVoice = voices.filter(function(v){ return /^te/i.test(v.lang); })[0];
      var text = btn.getAttribute('data-speech-te') || '';
      if(!text){ setState('error'); return; }
      var utter = new SpeechSynthesisUtterance(text);
      utter.lang = teluguVoice ? teluguVoice.lang : 'en-IN';
      utter.onstart = function(){ speaking = true; setState('speaking'); };
      utter.onend = function(){ speaking = false; setState(null); };
      utter.onerror = function(){ speaking = false; setState('error'); };
      speechSynthesis.speak(utter);
    });
  });

  window.addEventListener('beforeunload', function(){ try { speechSynthesis.cancel(); } catch(e){} });
})();
</script>
"""


def render_parent_report_page(
    student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, title: str = "Report Card", token: str = ""
) -> str:
    """`student` is the single student this link belongs to (parent links
    always resolve to exactly one student — see api/public.py). A single
    scrolling page (see module docstring): overall summary, one "listen to
    full analysis" action, every subject as its own card, a monthly
    attendance table, then the same Teacher's Advice cards shown on the
    Know About Student page."""
    header = TOPBAR_HEADER.format(school=_esc(school_name or "School"), student_name=_esc(student["name"]))
    exam_order = [e["key"] for e in exam_defs]
    class_strength = settings.class_strength_override or len(all_students)
    facts = _compute_facts(student, exam_order, class_strength, school_name)

    content = f'<div class="view-shell" id="viewShell" data-token="{_esc(token)}">'
    content += _render_summary_card(student, all_students, exam_defs, settings, facts)
    content += _render_listen_section(student, all_students, exam_defs, settings)
    content += _render_subjects_section(student, all_students, exam_defs, settings)
    content += _render_attendance_section(student)
    content += _render_advice_section_inline(student, all_students, exam_defs, settings, student["name"])
    content += _render_view_footer(school_name, student["name"], token)
    content += "</div>"
    content += VIEW_REPORT_SCRIPT

    return SIMPLE_SHELL.format(
        title=_esc(title),
        css=PARENT_CSS,
        html_class="scroll-html",
        body_class="scroll-body-root",
        header=header,
        content=content,
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
        f'<img src="/api/public/report/{_esc(token)}/school-photo" alt="" loading="eager">'
        '<div class="landing-hero-caption">'
        f'<div class="eyebrow">{_esc(school_name or "School")}</div>'
        f'<div class="name">{_esc(student_name)}</div>'
        "</div></div>"
    )
    content = (
        '<div class="landing-body">'
        '<span class="pill landing-badge">📘 డిజిటల్ ప్రోగ్రెస్ కార్డు</span>'
        '<p class="landing-greeting">నమస్కారం! 🙏<br>మీ పిల్లల చదువు వివరాలు ఇక్కడ ఉన్నాయి.</p>'
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
        "</div>"
        '<p class="landing-privacy">🔒 ఈ లింక్ మీ కోసం మాత్రమే / This link is only for you</p>'
        "</div>"
    )
    return SIMPLE_SHELL.format(
        title=_esc(f"{student_name} — Report"),
        css=PARENT_CSS,
        html_class="landing-html",
        body_class="landing-body-root",
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


# Icon + card title for each of the five canned answers, in the same order
# as _DEFAULT_CHAT_QUESTIONS, reused to build the "Teacher's Advice" panel
# below from the exact same text the chat would give for that question.
_ADVICE_META = [
    ("\U0001f4aa", "బలాలు"),
    ("\U0001f4da", "మెరుగుపడాల్సిన సబ్జెక్టులు"),
    ("\U0001f3c5", "ర్యాంకు"),
    ("\U0001f4c5", "హాజరు"),
    ("\U0001f4a1", "చదువు చిట్కాలు"),
]


def _build_advice_cards(student: dict, all_students: list[dict], exam_defs: list[dict], settings) -> list[str]:
    """One card per canned chat answer that actually has something to say
    for this student — shared by the Know About Student banner/modal and
    the inline Teacher's Advice section on the single-scroll View Report
    page, so both always show the exact same text."""
    cards = []
    for (icon, title), question in zip(_ADVICE_META, _DEFAULT_CHAT_QUESTIONS):
        answer = answer_canned_question(question, student, all_students, exam_defs, settings)
        if not answer:
            continue
        cards.append(
            f'<div class="advice-card"><span class="advice-num">{len(cards) + 1}</span>'
            f'<div class="advice-body"><div class="advice-title">{icon} {_esc(title)}</div>'
            f'<div class="advice-text">{_esc(answer)}</div></div></div>'
        )
    return cards


def _study_plan_placeholder_card(next_num: int) -> str:
    """A hidden card, filled in (and un-hidden) by client-side JS that
    fetches /report/{token}/study-plan after the page has rendered — see
    that route and study_plan.py for why this is fetched lazily instead of
    rendered server-side. Stays hidden forever if the fetch finds no weak
    subject or no syllabus for it, so there's no empty/stuck-loading card
    left behind in the common case."""
    return (
        f'<div class="advice-card" id="studyPlanCard" hidden><span class="advice-num">{next_num}</span>'
        '<div class="advice-body"><div class="advice-title">\U0001f4d8 సిలబస్ ఆధారిత ప్రణాళిక / Syllabus-based Plan</div>'
        '<div class="advice-text" id="studyPlanText">లోడ్ అవుతోంది…</div></div></div>'
    )


def _render_advice_section(student: dict, all_students: list[dict], exam_defs: list[dict], settings, student_name: str) -> str:
    cards = _build_advice_cards(student, all_students, exam_defs, settings)
    if not cards:
        return ""
    cards.append(_study_plan_placeholder_card(len(cards) + 1))
    return (
        '<button type="button" class="advice-banner" id="adviceToggle">'
        '<span class="ab-icon">\U0001f469‍\U0001f3eb</span>'
        '<span class="ab-text">'
        '<span class="ab-title">ఉపాధ్యాయుల సలహాలు / Teacher’s Advice</span>'
        '<span class="ab-sub">బలాలు, ర్యాంకు, సలహాలు ఒకేచోట / Strengths, rank &amp; tips</span>'
        "</span>"
        '<span class="ab-chev">›</span>'
        "</button>"
        '<div class="analysis-modal" id="adviceModal" hidden>'
        '<div class="analysis-sheet">'
        '<button type="button" class="analysis-close" id="adviceClose" aria-label="Close">✕</button>'
        '<h2>\U0001f469‍\U0001f3eb ఉపాధ్యాయుల సలహాలు</h2>'
        f'<p class="advice-greeting">ప్రియమైన {_esc(student_name)} తల్లిదండ్రులకు,</p>'
        + "".join(cards)
        + "</div></div>"
    )


def _render_advice_section_inline(student: dict, all_students: list[dict], exam_defs: list[dict], settings, student_name: str) -> str:
    """Same cards as _render_advice_section, shown directly in the page
    flow instead of behind a banner/modal — used by the single-scroll View
    Report page, which already scrolls, so nothing needs to hide behind a
    toggle the way it does on the fixed-shell chat page."""
    cards = _build_advice_cards(student, all_students, exam_defs, settings)
    if not cards:
        return ""
    cards.append(_study_plan_placeholder_card(len(cards) + 1))
    return (
        '<div class="view-advice-card">'
        '<div class="section-heading">\U0001f469‍\U0001f3eb ఉపాధ్యాయుల సలహాలు / Teacher’s Advice</div>'
        f'<p class="advice-greeting" style="margin-top:.8em">ప్రియమైన {_esc(student_name)},</p>'
        + "".join(cards)
        + "</div>"
    )


def render_report_about_page(student: dict, all_students: list[dict], exam_defs: list[dict], settings, school_name: str, token: str) -> str:
    """The "Know About Student" chat: a parent types a free-form question
    and gets an answer grounded in this one student's own report data (see
    app/reports/chat_context.py + app/integrations/chat.py, called via
    POST .../ask). Keeps no server-side conversation state — the page's own
    script resends the growing `history` array with every question, same
    statelessness as the rest of this API.

    Also carries a compact "Teacher's Advice" entry banner above the chat,
    opening a bottom sheet with the same five canned answers re-presented as
    numbered cards — a parent who doesn't know what to ask gets a ready
    summary; one who does still has the free-form chat below it."""
    student_name = student["name"]
    header = TOPBAR_HEADER.format(school=_esc(school_name or "School"), student_name=_esc(student_name))
    chips = "".join(f'<button type="button" class="chat-chip" data-q="{_esc(q)}">{_esc(q)}</button>' for q in _DEFAULT_CHAT_QUESTIONS)
    advice_section = _render_advice_section(student, all_students, exam_defs, settings, student_name)
    content = (
        f'<div class="chat-shell" id="chatRoot" data-token="{_esc(token)}">'
        f"{advice_section}"
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
        "var adviceToggle=document.getElementById('adviceToggle');"
        "var adviceModal=document.getElementById('adviceModal');"
        "var adviceClose=document.getElementById('adviceClose');"
        "if(adviceToggle&&adviceModal){"
        "adviceToggle.addEventListener('click',function(){adviceModal.hidden=false;});"
        "if(adviceClose)adviceClose.addEventListener('click',function(){adviceModal.hidden=true;});"
        "adviceModal.addEventListener('click',function(e){if(e.target===adviceModal)adviceModal.hidden=true;});"
        "}"
        "var studyPlanCard=document.getElementById('studyPlanCard');"
        "if(studyPlanCard){"
        "fetch('/api/public/report/'+token+'/study-plan').then(function(r){return r.json();}).then(function(data){"
        "if(data&&data.available){"
        "document.getElementById('studyPlanText').textContent=data.plan;"
        "studyPlanCard.hidden=false;"
        "}"
        "}).catch(function(){});"
        "}"
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
        # `usedChip` is the specific chip button clicked (if any) — only
        # that one gets removed on send, so the rest stay available for a
        # follow-up tap instead of the whole suggestions row disappearing
        # after the first question (typed or tapped).
        "function send(question,usedChip){"
        "question=(question||'').trim();"
        "if(busy||!question)return;"
        "busy=true;sendBtn.disabled=true;"
        "if(usedChip){"
        "usedChip.remove();"
        "if(suggestions&&!suggestions.querySelector('.chat-chip'))suggestions.style.display='none';"
        "}"
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
        "btn.addEventListener('click',function(){send(btn.getAttribute('data-q'),btn);});"
        "});"
        "})();"
        "</script>"
    )
    return SIMPLE_SHELL.format(
        title=_esc(f"{student_name} — Know About Student"),
        css=PARENT_CSS,
        html_class="scroll-html",
        body_class="scroll-body-root",
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
