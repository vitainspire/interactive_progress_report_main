"""The official AP SSC exam blueprint's marks-weightage per topic, plus
each subject's exam format and a curated list of "easy marks" exam-
technique tips — transcribed from a Subject Analysis tool the teacher
shared (itself built from the same government blueprint documents this
app's syllabus_chapter was transcribed from). See schema.sql for why this
is a separate table from syllabus_chapter: the blueprint groups topics at
a different granularity (exam-weightage groupings, not the textbook's own
chapter breakdown) and carries marks, not teaching periods.

Seeded once into subject_blueprint / subject_exam_info on startup, same
idempotent "only if empty" pattern as app/db/syllabus_seed.py.
"""
from __future__ import annotations

import json

import psycopg

# Each tuple: (topic_name, marks, choice_marks | None) — choice_marks is the
# extra marks available via an internal-choice question on that topic, kept
# separate from the base marks since it's not guaranteed weight every exam.
BLUEPRINT_BY_CLASS_SUBJECT: dict[tuple[str, str], list[tuple[str, int, int | None]]] = {
    ("10", "TELUGU"): [
        ("భాషాంశాలు, వ్యాకరణం", 32, None),
        ("పద్యభాగం", 20, None),
        ("గద్యభాగం", 20, None),
        ("ఉపవాచకం", 20, None),
        ("సృజనాత్మక ప్రశ్న", 8, None),
    ],
    ("10", "HINDI"): [
        ("Reading (పఠనం)", 35, None),
        ("Expression (అభివ్యక్తి)", 32, None),
        ("Creative writing", 18, None),
        ("Grammar (భాషా కీ బాత్)", 15, None),
    ],
    ("10", "ENGLISH"): [
        ("Grammar & Vocabulary", 40, None),
        ("Reading Comprehension", 30, None),
        ("Creative Expression", 30, None),
    ],
    ("10", "MATHS"): [
        ("Probability", 13, None),
        ("Statistics", 12, None),
        ("Pair of Linear Equations", 11, None),
        ("Coordinate Geometry", 10, None),
        ("Real Numbers", 9, None),
        ("Polynomials", 7, None),
        ("Quadratic Equations", 7, None),
        ("Introduction to Trigonometry", 7, None),
        ("Circles", 7, None),
        ("Arithmetic Progressions", 5, 8),
        ("Surface Areas and Volumes", 5, 8),
        ("Triangles", 3, 8),
        ("Applications of Trigonometry", 3, 8),
        ("Areas Related to Circles", 1, 8),
    ],
    ("10", "PHYSICAL SCIENCE"): [
        ("Carbon and its Compounds", 11, None),
        ("Light: Reflection and Refraction", 11, None),
        ("Electricity", 11, None),
        ("Acids, Bases and Salts", 10, None),
        ("Chemical Reactions and Equations", 9, None),
        ("Metals and Non-metals", 9, None),
        ("Human Eye and Colourful World", 9, None),
        ("Magnetic Effects of Current", 8, None),
    ],
    ("10", "BIOLOGY"): [
        ("Life Processes", 14, 8),
        ("How do Organisms Reproduce", 10, 4),
        ("Heredity", 10, None),
        ("Our Environment", 10, None),
        ("Control and Coordination", 6, 8),
    ],
    ("10", "SOCIAL"): [
        ("Rise of Nationalism in Europe", 9, None),
        ("Development", 9, None),
        ("Water Resources", 8, None),
        ("Nationalism in India", 8, None),
        ("Power Sharing", 8, None),
        ("Sectors of Indian Economy", 8, None),
        ("Globalisation", 8, 2),
        ("Map question (India + World)", 8, None),
        ("Gender, Religion and Caste", 6, None),
        ("Resources and Development", 5, None),
        ("Forest and Wildlife", 4, None),
        ("Minerals and Energy", 4, None),
        ("Manufacturing Industries", 4, None),
        ("Making of a Global World", 4, 2),
        ("Print Culture", 4, 8),
        ("Federalism", 4, None),
        ("Outcomes of Democracy", 4, None),
        ("Political Parties", 3, 9),
    ],
}

# (exam_format, [easy-marks tips...]) per (class_level, subject).
EXAM_INFO_BY_CLASS_SUBJECT: dict[tuple[str, str], tuple[str, list[str]]] = {
    ("10", "TELUGU"): (
        "100 మార్కులు, 3 గం 15 ని, 33 ప్రశ్నలు",
        [
            "భాషాంశాలు (ప్ర 12–25): సంధి, సమాసం, వాక్య రకాలు, కర్తరి–కర్మణి; ఒక్కొక్కటి 1 మార్కు",
            "పదవిజ్ఞానం (ప్ర 7–11): అర్థాలు, పర్యాయపదాలు, ప్రకృతి–వికృతి, నానార్థాలు; 10 మార్కులు",
            "పువ్వు గుర్తు పద్యాల ప్రతిపదార్థం (8): శతకమాధుర్యం పద్యం తప్పనిసరి",
            "అలంకారం, ఛందస్సు (2+2): ఉత్పలమాల, చంపకమాల, మత్తేభం, శార్దూలం గణాలు",
            "సృజనాత్మక ప్రశ్న (8): లేఖ, కరపత్రం, సంభాషణ నమూనాలు",
        ],
    ),
    ("10", "HINDI"): (
        "100 మార్కులు, 3 గం 15 ని, 31 ప్రశ్నలు",
        [
            "భాషా కీ బాత్ (15 × 1): తత్సమ్–తద్భవ్, విలోమ్, పర్యాయ్, సంధి, సమాస్, ఉపసర్గ్–ప్రత్యయ్",
            "లేఖ (6), నిబంధ్ (6): పర్యావరణం, జల సంరక్షణ, మొబైల్ ఫోన్ అంశాల నమూనాలు",
            "8 మార్కుల పాఠాలు: బరసతే బాదల్, హమ్ భారతవాసీ, ఈద్గాహ్, లోకగీత్",
            "కవి పరిచయం (5): పంత్, దినకర్, రహీమ్, బిహారీ",
        ],
    ),
    ("10", "ENGLISH"): (
        "100 మార్కులు, 3 గం 15 ని",
        [
            "Grammar (40): articles, prepositions, tenses, voice, reported speech; ఒక్కో మార్కు ప్రశ్నలు",
            "Creative Expression (30): letter, diary, conversation, story; ప్రతి ఫార్మాట్‌కి ఒక నమూనా",
            "Study skills (5 + 5): tables, pie chart, bar chart నుంచి సమాధానాలు",
            "Reading: ప్రశ్నలోని పదాలు passage లో వెతికి పూర్తి వాక్యంతో రాయడం",
        ],
    ),
    ("10", "MATHS"): (
        "100 మార్కులు, 3 గం 15 ని, 33 ప్రశ్నలు",
        [
            "Probability (13) + Statistics (12): ఫార్ములాలతో 25 మార్కులు",
            "Section I (12 × 1): నిర్వచనాలు, ఫార్ములాలు, ఒక్క స్టెప్ లెక్కలు",
            "Coordinate Geometry (10): distance, section formula రోజూ 5 లెక్కలు",
            "Trigonometry విలువల పట్టిక (0°–90°) కంఠస్థం",
        ],
    ),
    ("10", "PHYSICAL SCIENCE"): (
        "సైన్స్ పేపర్ I, 50 మార్కులు, 2 గం, 17 ప్రశ్నలు",
        [
            "రసాయన సమీకరణాల తుల్యం (balancing), చర్యల రకాలు",
            "కిరణ చిత్రాలు: దర్పణాలు, కటకాలు; హ్రస్వదృష్టి, దీర్ఘదృష్టి",
            "Ohm's law లెక్కలు, శ్రేణి–సమాంతర నిరోధాలు",
            "Carbon compounds: నామకరణం, సమజాతీయ శ్రేణి",
        ],
    ),
    ("10", "BIOLOGY"): (
        "సైన్స్ పేపర్ II, 50 మార్కులు, 2 గం, 17 ప్రశ్నలు",
        [
            "చిత్రాలు: పత్రరంధ్రం, స్త్రీ ప్రత్యుత్పత్తి వ్యవస్థ, మెదడు, గుండె",
            "Life Processes (14 + 8): జీర్ణక్రియ, శ్వాసక్రియ, రక్తప్రసరణ",
            "తేడాలు: ధమనులు–సిరలు, నాడీ–హార్మోన్ నియంత్రణ",
            "మెండల్ బఠానీ లక్షణాలు, లింగ నిర్ధారణ, ఓజోన్ క్షీణత",
        ],
    ),
    ("10", "SOCIAL"): (
        "100 మార్కులు, 3 గం 15 ని, 33 ప్రశ్నలు",
        [
            "మ్యాప్ ప్రశ్న (8): భారతదేశం 4 + ప్రపంచం 4; Thar, Chennai, Godavari, Italy, Nigeria, Brazil",
            "Development (9), Nationalism in Europe (9): ముఖ్యాంశాల చిన్న నోట్స్",
            "Section I (12 × 1): తేదీలు, వ్యక్తులు, నిర్వచనాలు",
            "Power Sharing, Sectors, Globalisation (ఒక్కొక్కటి 8): పోలిక పట్టికలు",
        ],
    ),
}

# Generic remedial-coaching tips — not subject-specific, so kept as a plain
# constant rather than a DB row per subject (same as the source tool, which
# never varied these per subject either).
GENERAL_TIPS = [
    "ప్రత్యేక తరగతి: వారానికి 4 రోజులు, సాయంత్రం 45 నిమిషాలు (Rising Stars కు)",
    "ప్రతి శనివారం 20 మార్కుల స్లిప్ టెస్ట్: ఆ వారం చాప్టర్ నుంచి, మార్కులు రిజిస్టర్‌లో",
    "గత 3 సంవత్సరాల ప్రశ్నాపత్రాలు, మోడల్ పేపర్ల సాధన",
    "D1, D2 గ్రేడ్ పిల్లల తల్లిదండ్రులతో నెలకోసారి మాట్లాడటం",
    "ముందు బెంచీలో కూర్చోబెట్టి తరగతిలో తరచూ ప్రశ్నలు అడగడం",
]


def seed(conn: psycopg.Connection) -> None:
    for (class_level, subject), topics in BLUEPRINT_BY_CLASS_SUBJECT.items():
        existing = conn.execute(
            "SELECT 1 FROM subject_blueprint WHERE class_level = %s AND subject = %s LIMIT 1", (class_level, subject)
        ).fetchone()
        if existing:
            continue
        for order, (topic_name, marks, choice_marks) in enumerate(topics):
            conn.execute(
                "INSERT INTO subject_blueprint (class_level, subject, topic_name, marks, choice_marks, sort_order) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (class_level, subject, topic_name, marks, choice_marks, order),
            )

    for (class_level, subject), (exam_format, tips) in EXAM_INFO_BY_CLASS_SUBJECT.items():
        existing = conn.execute(
            "SELECT 1 FROM subject_exam_info WHERE class_level = %s AND subject = %s LIMIT 1", (class_level, subject)
        ).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO subject_exam_info (class_level, subject, exam_format, tips) VALUES (%s, %s, %s, %s)",
            (class_level, subject, exam_format, json.dumps(tips)),
        )
