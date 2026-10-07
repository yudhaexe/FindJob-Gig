# FindJob&Gig — System Design

> Lihat [PLANNING.md](PLANNING.md) untuk scope & roadmap, [DESIGN-UIUX.md](DESIGN-UIUX.md) untuk UI.

---

## 1. Komponen

| Komponen | Tanggung jawab | Teknologi |
|---|---|---|
| **Source connector** (`backend/scraper/sources/<name>.py`) | Ambil data dari 1 sumber berdasarkan `ScrapeQuery`, kembalikan list raw item | httpx, feedparser, selectolax, python-jobspy |
| **Normalizer** (`normalize.py` + fungsi `to_job()` per sumber) | Ubah raw item → `Job` (skema seragam) | pydantic |
| **Classifier** (`classify.py`) | Isi `employment_type`, `category`, `work_mode`, `seniority`, `skills`, `duration`, `salary` dari teks | regex + kamus `config/*.yaml` |
| **Dedup** (`dedup.py`) | Gabungkan job yang sama dari sumber berbeda | hash fingerprint |
| **FileStore** (`storage/filestore.py`) | Baca/tulis JSONL secara aman (atomic write), kompaksi | orjson |
| **Index** (`storage/index.py`) | Index in-memory untuk search/filter/facet; reload saat mtime file berubah | Python murni |
| **Runner** (`scraper/runner.py`) | Jalankan beberapa sumber paralel (asyncio), catat progress ke `runs/` | asyncio |
| **API** (`app/main.py`) | REST JSON untuk UI; serve `frontend/dist` di mode produksi | FastAPI |
| **CLI** (`fjg`) | `scrape`, `sources`, `reindex`, `compact`, `export` | Typer |
| **UI** (`frontend/`) | Search, filter, tabel, detail, panel scrape | Vite + React + TS + Tailwind |

## 2. Alur Data

```
ScrapeQuery {keywords, types, sources, location, country, remote_only, max_per_source, since_hours}
      │
      ▼
Runner ──(paralel, rate limit per sumber)──► Connector.fetch(query) ──► raw items
      │                                                                    │
      │                                     simpan apa adanya ─────────────┤
      │                                     data/raw/<src>/<date>.jsonl    │
      │                                                                    ▼
      │                                                    Connector.to_job(raw) → Job (parsial)
      │                                                                    ▼
      │                                                    classify(job) → field turunan
      │                                                                    ▼
      │                                                    dedup + upsert ke data/jobs/<src>.jsonl
      ▼
data/runs/<run_id>.json  (status per sumber: ok/error, jumlah baru/update/skip, durasi, pesan error)
      │
      ▼
Index reload → UI menampilkan hasil
```

Prinsip: **raw selalu disimpan**. Kalau logika normalize/classify diperbaiki, cukup `fjg reindex` (re-normalize dari raw) tanpa scrape ulang.

## 3. Skema Data

### 3.1 `Job` (normalized), 1 baris JSONL

```jsonc
{
  "id": "remotive:1923456",            // "<source>:<external_id>" atau "<source>:sha1(url)"
  "fingerprint": "a1b2c3…",            // sha1(norm(title)+norm(company)) untuk dedup lintas sumber
  "source": "remotive",
  "source_name": "Remotive",
  "source_url": "https://remotive.com/remote-jobs/…",
  "apply_url": "https://…",            // bisa sama dengan source_url
  "duplicates": ["remoteok:998877"],   // id job sama di sumber lain

  "title": "Senior React Developer",
  "company": "Acme Inc",
  "company_url": "https://acme.com",
  "company_logo": "https://…/logo.png",

  "category": "job",                   // job | gig
  "employment_type": "fulltime",       // fulltime | parttime | contract | freelance | internship | temporary | unknown
  "work_mode": "remote",               // remote | hybrid | onsite | unknown
  "seniority": "senior",               // intern | junior | mid | senior | lead | unknown
  "location": {
    "raw": "Jakarta, Indonesia",
    "city": "Jakarta",
    "country": "ID",                   // ISO-3166 alpha-2, null bila tidak diketahui
    "regions": ["ID", "SEA", "APAC"]   // semua region yang mencakup lokasi ini (lihat §5a)
  },
  "remote_scope": {                    // hanya bila work_mode = remote/hybrid
    "type": "worldwide",               // worldwide | regions | countries | timezone | unknown
    "regions": [],                     // mis. ["EU"] untuk "Remote (Europe only)"
    "countries": [],                   // mis. ["US"] untuk "Remote - US only"
    "timezones": [],                   // mis. ["UTC-5..UTC+1"] / ["CET"]
    "raw": "Anywhere in the world"
  },

  "salary": {                          // untuk job
    "min": 8000000, "max": 12000000,
    "currency": "IDR",                 // mata uang asli, TIDAK dikonversi
    "currency_guessed": false,         // true bila "$" tanpa kode jelas
    "period": "month",                 // hour | day | week | month | year | fixed | unknown
    "raw": "Rp 8 - 12 juta / bulan",
    "estimated": false                 // true bila hasil tebakan regex dari deskripsi
  },
  "budget": null,                      // untuk gig: {min, max, currency, type: fixed|hourly, raw}
  "duration": {                        // durasi kontrak/proyek
    "value": 3, "unit": "month",       // hour | day | week | month | year
    "raw": "3 months contract"
  },

  "skills": ["react", "typescript", "nextjs"],
  "tags": ["frontend"],                // tag asli dari sumber
  "description_text": "…",             // teks penuh (plain)
  "description_html": "…",             // HTML asli bila ada (disanitasi saat tampil)

  "posted_at": "2026-10-06T09:12:00Z",
  "expires_at": null,
  "fetched_at": "2026-10-07T02:00:00Z",
  "first_seen_at": "2026-10-06T10:00:00Z",
  "updated_at": "2026-10-07T02:00:00Z",

  "matched_queries": ["react"],        // keyword scrape yang menemukan job ini
  "raw_ref": { "file": "raw/remotive/2026-10-07.jsonl", "line": 42 },
  "raw": { /* objek asli dari sumber, disimpan utuh */ }
}
```

Field yang tidak diketahui = `null` / `"unknown"`, **jangan ditebak tanpa dasar**.

### 3.2 `ScrapeQuery`

```jsonc
{
  "keywords": ["react", "frontend"],     // OR antar keyword
  "types": ["freelance", "contract"],    // kosong = semua
  "category": "any",                     // job | gig | any
  "sources": ["remotive", "reddit"],     // kosong = sumber yang cocok dengan region
  "region": "ID",                        // "ALL" | kode region/negara (lihat §5a)
  "location": "Jakarta",                 // opsional, kota/area lebih spesifik
  "remote_only": false,
  "since_hours": 72,
  "max_per_source": 100
}
```

### 3.3 `Run` (`data/runs/<run_id>.json`)

```jsonc
{
  "id": "2026-10-07T02-00-00_ab12",
  "query": { /* ScrapeQuery */ },
  "status": "running",                   // queued | running | done | failed | partial
  "started_at": "…", "finished_at": null,
  "sources": {
    "remotive": { "status": "done", "fetched": 80, "new": 12, "updated": 5, "skipped": 63, "ms": 1840, "error": null },
    "reddit":   { "status": "error", "error": "429 Too Many Requests", "ms": 900 }
  }
}
```

## 4. Storage (file)

```
data/                         # .gitignore
├─ raw/<source>/<YYYY-MM-DD>.jsonl   # append-only, data mentah
├─ jobs/<source>.jsonl               # normalized, 1 baris = 1 job, unik per id
├─ runs/<run_id>.json
├─ state/sources.json                # last_success, fail_count, disabled, cursor per sumber
├─ state/schedules.json              # jadwal scrape (dibuat/diubah dari UI atau CLI)
└─ archive/                          # job > retensi (opsional)
config/                       # di-commit
├─ sources.yaml                      # enable/disable, rate limit, parameter tiap sumber
├─ skills.yaml                       # kamus skill (~300 entri + alias)
├─ rules.yaml                        # regex type/work_mode/seniority/duration/salary
├─ regions.yaml                      # hierarki region → negara, alias lokasi, timezone
├─ currencies.yaml                   # simbol & kode mata uang untuk parsing (tanpa kurs)
└─ telegram_channels.yaml, ats_companies.yaml
```

- **Upsert:** load `jobs/<source>.jsonl` → dict by id → merge (pertahankan `first_seen_at`) → tulis ke file `.tmp` → `os.replace` (atomic).
- **Lock:** satu lock file per sumber (`.lock`) agar CLI dan API tidak menulis bersamaan.
- **Kompaksi** (`fjg compact`): hapus raw > N hari, pindahkan job > retensi ke `archive/`.
- **Jalur upgrade:** bila > ~200k job, ganti Index + FileStore ke SQLite (FTS5) di `data/fjg.db`, API tetap sama.

## 5. Index & Search (tanpa LLM)

- Saat start / file berubah: load semua `jobs/*.jsonl` → list `Job` ringan (tanpa `raw`, `description_html`) + inverted index token → set(id) untuk `title`, `company`, `skills`, `description_text`.
- Tokenizer: lowercase, hapus aksen, split non-alfanumerik, kata stop ID/EN, sinonim sederhana dari `skills.yaml` (mis. `js` → `javascript`, `reactjs` → `react`).
- Query: `react -wordpress "senior engineer"` → AND antar term, `-` untuk exclude, kutip untuk frasa.
- Skor: title ×3, skills ×2, company ×2, description ×1, ditambah bonus kebaruan.
- Filter: region (+ include_worldwide), category, employment_type, work_mode, source, country, seniority, currency, salary_min (wajib currency), has_salary, posted_within, duration_max.
- Facet: jumlah per nilai filter (untuk badge angka di sidebar).
- `raw` dan `description_html` dibaca dari file **hanya saat** `GET /api/jobs/{id}`.

## 5a. Region Focus

User memilih **satu region fokus** (atau **All regions**) di header. Pilihan ini berlaku untuk **pencarian** (filter hasil) dan **scrape** (sumber + parameter lokasi). Pilihan disimpan di URL (`?region=SEA`) dan `localStorage`.

### Hierarki (`config/regions.yaml`)

```yaml
ALL:   { label: "All regions" }
GLOBAL_REMOTE: { label: "Worldwide remote" }     # hanya remote_scope = worldwide
APAC:  { label: "Asia Pacific", children: [SEA, EA, SA, OC] }
SEA:   { label: "Southeast Asia", countries: [ID, SG, MY, TH, VN, PH] }
ID:    { label: "Indonesia", countries: [ID], aliases: [jakarta, bandung, surabaya, bali, yogyakarta, jabodetabek, tangerang, bekasi, depok] }
EA:    { label: "East Asia", countries: [JP, KR, CN, HK, TW] }
SA:    { label: "South Asia", countries: [IN, PK, BD, LK] }
OC:    { label: "Oceania", countries: [AU, NZ] }
EU:    { label: "Europe", countries: [DE, NL, GB, FR, ES, PL, …], aliases: [emea, cet, europe] }
NA:    { label: "North America", countries: [US, CA], aliases: [usa, "us only", est, pst] }
LATAM: { label: "Latin America", countries: [BR, MX, AR, CO, …] }
MEA:   { label: "Middle East & Africa", countries: [AE, SA, EG, NG, ZA, KE, …] }
```

Region juga bisa berupa satu negara (`?region=SG`). Daftar region bisa diedit tanpa mengubah kode.

### Aturan pencocokan (filter hasil)

Job cocok dengan region **R** bila salah satu terpenuhi:
1. `location.regions` berisi R (lokasi kantor/onsite/hybrid di R), **atau**
2. job remote dan `remote_scope.regions/countries` mencakup R, **atau**
3. job remote dengan `remote_scope.type = worldwide` **dan** toggle **"Include worldwide remote"** aktif (default: aktif).

`ALL` = tanpa filter region. `remote_scope.type = unknown` dianggap worldwide, ditandai `?` di UI, dan bisa disembunyikan lewat toggle "Hide unclear remote scope".

### Parsing lokasi (rule-based)
- Prioritas: field negara terstruktur dari sumber (JobSpy, JobStreet, Himalayas) → alias kota/negara di `regions.yaml` → kode/kata timezone (`CET`, `EST`, `GMT+7`, `UTC+8`) → `unknown`.
- Pola remote scope: `remote (only )?(in )?<X>`, `<X> only`, `anywhere`, `worldwide`, `timezone|tz|±N hours of <tz>`.

### Region → scrape
`config/sources.yaml` mencatat `markets` tiap sumber. Saat scrape dengan region R:
- Sumber yang tidak relevan dengan R tidak dicentang (mis. JobStreet ID hanya untuk ID/SEA/APAC/ALL), tapi user tetap bisa mencentang manual.
- Parameter lokasi diteruskan ke sumber: JobSpy `location` + `country_indeed`, Himalayas `country`, JobStreet `where`, dst.
- Region ALL = semua sumber enabled, tanpa parameter lokasi.

## 5b. Mata Uang (tanpa konversi)

- Salary/budget **selalu tampil dalam mata uang aslinya**, tidak ada konversi kurs.
- `currencies.yaml` hanya untuk mengenali simbol/kode (`Rp`, `IDR`, `$`, `USD`, `S$`, `€`, `£`, `RM`, `₹`, …). `$` tanpa konteks → `USD`, ditandai `currency_guessed: true`.
- Karena tidak ada konversi: **sort by salary** dan filter **Min salary** hanya aktif bila filter **Currency** dipilih (mis. IDR). Kalau tidak dipilih, opsi itu non-aktif dengan tooltip "Pick a currency to sort/filter by salary".
- Perbandingan salary juga dinormalisasi per periode memakai faktor jam/bulan/tahun yang tetap (1 thn = 12 bln, 1 bln = 173 jam). Ini hanya konversi periode, bukan konversi mata uang, dan nilai aslinya tetap ditampilkan.

## 5c. Scrape Terjadwal

Disediakan dua cara yang memakai **daftar jadwal yang sama** (`data/state/schedules.json`):

```jsonc
{
  "id": "sched_ab12",
  "name": "React gigs SEA",
  "enabled": true,
  "query": { /* ScrapeQuery, termasuk region */ },
  "every": "6h",                 // 30m | 1h | 6h | 12h | 1d  (atau "cron": "0 */6 * * *")
  "last_run_id": "…", "last_run_at": "…", "next_run_at": "…"
}
```

1. **Scheduler internal** (APScheduler di dalam proses FastAPI): menjalankan jadwal selama aplikasi menyala.
2. **Windows Task Scheduler** (untuk saat aplikasi tidak menyala): `scripts/register-task.ps1` mendaftarkan task yang tiap 30 menit menjalankan `fjg schedule run-due`. Perintah ini hanya mengeksekusi jadwal yang sudah jatuh tempo.

Pengaman: lock global agar jadwal yang sama tidak jalan dua kali (internal + Task Scheduler), jadwal yang terlewat hanya dijalankan **sekali** (tanpa catch-up beruntun), dan setelah 3 kali gagal berturut-turut jadwal di-pause dengan status di UI.

## 6. Klasifikasi Rule-Based

Semua rule di `config/rules.yaml`, dievaluasi berurutan, **match pertama menang**. Data dari sumber (mis. JobSpy `job_type`) lebih diprioritaskan daripada regex.

| Field | Contoh rule |
|---|---|
| category=gig | sumber gig (reddit hiring, freelancer, HN freelancer) · `\b(gig|task|one[- ]off|fixed price|per project)\b` |
| employment_type | `intern(ship)?|magang` → internship · `freelance|lepas` → freelance · `contract|kontrak|PKWT` → contract · `part[- ]?time|paruh waktu` → parttime · `full[- ]?time|PKWTT|tetap` → fulltime |
| work_mode | `hybrid` → hybrid · `remote|wfh|work from (home|anywhere)|anywhere` → remote · `onsite|on-site|wfo|di kantor` → onsite |
| seniority | `intern|magang` · `junior|jr\.?|entry|fresh ?grad` · `senior|sr\.?` · `lead|principal|head|manager` |
| duration | `(\d+)\s*(bulan|months?|minggu|weeks?|hari|days?|jam|hours?)` dekat kata `contract|kontrak|durasi|duration|project` |
| salary | `(Rp|IDR)\s?[\d.,]+(\s?(jt|juta|rb|ribu|k))?` · `\$\s?[\d,.]+k?(\s?[-–]\s?\$?[\d,.]+k?)?\s?(/|per)\s?(hr|hour|jam|month|bulan|year|yr|tahun)` |
| Reddit | judul `[Hiring]` → simpan, `[For Hire]` → buang |
| HN | baris pertama `Company | Role | Location | REMOTE | $Salary` → split `|` |

## 7. Dedup

1. Dalam satu sumber: unik by `id`.
2. Lintas sumber: `fingerprint = sha1(norm(title) + "|" + norm(company))`, window 14 hari. Job duplikat **tetap disimpan**, tapi di UI dikelompokkan: yang paling lengkap jadi "utama", yang lain di `duplicates` (tampil "juga ada di: RemoteOK, LinkedIn").

## 8. API

| Method | Path | Fungsi |
|---|---|---|
| GET | `/api/jobs?q=&region=&include_worldwide=&category=&type=&mode=&source=&country=&seniority=&currency=&salary_min=&has_salary=&posted_within=&sort=&page=&page_size=` | List ringan (tanpa raw), + `total`, `facets` |
| GET | `/api/regions` | Hierarki region + jumlah job per region |
| GET/POST | `/api/schedules` | Daftar / buat jadwal |
| PATCH/DELETE | `/api/schedules/{id}` | Ubah, aktif/nonaktif, hapus |
| POST | `/api/schedules/{id}/run` | Jalankan sekarang |
| GET | `/api/jobs/{id}` | Job lengkap: deskripsi penuh, `raw`, duplikat |
| GET | `/api/facets` | Nilai filter + jumlah |
| GET | `/api/sources` | Daftar sumber, enabled, status terakhir, atribusi |
| POST | `/api/scrape` | Body `ScrapeQuery` → `{run_id}` (jalan di background) |
| GET | `/api/runs` · `/api/runs/{id}` | Riwayat & progress scrape (UI polling tiap 1 detik) |
| GET | `/api/export?format=csv|json&<filter yang sama>` | Export hasil filter |

`sort`: `relevance` (default bila ada q) · `newest` · `salary_desc` (hanya bila `currency` diisi) · `company`.

## 9. CLI

```bash
fjg scrape -k "react" -k "frontend" --type freelance --source reddit,hn --since 72
fjg scrape -k "designer" --region SEA  # region focus
fjg scrape --preset indonesia          # preset di config/sources.yaml
fjg schedule list | add | run-due      # jadwal scrape
powershell scripts/register-task.ps1   # daftarkan ke Windows Task Scheduler
fjg sources                            # daftar sumber + status
fjg reindex                            # re-normalize dari raw
fjg compact --keep-days 90
fjg export --q react --format csv > react.csv
```

## 10. Struktur Repo

```
FindJob&Gig/
├─ PLANNING.md · DESIGN-SYSTEM.md · DESIGN-UIUX.md · HANDOVER.md
├─ .gitignore                    # data/, node_modules/, .venv/, dist/
├─ config/                       # yaml rule & sumber (di-commit)
├─ backend/
│  ├─ pyproject.toml
│  ├─ core/models.py             # pydantic: Job, JobSummary, ScrapeQuery, Run, JobsPage
│  ├─ core/paths.py              # lokasi config/ & data/ (override: FJG_DATA_DIR)
│  ├─ app/main.py                # FastAPI
│  ├─ app/routes/{jobs,scrape,sources}.py
│  ├─ scraper/
│  │  ├─ base.py                 # class Source: name, category, fetch(query), to_job(raw)
│  │  ├─ sources/{remotive,remoteok,arbeitnow,jobicy,himalayas,wwr,hn,reddit,freelancer,jobspy,jobstreet,glints,kalibrr,telegram}.py
│  │  ├─ normalize.py · classify.py · regions.py · money.py · dedup.py · runner.py · scheduler.py
│  │  └─ cli.py
│  ├─ storage/{filestore,index}.py
│  └─ tests/fixtures/<source>.json   # contoh response untuk test parser
├─ frontend/                     # Vite + React + TS + Tailwind
├─ package.json                  # root: npm i / start / test / build / serve / fjg
├─ scripts/{lib,setup,dev,run}.mjs  # Node murni, tanpa dependensi
├─ scripts/register-task.ps1     # Windows Task Scheduler (M6)
└─ start.bat                     # double-click: install bila perlu, lalu npm start
```

## 11. Kontrak Connector

```python
class Source(Protocol):
    name: str                # "remotive"
    display_name: str        # "Remotive"
    category: Literal["job", "gig", "mixed"]
    markets: set[str]        # kode region dari regions.yaml, mis. {"ALL"} / {"ID"} / {"SEA","APAC"}
    supports_keyword: bool   # False → runner filter keyword secara lokal
    rate_limit: float        # request per detik
    attribution: str | None

    async def fetch(self, q: ScrapeQuery, client: httpx.AsyncClient) -> list[dict]: ...
    def to_job(self, raw: dict) -> Job: ...
```

Menambah sumber baru = 1 file + 1 entri di `config/sources.yaml` + 1 fixture test.

## 12. Multi-Provider (beberapa repo/scraper untuk satu sumber)

Satu **source** (mis. `linkedin`, `glints`) bisa punya beberapa **provider**, yaitu implementasi berbeda:

```yaml
# config/sources.yaml
linkedin:
  mode: fallback            # fallback | parallel | single
  providers:
    - jobspy                # python-jobspy (library, venv utama)
    - linkedin_guest        # connector kita sendiri ke guest endpoint
    - spinlud_selenium      # opsional, enabled: false (butuh Chrome + cookie login)
glints:
  mode: single
  providers: [glints_cloudscraper]   # port dari ifqygazhar/jobscraper-api (MIT)
indeed:
  mode: fallback
  providers: [jobspy]
```

- **fallback** (default): coba provider #1. Kalau error, 0 hasil, atau 403/429, lanjut ke #2. Hemat request, risiko diblokir kecil.
- **parallel**: semua provider jalan, hasil digabung lewat dedup (`id`/`fingerprint`). Cakupan maksimal, tapi request ke situs yang sama berlipat. Dipakai untuk membandingkan atau memvalidasi.
- **single**: hanya satu.
- Setiap `Job` mencatat `provider` di samping `source`, dan status/health dilacak **per provider** (UI Sources menampilkan keduanya).

**Cara memasukkan repo pihak ketiga**
| Jenis repo | Cara | Contoh |
|---|---|---|
| Library di PyPI, aktif, populer | `pip install` versi di-pin, di venv utama | JobSpy |
| Repo aplikasi (Flask/CLI), bukan library | **Port** fungsi yang diperlukan ke `sources/<name>.py`, cantumkan lisensi + link asal di header file | ifqygazhar → Glints |
| Repo berat/bentrok dependensi (Selenium, versi pin lama) | Jalankan sebagai **subprocess di venv terpisah** (`providers/<name>/.venv`), komunikasi via JSON stdout | spinlud (opsional) |

Aturan menambah provider: lisensi permisif, kode dibaca dulu (tidak menjalankan kode yang belum diperiksa), versi di-pin, ada fixture test, dan default `enabled: false` sampai lolos probe.
