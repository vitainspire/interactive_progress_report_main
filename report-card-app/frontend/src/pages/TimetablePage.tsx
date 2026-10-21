import { Link } from "react-router-dom";
import { CalendarIcon } from "../components/Icons";

export function TimetablePage() {
  return (
    <section>
      <Link to="/tools" className="text-sm font-medium underline-offset-4 hover:underline" style={{ color: "var(--text-secondary)" }}>
        ← All tools
      </Link>

      <div className="soft-card mt-4 flex flex-col items-center p-10 text-center">
        <span className="icon-chip" style={{ width: "3rem", height: "3rem" }}>
          <CalendarIcon size={22} />
        </span>
        <h1 className="font-display mt-4 text-xl font-bold" style={{ color: "var(--text-primary)" }}>
          Timetable Creator
        </h1>
        <p className="mt-2 max-w-md text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          Build your school's weekly timetable across every class and teacher, and instantly find a substitute when
          someone's absent. This tool is on its way — it'll appear here once it's ready.
        </p>
      </div>
    </section>
  );
}
