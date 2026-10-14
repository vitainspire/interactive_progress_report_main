from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.db import repository as repo

SUBJECT_ALIASES = {
    "MATH": "MATHS",
    "MATHS": "MATHS",
    "MATHEMATICS": "MATHS",
    "SCIENCE": "PHYSICAL SCIENCE",
    "PHYSICS": "PHYSICAL SCIENCE",
    "PS": "PHYSICAL SCIENCE",
    "BIO": "BIOLOGY",
    "BIOLOGY": "BIOLOGY",
    "SST": "SOCIAL",
    "SOCIAL": "SOCIAL",
    "SOCIALSTUDIES": "SOCIAL",
    "TELUGU": "TELUGU",
    "HINDI": "HINDI",
    "ENGLISH": "ENGLISH",
}

PHASE_ALIAS_PATTERNS = [
    (r"\bfa[\s\-]?(\d+)\b", "FA{0}"),
    (r"\bformative\s*assessment[\s\-]?(\d+)\b", "FA{0}"),
    (r"\bsa[\s\-]?(\d+)\b", "SA{0}"),
    (r"\bsummative\s*assessment[\s\-]?(\d+)\b", "SA{0}"),
    (r"\bpre[\s\-]?final\b", "PREFINAL"),
]


@dataclass
class Vocab:
    sections: list[str]
    subjects: list[str]
    phase_codes: list[str]
    students: list[sqlite3.Row]


def load_vocab(conn: sqlite3.Connection, user_id: int, class_id: int) -> Vocab:
    return Vocab(
        sections=repo.list_sections(conn, user_id, class_id),
        subjects=repo.list_subjects(conn, user_id, class_id),
        phase_codes=[p["code"] for p in repo.list_phases(conn, user_id, class_id)],
        students=repo.list_students(conn, user_id, class_id),
    )
