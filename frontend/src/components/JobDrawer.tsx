// Job drawer (DESIGN-UIUX.md §2.3): header + Overview / Description / Raw JSON for one job.
import DOMPurify from "dompurify";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import {
  CATEGORY_LABEL, MODE_LABEL, SENIORITY_LABEL, TYPE_LABEL, duration, fullDate, locationLabel, moneyFull, relTime, typeKey,
} from "../lib/format";
import { highlightDom, highlightText, termsRegex } from "../lib/highlight";
import type { Job, JobSummary } from "../lib/types";
import type { Labels } from "./Results";

// Links in source HTML open outside the app and never get the opener.
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noreferrer noopener");
  }
});

type Tab = "overview" | "description" | "raw";
const TABS: [Tab, string][] = [
  ["overview", "Overview"],
  ["description", "Description"],
  ["raw", "Raw JSON"],
];

interface Props {
  id: string;
  q: string;
  labels: Labels;
  attribution: (source: string) => string | null;
  onClose: () => void;
  onOpen: (id: string) => void;
  onPrev?: () => void;
  onNext?: () => void;
  onUpdateStatus?: (id: string, status: "keep" | "removed" | null) => void;
}

export function JobDrawer({ id, q, labels, attribution, onClose, onOpen, onPrev, onNext, onUpdateStatus }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [copied, setCopied] = useState(false);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    api
      .job(id, ctrl.signal)
      .then(setJob)
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : String(e));
      });
    return () => ctrl.abort();
  }, [id]);

  useEffect(() => {
    panel.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    panel.current?.querySelector("[data-scroll]")?.scrollTo({ top: 0 });
  }, [id]);

  const current = job?.id === id ? job : null;
  const applyUrl = current ? current.apply_url ?? current.source_url : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector("[data-modal]")) return;
      if (e.key === "Escape") onClose();
      else if ((e.key === "ArrowDown" || e.key === "j") && onNext) onNext();
      else if ((e.key === "ArrowUp" || e.key === "k") && onPrev) onPrev();
      else if (e.key === "o" && applyUrl) window.open(applyUrl, "_blank", "noopener,noreferrer");
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, onNext, onPrev, applyUrl]);

  // Click outside closes, except on a result row (that switches job) or inside a modal.
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      const t = e.target as Element;
      if (panel.current?.contains(t) || t.closest("[data-job-row], [data-modal], header")) return;
      onClose();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [onClose]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the URL bar still has it */
    }
  };

  const iconBtn = "h-8 min-w-8 rounded-ui px-2 text-muted hover:bg-surface hover:text-fg disabled:opacity-30";

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={current?.title ?? "Job details"}
      tabIndex={-1}
      className="fixed inset-0 z-30 flex flex-col bg-bg shadow-2xl outline-none md:inset-y-0 md:left-auto md:w-[45%] md:min-w-[480px] md:max-w-[880px] md:border-l md:border-border"
    >
      <div className="flex items-center gap-1 border-b border-border px-3 py-1.5">
        <button type="button" onClick={onClose} className={iconBtn} aria-label="Close (Esc)" title="Close (Esc)">
          ✕
        </button>
        <span className="ml-auto" />
        <button type="button" onClick={onPrev} disabled={!onPrev} className={iconBtn} aria-label="Previous job" title="Previous (↑ / k)">
          ↑
        </button>
        <button type="button" onClick={onNext} disabled={!onNext} className={iconBtn} aria-label="Next job" title="Next (↓ / j)">
          ↓
        </button>
        <button
          type="button"
          onClick={() => {
            const nextStatus = current?.user_status === "keep" ? null : "keep";
            if (current) {
              setJob({ ...current, user_status: nextStatus });
              onUpdateStatus?.(current.id, nextStatus);
            }
          }}
          disabled={!current}
          className={`${iconBtn} ${current?.user_status === "keep" ? "font-semibold text-amber-500" : ""}`}
          title={current?.user_status === "keep" ? "Remove keep tag" : "Keep (Save) job"}
        >
          {current?.user_status === "keep" ? "★ Kept" : "☆ Keep"}
        </button>
        <button
          type="button"
          onClick={() => {
            const nextStatus = current?.user_status === "removed" ? null : "removed";
            if (current) {
              setJob({ ...current, user_status: nextStatus });
              onUpdateStatus?.(current.id, nextStatus);
            }
          }}
          disabled={!current}
          className={`${iconBtn} ${current?.user_status === "removed" ? "font-semibold text-accent" : ""}`}
          title={current?.user_status === "removed" ? "Restore job" : "Remove / Hide job"}
        >
          {current?.user_status === "removed" ? "↺ Restore" : "✕ Remove"}
        </button>
        <button type="button" onClick={copyLink} className={iconBtn}>
          {copied ? "✓ Copied" : "⧉ Copy link"}
        </button>
      </div>

      <div data-scroll className="min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <p role="alert" className="p-6 text-danger">
            Couldn't load this job ({error}).
          </p>
        ) : !current ? (
          <div aria-hidden className="space-y-3 p-5">
            <div className="h-5 w-2/3 animate-pulse rounded bg-surface" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-surface" />
            <div className="h-3 w-1/3 animate-pulse rounded bg-surface" />
          </div>
        ) : (
          <>
            <DrawerHeader job={current} labels={labels} applyUrl={applyUrl!} attribution={attribution(current.source)} onOpen={onOpen} />
            <div role="tablist" className="sticky top-0 z-10 flex gap-1 border-b border-border bg-bg px-4">
              {TABS.map(([t, label]) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => setTab(t)}
                  className={`-mb-px border-b-2 px-3 py-2 font-medium ${
                    tab === t ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div role="tabpanel" className="px-4 py-4">
              {tab === "overview" && <Overview job={current} labels={labels} onOpen={onOpen} />}
              {tab === "description" && <Description job={current} q={q} />}
              {tab === "raw" && <RawJson job={current} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function DrawerHeader({
  job, labels, applyUrl, attribution, onOpen,
}: { job: Job; labels: Labels; applyUrl: string; attribution: string | null; onOpen: (id: string) => void }) {
  const summary = job as unknown as JobSummary;
  const salary = moneyFull(job.salary, job.salary?.period ?? "unknown")
    ?? moneyFull(job.budget, job.budget?.type === "hourly" ? "hour" : job.budget?.type ?? "unknown");
  const key = typeKey(summary);
  const posted = job.posted_at ?? job.first_seen_at;
  const meta = [
    locationLabel(summary, labels.region),
    key !== "unknown" ? TYPE_LABEL[key] : null,
    job.seniority !== "unknown" ? SENIORITY_LABEL[job.seniority] : null,
  ].filter(Boolean);

  return (
    <div className="space-y-2 px-4 pb-3 pt-4">
      <h2 className="text-xl font-semibold leading-snug">{job.title}</h2>
      <p className="text-muted">
        {job.company && (
          <>
            {job.company_url ? (
              <a href={job.company_url} target="_blank" rel="noreferrer noopener" className="text-fg hover:underline">
                {job.company} ↗
              </a>
            ) : (
              <span className="text-fg">{job.company}</span>
            )}
            {" · "}
          </>
        )}
        {meta.join(" · ")}
      </p>
      {(salary || posted) && (
        <p>
          {salary && <span className="font-medium tabular-nums">{salary}</span>}
          {salary && posted && <span className="text-muted"> · </span>}
          {posted && (
            <span className="text-muted" title={fullDate(posted)}>
              {job.posted_at ? "Posted" : "First seen"} {relTime(posted)} ago
            </span>
          )}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
        <a
          href={applyUrl}
          target="_blank"
          rel="noreferrer noopener"
          title="Open the posting (o)"
          className="inline-flex h-9 items-center rounded-ui bg-accent px-4 font-medium text-accent-fg hover:opacity-90"
        >
          Apply on {labels.source(job.source)} ↗
        </a>
        {job.duplicates.length > 0 && (
          <span className="text-muted">
            Also on:{" "}
            {job.duplicates.map((d, i) => (
              <span key={d}>
                {i > 0 && ", "}
                <button type="button" onClick={() => onOpen(d)} className="text-accent hover:underline">
                  {labels.source(d.split(":")[0])}
                </button>
              </span>
            ))}
          </span>
        )}
      </div>
      {attribution && <p className="text-xs text-muted">{attribution}</p>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-5">
      <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-muted">{title}</h3>
      <dl className="grid grid-cols-[8.5rem_1fr] gap-x-3 gap-y-1.5">{children}</dl>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  if (children == null || children === false || children === "" || (Array.isArray(children) && !children.length)) return null;
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  );
}

function Tags({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((t) => (
        <span key={t} className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs">
          {t}
        </span>
      ))}
    </span>
  );
}

function When({ iso }: { iso: string | null }) {
  if (!iso) return null;
  return (
    <span>
      {fullDate(iso)} <span className="text-muted">({relTime(iso)} ago)</span>
    </span>
  );
}

const known = (v: string, labels: Record<string, string>) => (v && v !== "unknown" ? labels[v] ?? v : null);

function Overview({ job, labels, onOpen }: { job: Job; labels: Labels; onOpen: (id: string) => void }) {
  const scope = job.remote_scope;
  const scopeText = scope
    ? [
        scope.type === "unknown" ? "Unclear" : scope.type[0].toUpperCase() + scope.type.slice(1),
        [...scope.regions.map(labels.region), ...scope.countries.map(labels.country), ...scope.timezones].join(", "),
      ].filter(Boolean).join(": ")
    : null;
  const salaryNote = job.salary
    ? [job.salary.estimated && "parsed from text", job.salary.currency_guessed && "currency guessed", job.salary.raw && `“${job.salary.raw}”`]
        .filter(Boolean).join(" · ")
    : "";

  return (
    <div>
      <Section title="POSITION">
        <Row label="Category">{CATEGORY_LABEL[job.category]?.replace(/s$/, "")}</Row>
        <Row label="Type">{known(job.employment_type, TYPE_LABEL)}</Row>
        <Row label="Seniority">{known(job.seniority, SENIORITY_LABEL)}</Row>
        <Row label="Duration">{duration(job.duration) ?? job.duration?.raw}</Row>
        <Row label="Skills">{job.skills.length > 0 && <Tags items={job.skills} />}</Row>
        <Row label="Topics">{job.topics.length > 0 && <Tags items={job.topics} />}</Row>
        <Row label="Source tags">{job.tags.length > 0 && <Tags items={job.tags} />}</Row>
      </Section>
      {(job.salary || job.budget) && (
        <Section title="COMPENSATION">
          <Row label="Salary">
            {job.salary && (
              <>
                <span className="tabular-nums">{moneyFull(job.salary, job.salary.period) ?? job.salary.raw}</span>
                {salaryNote && <span className="text-muted"> ({salaryNote})</span>}
              </>
            )}
          </Row>
          <Row label="Budget">
            {job.budget && (
              <>
                <span className="tabular-nums">
                  {moneyFull(job.budget, job.budget.type === "hourly" ? "hour" : job.budget.type) ?? job.budget.raw}
                </span>
                {job.budget.raw && <span className="text-muted"> (“{job.budget.raw}”)</span>}
              </>
            )}
          </Row>
        </Section>
      )}
      <Section title="LOCATION">
        <Row label="Work mode">{known(job.work_mode, MODE_LABEL)}</Row>
        <Row label="Remote scope">
          {scopeText && (
            <>
              {scopeText}
              {scope?.raw && <span className="text-muted"> (“{scope.raw}”)</span>}
            </>
          )}
        </Row>
        <Row label="Location">{job.location.raw}</Row>
        <Row label="City">{job.location.city}</Row>
        <Row label="Country">{job.location.country && `${labels.country(job.location.country)} (${job.location.country})`}</Row>
        <Row label="Regions">{job.location.regions.map(labels.region).join(", ")}</Row>
      </Section>
      <Section title="TIME">
        <Row label="Posted">{job.posted_at && <When iso={job.posted_at} />}</Row>
        <Row label="First seen">{job.first_seen_at && <When iso={job.first_seen_at} />}</Row>
        <Row label="Updated">{job.updated_at && <When iso={job.updated_at} />}</Row>
        <Row label="Last fetched">{job.fetched_at && <When iso={job.fetched_at} />}</Row>
        <Row label="Expires">{job.expires_at && <When iso={job.expires_at} />}</Row>
      </Section>
      <Section title="SOURCE">
        <Row label="Source">
          <a href={job.source_url} target="_blank" rel="noreferrer noopener" className="text-accent hover:underline">
            {labels.source(job.source)} ↗
          </a>
          {job.provider && job.provider !== job.source && <span className="text-muted"> via {job.provider}</span>}
        </Row>
        <Row label="Apply URL">
          {job.apply_url && job.apply_url !== job.source_url && (
            <a href={job.apply_url} target="_blank" rel="noreferrer noopener" className="break-all text-accent hover:underline">
              {job.apply_url}
            </a>
          )}
        </Row>
        <Row label="Matched by">{job.matched_queries.map((m) => `“${m}”`).join(" · ")}</Row>
        <Row label="Also on">
          {job.duplicates.length > 0 && (
            <span className="flex flex-wrap gap-x-2">
              {job.duplicates.map((d) => (
                <button key={d} type="button" onClick={() => onOpen(d)} className="font-mono text-xs text-accent hover:underline">
                  {d}
                </button>
              ))}
            </span>
          )}
        </Row>
        <Row label="Job ID"><span className="font-mono text-xs">{job.id}</span></Row>
        <Row label="Raw record">{job.raw_ref && <span className="font-mono text-xs">data/{job.raw_ref.file}:{job.raw_ref.line}</span>}</Row>
      </Section>
    </div>
  );
}

function Description({ job, q }: { job: Job; q: string }) {
  const box = useRef<HTMLDivElement>(null);
  const re = useMemo(() => termsRegex(q), [q]);

  useEffect(() => {
    const el = box.current;
    if (!el || !job.description_html) return;
    const frag = DOMPurify.sanitize(job.description_html, { RETURN_DOM_FRAGMENT: true });
    highlightDom(frag, re);
    el.replaceChildren(frag);
  }, [job.description_html, re]);

  if (job.description_html) return <div ref={box} className="desc" />;
  if (job.description_text) return <div className="desc whitespace-pre-wrap">{highlightText(job.description_text, re)}</div>;
  return <p className="text-muted">This source didn't provide a description. Open the posting to read it.</p>;
}

function RawJson({ job }: { job: Job }) {
  const [normalized, setNormalized] = useState(false);
  const [filter, setFilter] = useState("");
  const [copied, setCopied] = useState(false);
  const value = useMemo(() => {
    if (!normalized) return job.raw;
    const { raw: _raw, ...rest } = job;
    return rest;
  }, [job, normalized]);
  const text = useMemo(() => JSON.stringify(value, null, 2), [value]);
  const needle = filter.trim().toLowerCase();

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked */
    }
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: `${job.id.replace(/[^\w.-]+/g, "_")}${normalized ? "" : ".raw"}.json`,
    });
    a.click();
    URL.revokeObjectURL(url);
  };

  const btn = "h-8 rounded-ui border border-border px-3 hover:bg-surface";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Find in JSON…"
          aria-label="Find in JSON"
          className="h-8 min-w-0 flex-1 rounded-ui border border-border bg-surface px-2"
        />
        <button type="button" className={btn} onClick={copy}>
          {copied ? "✓ Copied" : "Copy"}
        </button>
        <button type="button" className={btn} onClick={download}>
          Download
        </button>
      </div>
      <label className="flex items-center gap-2 text-muted">
        <input type="checkbox" checked={normalized} onChange={(e) => setNormalized(e.target.checked)} />
        Show normalized job
      </label>
      {value == null ? (
        <p className="text-muted">No raw record stored for this job.</p>
      ) : (
        <div className="overflow-x-auto rounded-ui border border-border bg-surface p-3 font-mono text-xs leading-5">
          <JsonNode value={value} depth={0} needle={needle} />
        </div>
      )}
    </div>
  );
}

function contains(value: unknown, needle: string): boolean {
  return !!needle && JSON.stringify(value).toLowerCase().includes(needle);
}

function Hit({ text, needle }: { text: string; needle: string }) {
  if (!needle) return <>{text}</>;
  const i = text.toLowerCase().indexOf(needle);
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark>{text.slice(i, i + needle.length)}</mark>
      <Hit text={text.slice(i + needle.length)} needle={needle} />
    </>
  );
}

function Primitive({ value, needle }: { value: unknown; needle: string }) {
  if (value === null) return <span className="text-muted">null</span>;
  if (typeof value === "string") return <span className="text-[var(--t-internship)] break-all">"<Hit text={value} needle={needle} />"</span>;
  if (typeof value === "number") return <span className="text-[var(--t-fulltime)]"><Hit text={String(value)} needle={needle} /></span>;
  return <span className="text-[var(--t-parttime)]">{String(value)}</span>;
}

function JsonNode({ name, value, depth, needle }: { name?: string; value: unknown; depth: number; needle: string }) {
  const label = name !== undefined && (
    <span className="text-[var(--t-contract)]">
      <Hit text={name} needle={needle} />
      <span className="text-muted">: </span>
    </span>
  );
  if (value === null || typeof value !== "object") {
    return (
      <div className="pl-4 -indent-4">
        {label}
        <Primitive value={value} needle={needle} />
      </div>
    );
  }
  const entries = Array.isArray(value) ? value.map((v, i) => [String(i), v] as const) : Object.entries(value);
  const [open, close] = Array.isArray(value) ? ["[", "]"] : ["{", "}"];
  if (!entries.length) {
    return (
      <div>
        {label}
        <span className="text-muted">{open + close}</span>
      </div>
    );
  }
  return (
    <details open={depth < 2 || contains(value, needle)} className="[&>summary::-webkit-details-marker]:hidden">
      <summary className="cursor-pointer list-none select-none hover:bg-bg">
        {label}
        <span className="text-muted">
          {open} <span className="text-[10px]">{entries.length} {Array.isArray(value) ? "items" : "keys"}</span>
        </span>
      </summary>
      <div className="border-l border-border pl-3 ml-1">
        {entries.map(([k, v]) => (
          <JsonNode key={k} name={Array.isArray(value) ? undefined : k} value={v} depth={depth + 1} needle={needle} />
        ))}
      </div>
      <span className="text-muted">{close}</span>
    </details>
  );
}
