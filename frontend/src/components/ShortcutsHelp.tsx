// Keyboard shortcut cheat sheet, opened with "?".
const ROWS: [string, string][] = [
  ["/", "Focus search"],
  ["j / k  or  ↓ / ↑", "Move through results"],
  ["Enter", "Open selected job"],
  ["s", "Keep (★) selected job"],
  ["x", "Remove / restore selected job"],
  ["n / p", "Next / previous page"],
  ["o", "Open source page (in drawer)"],
  ["Esc", "Close drawer or dialog"],
  ["Shift+S", "Scrape now"],
  ["?", "Show this help"],
];

export function ShortcutsHelp({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Keyboard shortcuts"
        className="w-full max-w-sm rounded-ui border border-border bg-bg p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-2 font-semibold">Keyboard shortcuts</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          {ROWS.map(([k, d]) => (
            <div key={k} className="contents">
              <dt><kbd className="rounded border border-border bg-surface px-1.5 font-mono text-xs">{k}</kbd></dt>
              <dd className="text-muted">{d}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
