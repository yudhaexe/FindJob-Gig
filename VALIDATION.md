# Validasi Sumber — Freelance Kreatif (Foto/Video)

> Diuji **2026-10-07** dari laptop (IP rumahan, Indonesia) dengan request nyata.
> Fokus: freelance/jasa **photography, videography, photo editor, video editor** dan sejenisnya.
> Script: `backend/probes/probe_jobspy.py`, `backend/probes/probe_apis.py` (output ke `data/probes/`, gitignored).

## Ringkasan

| Sumber | Status | Waktu | Hasil | Relevan kreatif | Salary/Budget | Catatan |
|---|---|---|---|---|---|---|
| **Freelancer.com API** | ✅ | 9.4 dtk (6 query) | 118 | **91** | ✅ budget + mata uang | **Sumber gig terbaik**: proyek nyata (wedding photo, video montage, headshot, event photographer) |
| **JobStreet ID** (API internal) | ✅ | 5.8 dtk (4 query) | 65 | **57** | sebagian (`Rp 6.000.000 – Rp 9.000.000 per month`) | Lowongan ID: Videografer, Photographer & Videographer, Video Editor |
| **Kalibrr** (API internal) | ✅* | ~1 dtk | 56 (video editor) | — | — | *Percobaan pertama gagal DNS (sementara), retry OK |
| **Himalayas API** | ✅ | 6.1 dtk | 61 | **57** | — | Remote photographer/videographer global |
| **JobSpy – Indeed US** (contract) | ✅ | 1.2 dtk | 20 | ~20 | 10/20 (`USD 45–65/hourly`) | Wedding videographer, content creator kontrak |
| **JobSpy – Indeed ID** | ✅ | 1.2–1.4 dtk | 3 (`videografer`) / 20 (`video editor`) | ~18 | 13/23 (`IDR 5–6M/monthly`) | Ada judul "Video Editor (Freelance)" |
| **JobSpy – Glassdoor** | ✅ | 2.6 dtk | 15 | 15 | **14/15** | "Freelance Photographer/Videographer USD 50–100/hourly" |
| **JobSpy – ZipRecruiter** | ✅ | 1.7 dtk | 15 | 15 | 11/15 | US saja |
| **JobSpy – LinkedIn** | ⚠️ | 5.7–12 dtk | 17–20 | ~60% | ❌ tidak ada | Lambat. Hasil "freelance photographer Indonesia" bercampur (social media, sketch artist) |
| **JobSpy – Google Jobs** | ❌ | — | 0 | — | — | `Google returned no job data`, rusak di JobSpy 1.2.0 |
| **Reddit** `.json` | ❌ | — | — | — | — | `403 Blocked` untuk semua subreddit |
| **Reddit** `.rss` | ⚠️ | ~1.5 dtk | 25/feed | r/forhire: 4–11 `[Hiring]` | kadang di judul (`$20 - professional headshot`) | Jalan, tapi **429 setelah ~2 request**. Perlu jeda ≥10–15 dtk atau OAuth |
| RemoteOK | ✅ | 1.4 dtk | 99 | 14 (mayoritas noise) | ✅ | Hampir tidak ada role kreatif |
| Arbeitnow | ✅ | 1.9 dtk | 750 | 15 (noise: "Photovoltaik", "Video Games") | — | Pasar Jerman, tidak relevan |
| Jobicy | ✅ | 9.8 dtk | 69 | 4 | — | Sedikit (mis. "On-Call Video Editor – Contractor pool") |
| Remotive | ✅ | 6 dtk | 17 | **0** | — | Tidak ada role kreatif |
| We Work Remotely RSS | ✅ | 2.8 dtk | 89 | **0** | — | Tidak ada role kreatif |
| HN "Who is hiring" | ✅ | 4.2 dtk | 15–22 hit "video" | ~0 | — | Isinya software engineer; tidak berguna untuk niche ini |
| Glints (GraphQL langsung) | ❌ | — | — | — | — | `403 Forbidden` |
| **Glints via `cloudscraper`** (cara repo ifqygazhar/jobscraper-api) | ✅ | ~2 dtk | halaman explore berisi JSON | ✅ "Editor Video", "Video Editor" | ? | **Tanpa login.** Data diambil dari JSON yang tertanam di HTML |
| Projects.co.id | ❌ | — | — | — | — | `403 Forbidden` |

## Contoh Output Nyata

**Freelancer.com** (gig + budget, mata uang asli)
```
Traditional Wedding Photography + Full Reel   | INR 1500–12500 fixed | Photography, After Effects, Photo Editing
Product Photographer & Video Editor            | INR 15000–30000 fixed
Birthday Video Montage Creation                | USD 30–250 fixed     | Videography, Video Production
Awards Evening Event Photographer              | AUD 750–1500 fixed
Casual Natural Indoor Headshot                 | GBP 20–250 fixed     | Photoshop, Photo Editing
```

**JobStreet ID**
```
VIDEOGRAFER                        | PT Faito Racing Development Indonesia | Rp 6.000.000 – Rp 9.000.000 per month | Full time
Videographer / Content Creator     | Yayasan Daur Pangan Nusantara         | Rp 5.500.000 – Rp 7.000.000 per month | Full time
Video Editor & Grapic Designer     | GAMATECHA SOLUSI NUSANTARA            | Rp 2.500.000 – Rp 3.500.000 per month | Full time
```

**JobSpy – Indeed / Glassdoor**
```
Wedding Videographer/ Photographer     | Avkreations LLC     | Manassas, VA, US | contract | USD 45–65/hourly
Video Editor (Freelance)               | PT. Naganaya Indonesia | Jakarta, ID    | —        | IDR 2–4M/monthly
Fotografer, Videografer + Editor       | Independent Recruitment | Tangerang, ID | —        | IDR 5–6M/monthly
Freelance Photographer/Videographer…   | Real Estate Production Network | New York, NY | — | USD 50–100/hourly
```

**Reddit r/forhire, r/slavelabour, r/PhotoshopRequest** (RSS)
```
[Hiring] After Effects / Premiere Motion Graphics Editor for Weekly Personal Finance Channel
[hiring] looking for a video editor
[TASK] Film 15 short cooking videos a month for a recipe app, $250/month + $50 bonus per v…
$20 - professional headshot            (r/PhotoshopRequest)
```

## Field yang Tersedia per Sumber (untuk mapping ke skema `Job`)

| Field | Freelancer | JobStreet | JobSpy | Himalayas | Reddit |
|---|---|---|---|---|---|
| Title, URL | ✅ | ✅ | ✅ | ✅ | ✅ |
| Company | — (client) | ✅ | ✅ | ✅ | — |
| Salary/Budget | ✅ min/max/currency/fixed\|hourly | label teks | ✅ min/max/currency/interval | sebagian | regex dari judul/isi |
| Type | `fixed`/`hourly` | `workTypes` (Full time/Contract/…) | `job_type` | `employmentType` | dari tag `[Hiring]`/`[TASK]` |
| Skill/Kategori | ✅ (`jobs[]`) | — | — | ✅ | — |
| Lokasi | negara client | ✅ | ✅ | ✅ (+ timezone) | — |
| Deskripsi penuh | ✅ (`full_description`) | ringkas (perlu detail call) | ✅ markdown | ✅ | ✅ |

## Kesimpulan & Perubahan Rencana

1. **JobSpy terbukti bekerja** untuk Indeed (US & ID), Glassdoor, ZipRecruiter dan LinkedIn. Google Jobs rusak, jadi **di-disable**. LinkedIn tetap dipakai, tapi tanpa salary dan dengan rate yang pelan.
2. **Sumber utama niche kreatif** (urutan prioritas baru):
   1. Freelancer.com (gig + budget) ← **naik ke P1**
   2. JobStreet ID + Kalibrr + Indeed ID (pasar Indonesia) ← **naik ke P1**
   3. JobSpy Indeed/Glassdoor/ZipRecruiter (global, kontrak/part-time)
   4. Himalayas (remote kreatif)
   5. Reddit r/forhire, r/slavelabour, r/PhotoshopRequest, r/VideoEditingRequests, **wajib OAuth** (app "script" gratis, ±100 req/menit). Fallback RSS dengan jeda 15 dtk.
3. **Turun prioritas** untuk niche ini: Remotive, We Work Remotely, HN, Arbeitnow, RemoteOK dan Jobicy. Tetap ada sebagai sumber umum, tapi tidak dicentang default di preset "Creative".
4. **Dibuang**: Projects.co.id (403), Google Jobs via JobSpy. ~~Glints~~ → **bisa** lewat `cloudscraper` (lihat bawah).
5. **Klasifikasi**: regex kata kunci kreatif terlalu longgar (`photo` cocok dengan "Photovoltaik", `video` dengan "Video Games"). Perlu kamus khusus kategori **Creative** dengan word boundary dan daftar exclude (`photovoltaic`, `video game`, `data annotator`, …).
6. Tambahkan **preset "Creative / Photo & Video"** di Scrape modal: keyword `photographer, videographer, video editor, photo editor, retoucher, fotografer, videografer, editor video, content creator` + sumber di poin 2.

## Cara Menjalankan Ulang

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install python-jobspy httpx feedparser selectolax   # sementara, sampai M5
.\.venv\Scripts\python.exe probes\probe_jobspy.py
.\.venv\Scripts\python.exe probes\probe_apis.py
# hasil: data/probes/*.json + _summary_*.json
```

## Pencarian Repo Lanjutan (GitHub Search API, 2026-10-07)

| Repo | ★ | Push | Lisensi | Cara kerja | Verdict |
|---|---|---|---|---|---|
| [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) | 4.4k | 2026-10-07 | MIT | HTTP, guest endpoint LinkedIn/Indeed/dll | ✅ **Provider utama** |
| [spinlud/py-linkedin-jobs-scraper](https://github.com/spinlud/py-linkedin-jobs-scraper) | 497 | 2026-09-08 | MIT | Selenium + Chrome, **hanya mode login** (cookie `li_at`) | ⚠️ Opsional. Berisiko akun LinkedIn kena restrict; berat (Chrome) |
| [ifqygazhar/jobscraper-api](https://github.com/ifqygazhar/jobscraper-api) | 44 | 2025-10-28 | MIT | Flask + cloudscraper: Glints, JobStreet, Indeed, RemoteOK, Disnaker Bandung | ✅ **Referensi teknik** (Glints teruji jalan). Bukan library, jadi tidak di-install. Logikanya di-port ke connector kita + atribusi MIT |
| [rkaran112/gig-scanner](https://github.com/rkaran112/gig-scanner) | 0 | 2026-07-23 | — | FastAPI + scan Reddit gig | 📚 Referensi saja (tanpa lisensi, 0★) |
| [depermana12/jobstreet-scraper](https://github.com/depermana12/jobstreet-scraper) | 2 | 2025-08-08 | — | CLI JobStreet | ❌ Kita sudah punya endpoint API langsung |
| Glints/Kalibrr/Craigslist/Reddit scraper lain | 0–22 | mayoritas < 2025 | campur | — | ❌ Kecil/mati/tanpa lisensi |
