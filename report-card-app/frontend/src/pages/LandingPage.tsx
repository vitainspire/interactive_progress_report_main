import { Link } from "react-router-dom";
import { BarChartIcon, SheetIcon, SpeakerWaveIcon, TeluguGlyphIcon } from "../components/Icons";

function ReportCardMock() {
  const rows = [
    { subject: "TELUGU", fa: "45", sa: "70", grade: "A2", tone: "ga" },
    { subject: "ENGLISH", fa: "41", sa: "66", grade: "B1", tone: "gb" },
    { subject: "MATHS", fa: "48", sa: "77", grade: "A1", tone: "ga" },
  ];
  const toneColor: Record<string, string> = { ga: "#16a34a", gb: "#2563eb" };

  return (
    <div
      className="w-full max-w-sm rounded-lg p-4"
      style={{
        background: "linear-gradient(155deg, #eef2ff 0%, #fffbea 100%)",
        boxShadow: "var(--shadow-pop)",
        transform: "rotate(-2.5deg)",
      }}
    >
      <div className="overflow-hidden rounded-md" style={{ background: "#fff", border: "1px solid rgba(15,23,42,0.08)" }}>
        <div
          className="px-4 py-2.5 text-center text-sm font-bold text-white"
          style={{ background: "linear-gradient(120deg, var(--lp-navy), #2563eb 70%)" }}
        >
          S.P.P HIGH SCHOOL
        </div>
        <div className="flex justify-center" style={{ background: "#fff" }}>
          <span
            className="-mt-2.5 rounded-full px-4 py-1 text-[10px] font-bold tracking-wide text-[#1b1b1b]"
            style={{ background: "linear-gradient(90deg, var(--lp-gold), #f5b700)" }}
          >
            STUDENT REPORT CARD
          </span>
        </div>
        <div className="px-4 pb-1 pt-3 text-[11px] font-semibold" style={{ color: "var(--lp-navy)" }}>
          ARAVA LAKSHMI <span className="font-normal text-slate-400">· Class 10 · Roll 7</span>
        </div>
        <table className="mt-1 w-full text-[11px]">
          <thead>
            <tr style={{ background: "#f1f5fb", color: "#475569" }}>
              <th className="px-3 py-1 text-left font-semibold">Subject</th>
              <th className="px-2 py-1 font-semibold">FA-1</th>
              <th className="px-2 py-1 font-semibold">SA-1</th>
              <th className="px-2 py-1 font-semibold">Grade</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.subject} style={{ borderTop: "1px solid #eef1f6" }}>
                <td className="px-3 py-1 font-medium" style={{ color: "var(--lp-navy)" }}>
                  {r.subject}
                </td>
                <td className="px-2 py-1 text-center text-slate-500">{r.fa}</td>
                <td className="px-2 py-1 text-center text-slate-500">{r.sa}</td>
                <td className="px-2 py-1 text-center">
                  <span className="rounded-full px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: toneColor[r.tone] }}>
                    {r.grade}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between px-4 py-2.5 text-[10px]" style={{ background: "#f8fafc", color: "#64748b" }}>
          <span>
            Rank <b style={{ color: "var(--lp-navy)" }}>3</b> of 62
          </span>
          <span>Attendance 92%</span>
        </div>
      </div>
    </div>
  );
}

function Feature({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div>
      <div
        className="flex h-10 w-10 items-center justify-center rounded-md"
        style={{ background: "var(--lp-gold-soft)", color: "var(--lp-navy)" }}
      >
        {icon}
      </div>
      <h3 className="mt-3 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h3>
      <p className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {body}
      </p>
    </div>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="flex gap-4">
      <div
        className="flex h-8 w-8 flex-none items-center justify-center rounded-full text-sm font-bold"
        style={{ background: "var(--lp-navy)", color: "#fff" }}
      >
        {n}
      </div>
      <div>
        <h3 className="font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}
        </h3>
        <p className="mt-1 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {body}
        </p>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <div style={{ background: "var(--page-plane)" }}>
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <span className="icon-chip font-display" style={{ width: "2.2rem", height: "2.2rem", fontWeight: 700 }}>
            RC
          </span>
          <span className="hidden font-display text-base font-bold sm:inline" style={{ color: "var(--text-primary)" }}>
            Report Card Generator
          </span>
        </div>
        <nav className="flex flex-none items-center gap-1 sm:gap-2">
          <Link
            to="/login"
            className="whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold transition-colors duration-200 hover:bg-[var(--accent-soft)] sm:px-4"
            style={{ color: "var(--text-primary)" }}
          >
            Log in
          </Link>
          <Link to="/signup" className="accent-fill whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold text-white sm:px-4">
            Get started
          </Link>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 pb-16 pt-10 md:grid-cols-2 md:pb-24 md:pt-16">
          <div>
            <h1
              className="font-serif text-[2.6rem] font-semibold leading-[1.08] tracking-tight md:text-[3.4rem]"
              style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}
            >
              One spreadsheet.
              <br />
              Every report card, done.
            </h1>
            <p className="mt-5 max-w-md text-base leading-relaxed md:text-lg" style={{ color: "var(--text-secondary)" }}>
              Upload your class's marks once and get bilingual report cards, a class performance overview, and
              parent-ready WhatsApp links — no manual formatting, no translating by hand.
            </p>
            <div className="mt-7 flex flex-col items-start gap-3">
              <Link to="/signup" className="accent-fill rounded-md px-6 py-3.5 text-base font-semibold text-white">
                Create your first report card
              </Link>
              <Link to="/login" className="text-sm font-medium underline-offset-4 hover:underline" style={{ color: "var(--text-secondary)" }}>
                Already using it? Log in
              </Link>
            </div>
          </div>
          <div className="flex justify-center md:justify-end">
            <ReportCardMock />
          </div>
        </section>

        <section className="border-y" style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}>
          <div className="mx-auto max-w-3xl px-6 py-14 text-center">
            <p className="font-serif text-xl leading-snug md:text-2xl" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
              Report card season usually means a week of copy-pasting marks into a template, translating comments by
              hand, and printing cards parents only glance at before setting them aside.
            </p>
            <p className="mt-3 text-base" style={{ color: "var(--text-secondary)" }}>
              This replaces that week with one upload.
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-16 md:py-24">
          <h2 className="font-serif text-2xl font-semibold md:text-3xl" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
            What happens when you upload a sheet
          </h2>
          <div className="mt-10 grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4">
            <Feature
              icon={<SheetIcon size={22} />}
              title="Upload once, generate for the whole class"
              body="Any school's Excel or Google Sheets layout — subjects, exams, and attendance are read automatically, no template to match."
            />
            <Feature
              icon={<TeluguGlyphIcon size={22} />}
              title="Every card speaks Telugu, automatically"
              body="Each report includes a plain-language summary of strengths, weak subjects, and attendance, written in Telugu from the marks — not a generic template."
            />
            <Feature
              icon={<SpeakerWaveIcon size={22} />}
              title="Parents don't have to read to understand"
              body="The link sent to parents is a page per subject plus a results page, with a listen button that narrates it in Telugu — built for a phone, not a printer."
            />
            <Feature
              icon={<BarChartIcon size={22} />}
              title="See the whole class at a glance"
              body="Pass rate, grade distribution, subject averages, and who needs attention — computed from the same upload, no extra work."
            />
          </div>
        </section>

        <section className="border-y" style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}>
          <div className="mx-auto max-w-3xl px-6 py-16 md:py-24">
            <h2 className="font-serif text-2xl font-semibold md:text-3xl" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
              How it works
            </h2>
            <div className="mt-10 space-y-8">
              <Step n="1" title="Upload your marks sheet" body="An Excel file, a CSV export, or a Google Sheets link — whatever your school already uses." />
              <Step
                n="2"
                title="Check the class overview"
                body="See pass rate, grade distribution, and who needs attention before anything goes out."
              />
              <Step
                n="3"
                title="Print or send"
                body="Print the full set for your records, or send each parent their own child's link over WhatsApp or SMS."
              />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20 text-center md:py-28">
          <h2 className="font-serif text-2xl font-semibold md:text-3xl" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
            Ready to see your class's first report card?
          </h2>
          <div className="mt-7">
            <Link to="/signup" className="accent-fill inline-block rounded-md px-7 py-3.5 text-base font-semibold text-white">
              Get started
            </Link>
          </div>
        </section>
      </main>

      <footer className="px-6 py-8 text-center text-xs" style={{ color: "var(--text-muted)" }}>
        <span className="font-display font-semibold" style={{ color: "var(--text-secondary)" }}>
          Report Card Generator
        </span>
        {" · "}
        <Link to="/login" className="hover:underline">
          Log in
        </Link>
        {" · "}
        <Link to="/signup" className="hover:underline">
          Register
        </Link>
      </footer>
    </div>
  );
}
