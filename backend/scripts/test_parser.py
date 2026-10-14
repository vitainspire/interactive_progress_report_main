import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.parsing.xlsx_parser import parse_workbook

result = parse_workbook(r"D:\inteactive progress report\PROGRESS 1.xlsx")
print("Phases:", [(p.code, p.label, p.start_col, p.end_col) for p in result.phases])
print("Student count:", len(result.students))
print("Headmaster:", result.headmaster_name)
print("Staff entries:", len(result.staff))
for s in result.staff[:16]:
    print(" ", s)

abhishek = next(s for s in result.students if "ABHISHEK" in s.name.upper())
print("\n--- Abhishek record ---")
print("name/section:", abhishek.name, abhishek.section)
for code, exam in abhishek.exams.items():
    print(code, exam)
print("attendance:", abhishek.attendance)
print("total present/working:", abhishek.total_present, abhishek.total_working_days)

sections = {}
for s in result.students:
    sections[s.section] = sections.get(s.section, 0) + 1
print("\nSection counts:", sections)
