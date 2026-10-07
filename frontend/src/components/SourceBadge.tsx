// Source logo: the site's icon from /sources/<key>.png (downloaded into frontend/public/sources),
// falling back to initials on a colour derived from the name when there is no image.
import { useState } from "react";

function hue(name: string): number {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

function initials(label: string): string {
  const words = label.replace(/[()&/]/g, " ").split(/\s+/).filter(Boolean);
  const two = words.length > 1 ? words[0][0] + words[1][0] : label.slice(0, 2);
  return two.toUpperCase();
}

/** JobSpy jobs carry the board they came from in `provider` (indeed, linkedin, …). */
export const logoKey = (job: { source: string; provider?: string | null }) =>
  job.source === "jobspy" && job.provider ? job.provider : job.source;

export function SourceBadge({ logo, label, size = 24 }: { logo: string; label: string; size?: number }) {
  const [broken, setBroken] = useState(false);
  if (!broken) {
    return (
      <img
        src={`/sources/${logo}.png`}
        alt={label}
        title={label}
        width={size}
        height={size}
        onError={() => setBroken(true)}
        className="inline-block shrink-0 rounded object-contain"
        style={{ width: size, height: size }}
      />
    );
  }
  const h = hue(logo);
  return (
    <span
      title={label}
      aria-label={label}
      className="inline-flex shrink-0 items-center justify-center rounded font-semibold leading-none"
      style={{ width: size, height: size, fontSize: size * 0.45, color: `hsl(${h} 60% 35%)`, background: `hsl(${h} 70% 50% / 0.16)` }}
    >
      {initials(label)}
    </span>
  );
}
