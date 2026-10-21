export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  default_school_name: string;
}

export interface BatchSummary {
  id: number;
  name: string;
  school_name: string;
  fa_total: number;
  sa_total: number;
  fa_marks_per_subject: number;
  sa_marks_per_subject: number;
  class_strength_override: number | null;
  class_level: string;
  source_filename: string | null;
  exam_codes: string[];
  created_at: string;
  student_count: number;
}

export interface StudentBrief {
  id: number;
  name: string;
  section: string;
  roll_no: string;
  phone: string;
}

export interface BatchDetail extends BatchSummary {
  students: StudentBrief[];
}

export interface GradeCount {
  grade: string;
  count: number;
}

export interface SubjectAverage {
  subject: string;
  avg_marks: number;
  max_marks: number;
  avg_pct: number;
}

export interface RankedStudent {
  id: number;
  name: string;
  rank: number | null;
  total_marks: number | string;
  grade: string;
  reason?: "fail" | "low";
}

export interface ExamTrendPoint {
  exam: string;
  avg_pct: number | null;
}

export interface ClassStats {
  selected_exam: string | null;
  available_exams: string[];
  total_students: number;
  class_strength: number;
  graded_count: number;
  pass_count: number;
  fail_count: number;
  grade_distribution: GradeCount[];
  subject_averages: SubjectAverage[];
  top_students: RankedStudent[];
  attention_students: RankedStudent[];
  avg_attendance_pct: number | null;
  exam_trend: ExamTrendPoint[];
}

export interface SendResult {
  student_id: number;
  name: string;
  channel: "whatsapp" | "sms" | "none";
  status: "sent" | "failed" | "skipped";
  detail: string;
  report_url: string | null;
}

export interface TtClass {
  id: number;
  grade: string;
  section: string;
}

export interface TtSubject {
  id: number;
  name: string;
  code: string;
}

export interface TtTeacher {
  id: number;
  name: string;
  code: string;
  max_periods_per_day: number | null;
  subject_ids: number[];
}

export interface TtClassSubject {
  subject_id: number;
  subject_name: string;
  subject_code: string;
  teacher_id: number | null;
  teacher_name: string | null;
  teacher_code: string | null;
  periods_per_week: number;
}

export interface TtBreak {
  after_period: number;
  duration_minutes: number;
  label: string;
}

export interface TtTimetableEntry {
  day: string;
  period: number;
  subject_id: number;
  subject_name: string;
  subject_code: string;
  teacher_id: number | null;
  teacher_name: string | null;
  teacher_code: string | null;
}

export interface TtGenerateResult {
  ok: boolean;
  classes_generated: number;
  total_periods_placed: number;
  issues: { class_name: string; subject_name: string; reason: string }[];
}

export interface TtSchoolConfig {
  working_days: string[];
  periods_per_day: number;
  start_time: string;
  end_time: string;
  breaks: TtBreak[];
}
