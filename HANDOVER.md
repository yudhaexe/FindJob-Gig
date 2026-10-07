# FindJob&Gig — Handover / Memory

> File ini adalah "memori" proyek. Baca ini dulu sebelum lanjut kerja (manusia atau AI agent).
> Update bagian **Status** dan **Log Sesi** setiap selesai sesi kerja.

---

## Ringkasan Proyek

Web app lokal untuk mengumpulkan lowongan kerja + freelance/gig dari banyak sumber (Remotive, RemoteOK, HN, Reddit, Freelancer.com, LinkedIn/Indeed via JobSpy, JobStreet/Glints/Kalibrr, Telegram). User scrape & cari by **keyword** dan **type**. **Tanpa LLM**: klasifikasi rule-based. Data disimpan sebagai **file JSONL** di `data/` (gitignored), termasuk deskripsi penuh + raw JSON. Backend Python (FastAPI + scraper), frontend React ringan (Vite).

Dokumen: [PLANNING.md](PLANNING.md) · [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) · [DESIGN-UIUX.md](DESIGN-UIUX.md)

## Status Saat Ini

- **Fase:** **M1 selesai** (2026-10-07). Berikutnya **M2**.
- **Kode M1:** `storage/filestore.py` (JSONL, atomic replace, lock file per sumber, runs), `scraper/{base,runner,normalize,classify,money,regions,dedup,text}.py`, connector **Freelancer.com, JobStreet ID, Himalayas**, CLI `fjg scrape` / `fjg sources`. Config: `config/{sources,rules,skills,topics,regions,currencies}.yaml`. 46 test lulus (fixture asli di `backend/tests/fixtures/`).
- **Terverifikasi nyata:** `fjg scrape --preset creative --max 30 --since 168` → jobstreet 67, freelancer 126, himalayas 28 job tersimpan (~25 dtk). Scrape ulang → `new=0 updated=0` (idempoten).
- **Git:** branch `main`, commit M1 = `fcc8e62` (lihat `git log`).
- **Mode provider:** fallback (D15). Saat ini tiap sumber baru punya 1 provider; kolom `provider` sudah ada di `Job`.
- **Next step (M2):** `storage/index.py` (load JSONL → index in-memory, reload by mtime, `dedup.group_duplicates`), `/api/jobs` filter/sort/paging/facets + `/api/regions`, UI tabel + search + filter sidebar + region selector.
- **Belum dikerjakan dari desain:** `fjg reindex` (re-normalize dari raw), `state/sources.json` (fail_count/auto-disable), detail call JobStreet (deskripsi penuh; sekarang hanya teaser).

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
