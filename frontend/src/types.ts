export type Role = "admin" | "teacher" | "student";

export interface SchoolClass {
  id: number;
  name: string;
  short_code: string | null;
  order_index: number;
  sections: string[];
  total_students: number;
}

export interface TeacherAssignment {
  class_id: number;
  section: string;
  subjects: string[];
  restricted: boolean;
}

export interface TeacherAccount {
  id: number;
  email: string;
  display_name: string;
  assignments: TeacherAssignment[];
}

export interface StudentAccount {
  id: number;
  display_name: string;
  roll_no: string;
  student_id: number;
  section: string;
  class_id: number;
}

export interface AccountsResponse {
  teachers: TeacherAccount[];
  students: StudentAccount[];
}

export interface TextbookTopic {
  chapter_no: string | null;
  title: string;
  page: number | null;
}

export interface Textbook {
  subject: string;
  filename: string;
  uploaded_at: string;
  topics: TextbookTopic[];
}

export interface FocusTopics {
  subject: string;
  topics: TextbookTopic[];
}

export interface Student {
  id: number;
  s_no: number | null;
  section: string;
  name: string;
  gender: string | null;
  father_name: string | null;
  mother_name: string | null;
  latest_phase_code: string | null;
  latest_result: string | null;
  latest_total_marks: number | null;
  latest_max_total: number | null;
  total_present: number | null;
  total_working_days: number | null;
}

export interface FailureRow {
  student_id: number;
  phase_code: string;
  subject: string;
  marks: number | null;
  max_marks: number | null;
  grade: string | null;
  name: string;
  section: string;
}

export interface Phase {
  code: string;
  label: string;
  order_index: number;
}

export interface Meta {
  sections: string[];
  subjects: string[];
  phases: Phase[];
  total_students: number;
}

export interface ExamResult {
  id: number;
  student_id: number;
  phase_code: string;
  subject: string;
  marks: number | null;
  max_marks: number | null;
  grade: string | null;
  is_pass: boolean | null;
}

export interface ExamSummary {
  id: number;
  student_id: number;
  phase_code: string;
  total_marks: number | null;
  max_total: number | null;
  total_grade: string | null;
  result: string | null;
  rank: number | null;
}

export interface SubjectTrendPoint {
  phase_code: string;
  marks: number;
  max_marks: number;
  pct: number;
  grade: string | null;
}

export interface SubjectTrend {
  subject: string;
  direction: "improving" | "declining" | "stable" | "fluctuating" | "single" | "no_data";
  points: SubjectTrendPoint[];
}

export interface AttendanceMonth {
  id: number;
  student_id: number;
  month: string;
  days_present: number | null;
  working_days: number | null;
}

export interface AttendanceSummary {
  student_id: number;
  total_present: number | null;
  total_working_days: number | null;
}

export interface StudentDetail {
  student: Student;
  total_students_in_class: number;
  exam_summaries: ExamSummary[];
  exam_results: ExamResult[];
  subject_trends: SubjectTrend[];
  attendance_months: AttendanceMonth[];
  attendance_summary: AttendanceSummary | null;
  focus_topics: FocusTopics[];
  subject_restricted: boolean;
  own_subjects: string[];
  showing_all_subjects: boolean;
}

export interface ChartSpec {
  type: "bar" | "line";
  title: string;
  data: { name: string; value: number | null }[];
}

export interface QueryResponse {
  answer: string;
  intent: string;
  table: { columns: string[]; rows: (string | number)[][] } | null;
  chart: ChartSpec | null;
  suggestions: string[];
}

export interface DashboardData {
  total_students: number;
  sections: string[];
  phases: Phase[];
  phase_section_summary: {
    phase_code: string;
    section: string | null;
    student_count: number;
    average_total: number | null;
    max_total: number | null;
    passed: number;
    failed: number;
  }[];
  latest_phase_subject_averages: { subject: string; average: number; max_marks: number }[];
}

export interface Settings {
  school_name: string;
  school_udise: string;
  headmaster_name: string;
  headmaster_phone: string;
}
