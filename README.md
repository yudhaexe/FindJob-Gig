# FindJob&Gig

Aplikasi lokal untuk mengumpulkan lowongan kerja **dan** kerjaan freelance/gig dari banyak situs (JobStreet, Kalibrr, Freelancer.com, Himalayas, Hacker News, Reddit, Telegram, dll.) dalam satu halaman. Ketik kata kunci, pilih tipe, lalu cari. Semua data tersimpan di komputer kamu sendiri, tanpa akun dan tanpa AI.

---

## Mulai cepat (Windows)

### 1. Install dua program ini (sekali saja)

| Program | Unduh | Catatan |
|---|---|---|
| **Node.js** (versi LTS) | https://nodejs.org | Klik Next terus sampai selesai |
| **Python 3.11 atau lebih baru** | https://www.python.org/downloads | **Centang "Add python.exe to PATH"** di layar pertama installer |

Setelah install, **restart komputer** (atau tutup semua jendela terminal) supaya terdeteksi.

### 2. Jalankan

**Klik dua kali `start.bat`** di folder ini.

- Pertama kali: dia memasang semua kebutuhan sendiri (butuh internet, sekitar 2-5 menit).
- Setelah itu langsung jalan dalam beberapa detik.

Biarkan jendela hitam yang muncul tetap terbuka. Itu mesin aplikasinya.

### 3. Buka di browser

Buka alamat **http://localhost:5173**

### 4. Berhenti

Tekan **Ctrl + C** di jendela hitam, atau tutup jendelanya.

---

## Cara pakai

1. Klik tombol **⟳ Scrape** (kanan atas).
2. Isi kata kunci (misal `video editor`), tekan **Enter** untuk menambah. Pilih region dan sumber, lalu klik **▶ Start**.
3. Tunggu progress selesai, lalu klik **View results**.
4. Persempit hasil dengan filter di sisi kiri (tipe, remote/onsite, gaji, sumber, dll.). Kotak pencarian bisa memakai:
   - `video editor` : semua kata harus ada
   - `-wedding` : buang yang mengandung kata itu
   - `"after effects"` : frasa persis
   - `photo*` : awalan kata
5. Klik satu lowongan untuk melihat detail. Tombol ★ menyimpan, ✕ menyembunyikan.
6. Tombol **CSV / JSON** di atas tabel mengunduh semua hasil yang sedang tampil.

### Scrape otomatis (jadwal)

Di jendela Scrape, centang **Save as schedule** dan pilih interval. Daftar jadwal ada di tombol **⏱** di header.
Supaya jadwal tetap jalan walau aplikasi ditutup, jalankan sekali (klik kanan Start > Windows PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1
```

### Pintasan keyboard

Tekan **?** di aplikasi untuk melihat daftar lengkap. Beberapa yang utama: `/` cari, `j`/`k` naik-turun, `Enter` buka, `s` simpan ★, `x` sembunyikan, `Shift+S` scrape.

---

## Kalau ada masalah

| Gejala | Solusi |
|---|---|
| `start.bat` bilang Python/Node tidak ditemukan | Install ulang dan pastikan "Add to PATH" tercentang, lalu restart komputer |
| `Port 8000 masih dipakai` | Tutup jendela hitam lama, lalu jalankan lagi. Kalau tetap, restart komputer |
| Halaman kosong / "0 results" | Region tersimpan mungkin terlalu sempit. Pilih **All regions** di kiri atas, atau klik Scrape dulu |
| Scrape satu sumber gagal | Normal sesekali (situs membatasi akses). Lihat log di jendela Scrape, coba lagi nanti |
| Install pertama gagal | Pastikan internet aktif, lalu klik dua kali `start.bat` lagi |

## Data kamu

Semua tersimpan di folder `data/` (tidak ikut ke Git). Untuk membersihkan data lama:

```
npm run fjg -- prune --days 90 --dry-run
```

Hapus `--dry-run` untuk benar-benar memindahkannya ke `data/archive/`. Lowongan yang kamu tandai ★ tidak ikut terpengaruh.

---

## Untuk developer

Butuh Node >= 20 dan Python >= 3.11. Semua perintah dari root repo:

| Perintah | Fungsi |
|---|---|
| `npm i` | Install semua (buat `backend/.venv`, pip install, npm install frontend) |
| `npm start` | Backend (:8000) + frontend (:5173) dengan auto-reload |
| `npm test` | pytest backend + typecheck frontend |
| `npm run build` | Build frontend ke `frontend/dist` |
| `npm run serve` | Build lalu layani semuanya dari :8000 (mode produksi) |
| `npm run fjg -- <args>` | CLI, mis. `npm run fjg -- scrape --preset creative`, `npm run fjg -- sources` |

Dokumentasi: [HANDOVER.md](HANDOVER.md) (status & keputusan, baca dulu) · [PLANNING.md](PLANNING.md) · [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) · [DESIGN-UIUX.md](DESIGN-UIUX.md)

> Folder ini bernama `FindJob&Gig` (ada tanda `&`). Kalau menjalankan perintah manual di terminal, selalu beri tanda kutip pada path-nya.
