# FindJob&Gig — Handover / Memory

> File ini adalah "memori" proyek. Baca ini dulu sebelum lanjut kerja (manusia atau AI agent).
> Update bagian **Status** dan **Log Sesi** setiap selesai sesi kerja.

---

## Ringkasan Proyek

Web app lokal untuk mengumpulkan lowongan kerja + freelance/gig dari banyak sumber (Remotive, RemoteOK, HN, Reddit, Freelancer.com, LinkedIn/Indeed via JobSpy, JobStreet/Glints/Kalibrr, Telegram). User scrape & cari by **keyword** dan **type**. **Tanpa LLM**: klasifikasi rule-based. Data disimpan sebagai **file JSONL** di `data/` (gitignored), termasuk deskripsi penuh + raw JSON. Backend Python (FastAPI + scraper), frontend React ringan (Vite).

Dokumen: [PLANNING.md](PLANNING.md) · [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) · [DESIGN-UIUX.md](DESIGN-UIUX.md)

## Status Saat Ini

- **Fase:** **M6 selesai** (2026-10-07). Berikutnya **M7** (lihat PLANNING.md: kolom tabel bisa diatur, export, dll).
- **Kode M1:** `storage/filestore.py`, `scraper/{base,runner,normalize,classify,money,regions,dedup,text}.py`, connector **Freelancer.com, JobStreet ID, Himalayas**, CLI `fjg scrape` / `fjg sources`. Config: `config/{sources,rules,skills,topics,regions,currencies}.yaml`.
- **Kode M2:** `storage/index.py` (`JobIndex`: load JSONL → doc ringan, reload otomatis by mtime/size tiap ≤1 dtk, `group_duplicates`, search AND/`-exclude`/`"frasa"`/`prefix*`, plural sederhana, alias skill dari `skills.yaml`, skor title×3 skills×2 company×2 desc×1 + bonus kebaruan; filter region/type/mode/source/country/seniority/currency/salary_min/has_salary/posted_within/duration_max; facet disjunktif; sort relevance/newest/salary_desc/company). API: `/api/jobs`, `/api/jobs/{id}`, `/api/facets`, `/api/regions` (tree + count), `/api/sources` (+ jumlah job, last_fetched). Frontend: `hooks/useUrlState.ts` (semua state di URL, region juga di localStorage), `hooks/useApi.ts`, `lib/format.ts`, `components/{RegionSelect,FilterSidebar,Results}.tsx`, `App.tsx` (header, sidebar, chips, sort, tabel ≥768px, kartu mobile, bottom sheet filter <1024px, pagination, state kosong/error, `/` fokus search).
- **Kode M3:** `app/routes/scrape.py`: `POST /api/scrape` (202 + `run_id`, run ditulis `queued` dulu lalu `run_scrape` jalan sebagai asyncio task), `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/scrape/sources?region=&category=` (sumber + `in_region`/`selected` + presets). `run_scrape` menerima `run_id` + `sources`. `FileStore.get_job/load_run` menolak id yang bukan nama file aman. Frontend: `components/JobDrawer.tsx` (Overview / Description dengan DOMPurify + highlight / Raw JSON tree + cari + Copy/Download + toggle normalized; `↑↓`/`j k`, `o`, `Esc`, klik luar, Copy link), `components/ScrapeModal.tsx` (keyword chip, region, lokasi, kategori, tipe, remote, since, max, sumber auto per region + label "not in region", preset, progress per sumber), `hooks/useScrapeRun.ts` (polling 1 dtk, id run di localStorage agar lanjut setelah reload), `lib/highlight.ts`. `?job=<id>` di URL, `j/k` + `Enter` di daftar, `Shift+S`, indikator header `⟳ 1/2`, toast "N new jobs · View", tombol scrape di state kosong / tanpa hasil.
- **Kode M4:** connector **Reddit Gigs** (`scraper/sources/reddit.py`: Atom RSS multi-subreddit r/forhire, r/slavelabour, r/PhotoshopRequest, r/VideoEditingRequests, filter [Hiring]/[Task] vs [For Hire]/[Offer]), connector **Hacker News Freelancer** (`scraper/sources/hackernews.py`: Algolia API query "SEEKING FREELANCER", parser pipe company/role/remote), budget extraction untuk gig di `classify.py` & connector (fixed vs hourly), preset baru `gigs` di `config/sources.yaml`.
- **Kode M5:** connector **JobSpy** (`scraper/sources/jobspy.py`: Indeed, Glassdoor, ZipRecruiter, LinkedIn via python-jobspy 1.2.0), connector **Kalibrr ID & SEA** (`scraper/sources/kalibrr.py`: REST search API publik), connector **Telegram Job Channels** (`scraper/sources/telegram.py`: preview web HTML publik `@loker_id`, `@idrecruitments`), preset `indonesia` diperbarui (`jobstreet, kalibrr, telegram, jobspy`).
- **Kode M6:** `Schedule` di `core/models.py`; `FileStore.load_schedules/update_schedules` (read-modify-write di bawah lock lintas proses, file `state/schedules.json`); `scraper/scheduler.py` (`parse_every` min 30m, `claim_due` mendorong `next_run_at` sebelum run → tidak ada double run internal vs Task Scheduler, slot terlewat jalan sekali, `record_result` pause setelah 3 gagal, `run_due`, `run_now`, `loop` tick 30 dtk); lifespan di `app/main.py` menjalankan loop (`FJG_NO_SCHEDULER=1` mematikan; `tests/conftest.py` mengaturnya); API `app/routes/schedules.py` (`GET/POST /api/schedules`, `PATCH/DELETE /{id}`, `POST /{id}/run`, `GET /task-status`); CLI `fjg schedule list|add|run-due|status`; `scripts/register-task.ps1` (task `FindJobGig`, tiap 30 mnt). Frontend: `SchedulesPanel.tsx` (+ `useSchedules`), tombol header `⏱ N` (kuning bila ada yang ter-pause), "Save as schedule" di ScrapeModal.
- **Fitur Tambahan (Error Handling, Logs, Scan Filter, Keep/Remove):**
  - **Anti Silent Error:** `jobspy.py`, `reddit.py`, `telegram.py` tidak swallow error kosong; runner menaikkan `SourceBlocked`/`SourceError`, status run akurat (`failed`/`partial`/`done`).
  - **Granular Scrape Logs:** `SourceRunResult.logs` berisi trace query/fetch/warning/error/stats; UI modal menampilkan viewer log collapsible per sumber.
  - **Scan History Filter (`scan_run_id`):** `Job` & `JobSummary` menyimpan `scan_run_id`. Index dan API memfilter berdasarkan run ID atau rentang waktu run. Sidebar memiliki dropdown riwayat jam scrape (`HH:mm DD/MM` + jumlah new/fetched).
  - **Keep (★) & Remove (✕) Tagging:** `user_status` ("keep" | "removed" | null) disimpan persisten di `jobs/<source>.jsonl`. `upsert_jobs` tidak mereset status saat re-scrape. Endpoint `POST /api/jobs/{id}/status`. Action buttons di tabel, kartu, drawer. Filter status di sidebar (Active, Kept ★, Removed ✕, All).
- **Tes:** 70 lulus (termasuk tes schedules: interval, claim tanpa double run, pause 3 gagal, CRUD API; juga  tes runner logs, anti silent error, scan filter, user status persistence & API). `npm run build` ok.
- **Terverifikasi nyata:** Live scrape CLI terverifikasi untuk Kalibrr, Telegram, JobSpy Indeed ID, Hacker News, Freelancer, JobStreet.
- **Git:** branch `main`.
- **Mode provider:** fallback (D15).
- **Next step (M7):** lihat PLANNING.md. Belum diverifikasi: `register-task.ps1` di Windows nyata dan UI panel di browser.
- **Ditunda:** edit penuh query jadwal di panel (sekarang hanya nama/interval/pause/hapus; ubah query = hapus + buat ulang), cron expression, tombol Retry per sumber, panel Runs lengkap (riwayat), next/prev lintas halaman di drawer, TanStack Table/Virtual (tabel native + paging 50 cukup sekarang; pakai saat kolom bisa diatur di M7), pin region (★), `fjg reindex`, `state/sources.json`, detail call JobStreet.

## Cara Menjalankan

Semua dari **root repo** (butuh Node ≥ 20 + Python ≥ 3.11):

| Perintah | Fungsi |
|---|---|
| `npm i` | Install semua: buat `backend/.venv`, pip install backend, npm install frontend (lewat `postinstall` → `scripts/setup.mjs`) |
| `npm start` | Jalankan backend (:8000, auto-reload) + frontend (:5173) di satu terminal, Ctrl+C menghentikan keduanya |
| `npm test` | pytest backend + typecheck frontend |
| `npm run build` | Build frontend ke `frontend/dist` |
| `npm run serve` | Build lalu serve semuanya dari FastAPI di :8000 (mode produksi) |
| `npm run fjg -- <args>` | CLI, mis. `npm run fjg -- scrape --preset creative`, `npm run fjg -- scrape -k "video editor" -s jobstreet --since 72`, `npm run fjg -- sources` |
| `start.bat` | Double-click: install bila belum, lalu `npm start` |

Script root tidak punya dependensi, cukup Node murni di `scripts/*.mjs`.

## Keputusan yang Sudah Diambil

| # | Keputusan | Alasan |
|---|---|---|
| D1 | Tanpa LLM; klasifikasi regex + kamus di `config/*.yaml` | Permintaan user |
| D2 | ~~Cloudflare~~ → **jalan lokal**, deploy ditunda | User: "lupakan soal Cloudflare" (rev 2) |
| D3 | Storage = **file JSONL** di `data/`, gitignored | User (rev 2). Upgrade path: SQLite FTS5 bila > ~200k job |
| D4 | Simpan **semua**: deskripsi penuh + raw JSON | User (rev 2); raw memungkinkan `reindex` tanpa scrape ulang |
| D5 | Pasar: **global + Indonesia** | User (rev 2) |
| D6 | Frontend: Vite + React + TS + Tailwind + TanStack Table, minim dependensi | User: "lightweight, React boleh" |
| D7 | Backend: Python (FastAPI) karena JobSpy berbasis Python, satu bahasa untuk scraper + API | Konsistensi |
| D8 | UI: tabel padat (Nama Loker, Perusahaan, Salary/Budget, Type, Durasi, Lokasi/Mode, Sumber, Diposting) + drawer detail dengan tab Ringkasan / Deskripsi / Raw JSON | User (rev 2) |
| D9 | Tidak scraping X/Twitter, FB, IG, Upwork, Fiverr di fase awal | Butuh login / anti-bot / ToS |
| D10 | 1 file per sumber, kontrak `fetch()` + `to_job()` | Mudah tambah/matikan sumber |
| D11 | UI **English only**, tanpa library i18n | User (rev 3) |
| D12 | Scrape terjadwal: scheduler internal (APScheduler) + Windows Task Scheduler (`fjg schedule run-due`), daftar jadwal sama di `data/state/schedules.json` | User (rev 3) |
| D13 | **Tanpa konversi mata uang**; sort/filter salary hanya aktif bila Currency dipilih | User (rev 3); membandingkan mata uang berbeda tidak valid tanpa kurs |
| D14 | **Region focus** + All regions, hierarki di `config/regions.yaml`; job remote worldwide ikut tampil di region mana pun (toggle) | User (rev 3) |
| D15 | Multi-provider per sumber, **default mode `fallback`**; `parallel` opsional per sumber; provider baru `enabled: false` sampai lolos probe | User (2026-10-07). Hemat request & risiko ban kecil |
| D16 | Kode region tidak boleh sama dengan kode negara ISO → South Asia = `SAS` (bukan `SA` = Saudi Arabia) | Region bisa berupa negara (`?region=SG`) |
| D17 | `duplicates` dihitung saat baca (index), tidak ditulis ke file; job tanpa company tidak di-dedup lintas sumber | Selalu konsisten; judul gig saja terlalu sering bentrok |
| D18 | Salary tebakan dari **deskripsi** hanya diterima bila ada periode (/hr, per month, …); dari **judul** selalu diterima | Deskripsi penuh angka pendanaan/harga ("US$218M") |
| D19 | Pencarian: kata di-AND, `-x` exclude, `"frasa"`, `x*` prefix; plural sederhana (editor↔editors), tanpa stemming lain | Prediktabel; `react` tidak ikut cocok `reactive` |
| D20 | Silent error dilarang; semua connector wajib me-raise `SourceBlocked`/`SourceError`; runner menandai status run sebagai `failed` jika seluruh sumber error, `partial` jika sebagian error | User (2026-10-07); mencegah scraper diam-diam gagal mengembalikan 0 hasil tanpa notifikasi |
| D21 | Tagging `user_status` ("keep" / "removed") disimpan persisten di file JSONL masing-masing sumber; dilindungi dalam `upsert_jobs` agar tidak hilang saat scrape ulang | User (2026-10-07); memfasilitasi bookmark/simpan & hapus lowongan yang tahan refresh & re-scrape |
| D23 | Scheduler internal = loop asyncio tick 30 dtk, **bukan APScheduler** (tanpa dependensi baru; logika sama dengan `run-due` CLI). Hanya interval `<n>m/h/d` ≥ 30m, tanpa cron | Sederhana, satu kode untuk app dan Task Scheduler |
| D22 | Filter scan history (`scan_run_id`) mengikat ID run dan fallback ke rentang waktu `started_at` - `finished_at` run | User (2026-10-07); memungkinkan user memfilter lowongan dari jam scan tertentu |


## Gotchas

- **Remotive & RemoteOK wajib atribusi + link balik**; Remotive maks ~4 fetch/hari, >2 req/menit diblok. RemoteOK API delay 24 jam.
- **Upwork RSS sudah mati (2024)**.
- **Reddit:** `.json` anonim = **403 Blocked**; `.rss` jalan tapi **429 setelah ~2 request**. Pakai OAuth (app script gratis) atau jeda ≥15 dtk.
- **Google Jobs via JobSpy 1.2.0 rusak** (`Google returned no job data`). Projects.co.id 403. Glints GraphQL 403, tapi **halaman explore via `cloudscraper` jalan tanpa login**.
- Kalibrr pernah gagal DNS sekali (sementara), jadi tambahkan retry.
- Regex kreatif harus pakai word boundary + exclude (`photovoltaic`, `video game`, `data annotator`).
- **JobSpy:** LinkedIn cepat kena 429. Batasi `results_wanted` dan beri jeda antar query.
- Endpoint JobStreet/Glints/Kalibrr & Freelancer.com **belum diverifikasi**. Cek dulu via DevTools.
- Tulis file dengan atomic replace + lock per sumber (CLI dan API bisa jalan bersamaan).
- Nama folder mengandung `&`, jadi path harus selalu di-quote: `"D:\Github\FindJob&Gig"`.
- **Commit tanpa `Co-Authored-By`** atau atribusi tambahan (permintaan user).
- **`&` di path merusak shim `.cmd` npm** (`node_modules\.bin\*.cmd`) di Windows. Karena itu script di `frontend/package.json` memanggil tool lewat `node node_modules/<pkg>/bin/...`. Jangan pakai `npx vite`/`tsc` langsung; tambahkan tool baru dengan pola yang sama.
- **JobStreet** search API hanya memberi teaser; `daterange` hanya menerima 1/3/7/14/31 hari; `pageSize` bisa sampai 100. Header browser UA diperlukan.
- **Himalayas** search: 20 job/halaman lewat `page`, filter `country=<nama negara>`. Banyak job lama, jadi `--since` kecil membuang sebagian besar hasil.
- **Freelancer.com** search fuzzy (keyword "retoucher" bisa mengembalikan "Retype Pages"); `topics` membantu memilah. Perlu `location_details=true` agar gig onsite punya lokasi.
- Output CLI berisi ✓/✗; saat di-pipe di Windows tampil `?` (stdout di-set `errors="replace"`), bukan error.
- **YAML 1.1:** kode negara `NO` (Norwegia) terbaca `false` kalau tidak dikutip. Kutip kode seperti `"NO"`, `"ON"`, `"YES"` di config.
- Vite dev server listen di `localhost` (IPv6), jadi `curl 127.0.0.1:5173` gagal; pakai `localhost:5173`.
- **uvicorn `--reload` kadang tidak memuat route baru** (proses :8000 lama tetap jalan). Kalau endpoint baru 404, restart `npm start`.
- Screenshot Claude-in-Chrome sering timeout di app ini; verifikasi lewat DOM (`javascript_tool`) lebih andal.
- Starlette mengeluarkan DeprecationWarning "install httpx2" di TestClient. Ini aman diabaikan.

## Pertanyaan Terbuka

Tidak ada (semua dijawab di rev 3).

## Log Sesi

| Tanggal | Ringkasan | Next |
|---|---|---|
| 2026-10-07 | Riset repo GitHub & sumber data, PLANNING.md + HANDOVER.md (rev 1, Cloudflare) | Jawab keputusan terbuka |
| 2026-10-07 | Rev 2: Cloudflare di-drop, storage file, simpan semua, React ringan, pasar global+ID. Buat DESIGN-SYSTEM.md + DESIGN-UIUX.md + .gitignore | Mulai M0 |
| 2026-10-07 | Rev 3: UI EN, schedules (internal + Task Scheduler), tanpa konversi kurs, region focus + All regions. Update semua dokumen design | Mulai M0 |
| 2026-10-07 | **M0 selesai**: git init, scaffold backend + frontend, skema pydantic, start.bat/ps1. Terverifikasi: pytest 3/3, `npm run build` ok, `/api/health` + proxy Vite `/api/jobs` ok | M1 |
| 2026-10-07 | Root `npm i` / `npm start` / `npm test` / `serve` / `fjg` (scripts/*.mjs). Diuji dari clean install. Audit repo & library (PLANNING §3). Commit pertama tanpa co-author (permintaan user) | M1 |
| 2026-10-07 | Validasi nyata 18 sumber + 8 kasus JobSpy untuk freelance foto/video → VALIDATION.md; prioritas sumber & M1 diubah | M1 |
| 2026-10-07 | Cari repo lagi (GitHub Search API): Glints bisa via cloudscraper; spinlud LinkedIn butuh login (opsional). Desain multi-provider (fallback/parallel) di DESIGN-SYSTEM §12. LinkedIn naik ke P1. User setuju fallback (D15). Commit `8d64998` | M1 |
| 2026-10-07 | **M1 selesai**: FileStore, runner, classify (rules/skills/topics yaml), money, regions, dedup, 3 connector (Freelancer, JobStreet, Himalayas), `fjg scrape`/`sources`. 46 test. Scrape nyata preset creative OK & idempoten. Commit `fcc8e62` | M2 |
| 2026-10-07 | **M2 selesai**: JobIndex + API jobs/facets/regions/sources, UI tabel + search + filter sidebar + region selector + chips + paging, state di URL. Fix `NO` di regions.yaml. 53 test. Commit `7edc580` | M3 |
| 2026-10-07 | **M3 selesai**: API scrape/runs/scrape-sources, Job drawer (Overview/Description/Raw JSON), Scrape modal + progress + indikator header + toast, keyboard j/k/Enter/Shift+S. Dependensi baru: `dompurify`. 56 test. Diverifikasi di browser. Commit `dba3809` | M4 |
| 2026-10-07 | **M4 selesai**: Connector Reddit Gigs (RSS multi-subreddit + filtering hiring/task), Hacker News Freelancer (Algolia API), ekstraksi budget gig & classify budget, preset `gigs`. 60 test lulus, live scrape HN terverifikasi. | M5 |
| 2026-10-07 | **M5 selesai**: Connector JobSpy (Indeed, Glassdoor, ZipRecruiter, LinkedIn via python-jobspy 1.2.0), connector Kalibrr (ID & SEA REST), connector Telegram Job Channels (HTML preview @loker_id, @idrecruitments). 65 test lulus, live scrape terverifikasi. | User request: silent errors, scan history filter, logs, keep/remove tagging |
| 2026-10-07 | **Fitur Tambahan (Error Handling, Logs, Scan History, Keep & Remove)**: (1) Anti silent error & auto fail/partial run status, (2) Granular execution logs per source di runner + UI expandable log viewer di progress modal, (3) Scan history & time filter (`scan_run_id`) di API, Index, dan sidebar dropdown, (4) Persistent Keep (★) & Remove (✕) tagging di JSONL, endpoint status, table/card/drawer actions, dan sidebar filter. 66 test lulus, build clean. | M6 |
| 2026-10-07 | **M6 selesai**: schedules.json + scheduler (claim, pause 3 gagal), API, CLI `fjg schedule`, `register-task.ps1`, Schedules panel + Save as schedule + badge header. 70 test lulus, build clean, CLI smoke OK. | M7; verifikasi Task Scheduler & UI di browser |
