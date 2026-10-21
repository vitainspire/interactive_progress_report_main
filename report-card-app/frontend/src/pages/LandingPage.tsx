import { Link } from "react-router-dom";
import { BarChartIcon, SheetIcon, SpeakerWaveIcon, TeluguGlyphIcon } from "../components/Icons";
import classOverviewScreenshot from "../assets/landing/class-overview.png";
import reportCardScreenshot from "../assets/landing/report-card.png";

function ReportCardShot() {
  return (
    <div
      className="w-full max-w-sm overflow-hidden rounded-lg"
      style={{
        boxShadow: "var(--shadow-pop)",
        transform: "rotate(-2.5deg)",
        border: "1px solid rgba(15,23,42,0.08)",
      }}
    >
      <img src={reportCardScreenshot} alt="A real parent report page, exactly as a parent sees it on their phone" className="block w-full" />
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
            <ReportCardShot />
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
          <div className="mt-10 grid grid-cols-1 gap-10 sm:grid-cols-2">
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
              title="A printable analysis for every subject"
              body="Pick any subject and see grade trends, top performers, and students needing attention for the whole class — plus which exam chapters are worth the most marks, from the real SSC blueprint."
            />
          </div>
        </section>

        <section className="border-y" style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}>
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-6 py-16 md:grid-cols-2 md:py-24">
            <div>
              <span className="icon-chip" style={{ width: "2.2rem", height: "2.2rem" }}>
                <BarChartIcon size={18} />
              </span>
              <h2
                className="mt-4 font-serif text-2xl font-semibold md:text-3xl"
                style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}
              >
                See the whole class at a glance
              </h2>
              <p className="mt-4 max-w-md text-base leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                Pass rate, grade distribution, subject averages, and who needs attention — computed the moment you
                upload, from the same sheet, no extra work. This is the real dashboard, not a mockup.
              </p>
            </div>
            <div className="overflow-hidden rounded-lg" style={{ boxShadow: "var(--shadow-pop)", border: "1px solid rgba(15,23,42,0.08)" }}>
              <img
                src={classOverviewScreenshot}
                alt="The real class overview dashboard: pass rate, grade distribution, subject averages, top performers, and students needing attention"
                className="block w-full"
              />
            </div>
          </div>

          <div className="mx-auto max-w-3xl border-t px-6 py-16 md:py-24" style={{ borderColor: "var(--border)" }}>
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
