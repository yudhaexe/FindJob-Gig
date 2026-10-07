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
  posted_at: string | null;
  duplicate_count: number;
}

export interface JobsPage {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
  facets: Record<string, Record<string, number>>;
}

export interface Health {
  status: string;
  version: string;
  data_dir: string;
}
