"""Rule-based Telugu narrative generation for the progress card's analysis section.

This mirrors the phrasing style of the original hand-written sample report
(congratulations -> steady subjects -> declining subjects with a trail of
percentages -> suggestions -> fail-check -> attendance remark) but is driven
entirely by the computed SubjectSeries / AttendanceInsight / RankInsight data,
so it works for any student rather than being specific to one.
"""
from __future__ import annotations

from app.reports.insights import AttendanceInsight, RankInsight, SubjectSeries

SUBJECT_TE = {
    "TELUGU": "తెలుగు",
    "HINDI": "హిందీ",
    "ENGLISH": "ఇంగ్లీష్",
    "MATHS": "గణితం",
    "PHYSICAL SCIENCE": "ఫిజికల్ సైన్స్",
    "BIOLOGY": "బయాలజీ",
    "SOCIAL": "సోషల్",
}

SUBJECT_ADVICE = {
    "TELUGU": "పద్యాలు, వ్యాకరణం, ప్రశ్న-జవాబులను రోజూ రాసి సాధన చేయాలి.",
    "HINDI": "వ్యాకరణం, పాఠాల ప్రశ్న-జవాబులను రోజూ రాసి సాధన చేయాలి.",
    "ENGLISH": "గ్రామర్, కాంప్రహెన్షన్ ప్రశ్నలను వారానికి కొన్నిసార్లు సాధన చేయాలి.",
    "MATHS": "ఫార్ములాలు, లెక్కలను రోజూ కొద్ది సమయం సాధన చేయాలి.",
    "PHYSICAL SCIENCE": "సూత్రాలు, న్యూమరికల్స్ వారానికి కనీసం 3 రోజులు సాధన చేయాలి.",
    "BIOLOGY": "డయాగ్రామ్స్, ముఖ్యమైన పదాలు రోజూ 30 నిమిషాలు రివిజన్ చేయాలి.",
    "SOCIAL": "మ్యాప్‌లు, ముఖ్యమైన సంఘటనలు, తేదీలను రివిజన్ చేయాలి.",
}


def subject_te(subject: str) -> str:
    return SUBJECT_TE.get(subject, subject.title())


def first_name(full_name: str) -> str:
    tokens = [t for t in full_name.strip().split() if t]
    if len(tokens) >= 3:
        pick = tokens[1]
    elif len(tokens) == 2:
        pick = tokens[1]
    else:
        pick = tokens[0] if tokens else full_name
    return pick.title()


def trend_arrow_text(series: SubjectSeries) -> str:
    parts = [f"{p.pct:g}%" for p in series.points]
    return " → ".join(parts)


def build_analysis_html(
    name: str,
    subject_series: list[SubjectSeries],
    rank_insight: RankInsight,
    any_fail: bool,
    total_students: int,
) -> str:
    fname = first_name(name)
    improving = [s for s in subject_series if s.direction == "improving"]
    declining = [s for s in subject_series if s.direction == "declining"]
    stable = [s for s in subject_series if s.direction == "stable" and len(s.points) > 1]

    praise_bullets: list[str] = []
    if rank_insight.direction == "improving" and len(rank_insight.points) > 1:
        best_rank = min(r for _, r in rank_insight.points)
        praise_bullets.append(f"ర్యాంక్ మెరుగుపడుతూ వస్తోంది, ఇప్పుడు {best_rank}వ స్థానంలో ఉన్నాడు/ఉంది (మొత్తం {total_students} మందిలో).")
    elif rank_insight.points:
        best_rank = min(r for _, r in rank_insight.points)
        if best_rank <= max(3, total_students // 10):
            praise_bullets.append(f"నిలకడగా టాప్ ర్యాంకుల్లో ఉన్నాడు/ఉంది (మొత్తం {total_students} మందిలో {best_rank}వ స్థానం).")
    for s in improving:
        praise_bullets.append(f"<b>{subject_te(s.subject)}:</b> {trend_arrow_text(s)}. మంచి మెరుగుదల కనిపిస్తోంది.")
    for s in stable:
        praise_bullets.append(f"<b>{subject_te(s.subject)}:</b> అన్ని పరీక్షల్లోనూ నిలకడగా ఉంది.")
    if not any_fail and any(s.points for s in subject_series):
        praise_bullets.append("ఏ పరీక్షలోనూ ఏ సబ్జెక్టులోనూ FAIL లేదు.")
    if not praise_bullets:
        praise_bullets.append("ప్రతి పరీక్షలోనూ స్థిరంగా ప్రయత్నిస్తున్నాడు/ఉంది.")

    intro = f"<p><b>అభినందనలు 🎉</b> {fname} మంచి ప్రతిభ చూపిస్తున్నాడు/ఉంది.</p>" if (improving or (rank_insight.points and min(r for _, r in rank_insight.points) <= 3)) else f"<p>{fname} ప్రదర్శనపై విశ్లేషణ కింద ఇవ్వబడింది.</p>"

    html = [intro, "<ul>" + "".join(f"<li>{b}</li>" for b in praise_bullets) + "</ul>"]

    if declining:
        html.append(
            "<p><b>శ్రద్ధ అవసరమైన అంశాలు:</b> మొత్తం ప్రదర్శన బాగున్నా, కొన్ని సబ్జెక్టుల్లో క్రమంగా తగ్గుదల ఉంది:</p>"
        )
        concern_bullets = [f"<b>{subject_te(s.subject)}:</b> {trend_arrow_text(s)}, వరుసగా తగ్గుతోంది." for s in declining]
        html.append("<ul>" + "".join(f"<li>{b}</li>" for b in concern_bullets) + "</ul>")
        html.append("<p>ఇవి ఆందోళనకరం కాదు, కానీ ఇలాగే తగ్గితే తర్వాతి పరీక్షల్లో మార్కులు తగ్గే అవకాశం ఉంది.</p>")
        html.append("<p><b>సూచనలు:</b></p>")
        suggestion_bullets = [f"{subject_te(s.subject)}: {SUBJECT_ADVICE.get(s.subject, 'రోజూ కొంత సమయం కేటాయించి సాధన చేయాలి.')}" for s in declining]
        suggestion_bullets.append("అన్ని సబ్జెక్టులకూ సమానంగా సమయం కేటాయించాలి. వారానికి ఒక స్వీయ-పరీక్ష రాసి తప్పులు సరిదిద్దుకోవాలి.")
        html.append("<ul>" + "".join(f"<li>{b}</li>" for b in suggestion_bullets) + "</ul>")

    return "".join(html)


def build_fail_html(fail_rows, staff_by_section: dict[str, str], any_data: bool) -> str:
    if not any_data:
        return "<p>పరీక్షల మార్కులు ఇంకా అందుబాటులో లేవు.</p>"
    if not fail_rows:
        subj_notes = []
        for subject, teacher in staff_by_section.items():
            if teacher:
                subj_notes.append(f"{subject_te(subject)} ({teacher} గారు)")
        tail = ""
        if subj_notes:
            tail = " అయినా " + ", ".join(subj_notes) + " టీచర్లను కలిసి సలహాలు తీసుకుంటే మరింత మెరుగైన ఫలితాలు సాధించవచ్చు."
        return f"<p>ఏ పరీక్షలోనూ FAIL లేదు ✅.{tail}</p>"
    lines = [f"<li>{subject_te(r['subject'])} ({r['phase_code']}): {r['marks']}/{r['max_marks']} ({r['grade']})</li>" for r in fail_rows]
    return "<p>కింది సబ్జెక్టుల్లో మెరుగుపడాల్సిన అవసరం ఉంది:</p><ul>" + "".join(lines) + "</ul>"


def build_focus_html(focus_topics: list[dict]) -> str:
    """focus_topics: [{subject, topics: [{title, ...}]}] for subjects the
    student is currently failing, where a textbook chapter list exists.
    Empty string (no box rendered) when there's nothing to show."""
    blocks = []
    for item in focus_topics:
        titles = [t["title"] for t in item["topics"]]
        if not titles:
            continue
        blocks.append(f"<li><b>{subject_te(item['subject'])}:</b> {', '.join(titles)}</li>")
    if not blocks:
        return ""
    return "<p>పాఠ్యపుస్తకం సూచిక ఆధారంగా, ఈ పాఠాలపై ప్రత్యేక దృష్టి పెట్టాలి:</p><ul>" + "".join(blocks) + "</ul>"


def build_attendance_remark(att: AttendanceInsight) -> str:
    if att.band == "no_data":
        return "<p>హాజరు వివరాలు అందుబాటులో లేవు.</p>"
    if att.band == "excellent":
        return f"<p><b>మొత్తం: {att.total_present:g} / {att.total_working:g} రోజులు ({att.pct:g}%)</b> అద్భుతమైన హాజరు, అభినందనలు! ఇలాగే కొనసాగించాలి.</p>"
    if att.band == "good":
        return f"<p><b>మొత్తం: {att.total_present:g} / {att.total_working:g} రోజులు ({att.pct:g}%)</b> హాజరు బాగానే ఉంది, మరింత మెరుగుపరుచుకోవచ్చు.</p>"
    return f"<p><b>మొత్తం: {att.total_present:g} / {att.total_working:g} రోజులు ({att.pct:g}%)</b> హాజరు తక్కువగా ఉంది, దీనిపై ప్రత్యేక శ్రద్ధ అవసరం.</p>"


HOME_ADVICE = (
    "<p><b>ఇంటి వద్ద:</b> సమయాన్ని సద్వినియోగం చేసుకోవాలి, పౌష్టికాహారం తీసుకోవాలి, చక్కటి స్టడీ ప్లాన్ రూపొందించుకోవాలి, "
    "చదువుకు అనుకూలమైన ప్రశాంత వాతావరణం ఉండేలా తల్లిదండ్రులు చూడాలి.</p>"
)
