from __future__ import annotations

import re
from dataclasses import dataclass

from app.nlq.vocab import PHASE_ALIAS_PATTERNS, SUBJECT_ALIASES, Vocab

WORD_RE = re.compile(r"[a-zA-Z]+")
STOPWORDS = {
    "the", "a", "an", "in", "of", "for", "is", "are", "was", "were", "how", "what",
    "who", "did", "do", "does", "show", "me", "tell", "about", "and", "to", "on", "has",
    "have", "student", "students", "class", "report", "please", "mark", "marks",
}


@dataclass
class ExtractedEntities:
    phase_code: str | None
    section: str | None
    subject: str | None
    student_ids: list[int]
    student_names: list[str]
    number: int | None
    tokens: list[str]


def extract_phase(question_lower: str, known_phase_codes: list[str]) -> str | None:
    for pattern, template in PHASE_ALIAS_PATTERNS:
        m = re.search(pattern, question_lower)
        if m:
            code = template.format(*m.groups()) if m.groups() else template
            if code in known_phase_codes:
                return code
            # tolerate unseen phase numbers mentioned but not yet in data
            return code
    return None


def extract_section(question_lower: str, sections: list[str]) -> str | None:
    m = re.search(r"\bsection[\s\-]*([a-z0-9]+)\b", question_lower)
    if m:
        candidate = m.group(1).upper()
        if candidate in sections:
            return candidate
    for sec in sections:
        if re.search(rf"\b{re.escape(sec.lower())}\b", question_lower):
            # avoid false-positive on common words when section is a bare letter
            if len(sec) > 1 or re.search(rf"\bsection\s*{re.escape(sec.lower())}\b", question_lower):
                return sec
    return None


def extract_subject(question_lower: str, subjects: list[str]) -> str | None:
    for alias, canonical in sorted(SUBJECT_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{alias.lower()}\b", question_lower) and canonical in subjects:
            return canonical
    for subj in subjects:
        if subj.lower() in question_lower:
            return subj
    return None


def extract_number(question_lower: str) -> int | None:
    m = re.search(r"\btop\s*(\d+)\b", question_lower) or re.search(r"\b(\d+)\b", question_lower)
    return int(m.group(1)) if m else None


def extract_students(question: str, vocab: Vocab) -> tuple[list[int], list[str]]:
    tokens = [t for t in WORD_RE.findall(question.upper()) if len(t) >= 3 and t.lower() not in STOPWORDS]
    if not tokens:
        return [], []
    scored: list[tuple[int, sqlite3.Row]] = []
    for student in vocab.students:
        name_tokens = student["name"].split()
        score = 0
        for t in tokens:
            for nt in name_tokens:
                if nt == t or (len(t) >= 4 and nt.startswith(t)):
                    score += 1
        if score > 0:
            scored.append((score, student))
    if not scored:
        return [], []
    scored.sort(key=lambda sp: -sp[0])
    best_score = scored[0][0]
    top = [s for score, s in scored if score == best_score]
    return [s["id"] for s in top], [s["name"] for s in top]


def extract_all(question: str, vocab: Vocab) -> ExtractedEntities:
    q_lower = question.lower()
    phase = extract_phase(q_lower, vocab.phase_codes)
    section = extract_section(q_lower, vocab.sections)
    subject = extract_subject(q_lower, vocab.subjects)
    number = extract_number(q_lower)
    student_ids, student_names = extract_students(question, vocab)
    tokens = WORD_RE.findall(q_lower)
    return ExtractedEntities(phase, section, subject, student_ids, student_names, number, tokens)
