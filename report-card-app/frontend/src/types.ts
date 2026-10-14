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

export interface SendResult {
  student_id: number;
  name: string;
  channel: "whatsapp" | "sms" | "none";
  status: "sent" | "failed" | "skipped";
  detail: string;
  report_url: string | null;
}
