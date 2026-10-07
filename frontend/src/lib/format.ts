// Display formatting (DESIGN-UIUX.md §5). Money is always shown in its original currency.
import type { Budget, Duration, EmploymentType, JobSummary, Salary } from "./types";

const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });

export function compact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${nf.format(n / 1e9)}B`;
  if (abs >= 1e6) return `${nf.format(n / 1e6)}M`;
  if (abs >= 1e4) return `${nf.format(n / 1e3)}k`;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
}

const PERIOD: Record<string, string> = {
  hour: "/hr", day: "/day", week: "/wk", month: "/mo", year: "/yr", fixed: " fixed", unknown: "",
};

export interface MoneyLabel {
  text: string;
  hint?: string; // tooltip explaining a "~"
}

/** "USD 60–80k/yr", "~IDR 10M/mo", "USD 500 fixed"; null when there's nothing to show. */
export function money(salary: Salary | null, budget: Budget | null): MoneyLabel | null {
  const m = salary ?? budget;
  if (!m || (m.min == null && m.max == null)) return null;
  const period = salary ? salary.period : budget?.type === "hourly" ? "hour" : budget?.type ?? "unknown";
  const lo = m.min ?? m.max!;
  const hi = m.max ?? m.min!;
  let range: string;
  if (lo === hi) range = compact(lo);
  else {
    // "60–80k" when both share a suffix, else "800–1.2k"
    const a = compact(lo), b = compact(hi);
    const sa = a.replace(/[\d.,]/g, ""), sb = b.replace(/[\d.,]/g, "");
    range = sa && sa === sb ? `${a.slice(0, -sa.length)}–${b}` : `${a}–${b}`;
  }
  const hints: string[] = [];
  if (m.currency_guessed) hints.push(`Currency guessed${m.raw ? ` from '${m.raw}'` : ""}`);
  if (salary?.estimated) hints.push("Parsed from description");
  const prefix = hints.length ? "~" : "";
  return { text: `${prefix}${m.currency ?? "?"} ${range}${PERIOD[period] ?? ""}`, hint: hints.join(" · ") || undefined };
}

const UNIT: Record<string, [string, string]> = {
  hour: ["hr", "hrs"], day: ["day", "days"], week: ["wk", "wks"], month: ["mo", "mo"], year: ["yr", "yrs"],
};

export function duration(d: Duration | null): string | null {
  if (!d?.value || !d.unit) return null;
  const [one, many] = UNIT[d.unit];
  return `${nf.format(d.value)} ${d.value === 1 ? one : many}`;
}

/** "5h", "3d" under a week, else "Sep 12" (with year when not this year). */
export function relTime(iso: string | null, now = Date.now()): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const mins = Math.max(0, (now - t) / 60000);
  if (mins < 60) return `${Math.max(1, Math.round(mins))}m`;
  if (mins < 60 * 24) return `${Math.round(mins / 60)}h`;
  if (mins < 60 * 24 * 7) return `${Math.round(mins / 1440)}d`;
  const d = new Date(t);
  const sameYear = d.getFullYear() === new Date(now).getFullYear();
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(sameYear ? {} : { year: "numeric" }) });
}

export function fullDate(iso: string | null): string | undefined {
  if (!iso) return undefined;
  return new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

export const TYPE_LABEL: Record<EmploymentType | "gig", string> = {
  fulltime: "Full-time", parttime: "Part-time", contract: "Contract", freelance: "Freelance",
  internship: "Internship", temporary: "Temporary", unknown: "—", gig: "Gig",
};

export const MODE_LABEL: Record<string, string> = {
  remote: "Remote", hybrid: "Hybrid", onsite: "Onsite", unknown: "Unknown",
};

export const SENIORITY_LABEL: Record<string, string> = {
  intern: "Intern", junior: "Junior", mid: "Mid", senior: "Senior", lead: "Lead", unknown: "Unknown",
};

export const CATEGORY_LABEL: Record<string, string> = { job: "Jobs", gig: "Gigs" };

/** Badge key: gigs show "Gig", jobs show their employment type. */
export function typeKey(j: JobSummary): EmploymentType | "gig" {
  return j.category === "gig" && j.employment_type === "unknown" ? "gig" : j.employment_type;
}

/** "🌐 Worldwide", "🌐 Remote·EU", "🌐 Remote ?", "🏢 Hybrid·Jakarta", "📍 Jakarta, ID". */
export function locationLabel(j: JobSummary, regionLabel: (code: string) => string = (c) => c): string {
  const loc = j.location;
  const place = [loc.city, loc.country].filter(Boolean).join(", ") || loc.raw || "";
  if (j.work_mode === "remote") {
    const s = j.remote_scope;
    if (!s || s.type === "unknown") return "🌐 Remote ?";
    if (s.type === "worldwide") return "🌐 Worldwide";
    const parts = [...s.regions.map(regionLabel), ...s.countries];
    if (parts.length) return `🌐 Remote·${parts.slice(0, 3).join(", ")}${parts.length > 3 ? "…" : ""}`;
    if (s.timezones.length) return `🌐 Remote·${s.timezones[0]}${s.timezones.length > 1 ? "…" : ""}`;
    return "🌐 Remote ?";
  }
  if (j.work_mode === "hybrid") return `🏢 Hybrid${place ? `·${place}` : ""}`;
  return place ? `📍 ${place}` : "—";
}
