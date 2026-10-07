# FindJob&Gig — Planning

> Agregator lowongan kerja + freelance/gig dari banyak sumber (job board, komunitas, sosmed).
> Cari by **keyword** dan **type** (full-time, part-time, contract, freelance, internship, gig, remote).
> **Tanpa LLM**: semua klasifikasi pakai rule, regex dan keyword.
> **Jalan lokal**: data disimpan sebagai **file** (gitignored), UI web React yang ringan.

Dibuat: 2026-10-07 · Rev 2: Cloudflare di-drop, storage pakai file · Rev 3: UI English, schedules, tanpa konversi kurs, region focus

Dokumen terkait:
- [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md): arsitektur, skema data, storage, API, scraper, klasifikasi
- [DESIGN-UIUX.md](DESIGN-UIUX.md): layout, wireframe, komponen, interaksi, design token
- [HANDOVER.md](HANDOVER.md): status, keputusan, log sesi

---

## 1. Keputusan dari User (Revisi 2)

| # | Pertanyaan | Jawaban |
|---|---|---|
| 1 | Pasar | **Keduanya**: global (remote) + Indonesia |
| 2 | Frontend | **React yang ringan** (Vite + React) |
| 3 | Penyimpanan | **File** (JSONL), folder `data/` di-gitignore. Cloudflare **tidak dipakai** (untuk sekarang) |
| 4 | Deskripsi | **Simpan semua** (deskripsi penuh + raw JSON dari sumber) |
| 5 | UI | Daftar menampilkan info penting (Nama Loker, Perusahaan, Salary, Durasi, Type, Lokasi, Sumber, Tanggal). **Detail** (klik) menampilkan semua info + raw JSON |
| 6 | Bahasa UI | **English only** (rev 3) |
| 7 | Scrape terjadwal | **Disediakan**: scheduler internal + Windows Task Scheduler (rev 3) |
| 8 | Mata uang | **Tanpa konversi**, tampilkan mata uang asli (rev 3) |
| 9 | Region | **Region focus** (mis. Indonesia, SEA, APAC, Europe, North America, …) + opsi **All regions**. Berlaku untuk filter hasil dan scrape (rev 3) |

## 2. Tujuan & Non-Tujuan

**Tujuan**
- User bisa **menjalankan scrape** berdasarkan keyword + type + sumber, dari UI atau CLI.
- Semua hasil dinormalisasi ke satu skema dan disimpan ke file.
- UI untuk mencari, memfilter, mengurutkan, dan melihat detail lengkap.
- Biaya Rp 0, jalan di laptop (Windows).

**Non-tujuan (fase awal)**
- Tidak pakai LLM/AI.
- Tidak ada login, multi-user, auto-apply.
- Tidak scraping platform yang butuh login (FB Group, IG, X/Twitter, LinkedIn Posts) atau yang anti-bot berat (Upwork, Fiverr).
- Tidak deploy ke cloud (bisa dipertimbangkan lagi nanti).

## 3. Repo & Library yang Dipakai (dicek 2026-10-07 via GitHub/PyPI API)

Kriteria: lisensi permisif, commit < 3 bulan terakhir, tidak di-archive, komunitas cukup besar.

### ✅ Dipakai (trusted & aktif)
| Repo | ★ | Push terakhir | Lisensi | Peran |
|---|---|---|---|---|
| [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) (`python-jobspy` 1.2.0, rilis 2026-10-02) | 4.4k | 2026-10-07 | MIT | **Satu-satunya scraper pihak ketiga**: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Naukri, Bayt |
| [encode/httpx](https://github.com/encode/httpx) | 15.5k | 2026-10-02 | BSD-3 | HTTP client async untuk semua connector |
| [rushter/selectolax](https://github.com/rushter/selectolax) | 1.7k | 2026-10-06 | MIT | Parsing HTML cepat (Telegram, situs ID) |
| [kurtmckee/feedparser](https://github.com/kurtmckee/feedparser) | 2.4k | 2026-10-06 | BSD-2 | RSS (We Work Remotely, Reddit `.rss` fallback) |
| [agronholm/apscheduler](https://github.com/agronholm/apscheduler) | 7.6k | 2026-10-05 | MIT | Scheduler internal (M6) |
| [fastapi/typer](https://github.com/fastapi/typer) | 20k | 2026-10-06 | MIT | CLI `fjg` |
| [TanStack/table](https://github.com/TanStack/table) | 28k | 2026-10-06 | MIT | Tabel hasil + sort + virtual scroll |
| [cure53/DOMPurify](https://github.com/cure53/DOMPurify) | 17k | 2026-10-05 | Apache-2.0 | Sanitasi deskripsi HTML |

Untuk sumber lain (Remotive, RemoteOK, Arbeitnow, Jobicy, Himalayas, HN Algolia, Reddit, Freelancer.com, JobStreet, Glints, Kalibrr) **kita tulis connector sendiri** di atas API/RSS resminya. Cara ini lebih stabil dan lebih bisa dipercaya daripada bergantung pada repo scraper kecil.

### 📚 Referensi saja (baca kodenya, jangan jadikan dependensi)
| Repo | ★ | Push terakhir | Alasan |
|---|---|---|---|
| [Feashliaa/job-board-aggregator](https://github.com/Feashliaa/job-board-aggregator) | 163 | 2026-10-06 | Aktif, MIT. Contoh endpoint Greenhouse/Lever/Ashby/Workday untuk connector ATS (P3) |
| [rainmanjam/jobspy-api](https://github.com/rainmanjam/jobspy-api) | 380 | 2025-05-29 | Pola FastAPI + JobSpy. Tidak aktif > 1 tahun |
| [Bulletin (Astro theme)](https://astro.build/themes/details/bulletin/) | — | — | Inspirasi UI job board |

### ❌ Tidak dipakai
| Repo | Alasan |
|---|---|
| [kbwhodat/jobdrop](https://github.com/kbwhodat/jobdrop) | Baru 3★ dan belum teruji komunitas. Overlap dengan JobSpy |
| [AbrarAdnan/Upwork-Scraper](https://github.com/AbrarAdnan/Upwork-Scraper), [valtumi/upwork_scraper](https://github.com/valtumi/upwork_scraper) | 0–2★, dan Upwork anti-bot berat |
| [amanfojnr/codejobs](https://github.com/amanfojnr/codejobs) | Mati sejak 2018 |
| gigbot | Ruby, tidak aktif |

## 4. Sumber Data (prioritas, **sudah divalidasi 2026-10-07**, lihat [VALIDATION.md](VALIDATION.md))

Fokus utama: **freelance/jasa kreatif** (photography, videography, photo/video editor).
✅ teruji jalan · ⚠️ jalan dengan syarat · ❌ gagal/dibuang

| Prioritas | Sumber | Kategori | Pasar | Hasil uji |
|---|---|---|---|---|
| P1 | **Freelancer.com** public projects API | gig | global | ✅ 91/118 relevan, budget + mata uang |
| P1 | **JobStreet ID**, **Kalibrr** (API JSON internal), **Glints** (cloudscraper, port dari ifqygazhar/jobscraper-api) | job | ID | ✅ 57/65 relevan, salary IDR sebagian. Glints ✅ tanpa login |
| P1 | **JobSpy**: Indeed (US + ID), Glassdoor, ZipRecruiter | job (contract/part-time) | global + ID | ✅ cepat (1–3 dtk), salary di ±50–90% |
| P1 | JobSpy: LinkedIn | job | global + ID | ✅ jalan (17–20 hasil). Lambat (6–12 dtk), tanpa salary. **Tetap dipakai**, ikut default |
| P2 | **Himalayas** API | job | global remote | ✅ 57/61 relevan |
| P2 | **Reddit** r/forhire, r/slavelabour, r/PhotoshopRequest, r/VideoEditingRequests, r/hiring | gig | global | ⚠️ `.json` 403. RSS jalan tapi 429 cepat, jadi **pakai OAuth** (app gratis) |
| P3 | Remotive, RemoteOK, Jobicy, Arbeitnow, We Work Remotely, HN | job | global | ✅ jalan, tapi hampir 0 role kreatif. Sumber umum, non-default di preset Creative |
| P3 | Telegram channel loker publik (`t.me/s/<channel>`) | job + gig | ID | belum diuji |
| ❌ | Google Jobs (via JobSpy), Projects.co.id | — | — | gagal (no data / 403) |
| ❌ | X/Twitter, Facebook, Instagram, Threads, Upwork, Fiverr | — | — | tidak dikerjakan |

Satu sumber bisa punya beberapa provider/repo (fallback atau parallel), lihat DESIGN-SYSTEM §12.

Aturan: hormati rate limit & ToS, cantumkan atribusi (Remotive/RemoteOK wajib), selalu simpan link asli.

## 5. Ringkasan Arsitektur

```
 ┌───────── React UI (Vite) ─────────┐        ┌──── CLI ────┐
 │ Search · Filter · Tabel · Detail  │        │ fjg scrape  │
 │ Panel "Scrape Sekarang"           │        └──────┬──────┘
 └───────────────┬───────────────────┘               │
                 │ HTTP JSON                          │
 ┌───────────────▼────────────────────────────────────▼───────┐
 │ Backend Python (FastAPI)                                    │
 │  /api/jobs  /api/jobs/{id}  /api/scrape  /api/runs  /facets │
 │  Scraper runner → sources/*.py → normalize → classify →     │
 │  dedup → FileStore                                          │
 │  In-memory index (reload saat file berubah)                 │
 └───────────────┬─────────────────────────────────────────────┘
                 │
          data/  (gitignored)
          ├─ raw/<source>/<YYYY-MM-DD>.jsonl
          ├─ jobs/<source>.jsonl         (normalized, 1 job per baris)
          └─ runs/<run_id>.json          (log tiap scrape)
```

Detail di [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md).

**Stack**
- Backend: Python 3.11+, FastAPI, Uvicorn, httpx, selectolax (HTML), feedparser (RSS), python-jobspy, pydantic, orjson.
- Frontend: Vite + React + TypeScript, Tailwind CSS, TanStack Table (tabel + sort + virtual scroll), tanpa state library berat (pakai URL query + React state).
- Satu perintah jalan: `start.bat` / `npm run dev` yang menyalakan backend + frontend.

## 6. Roadmap

| Fase | Isi | Selesai bila |
|---|---|---|
| **M0 Setup** | `git init`, `.gitignore`, scaffold `backend/` + `frontend/`, skema pydantic `Job` | `uvicorn` + `vite` jalan, halaman kosong tampil |
| **M1 Core data** | FileStore, normalize, classify (+ kamus Creative), dedup, 3 sumber (**Freelancer.com, JobStreet ID, Himalayas**), CLI `fjg scrape` | File `data/jobs/*.jsonl` terisi dan valid |
| **M2 API + UI dasar** | `/api/jobs` (filter, sort, paging), tabel hasil, search bar, filter sidebar, **region selector + parsing lokasi/remote scope** | Bisa cari keyword, filter type & region di browser |
| **M3 Detail + Scrape dari UI** | Drawer detail (Overview/Description/Raw JSON), Scrape modal (region-aware) + progress run | Klik baris → detail lengkap; scrape dari UI berhasil |
| **M4 Freelance/Gig** | Reddit, Freelancer.com, HN freelancer, parsing budget & durasi | Filter "Gigs" berisi data nyata |
| **M5 Job board besar + ID** | JobSpy, JobStreet/Glints/Kalibrr, Telegram | Lowongan Indonesia & LinkedIn/Indeed muncul |
| **M6 Schedules** | `schedules.json`, scheduler internal, `fjg schedule run-due`, `register-task.ps1`, Schedules panel | Jadwal jalan saat app hidup maupun mati |
| **M7 Polish** | Kolom bisa diatur, bookmark, export CSV, dark mode, shortcut keyboard, retensi data | Siap dipakai harian |

## 7. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Sumber memblokir (403/429) | Rate limit per sumber, backoff, User-Agent jujur, auto-disable setelah N gagal, status sumber di UI |
| Endpoint/HTML berubah | 1 modul per sumber + fixture test; raw disimpan sehingga bisa re-normalize tanpa scrape ulang |
| File membesar (deskripsi penuh + raw) | File per sumber, kompaksi (hapus duplikat/versi lama), opsi arsip > 90 hari ke `data/archive/` |
| Search lambat bila data > ~200k job | Index in-memory dulu; jalur upgrade: SQLite FTS5 (tetap 1 file lokal) tanpa ubah API |
| Klasifikasi tanpa LLM kurang akurat | Rule & kamus di `config/*.yaml` yang bisa diedit; nilai `unknown` lebih baik daripada salah |
| ToS / legal | Hanya data publik, atribusi, tidak bypass login/captcha |

## 8. Pertanyaan Terbuka

Tidak ada. Semua pertanyaan sudah dijawab di rev 3.
