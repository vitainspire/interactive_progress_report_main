const isDark = typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;

export const palette = {
  series: isDark
    ? ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
    : ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  status: {
    good: "#16a34a",
    warning: "#f59e0b",
    serious: "#ec835a",
    critical: isDark ? "#f87171" : "#dc2626",
  },
  gridline: isDark ? "#1f2937" : "#eef1f6",
  axis: isDark ? "#334155" : "#cbd5e1",
  mutedText: isDark ? "#64748b" : "#94a3b8",
  surface: isDark ? "#17213a" : "#ffffff",
};

export function seriesColor(index: number): string {
  return palette.series[index % palette.series.length];
}

const SECTION_COLOR_ORDER = ["A", "B", "C", "D", "E", "F"];
export function sectionColor(section: string): string {
  const idx = SECTION_COLOR_ORDER.indexOf(section.toUpperCase());
  return seriesColor(idx >= 0 ? idx : 0);
}

// Matches the server's preferred subject order (app/reports/insights.py) so a
// subject keeps the same color everywhere it's charted.
const SUBJECT_COLOR_ORDER = ["TELUGU", "HINDI", "ENGLISH", "MATHS", "PHYSICAL SCIENCE", "BIOLOGY", "SOCIAL"];
export function subjectColor(subject: string): string {
  const idx = SUBJECT_COLOR_ORDER.indexOf(subject.toUpperCase());
  return seriesColor(idx >= 0 ? idx : SUBJECT_COLOR_ORDER.length);
}
