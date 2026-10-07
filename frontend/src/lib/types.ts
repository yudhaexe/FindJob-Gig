// Mirrors backend/core/models.py — keep in sync.

export type Category = "job" | "gig";
export type EmploymentType =
  | "fulltime" | "parttime" | "contract" | "freelance" | "internship" | "temporary" | "unknown";
export type WorkMode = "remote" | "hybrid" | "onsite" | "unknown";
export type Seniority = "intern" | "junior" | "mid" | "senior" | "lead" | "unknown";
export type SalaryPeriod = "hour" | "day" | "week" | "month" | "year" | "fixed" | "unknown";

export interface Location {
  raw: string | null;
  city: string | null;
  country: string | null;
  regions: string[];
}

export interface RemoteScope {
  type: "worldwide" | "regions" | "countries" | "timezone" | "unknown";
  regions: string[];
  countries: string[];
  timezones: string[];
  raw: string | null;
}

export interface Salary {
  min: number | null;
  max: number | null;
  currency: string | null;
  currency_guessed: boolean;
  period: SalaryPeriod;
  raw: string | null;
  estimated: boolean;
}

export interface Budget {
  min: number | null;
  max: number | null;
  currency: string | null;
  currency_guessed: boolean;
  type: "fixed" | "hourly" | "unknown";
  raw: string | null;
}

export interface Duration {
  value: number | null;
  unit: "hour" | "day" | "week" | "month" | "year" | null;
  raw: string | null;
}

export interface JobSummary {
  id: string;
  source: string;
  source_name: string;
  source_url: string;
  title: string;
  company: string | null;
  company_logo: string | null;
  category: Category;
  employment_type: EmploymentType;
  work_mode: WorkMode;
  seniority: Seniority;
  location: Location;
  remote_scope: RemoteScope | null;
  salary: Salary | null;
  budget: Budget | null;
  duration: Duration | null;
  skills: string[];
  topics: string[];
  posted_at: string | null;
  first_seen_at: string | null;
  duplicate_count: number;
  scan_run_id?: string | null;
  user_status?: "keep" | "removed" | null;
}

export interface JobsPage {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
  sort: Sort;
  facets: Record<string, Record<string, number>>;
}

export type Sort = "relevance" | "newest" | "salary_desc" | "company";

export interface RegionInfo {
  code: string;
  label: string;
  children: string[];
  countries: string[];
  count: number;
}

export interface RegionsResponse {
  regions: RegionInfo[];
  countries: Record<string, { name: string; count: number }>;
}

export interface SourceInfo {
  name: string;
  display_name: string;
  category: string | null;
  markets: string[];
  enabled: boolean;
  attribution: string | null;
  jobs: number;
  last_fetched: string | null;
}

export interface SourcesResponse {
  sources: SourceInfo[];
  total: number;
  last_fetched: string | null;
}

export interface Health {
  status: string;
  version: string;
  data_dir: string;
}

/** Full job from GET /api/jobs/{id}. */
export interface Job extends Omit<JobSummary, "duplicate_count"> {
  fingerprint: string | null;
  source_name: string;
  provider: string | null;
  apply_url: string | null;
  duplicates: string[];
  company_url: string | null;
  tags: string[];
  description_text: string | null;
  description_html: string | null;
  expires_at: string | null;
  fetched_at: string;
  updated_at: string | null;
  matched_queries: string[];
  raw_ref: { file: string; line: number } | null;
  raw: Record<string, unknown> | null;
  scan_run_id?: string | null;
  user_status?: "keep" | "removed" | null;
}

export type ScrapeCategory = "job" | "gig" | "any";

export interface ScrapeQuery {
  keywords: string[];
  types: EmploymentType[];
  category: ScrapeCategory;
  sources: string[];
  region: string;
  location: string | null;
  remote_only: boolean;
  since_hours: number;
  max_per_source: number;
}

export type RunStatus = "queued" | "running" | "done" | "failed" | "partial";

export interface SourceRunResult {
  status: "queued" | "running" | "done" | "error" | "skipped";
  fetched: number;
  new: number;
  updated: number;
  skipped: number;
  ms: number | null;
  error: string | null;
  logs?: string[];
}

export interface Run {
  id: string;
  query: ScrapeQuery;
  trigger: "manual" | "schedule" | "cli";
  status: RunStatus;
  started_at: string | null;
  finished_at: string | null;
  stopped?: boolean;
  sources: Record<string, SourceRunResult>;
}

export interface ScrapeSource {
  name: string;
  display_name: string;
  category: "job" | "gig" | "mixed";
  markets: string[];
  enabled: boolean;
  in_region: boolean;
  selected: boolean;
}

export interface ScrapePreset {
  name: string;
  label: string;
  query: Partial<ScrapeQuery>;
}

export interface ScrapeSourcesResponse {
  sources: ScrapeSource[];
  presets: ScrapePreset[];
}

export interface Schedule {
  id: string;
  name: string;
  enabled: boolean;
  query: ScrapeQuery;
  every: string;
  last_run_id: string | null;
  last_run_at: string | null;
  last_status: RunStatus | null;
  next_run_at: string | null;
  consecutive_failures: number;
  paused_reason: string | null;
}
