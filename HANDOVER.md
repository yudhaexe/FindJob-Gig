# FindJob&Gig — Handover / Memory

> File ini adalah "memori" proyek. Baca ini dulu sebelum lanjut kerja (manusia atau AI agent).
> Update bagian **Status** dan **Log Sesi** setiap selesai sesi kerja.

---

## Ringkasan Proyek

Web app lokal untuk mengumpulkan lowongan kerja + freelance/gig dari banyak sumber (Remotive, RemoteOK, HN, Reddit, Freelancer.com, LinkedIn/Indeed via JobSpy, JobStreet/Glints/Kalibrr, Telegram). User scrape & cari by **keyword** dan **type**. **Tanpa LLM**: klasifikasi rule-based. Data disimpan sebagai **file JSONL** di `data/` (gitignored), termasuk deskripsi penuh + raw JSON. Backend Python (FastAPI + scraper), frontend React ringan (Vite).

Dokumen: [PLANNING.md](PLANNING.md) · [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) · [DESIGN-UIUX.md](DESIGN-UIUX.md)

## Status Saat Ini

- **Fase:** **M0 selesai** (2026-10-07). Berikutnya **M1**.
- **Kode:** scaffold backend (FastAPI + skema pydantic di `backend/core/models.py`, endpoint `/api/health` + stub `/api/jobs`, CLI `fjg info`, 3 test lulus) dan frontend (Vite 8 + React 19 + TS 7 + Tailwind 4, shell header + empty state, proxy `/api` → :8000). Branch `main`, commit terakhir: `8d64998` (lihat `git log`).
- **Validasi sumber selesai** (fokus freelance foto/video): lihat [VALIDATION.md](VALIDATION.md). Script probe ada di `backend/probes/`.
- **Mode provider:** fallback (D15), sudah disetujui user.
- **Next step:** M1 = `storage/filestore.py` (JSONL + atomic write + lock), `scraper/base.py`, normalize/classify (+ kamus Creative)/dedup, sumber **Freelancer.com + JobStreet ID + Himalayas**, `fjg scrape`.

## Cara Menjalankan

Semua dari **root repo** (butuh Node ≥ 20 + Python ≥ 3.11):

| Perintah | Fungsi |
|---|---|
| `npm i` | Install semua: buat `backend/.venv`, pip install backend, npm install frontend (lewat `postinstall` → `scripts/setup.mjs`) |
| `npm start` | Jalankan backend (:8000, auto-reload) + frontend (:5173) di satu terminal, Ctrl+C menghentikan keduanya |
| `npm test` | pytest backend + typecheck frontend |
| `npm run build` | Build frontend ke `frontend/dist` |
| `npm run serve` | Build lalu serve semuanya dari FastAPI di :8000 (mode produksi) |
| `npm run fjg -- <args>` | CLI, mis. `npm run fjg -- info` |
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
