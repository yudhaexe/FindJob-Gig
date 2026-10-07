// Small square "logo" for a source: its initials on a colour derived from the name (no external requests).
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

export function SourceBadge({ source, label, size = 20 }: { source: string; label: string; size?: number }) {
  const h = hue(source);
  return (
    <span
      title={label}
      aria-label={label}
      className="inline-flex shrink-0 items-center justify-center rounded font-semibold leading-none"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.45,
        color: `hsl(${h} 60% 35%)`,
        background: `hsl(${h} 70% 50% / 0.16)`,
      }}
    >
      {initials(label)}
    </span>
  );
}
