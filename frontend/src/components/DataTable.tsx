export function DataTable({ columns, rows }: { columns: string[]; rows: (string | number)[][] }) {
  return (
    <div className="soft-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {columns.map((c) => (
              <th
                key={c}
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide"
                style={{ color: "var(--text-secondary)" }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t transition-colors hover:bg-[var(--accent-soft)]" style={{ borderColor: "var(--gridline)" }}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={typeof cell === "number" ? "font-mono px-3 py-2 text-right" : "px-3 py-2"}
                  style={{ color: "var(--text-primary)" }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
