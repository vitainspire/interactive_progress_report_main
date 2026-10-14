import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { palette } from "../palette";

export interface ChartDatum {
  name: string;
  value: number | null;
}

const tooltipStyle = {
  background: palette.surface,
  border: `1px solid ${palette.gridline}`, boxShadow: "var(--shadow-pop)",
  borderRadius: 12,
  fontSize: 13,
  fontFamily: "var(--font-mono)",
  color: "var(--text-primary)",
};

const axisTickStyle = { fill: palette.mutedText, fontSize: 12, fontFamily: "var(--font-body)" };

export function SimpleBarChart({
  data,
  colorByIndex,
  height = 220,
  valueLabel,
}: {
  data: ChartDatum[];
  colorByIndex?: (index: number, name: string) => string;
  height?: number;
  valueLabel?: string;
}) {
  const clean = data.filter((d) => d.value !== null) as { name: string; value: number }[];
  if (clean.length === 0) return <EmptyState />;
  const longLabels = clean.some((d) => d.name.length > 10);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={clean} margin={{ top: 4, right: 8, left: 0, bottom: longLabels ? 60 : 0 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} stroke={palette.gridline} />
        <XAxis dataKey="name" tick={axisTickStyle} axisLine={{ stroke: palette.axis }} tickLine={false} interval={0} angle={longLabels ? -35 : 0} textAnchor={longLabels ? "end" : "middle"} height={longLabels ? 70 : 24} />
        <YAxis tick={axisTickStyle} axisLine={false} tickLine={false} width={36} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value) => {
            const rounded = typeof value === "number" ? Math.round(value * 10) / 10 : value;
            return [valueLabel ? `${rounded} ${valueLabel}` : `${rounded}`, ""];
          }}
          labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
          cursor={{ fill: "rgba(128,128,128,0.08)" }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={48} fill={palette.series[0]} isAnimationActive={false} shape={(props: any) => <BarShape {...props} colorByIndex={colorByIndex} />} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function BarShape(props: any) {
  const { x, y, width, height, index, payload, colorByIndex } = props;
  const fill = colorByIndex ? colorByIndex(index, payload.name) : palette.series[0];
  return <rect x={x} y={y} width={width} height={height} fill={fill} rx={6} ry={6} />;
}

export function SimpleLineChart({ data, height = 220, valueLabel }: { data: ChartDatum[]; height?: number; valueLabel?: string }) {
  const clean = data.filter((d) => d.value !== null) as { name: string; value: number }[];
  if (clean.length === 0) return <EmptyState />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={clean} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={palette.gridline} />
        <XAxis dataKey="name" tick={axisTickStyle} axisLine={{ stroke: palette.axis }} tickLine={false} />
        <YAxis tick={axisTickStyle} axisLine={false} tickLine={false} width={36} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value) => {
            const rounded = typeof value === "number" ? Math.round(value * 10) / 10 : value;
            return [valueLabel ? `${rounded} ${valueLabel}` : `${rounded}`, ""];
          }}
          labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
        />
        <Line type="monotone" dataKey="value" stroke={palette.series[0]} strokeWidth={2} dot={{ r: 4, fill: palette.series[0] }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export interface MultiLineSeries {
  key: string;
  label: string;
  color: string;
}

/** One combined chart with a legend — for comparing several series (e.g. every
 * subject's % across exam phases) in a single view, instead of small multiples
 * that force side-by-side scanning to compare. */
export function MultiLineChart({
  categories,
  series,
  data,
  height = 280,
  valueLabel,
}: {
  categories: string[];
  series: MultiLineSeries[];
  data: Record<string, number | null | string>[];
  height?: number;
  valueLabel?: string;
}) {
  if (categories.length === 0 || series.length === 0) return <EmptyState />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={palette.gridline} />
        <XAxis dataKey="name" tick={axisTickStyle} axisLine={{ stroke: palette.axis }} tickLine={false} />
        <YAxis tick={axisTickStyle} axisLine={false} tickLine={false} width={36} domain={[0, 100]} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(value, name) => {
            const rounded = typeof value === "number" ? Math.round(value * 10) / 10 : value;
            return [valueLabel ? `${rounded} ${valueLabel}` : `${rounded}`, name];
          }}
          labelStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
        />
        <Legend wrapperStyle={{ fontSize: 12, fontFamily: "var(--font-body)", color: "var(--text-secondary)" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 3, fill: s.color }}
            connectNulls
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function EmptyState() {
  return <div className="flex h-[160px] items-center justify-center text-sm" style={{ color: palette.mutedText }}>No data yet</div>;
}
