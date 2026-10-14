"""Port of the original tool's templated Telugu "AI analysis" paragraph —
the exact wording the teacher's tool already produces, driven by the
student's own marks/grades/rank/attendance rather than an actual LLM call.
Kept as a pure function (given parsed data in, Telugu text out) so it can
be unit-tested without touching the database or HTML layer.
"""
from __future__ import annotations

from app.reports.numfmt import fmt_num

GRADE_POINTS = {"A1": 10, "A2": 9, "B1": 8, "B2": 7, "C1": 6, "C2": 5, "D1": 4, "D2": 3}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def build_analysis(student: dict, exam_order: list[str], class_strength: int) -> dict:
    """`student` is a parsed-sheet student row: {"name", "exams": {key: {...}}, "attendance": {...}|None}.
    Returns {"intro": str, "points": list[str]}; empty when the student has no exam data at all."""
    ks = [k for k in exam_order if k in student["exams"]]
    if not ks:
        return {"intro": "", "points": []}
    last_key = ks[-1]
    last_exam = student["exams"][last_key]

    subject_history: dict[str, list[dict]] = {}
    for q in ks:
        for x in student["exams"][q]["subjects"]:
            subject_history.setdefault(x["name"], []).append({"exam": q, "grade": x["grade"], "marks": x["marks"]})

    good, fail, low = [], [], []
    absentees = 0
    for name, history in subject_history.items():
        absentees += sum(1 for x in history if x["marks"] == "AB")
        graded = [x for x in history if x["grade"] in GRADE_POINTS]
        if not graded:
            continue
        avg = sum(GRADE_POINTS[x["grade"]] for x in graded) / len(graded)
        failed_exams = [x["exam"] for x in graded if x["grade"] == "D2"]
        if failed_exams:
            fail.append(f"{name} ({', '.join(failed_exams)})")
        else:
            if avg < 6:
                low.append(name)
            if avg >= 8:
                good.append(name)

    if good:
        a = f"నువ్వు {', '.join(good)} సబ్జెక్టులలో అన్ని పరీక్షలలో కలిపి చక్కటి మార్కులు సాధించావు. అభినందనలు! ఇదే కృషిని కొనసాగించు."
    else:
        a = "నీ ప్రయత్నం అభినందనీయం. ఇంకొంచెం కృషి చేస్తే తప్పకుండా మంచి గ్రేడ్లు సాధించగలవు."

    b = ""
    if absentees:
        b += "కొన్ని సబ్జెక్టులకు గైర్హాజరయ్యావు; ఆ పరీక్షలు తప్పకుండా రాయడానికి ప్రయత్నించు. "
    if fail:
        b += f"{', '.join(fail)} సబ్జెక్టులలో ఆయా పరీక్షలలో ఫెయిల్ అయ్యావు. వీటిపై ప్రత్యేక శ్రద్ధ అవసరం: ప్రతిరోజూ కనీసం ఒక గంట వీటికి కేటాయించు, తెలియని అంశాలను ఉపాధ్యాయులను అడిగి తెలుసుకో, ప్రశ్నలను పదే పదే సాధన చేయి. "
    if low:
        b += f"{', '.join(low)} సబ్జెక్టులలో అన్ని పరీక్షలలో కలిపి మార్కులు కొంచెం తక్కువగా ఉన్నాయి; కొద్ది శ్రమతో మెరుగుపడతాయి. "
    if not fail and not low and not b:
        b = "ఏ పరీక్షలోనూ ఏ సబ్జెక్టులోనూ ఫెయిల్ కాలేదు, చాలా సంతోషం. ఇదే నిలకడను కొనసాగించు. "

    prev_exam = student["exams"][ks[0]] if len(ks) > 1 else None
    if prev_exam and prev_exam["total_grade"] in GRADE_POINTS and last_exam["total_grade"] in GRADE_POINTS:
        cur_gp, prev_gp = GRADE_POINTS[last_exam["total_grade"]], GRADE_POINTS[prev_exam["total_grade"]]
        if cur_gp < prev_gp:
            b += f"{ks[0]} తో పోలిస్తే {last_key} లో మొత్తం గ్రేడ్ తగ్గింది, కాబట్టి జాగ్రత్తగా ఉండు."
        elif cur_gp > prev_gp:
            b += f"{ks[0]} నుండి {last_key} వరకు మొత్తం గ్రేడ్ మెరుగుపడింది, శభాష్!"

    c = ""
    att = student.get("attendance")
    if att and att["total_working"]:
        pct = round(att["total_present"] * 100 / att["total_working"])
        c = f"మొత్తం {fmt_num(att['total_working'])} పని దినాలలో {fmt_num(att['total_present'])} రోజులు ({pct}%) బడికి వచ్చావు. "
        if pct >= 90:
            c += "చాలా మంచి హాజరు! ఇదే క్రమశిక్షణను కొనసాగించు."
        elif pct >= 75:
            c += "హాజరు బాగానే ఉంది, ఇంకా మెరుగుపరచుకుంటే పాఠాలు పూర్తిగా అర్థమవుతాయి."
        else:
            c += "హాజరు తక్కువగా ఉంది. తరచుగా బడికి రాకపోవడం వల్ల పాఠాలు తప్పిపోయి చదువులో వెనుకబడే అవకాశం ఉంది. ఇకపై క్రమం తప్పకుండా బడికి రా."

    d = "ప్రతిరోజూ సమయపట్టిక ప్రకారం చదువు; ఆ రోజు నేర్చుకున్న పాఠాలను అదే రోజు ఒకసారి మళ్ళీ చదువు; సరైన నిద్ర, పౌష్టికాహారం తీసుకో; ఫోన్, టీవీ సమయం తగ్గించు. పట్టుదల, క్రమశిక్షణతో నువ్వు తప్పకుండా గొప్ప విజయం సాధిస్తావు. శుభాకాంక్షలు!"

    r = ""
    ranked = [q for q in ks if _is_num(student["exams"][q]["rank"])]
    if ranked:
        last_rk = ranked[-1]
        last_rank = student["exams"][last_rk]["rank"]
        n = class_strength or 0
        rank_list = ", ".join(f"{q} – {fmt_num(student['exams'][q]['rank'])}" for q in ranked)
        r = f"ర్యాంకులు: {rank_list} (మొత్తం {n} మంది విద్యార్థులలో). "
        if last_rank <= 3:
            r += f"{last_rk} లో టాప్ 3 లో నిలిచావు, అద్భుతం! ఈ స్థానాన్ని నిలబెట్టుకో. "
        elif n and last_rank <= n * 0.25:
            r += f"{last_rk} లో తరగతిలో మొదటి పావు భాగంలో ఉన్నావు, చాలా బాగుంది. టాప్ 3 లక్ష్యంగా పెట్టుకో. "
        elif n and last_rank <= n * 0.5:
            r += f"{last_rk} లో మధ్యస్థ స్థానంలో ఉన్నావు; కొంచెం ఎక్కువ కృషితో టాప్ ర్యాంకుల్లోకి రాగలవు. "
        else:
            r += f"{last_rk} లో ర్యాంకు మెరుగుపడాల్సిన అవసరం ఉంది; బలహీన సబ్జెక్టులపై ఎక్కువ దృష్టి పెడితే ర్యాంకు తప్పకుండా పెరుగుతుంది. "
        if len(ranked) > 1:
            first_rk = ranked[0]
            first_rank = student["exams"][first_rk]["rank"]
            if last_rank < first_rank:
                r += f"{first_rk} లో {fmt_num(first_rank)} వ ర్యాంకు నుండి {last_rk} లో {fmt_num(last_rank)} వ ర్యాంకుకు ఎదిగావు, శభాష్!"
            elif last_rank > first_rank:
                r += f"{first_rk} లో {fmt_num(first_rank)} వ ర్యాంకు నుండి {last_rk} లో {fmt_num(last_rank)} వ ర్యాంకుకు తగ్గింది; మళ్ళీ పైకి రావడానికి పట్టుదలతో చదువు."
            else:
                r += f"{first_rk} నుండి {last_rk} వరకు {fmt_num(last_rank)} వ ర్యాంకు నిలకడగా ఉంది; ఇంకా పైకి ఎదగడానికి ప్రయత్నించు."

    intro = f"ప్రియమైన {student['name']}, {', '.join(ks)} పరీక్షల ఫలితాల ఆధారంగా విశ్లేషణ:"
    points = [x for x in [a, b, r, c, d] if x]
    return {"intro": intro, "points": points}
