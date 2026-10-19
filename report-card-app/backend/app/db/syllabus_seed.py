"""Real AP SSC (10th class) syllabus chapters, transcribed from the actual
textbook table-of-contents pages the teacher shared, one list per subject.
Seeded once into syllabus_chapter (see schema.sql) on startup — this is
reference data shared by every batch/user, not something each teacher
re-enters. Powers app/reports/study_plan.py's syllabus-aware study plan.

Transcribed by reading the source pages directly (several used custom PDF
fonts that don't extract as real text, so OCR/text-extraction wasn't
reliable) — treat chapter names as best-effort and expect the occasional
typo, especially in Hindi/Telugu. Re-running seed() after fixing a row here
just requires deleting that subject's existing rows first (see seed()'s
"only if empty" guard below) since it never overwrites existing data.

Each entry: chapter_no, chapter_name, and whichever of genre/theme/author/
month/periods/page_range the source actually printed (language subjects
mostly skip periods/page_range page; SOCIAL here only covers the
Geography + History parts of the source image shared — Civics and
Economics chapters aren't in this list yet).
"""
from __future__ import annotations

import psycopg

PHYSICAL_SCIENCE = [
    dict(chapter_no=1, chapter_name="Heat", month="June", periods=8, page_range="1-19"),
    dict(chapter_no=2, chapter_name="Chemical Reactions and Equations", month="July", periods=8, page_range="20-44"),
    dict(chapter_no=3, chapter_name="Reflection of light by different surfaces", month="July", periods=8, page_range="45-68"),
    dict(chapter_no=4, chapter_name="Acids, Bases and Salts", month="August", periods=8, page_range="69-92"),
    dict(chapter_no=5, chapter_name="Refraction of Light at Plane Surfaces", month="August", periods=9, page_range="93-111"),
    dict(chapter_no=6, chapter_name="Refraction of Light at Curved Surfaces", month="September", periods=10, page_range="112-134"),
    dict(chapter_no=7, chapter_name="Human Eye and Colourful World", month="September-October", periods=8, page_range="135-159"),
    dict(chapter_no=8, chapter_name="Structure of Atom", month="October", periods=5, page_range="160-175"),
    dict(chapter_no=9, chapter_name="Classification of Elements - The Periodic Table", month="November", periods=10, page_range="176-201"),
    dict(chapter_no=10, chapter_name="Chemical Bonding", month="November-December", periods=10, page_range="202-227"),
    dict(chapter_no=11, chapter_name="Electric Current", month="December", periods=9, page_range="228-257"),
    dict(chapter_no=12, chapter_name="Electromagnetism", month="December-January", periods=10, page_range="258-285"),
    dict(chapter_no=13, chapter_name="Principles of Metallurgy", month="January", periods=5, page_range="286-301"),
    dict(chapter_no=14, chapter_name="Carbon and its Compounds", month="February", periods=12, page_range="302-341"),
]

BIOLOGY = [
    dict(chapter_no=1, chapter_name="Nutrition", month="June", periods=10),
    dict(chapter_no=2, chapter_name="Respiration", month="July", periods=10),
    dict(chapter_no=3, chapter_name="Transportation", month="July", periods=10),
    dict(chapter_no=4, chapter_name="Excretion", month="August", periods=10),
    dict(chapter_no=5, chapter_name="Coordination", month="September", periods=10),
    dict(chapter_no=6, chapter_name="Reproduction", month="October", periods=15),
    dict(chapter_no=7, chapter_name="Coordination in Life Processes", month="November-December", periods=10),
    dict(chapter_no=8, chapter_name="Heredity and Evolution", month="December", periods=15),
    dict(chapter_no=9, chapter_name="Our Environment", month="December", periods=10),
    dict(chapter_no=10, chapter_name="Natural Resources", month="January", periods=10),
]

MATHS = [
    dict(chapter_no=1, chapter_name="Real Numbers"),
    dict(chapter_no=2, chapter_name="Polynomials"),
    dict(chapter_no=3, chapter_name="Pair of Linear Equations in Two Variables"),
    dict(chapter_no=4, chapter_name="Quadratic Equations"),
    dict(chapter_no=5, chapter_name="Arithmetic Progressions"),
    dict(chapter_no=6, chapter_name="Triangles"),
    dict(chapter_no=7, chapter_name="Coordinate Geometry"),
    dict(chapter_no=8, chapter_name="Introduction to Trigonometry"),
    dict(chapter_no=9, chapter_name="Some Applications of Trigonometry"),
    dict(chapter_no=10, chapter_name="Tangents and Secants to a Circle"),
    dict(chapter_no=11, chapter_name="Areas Related to Circles"),
    dict(chapter_no=12, chapter_name="Surface Areas and Volumes"),
    dict(chapter_no=13, chapter_name="Statistics"),
    dict(chapter_no=14, chapter_name="Probability"),
]

# Only the Geography ("Resources Development and Equity") and History
# ("Contemporary World and India") parts were in the page shared — Civics
# and Economics chapters (Power Sharing, Federalism, Development, Sectors
# of the Indian Economy, etc., per the blueprint) aren't captured here yet.
SOCIAL = [
    dict(chapter_no=1, chapter_name="India: Relief Features", theme="Resources Development and Equity", month="June", periods=8, page_range="1-13"),
    dict(chapter_no=2, chapter_name="Ideas of Development", theme="Resources Development and Equity", month="June-July", periods=8, page_range="14-27"),
    dict(chapter_no=3, chapter_name="Production and Employment", theme="Resources Development and Equity", month="July", periods=6, page_range="28-43"),
    dict(chapter_no=4, chapter_name="Climate of India", theme="Resources Development and Equity", month="August", periods=10, page_range="44-57"),
    dict(chapter_no=5, chapter_name="Indian Rivers and Water Resources", theme="Resources Development and Equity", month="August", periods=10, page_range="58-70"),
    dict(chapter_no=6, chapter_name="The People", theme="Resources Development and Equity", month="October", periods=6, page_range="71-86"),
    dict(chapter_no=7, chapter_name="People and Settlement", theme="Resources Development and Equity", month="October", periods=6, page_range="87-100"),
    dict(chapter_no=8, chapter_name="People and Migration", theme="Resources Development and Equity", month="October-November", periods=7, page_range="101-114"),
    dict(chapter_no=9, chapter_name="Rampur: A Village Economy", theme="Resources Development and Equity", month="December-January", periods=6, page_range="115-129"),
    dict(chapter_no=10, chapter_name="Globalisation", theme="Resources Development and Equity", month="January", periods=4, page_range="130-144"),
    dict(chapter_no=11, chapter_name="Food Security", theme="Resources Development and Equity", month="January", periods=4, page_range="145-158"),
    dict(chapter_no=12, chapter_name="Sustainable Development with Equity", theme="Resources Development and Equity", month="February", periods=5, page_range="159-175"),
    dict(chapter_no=13, chapter_name="The World Between Wars 1900-1950: Part I", theme="Contemporary World and India", month="July", periods=12, page_range="176-186"),
    dict(chapter_no=14, chapter_name="The World Between Wars 1900-1950: Part II", theme="Contemporary World and India", month="July-August", periods=12, page_range="187-201"),
    dict(chapter_no=15, chapter_name="National Liberation Movements in the Colonies", theme="Contemporary World and India", month="September", periods=12, page_range="202-217"),
    dict(chapter_no=16, chapter_name="National Movement in India - Partition & Independence", theme="Contemporary World and India", month="September-October", periods=8, page_range="218-231"),
    dict(chapter_no=17, chapter_name="The Making of Independent India's Constitution", theme="Contemporary World and India", month="November", periods=8, page_range="232-247"),
    dict(chapter_no=18, chapter_name="Independent India (The First 30 Years - 1947-77)", theme="Contemporary World and India", month="November", periods=8, page_range="248-263"),
    dict(chapter_no=19, chapter_name="Emerging Political Trends 1977 to 2000", theme="Contemporary World and India", month="December", periods=10, page_range="264-281"),
    dict(chapter_no=20, chapter_name="Post-War World and India", theme="Contemporary World and India", month="December", periods=9, page_range="282-297"),
    dict(chapter_no=21, chapter_name="Social Movements in Our Times", theme="Contemporary World and India", month="February", periods=6, page_range="298-313"),
    dict(chapter_no=22, chapter_name="Citizens and the Governments", theme="Contemporary World and India", month="February", periods=5, page_range="314-320"),
]

ENGLISH = [
    dict(chapter_no=1, chapter_name="A Letter to God", genre="Prose", author="G.L. Fuentes", page_range="1"),
    dict(chapter_no=2, chapter_name="Dust of Snow", genre="Poem", author="Robert Frost", page_range="14"),
    dict(chapter_no=3, chapter_name="Fire and Ice", genre="Poem", author="Robert Frost", page_range="15"),
    dict(chapter_no=4, chapter_name="Nelson Mandela: Long Walk to Freedom", genre="Prose", author="Nelson Rolihlahla Mandela", page_range="16"),
    dict(chapter_no=5, chapter_name="A Tiger in the Zoo", genre="Poem", author="Leslie Norris", page_range="29"),
    dict(chapter_no=6, chapter_name="Two Stories about Flying - His First Flight", genre="Prose", author="Liam O'Flaherty", page_range="32"),
    dict(chapter_no=7, chapter_name="Two Stories about Flying - Black Aeroplane", genre="Prose", author="Frederick Forsyth", page_range="32"),
    dict(chapter_no=8, chapter_name="How to Tell Wild Animals", genre="Poem", author="Carolyn Wells", page_range="43"),
    dict(chapter_no=9, chapter_name="The Ball Poem", genre="Poem", author="John Berryman", page_range="46"),
    dict(chapter_no=10, chapter_name="From the Diary of Anne Frank", genre="Prose", author="Anne Frank", page_range="48"),
    dict(chapter_no=11, chapter_name="Amanda!", genre="Poem", author="Robin Klein", page_range="61"),
    dict(chapter_no=12, chapter_name="Glimpses of India - A Baker from Goa", genre="Prose", author="Lucio Rodrigues", page_range="63"),
    dict(chapter_no=13, chapter_name="Glimpses of India - Coorg", genre="Prose", author="Lokesh Abrol", page_range="63"),
    dict(chapter_no=14, chapter_name="Glimpses of India - Tea from Assam", genre="Prose", author="Arup Kumar Datta", page_range="63"),
    dict(chapter_no=15, chapter_name="The Trees", genre="Poem", author="Adrienne Rich", page_range="77"),
    dict(chapter_no=16, chapter_name="Mijbil the Otter", genre="Prose", author="Gavin Maxwell", page_range="80"),
    dict(chapter_no=17, chapter_name="Fog", genre="Poem", author="Carl Sandburg", page_range="93"),
    dict(chapter_no=18, chapter_name="Madam Rides the Bus", genre="Prose", author="Vallikkannan", page_range="94"),
    dict(chapter_no=19, chapter_name="The Tale of Custard the Dragon", genre="Poem", author="Ogden Nash", page_range="107"),
    dict(chapter_no=20, chapter_name="The Sermon at Benares", genre="Prose", page_range="111"),
    dict(chapter_no=21, chapter_name="For Anne Gregory", genre="Poem", author="William Butler Yeats", page_range="118"),
    dict(chapter_no=22, chapter_name="The Proposal", genre="Prose", author="Anton Chekhov", page_range="120"),
]

HINDI = [
    dict(chapter_no=1, chapter_name="बरसते बदल"),
    dict(chapter_no=2, chapter_name="ईदगाह"),
    dict(chapter_no=3, chapter_name="हम भारतवासी"),
    dict(chapter_no=4, chapter_name="कण-कण का अधिकारी"),
    dict(chapter_no=5, chapter_name="लोकगीत"),
    dict(chapter_no=6, chapter_name="अंतर्राष्ट्रीय स्तर पर हिंदी"),
    dict(chapter_no=7, chapter_name="भक्ति पद"),
    dict(chapter_no=8, chapter_name="स्वराज्य की नींव"),
    dict(chapter_no=9, chapter_name="दक्षिणी गंगा गोदावरी"),
    dict(chapter_no=10, chapter_name="नीति दोहे"),
    dict(chapter_no=11, chapter_name="जल ही जीवन है"),
    dict(chapter_no=12, chapter_name="धरती के सवाल अंतरिक्ष के जवाब"),
    dict(chapter_no=13, chapter_name="पठन हेतु"),
    dict(chapter_no=14, chapter_name="उपवाचक"),
    dict(chapter_no=15, chapter_name="शब्दकोश"),
]

TELUGU = [
    dict(chapter_no=1, chapter_name="ప్రత్యక్ష దైవాలు", genre="ఇతిహాసం", theme="తల్లిదండ్రుల సేవ", author="ఎల్చూరి", month="జూన్", page_range="01"),
    dict(chapter_no=2, chapter_name="బతుకు గంప", genre="కథానిక", theme="కుటుంబ విలువలు", author="మూలింటి చంద్రకళ", month="జూలై", page_range="15"),
    dict(chapter_no=3, chapter_name="శతక మాధుర్యం", genre="శతకం", theme="నైతిక విలువలు", author="వివిధ శతక కవులు", month="జూలై", page_range="27"),
    dict(chapter_no=4, chapter_name="ఉపన్యాస కళ", genre="వ్యాసం", theme="జీవననైపుణ్యం", author="వాసిరెడ్డి సీతాదేవి", month="ఆగస్టు", page_range="38"),
    dict(chapter_no=5, chapter_name="జలియన్‌వాలా బాగ్", genre="ఖండ కావ్యం", theme="దేశభక్తి", author="ఉమర్ అలీషా", month="ఆగస్టు", page_range="52"),
    dict(chapter_no=6, chapter_name="ప్రకృతి సందేశం", genre="గేయం", theme="ప్రకృతి వర్ణన", author="వై.సి.వి. రెడ్డి", month="సెప్టెంబర్", page_range="65"),
    dict(chapter_no=7, chapter_name="చేసారిన బాల్యం", genre="వ్యాసం", theme="వ్యక్తిత్వ వికాసం", author="శీలా వీర్రాజు", month="సెప్టెంబర్", page_range="76"),
    dict(chapter_no=8, chapter_name="జీవని", genre="కథ", theme="ప్రత్యేక అవసరాల పిల్లలు-చేయూత", author="వి. చంద్రశేఖరరావు", month="అక్టోబర్", page_range="86"),
    dict(chapter_no=9, chapter_name="రాజధర్మం", genre="ప్రబంధం", theme="నాయకత్వ లక్షణాలు", author="శ్రీకృష్ణదేవరాయలు", month="నవంబర్", page_range="100"),
    dict(chapter_no=10, chapter_name="కన్యాశుల్కం", genre="నాటకం", theme="ఆధునిక విద్యా ఆవశ్యకత", author="గురజాడ అప్పారావు", month="డిసెంబర్", page_range="112"),
    dict(chapter_no=11, chapter_name="యుద్ధ విజేత", genre="వచన కవిత", theme="శాంతి అవశ్యకత", author="నేతల ప్రతాప్ కుమార్", month="డిసెంబర్", page_range="128"),
    dict(chapter_no=12, chapter_name="సూక్తి సుధ", genre="సాహిత్యవ్యాసం", theme="ఉత్తమానవ గుణాలు", author="ఎస్.గంగప్ప", month="జనవరి", page_range="138"),
    dict(chapter_no=13, chapter_name="రామాయణం (ఉపవాచకం)", genre="ఇతిహాస కథ", theme="సంస్కృతి విలువలు", author="వాల్మీకి రామాయణం సంక్షిప్త వచనరూపం", month="జూలై-ఫిబ్రవరి", page_range="151-194"),
]

# Keyed by the normalized (uppercase) subject name this app already uses
# elsewhere (see exam_subject_result.subject / chat_canned.py's bucketing) —
# aliases for alternate spellings a teacher's sheet might use are handled in
# app/reports/study_plan.py, not duplicated here.
SYLLABUS_BY_SUBJECT: dict[str, list[dict]] = {
    "PHYSICAL SCIENCE": PHYSICAL_SCIENCE,
    "BIOLOGY": BIOLOGY,
    "MATHS": MATHS,
    "SOCIAL": SOCIAL,
    "ENGLISH": ENGLISH,
    "HINDI": HINDI,
    "TELUGU": TELUGU,
}


def seed(conn: psycopg.Connection) -> None:
    """Inserts each subject's chapters only if that subject has no rows yet
    — safe to call on every startup (see init_db), and never overwrites a
    subject someone has already corrected/edited in the database."""
    for subject, chapters in SYLLABUS_BY_SUBJECT.items():
        existing = conn.execute("SELECT 1 FROM syllabus_chapter WHERE subject = %s LIMIT 1", (subject,)).fetchone()
        if existing:
            continue
        for ch in chapters:
            conn.execute(
                "INSERT INTO syllabus_chapter (subject, chapter_no, chapter_name, genre, theme, author, month, periods, page_range) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    subject,
                    ch["chapter_no"],
                    ch["chapter_name"],
                    ch.get("genre"),
                    ch.get("theme"),
                    ch.get("author"),
                    ch.get("month"),
                    ch.get("periods"),
                    ch.get("page_range"),
                ),
            )
