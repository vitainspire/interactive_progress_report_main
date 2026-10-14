type IconProps = { size?: number; className?: string };

const base = { fill: "none", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function EyeIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function EyeOffIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M3 3l18 18" />
      <path d="M10.6 5.2A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a16.6 16.6 0 0 1-3.9 4.6M6.5 6.8C3.8 8.6 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 4.1-.9" />
      <path d="M9.5 9.8a3 3 0 0 0 4.2 4.2" />
    </svg>
  );
}

export function SearchIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

export function PlusIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function SheetIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <rect x="4" y="3.5" width="16" height="17" rx="2" />
      <path d="M4 9h16M4 14h16M9.5 9v11" />
    </svg>
  );
}

export function DotsIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} fill="currentColor">
      <circle cx="12" cy="5.5" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="12" cy="18.5" r="1.6" />
    </svg>
  );
}

export function PrinterIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M6 9V4h12v5" />
      <rect x="4" y="9" width="16" height="8" rx="1.5" />
      <path d="M6 14h12v6H6v-6z" />
    </svg>
  );
}

export function ExternalLinkIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M14 4h6v6" />
      <path d="M20 4l-9.5 9.5" />
      <path d="M18 14v5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 19V8a1.5 1.5 0 0 1 1.5-1.5H11" />
    </svg>
  );
}

export function TrashIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M4 7h16" />
      <path d="M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7" />
      <path d="M6 7l1 13a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 17 20l1-13" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

export function ZoomInIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M21 21l-4.8-4.8M10.5 7.5v6M7.5 10.5h6" />
    </svg>
  );
}

export function ZoomOutIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M21 21l-4.8-4.8M7.5 10.5h6" />
    </svg>
  );
}

export function FitScreenIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M9 4H5a1 1 0 0 0-1 1v4M15 4h4a1 1 0 0 1 1 1v4M9 20H5a1 1 0 0 1-1-1v-4M15 20h4a1 1 0 0 0 1-1v-4" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function LogoutIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" />
      <path d="M15 16l5-4-5-4M20 12H9" />
    </svg>
  );
}

export function SettingsIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 13.5a7.8 7.8 0 0 0 0-3l2-1.5-2-3.4-2.3.9a7.6 7.6 0 0 0-2.6-1.5L14 2h-4l-.5 2.4a7.6 7.6 0 0 0-2.6 1.5l-2.3-.9-2 3.4 2 1.5a7.8 7.8 0 0 0 0 3l-2 1.5 2 3.4 2.3-.9c.77.66 1.65 1.17 2.6 1.5L10 22h4l.5-2.4a7.6 7.6 0 0 0 2.6-1.5l2.3.9 2-3.4-2-1.5z" />
    </svg>
  );
}

export function UsersIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15.5 14.2c2.5.3 4.5 2.5 4.5 5.3" />
    </svg>
  );
}

export function InboxIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M4 12h4l2 3h4l2-3h4" />
      <path d="M5.5 5h13l2.5 7v7a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19v-7l2.5-7z" />
    </svg>
  );
}

export function SendIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M22 2L11 13" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  );
}

export function BarChartIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </svg>
  );
}

export function SpeakerWaveIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M4 10v4h4l5 4V6l-5 4H4z" />
      <path d="M16.5 9a4.5 4.5 0 0 1 0 6M19.5 6a8.5 8.5 0 0 1 0 12" />
    </svg>
  );
}

export function TeluguGlyphIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className}>
      <path d="M3 10c0-4 3.5-7 9-7s9 3 9 7-3.5 7-9 7l-5 4 1-5c-3-1.2-5-3.6-5-6z" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <text x="12" y="14" textAnchor="middle" fontSize="13" fontWeight={700} fontFamily="'Noto Sans Telugu', sans-serif" fill="currentColor">
        అ
      </text>
    </svg>
  );
}

export function PlugIcon({ size = 18, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} {...base} stroke="currentColor">
      <path d="M9 2v4M15 2v4" />
      <path d="M7 6h10v4a5 5 0 0 1-5 5 5 5 0 0 1-5-5V6z" />
      <path d="M12 15v3M9 22h6" />
    </svg>
  );
}
