export type WhatsappLanguage = "te" | "en_US";
export type WhatsappChannelMode = "whatsapp_then_sms" | "whatsapp_only" | "sms_only";

export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  default_school_name: string;
  school_address: string;
  has_school_photo: boolean;
  whatsapp_language: WhatsappLanguage;
  whatsapp_channel_mode: WhatsappChannelMode;
  default_country_code: string;
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
  total_fa_exams: number;
  total_sa_exams: number;
  class_level: string;
  source_filename: string | null;
  source_type: "file" | "sheet_link" | "drive_folder_item";
  source_folder_id: string | null;
  last_synced_at: string | null;
  exam_codes: string[];
  created_at: string;
  student_count: number;
}

export interface BatchSyncResult {
  batch: BatchSummary;
  added: number;
  updated: number;
  removed: number;
}

export interface DriveImportFileResult {
  file_name: string;
  status: "created" | "synced" | "failed" | "possible_duplicate";
  batch_id?: number;
  student_count?: number;
  added?: number;
  updated?: number;
  removed?: number;
  error?: string;
  // Present when status is "possible_duplicate" — everything needed to
  // call POST /batches/resolve-drive-duplicate without re-pasting the folder link.
  file_id?: string;
  mime_type?: string;
  folder_id?: string | null;
  candidate_batch_id?: number;
  candidate_batch_name?: string;
  overlap_count?: number;
  existing_student_count?: number;
  new_student_count?: number;
}

export interface ReferenceDocumentImportResult {
  file_name: string;
  status: "pending" | "failed";
  reference_document_id?: number;
  error?: string;
}

export interface DriveImportFolderResult {
  folder_id: string;
  results: DriveImportFileResult[];
  reference_documents: ReferenceDocumentImportResult[];
}

export interface DriveSyncFolderResult {
  results: DriveImportFileResult[];
  missing_batches: { id: number; name: string }[];
  reference_documents: ReferenceDocumentImportResult[];
}

export interface SyllabusChapterDraft {
  chapter_no: number;
  chapter_name: string;
  genre?: string | null;
  theme?: string | null;
  author?: string | null;
  month?: string | null;
  periods?: number | null;
  page_range?: string | null;
}

export interface BlueprintTopicDraft {
  topic_name: string;
  marks: number;
  choice_marks?: number | null;
}

export interface ReferenceDocumentExtraction {
  subject_guess: string | null;
  class_level_guess: string | null;
  document_type: "syllabus" | "blueprint" | "unknown";
  chapters: SyllabusChapterDraft[];
  topics: BlueprintTopicDraft[];
  exam_format: string | null;
  tips: string[];
}

export interface ReferenceDocument {
  id: number;
  file_name: string;
  mime_type: string;
  status: "pending" | "confirmed" | "rejected" | "failed";
  error: string | null;
  created_at: string;
  extracted: ReferenceDocumentExtraction | null;
}

export interface StudentBrief {
  id: number;
  name: string;
  section: string;
  roll_no: string;
  phone: string;
}

export interface StudentSubjectExamPoint {
  exam: string;
  marks: number | null;
  grade: string;
  max_marks: number;
  class_avg: number | null;
}

export interface StudentAnalyticsSubject {
  name: string;
  per_exam: StudentSubjectExamPoint[];
  trend: "up" | "down" | "flat" | null;
}

export interface StudentRankTrendPoint {
  exam: string;
  rank: number;
  class_strength: number;
  total_marks: number | null;
  grade: string;
}

export interface StudentAttendanceMonthPoint {
  month: string;
  attended: number;
  working_days: number;
}

export interface AdviceCard {
  icon: string;
  title: string;
  text: string;
}

export interface StudentStudyPlan {
  available: boolean;
  subject?: string;
  plan?: string;
}

export interface StudentAnalytics {
  id: number;
  name: string;
  section: string;
  roll_no: string;
  exams: string[];
  subjects: StudentAnalyticsSubject[];
  rank_trend: StudentRankTrendPoint[];
  attendance_trend: StudentAttendanceMonthPoint[];
  attendance_total: { present: number; working: number } | null;
  strengths: string[];
  weak_subjects: string[];
  failing_subjects: string[];
  advice_cards: AdviceCard[];
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
  excluded_periods: number[];
}

export interface TtTeacher {
  id: number;
  name: string;
  code: string;
  phone: string;
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

export interface TtTeacherTimetableEntry {
  day: string;
  period: number;
  class_id: number;
  class_name: string;
  subject_id: number;
  subject_name: string;
  subject_code: string;
}

export interface TtTeacherSubstitution {
  day: string;
  period: number;
  class_id: number;
  class_name: string;
  subject_id: number | null;
  subject_name: string | null;
}

export interface TtGenerateResult {
  ok: boolean;
  classes_generated: number;
  total_periods_placed: number;
  issues: { class_name: string; subject_name: string; reason: string }[];
}

export interface TtSubstituteCandidate {
  teacher_id: number;
  teacher_name: string;
  teacher_code: string;
  reason: "subject" | "class" | "other";
}

export interface TtSubstituteOptions {
  original: { subject_id: number; subject_name: string; teacher_id: number | null; teacher_name: string | null };
  candidates: TtSubstituteCandidate[];
}

export interface TtSubstitution {
  day: string;
  period: number;
  subject_id: number | null;
  subject_name: string | null;
  original_teacher_id: number | null;
  original_teacher_name: string | null;
  substitute_teacher_id: number;
  substitute_teacher_name: string;
}

export type TtNotifyStatus = "sent" | "failed" | "not_sent_no_phone" | "not_sent_sms_unconfigured" | "not_sent_invalid_phone";

export interface TtSubstitutionResult extends TtSubstitution {
  date: string;
  notify_status: TtNotifyStatus;
}

export interface TtSubstituteNotifyResult {
  class_name: string;
  period: number;
  subject_name: string | null;
  substitute_teacher_name: string;
  substitute_teacher_code: string;
  notify_status: TtNotifyStatus;
}

export interface TtLeave {
  id: number;
  teacher_id: number;
  teacher_name: string;
  teacher_code: string;
  start_date: string;
  end_date: string;
  reason: string;
}

export interface TtPendingNeed {
  leave_id: number;
  teacher_id: number;
  teacher_name: string;
  date: string;
  day: string;
  period: number;
  class_id: number;
  class_name: string;
  subject_id: number;
  subject_name: string;
  candidates: TtSubstituteCandidate[];
}

export interface TtPartialBusyEntry {
  teacher_id: number;
  periods: number[];
}

export interface TtGenerateDayRequest {
  date: string;
  whole_day_absent_teacher_ids: number[];
  partial_busy: TtPartialBusyEntry[];
}

export interface TtGeneratedSlot {
  class_id: number;
  class_name: string;
  day: string;
  period: number;
  subject_id: number | null;
  subject_name: string | null;
  original_teacher_id: number | null;
  substitute_teacher_id?: number;
  substitute_teacher_name?: string;
  substitute_teacher_code?: string;
}

export interface TtGenerateDayResult {
  date: string;
  day: string;
  resolved: TtGeneratedSlot[];
  unresolved: TtGeneratedSlot[];
}

export interface TtSchoolConfig {
  working_days: string[];
  periods_per_day: number;
  start_time: string;
  end_time: string;
  breaks: TtBreak[];
}

export interface TtImportClass {
  label: string;
  grade: string;
  section: string;
}

export interface TtImportGridCell {
  subject_code: string;
  teacher_code: string;
}

// class label -> day -> period (as a string key, since it round-trips
// through JSON) -> the cell found there.
export type TtImportGrid = Record<string, Record<string, Record<string, TtImportGridCell>>>;

export interface TtImportPreview {
  classes: TtImportClass[];
  subject_codes: string[];
  teacher_codes: string[];
  grid: TtImportGrid;
}

export interface TtImportConfirmResult {
  ok: boolean;
  classes_imported: number;
  periods_imported: number;
}
