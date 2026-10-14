import { useState } from "react";
import { LogoMarkIcon } from "./Icons";

type LogoProps = { size?: number; className?: string };

/**
 * Renders /public/logo.png if present; falls back to the gradient icon mark
 * when no logo file has been added yet. Drop a square image at
 * frontend/public/logo.png to replace the icon everywhere — no code change needed.
 */
export function Logo({ size = 36, className }: LogoProps) {
  const [imageFailed, setImageFailed] = useState(false);

  if (imageFailed) {
    return (
      <span
        className={`gradient-fill flex shrink-0 items-center justify-center rounded-full shadow-sm ${className ?? ""}`}
        style={{ width: size, height: size }}
      >
        <LogoMarkIcon size={Math.round(size * 0.5)} />
      </span>
    );
  }

  return (
    <img
      src="/logo.png"
      alt="School logo"
      width={size}
      height={size}
      className={`shrink-0 rounded-full object-cover shadow-sm ${className ?? ""}`}
      style={{ width: size, height: size }}
      onError={() => setImageFailed(true)}
    />
  );
}
