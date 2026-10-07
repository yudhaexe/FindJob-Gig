# FindJob&Gig — UI/UX Design

> Lihat [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) untuk API & skema data.
> **Bahasa UI: English only.** Dokumen ini berbahasa Indonesia, tapi semua label di wireframe adalah teks UI final (EN).

---

## 1. Prinsip

1. **Scan cepat:** daftar hasil padat seperti spreadsheet. Info penting dalam satu baris: Title, Company, Salary/Budget, Type, Duration, Location/Mode, Source, Posted.
2. **Detail sesuai permintaan:** semua info lain (deskripsi penuh, skill, link, duplikat, **raw JSON**) muncul di drawer saat baris diklik.
3. **Region focus:** satu pilihan region global di header (default **All regions**) yang memengaruhi hasil dan scrape.
4. **Jujur soal data:** nilai kosong tampil `—`, nilai hasil tebakan diberi `~`, salary **selalu dalam mata uang asli** (tanpa konversi), sumber selalu terlihat.
5. **Bisa dibagikan:** semua state (query, region, filter, sort, job yang dibuka) tersimpan di URL.
6. **Ringan:** satu halaman, virtual scroll untuk ribuan baris.

## 2. Struktur Layar

Area halaman: **Header** → **Filter Sidebar** → **Results** → **Job Drawer**. **Scrape** dibuka sebagai modal, sedangkan **Schedules / Sources / Runs** sebagai panel samping.

### 2.1 Desktop (≥ 1024px)

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ ◆ FindJob&Gig  [🌏 Southeast Asia ▾] [🔍 react -wordpress "senior"          ] [Jobs|Gigs|All]│
│                                       Updated 2h ago · ⏱ 3 schedules  [⟳ Scrape] [☰ Menu] │
├────────────────┬──────────────────────────────────────────────────────────────────────────┤
│ FILTERS  Reset │ 1,284 results · Region: SEA ✕ · react ✕ · Freelance ✕   Sort: [Newest ▾]  │
│                │                                                  [☰ Table | ▦ Cards] [⚙]  │
│ Region         ├──────────────────────────────────────────────────────────────────────────┤
│ ☑ Include      │ Title                 Company      Salary/Budget     Type    Duration    │
│   worldwide    │                       Location     Source            Posted              │
│   remote       ├──────────────────────────────────────────────────────────────────────────┤
│ ☐ Hide unclear │ Senior React Dev      Acme Inc     USD 60–80k/yr     Full    —           │
│   remote scope │ ★ react ts next       🌐 Worldwide Remotive          2h                  │
│                ├──────────────────────────────────────────────────────────────────────────┤
│ Type           │ Next.js landing page  (individual) USD 500 fixed     Gig     2 wks       │
│ ☑ Full-time 812│                       🌐 Remote·SEA Reddit           5h                  │
│ ☐ Part-time  64├──────────────────────────────────────────────────────────────────────────┤
│ ☑ Freelance 231│ Frontend Engineer     Tokopedia    IDR 15–25M/mo     Full    —           │
│ ☐ Contract  120│                       📍 Jakarta,ID JobStreet +2     1d                  │
│ ☐ Internship 57│ …                                                                        │
│ Work mode      │                                                                          │
│ ☑ Remote ☐ Hybrid ☐ Onsite                                                                │
│ Country (in region) ▸                                                                     │
│ Source (12) ▸  │                                                                          │
│ Posted         │                                                                          │
│ ○24h ◉3d ○7d ○30d ○Any                                                                    │
│ Currency       │                                                                          │
│ [Any ▾]  (IDR 412 · USD 690 · SGD 38 …)                                                   │
│ Min salary     │                                                                          │
│ [____] /[mo ▾] (disabled until a currency is picked)                                      │
│ ☐ Has salary   │                                                                          │
│ Seniority ▸    │                                                                          │
│ Max duration ▸ │                                     [ ← 1 2 3 … 52 → ]                   │
└────────────────┴──────────────────────────────────────────────────────────────────────────┘
```

Setiap baris tabel terdiri dari 2 baris teks. Baris 1 berisi data utama, baris 2 berisi skill/lokasi/sumber dengan warna redup.

### 2.2 Region Selector (header)

```
┌──────────── Region focus ────────────┐
│ 🔍 search region / country           │
│ ◉ 🌐 All regions                     │
│ ○ 🌍 Worldwide remote only           │
│ ── Asia Pacific ──────────────────── │
│ ○ Asia Pacific (all)            2,140│
│ ○   Southeast Asia               980 │
│ ○     Indonesia                  612 │
│ ○     Singapore                  141 │
│ ○   East Asia                    320 │
│ ○   South Asia                   410 │
│ ○   Oceania                      190 │
│ ── Europe ───────────────────── 1,870│
│ ── North America ────────────── 3,200│
│ ── Latin America ────────────── 260  │
│ ── Middle East & Africa ─────── 300  │
│ ★ Pinned: Indonesia, Southeast Asia  │
└──────────────────────────────────────┘
```

- Angka di setiap region adalah jumlah job yang cocok (mengikuti aturan region di DESIGN-SYSTEM §5a).
- Region bisa di-pin (★) supaya muncul di atas. Pilihan terakhir disimpan di `localStorage` dan URL `?region=SEA`.
- Bila region ≠ All, filter **Country (in region)** di sidebar menampilkan negara-negara di dalam region itu.
- Lokasi di tabel memakai label scope remote: `🌐 Worldwide`, `🌐 Remote·EU`, `🌐 Remote·US only`, `🌐 Remote ?` (scope tidak jelas), `🏢 Hybrid·Jakarta`, `📍 Singapore,SG`.

### 2.3 Job Drawer (klik baris → panel kanan, lebar ~45%)

```
                                   ┌──────────────────────────────────────────────┐
                                   │ ✕                       ↑ ↓   ⧉ Copy link    │
                                   │ Senior React Developer                       │
                                   │ Acme Inc ↗ · 🌐 Worldwide · Full-time · Senior│
                                   │ USD 60,000–80,000 / year  ·  Posted 2h ago   │
                                   │ [ Apply on Remotive ↗ ]  Also on: RemoteOK, LinkedIn │
                                   ├──────────────────────────────────────────────┤
                                   │ [Overview] [Description] [Raw JSON]          │
                                   ├──────────────────────────────────────────────┤
                                   │ POSITION                                     │
                                   │ Category        Job                          │
                                   │ Type            Full-time                    │
                                   │ Seniority       Senior                       │
                                   │ Duration        —                            │
                                   │ Skills          [react][typescript][next.js] │
                                   │ Source tags     [frontend][saas]             │
                                   │ COMPENSATION                                 │
                                   │ Salary          USD 60k–80k / year (source)  │
                                   │ LOCATION                                     │
                                   │ Work mode       Remote                       │
                                   │ Remote scope    Worldwide                    │
                                   │ Location        Anywhere                     │
                                   │ Regions         —                            │
                                   │ TIME                                         │
                                   │ Posted          Oct 6, 2026 09:12            │
                                   │ First seen      Oct 6, 2026 10:00            │
                                   │ Expires         —                            │
                                   │ SOURCE                                       │
                                   │ Source          Remotive ↗ (attribution)     │
                                   │ Matched by      "react" · run 2026-10-07 02:00│
                                   └──────────────────────────────────────────────┘
```

- **Overview** menampilkan **semua field `Job`** yang punya nilai, dikelompokkan Position · Compensation · Location · Time · Source.
- **Description**: HTML asli yang disanitasi (DOMPurify), keyword pencarian di-highlight.
- **Raw JSON**: objek `raw` asli, bisa dilipat, ada pencarian di dalam JSON, tombol [Copy] [Download], dan toggle "Show normalized job".
- `↑ ↓` pindah ke job sebelum/berikutnya tanpa menutup drawer. URL `?job=<id>`.

### 2.4 Mobile (< 768px)

```
┌───────────────────────────┐
│ ◆ FindJob&Gig  [🌏 SEA ▾] │
│ [🔍 react            ][⟳]│
│ [Filters (3)] [Newest ▾] │
├───────────────────────────┤
│ Senior React Developer    │
│ Acme Inc                  │
│ 💰 USD 60–80k/yr          │
│ [Full-time][🌐 Worldwide] │
│ ⏱ —  · Remotive · 2h      │
├───────────────────────────┤
│ Next.js landing page      │
│ 💰 USD 500 fixed          │
│ [Gig][🌐 Remote·SEA]      │
│ ⏱ 2 wks · Reddit · 5h     │
└───────────────────────────┘
```

Di mobile tampilan memakai kartu, filter dan region dibuka sebagai bottom sheet, dan drawer menjadi layar penuh.

### 2.5 Scrape Modal

```
┌──────────────────── Scrape now ─────────────────────┐
│ Keywords     [react] [frontend] [+ add]             │
│ Region       [🌏 Southeast Asia ▾]  (follows header) │
│ Location     [optional city, e.g. Jakarta]          │
│ Category     ◉ All  ○ Jobs  ○ Gigs                  │
│ Type         ☐Full-time ☐Part-time ☐Contract ☐Freelance ☐Internship │
│ ☐ Remote only   Since [72] hours   Max per source [100]│
│ Sources (auto-selected for region)                  │
│  ☑ Remotive ☑ RemoteOK ☑ HN ☑ Reddit ☑ Himalayas    │
│  ☑ JobStreet ☑ Glints ☑ Kalibrr ☐ LinkedIn (slow)   │
│  ☐ Arbeitnow (EU only — not in region)              │
│ ☐ Save as schedule: every [6h ▾]  name [React SEA ] │
│                              [Cancel] [▶ Start]     │
├────────────────── Progress ─────────────────────────┤
│ Remotive   ✔ 80 fetched · 12 new         1.8s       │
│ Reddit     ⟳ running…                               │
│ LinkedIn   ✖ 429 Too Many Requests     [Retry]      │
│ ▓▓▓▓▓▓▓░░░ 3/5 sources              [View results →]│
└─────────────────────────────────────────────────────┘
```

- Sumber otomatis dicentang sesuai region, dan sumber di luar region diberi label "not in region" tapi tetap bisa dicentang manual.
- Modal bisa ditutup saat scrape berjalan. Progress pindah ke indikator header (`⟳ 3/5`), lalu muncul toast "12 new jobs · View".

### 2.6 Schedules Panel (Menu → Schedules)

```
┌──────────────────────── Schedules ──────────────────────── [+ New] ┐
│ ● React SEA        every 6h   SEA   react, frontend                │
│   Last: 2h ago ✔ 12 new   Next: in 4h       [Run now] [Edit] [⏸]   │
│ ● Design gigs      every 12h  All   figma, ui designer · Gigs      │
│   Last: 9h ago ⚠ partial (Reddit 429)  Next: in 3h  [Run now] [Edit] [⏸] │
│ ○ Indonesia jobs   paused after 3 failures             [Resume]    │
├────────────────────────────────────────────────────────────────────┤
│ Background runs when app is closed:                                │
│ Windows Task Scheduler: ✔ registered (every 30 min)  [How to set up]│
└────────────────────────────────────────────────────────────────────┘
```

- Form jadwal sama dengan Scrape modal, ditambah field interval.
- Status Task Scheduler dibaca dari `fjg schedule status`. Tombol "How to set up" menampilkan perintah `scripts/register-task.ps1`.

### 2.7 Panel Lain (Menu)

- **Sources:** name, category, regions, last status, job count, consecutive failures, enable toggle, attribution link.
- **Run history:** daftar run (manual/scheduled), klik untuk detail per sumber.

## 3. Kolom Tabel

| Column | Isi | Format | Default |
|---|---|---|---|
| Title | `title` + skill (baris 2, maks 3 chip) | bold, ellipsis | ✔ |
| Company | `company` (+ logo 16px) | `(individual)` bila gig tanpa perusahaan | ✔ |
| Salary/Budget | `salary` atau `budget` | mata uang asli, lihat §5 | ✔ |
| Type | `employment_type` / Gig | badge | ✔ |
| Duration | `duration` | `3 mo`, `2 wks`, `—` | ✔ |
| Location | `work_mode` + scope/kota | lihat §2.2 | ✔ |
| Source | `source_name` (+N duplikat) | teks redup | ✔ |
| Posted | `posted_at` | relatif `2h`, `3d`; tooltip tanggal lengkap | ✔ |
| Seniority, Country, Expires, First seen, Currency | — | — | via ⚙ |

- Klik header untuk mengurutkan (sort **Salary** non-aktif sampai filter Currency dipilih). Kolom bisa diubah ukurannya dan disembunyikan, dan preferensi disimpan di `localStorage`.
- Baris yang sudah dibuka tampil redup. ★ untuk bookmark, ditambah filter "Saved".

## 4. Interaksi & Keyboard

| Action | Mouse | Keyboard |
|---|---|---|
| Focus search | klik | `/` |
| Change region | klik selector | `g r` |
| Move row | — | `j`/`k` atau `↓`/`↑` |
| Open detail | klik baris | `Enter` |
| Close drawer/modal | ✕ / klik luar | `Esc` |
| Open source page | Apply | `o` |
| Bookmark | ★ | `s` |
| Open scrape | ⟳ Scrape | `Shift+S` |

- Search otomatis dengan debounce 250 ms. Tooltip `?` menjelaskan sintaks (`-exclude`, `"phrase"`).
- Chip filter aktif (termasuk region) tampil di atas hasil dan bisa dihapus satu per satu.

## 5. Format Data (tanpa konversi mata uang)

| Data | Aturan | Contoh |
|---|---|---|
| Mata uang | **selalu kode ISO + nilai asli**, tidak pernah dikonversi | `IDR 8–12M/mo`, `USD 60–80k/yr`, `SGD 6k/mo`, `EUR 45/hr` |
| Singkatan | `k` = ribu, `M` = juta (format EN) | `IDR 15M`, `USD 120k` |
| Periode | `/hr` `/day` `/wk` `/mo` `/yr` `fixed` | `USD 500 fixed` |
| Mata uang ditebak | `~` + tooltip "Currency guessed from '$'" | `~USD 40/hr` |
| Salary dari deskripsi | `~` + tooltip "Parsed from description" | `~IDR 10M/mo` |
| Kosong | `—` | `—` |
| Waktu | relatif < 7 hari, absolut sesudahnya | `5h`, `3d`, `Sep 12` |
| Durasi | singkat | `3 mo`, `2 wks`, `10 days`, `—` |

Format angka memakai locale `en-US` (`60,000`).

## 6. State Kosong / Loading / Error

| State | Tampilan (EN) |
|---|---|
| Belum ada data | "No jobs yet. Run your first scrape." + [▶ Scrape All regions] [▶ Scrape Indonesia] [▶ Scrape SEA] |
| Tidak ada hasil | "No results for *react golang* in Southeast Asia." + saran: [Search All regions] · [Remove 'Freelance'] · [Extend to 30 days] · [Scrape this keyword] |
| Loading | skeleton 8 baris |
| Error API | red banner "Couldn't load jobs." + [Retry] |
| Sumber gagal | baris merah di progress; run berstatus `partial`, hasil sumber lain tetap tersimpan |
| Jadwal ter-pause | badge kuning di header "1 schedule paused" |

## 7. Design Token

```css
:root {
  --bg: #ffffff;  --surface: #f7f7f8;  --border: #e4e4e7;
  --text: #18181b; --text-muted: #71717a;
  --accent: #2563eb;  --accent-fg: #ffffff;
  --danger: #dc2626;  --success: #16a34a;  --warning: #d97706;
  --t-fulltime: #2563eb; --t-parttime: #7c3aed; --t-contract: #0891b2;
  --t-freelance: #ea580c; --t-gig: #ea580c; --t-internship: #16a34a; --t-unknown: #71717a;
  --radius: 8px; --row-h: 56px;
  --font: "Inter", system-ui, sans-serif; --font-mono: "JetBrains Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#0b0b0d; --surface:#151518; --border:#27272a; --text:#f4f4f5; --text-muted:#a1a1aa; }
}
```

- Teks tabel 14px, teks redup 13px, judul drawer 20px. Angka salary memakai `tabular-nums`.
- Badge: latar warna type dengan opacity 12% dan teks warna penuh. Spasi kelipatan 4px, kontras teks minimal AA.

## 8. Struktur Komponen React

```
App
├─ Header            (RegionSelect, SearchBar, CategoryToggle, LastUpdated, ScheduleBadge, ScrapeButton, RunIndicator, Menu)
├─ FilterSidebar     (RegionOptions, FilterGroup×n, CurrencySelect, MinSalary, FacetCount, Reset) → BottomSheet di mobile
├─ ResultsToolbar    (ResultCount, ActiveChips, SortSelect, ViewToggle, ColumnSettings)
├─ ResultsTable      (TanStack Table + virtual rows) | ResultsCards (mobile)
├─ Pagination
├─ JobDrawer         (DrawerHeader, Tabs: Overview | Description | RawJson)
├─ ScrapeModal       (QueryForm, RegionSelect, SourcePicker, SaveAsSchedule, RunProgress)
├─ SchedulesPanel · SourcesPanel · RunsPanel
└─ Toasts
hooks: useUrlState(), useRegion(), useJobs(query), useJob(id), useRun(id), useSchedules(), useLocalPref(key)
lib:   api.ts, format.ts (money/duration/time, no FX), regions.ts, highlight.ts
```

Dependensi minimal: `react`, `@tanstack/react-table`, `@tanstack/react-virtual`, `dompurify`, `tailwindcss`. JSON viewer dibuat sendiri. Tidak ada library i18n karena UI hanya berbahasa EN.

## 9. Aksesibilitas

- `<table>` asli dengan `aria-sort`, drawer dan modal memakai `role="dialog"` + focus trap.
- Semua aksi bisa dilakukan dengan keyboard, target sentuh minimal 40px di mobile.
- Badge selalu menampilkan teks, jadi warna bukan satu-satunya penanda.
