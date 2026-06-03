# Panduan Penggunaan: Fetch Artikel dari OpenAlex dengan Filter ISSN dan Keyword

Repository ini berisi tiga script Python untuk mengambil artikel ilmiah dari API OpenAlex berdasarkan daftar ISSN (dari SCImago), memfilter dengan kata kunci, dan membersihkan duplikat antar kelompok pencarian.

## Prasyarat

- Python 3.8 atau lebih baru
- `git` (untuk cloning)
- Akses internet (untuk API OpenAlex)

## 1. Clone Repository

```bash
git clone git@github.com:farisalfatih/find_references_scopus.git
cd find_references_scopus
```

## 2. Setup Virtual Environment

```bash
python -m venv venv
```

Aktifkan virtual environment:

- **Linux / Mac:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

Install dependencies (hanya `requests` yang diperlukan):

```bash
pip install requests
```

## 3. Persiapan Data ISSN

Script `get_issn_electronic.py` membaca file JSON hasil dari SCImago (sudah disediakan di folder `journal-lists/scimago_split/`) dan mengekstrak daftar ISSN elektronik berdasarkan pilihan kuartil (Q1–Q4).

**Cara menjalankan:**

```bash
python get_issn_electronic.py
```

Anda akan diminta memasukkan **path file JSON**. Contoh path yang tersedia:

- `journal-lists/scimago_split/subject_area_Computer_Science.json`
- `journal-lists/scimagojr_2025.json`
- Atau file lain di dalam `journal-lists/scimago_split/`

Setelah memilih, Anda diminta memilih kuartil:

- `semua` → semua jurnal
- `Q1,Q2` → hanya jurnal dengan kuartil Q1 dan Q2, dst.

Script akan mencetak daftar ISSN dalam format set Python, misalnya:

```
{"2157-846X", "2365-9440", ...}
```

**Copy hasil output tersebut** (dari `{ ... }`) untuk digunakan di script berikutnya.

## 4. Konfigurasi dan Menjalankan Fetch Artikel

Buka file `openalex_fetch.py` dan **ganti nilai `ISSN_ELECTRONIC`** dengan hasil copy dari langkah sebelumnya. Juga sesuaikan parameter lain sesuai kebutuhan:

- `YEAR_FROM` / `YEAR_TO` – rentang tahun publikasi
- `LANGUAGE` – filter bahasa (default `["en"]`)
- `SEARCH_GROUPS` – definisi kelompok kata kunci (contoh sudah ada)
- `OUTPUT_FILE` – nama file hasil (default `openalex_results.json`)
- `ISSN_BATCH_SIZE` – jumlah ISSN per request (default 50, bisa dinaikkan hingga 200)

**Contoh SEARCH_GROUPS:**

```python
SEARCH_GROUPS = {
    "LSTM Bitcoin": {
        "keywords": ["LSTM", "bitcoin"],
        "mode": "all",
    },
    "LSTM Bitcoin XGBoost": {
        "keywords": ["LSTM", "bitcoin", "XGBoost"],
        "mode": "all",
    },
}
```

Setelah konfigurasi selesai, jalankan:

```bash
python openalex_fetch.py
```

Proses akan mengambil artikel per kelompok dengan parameter `search` langsung di API (efisien). Hasil disimpan dalam file JSON dengan struktur:

```json
{
  "LSTM Bitcoin": [ {...}, ... ],
  "LSTM Bitcoin XGBoost": [ {...}, ... ]
}
```

## 5. Membersihkan Duplikat Antar Kelompok

Setelah fetch selesai, file `openalex_results.json` mungkin berisi artikel yang sama muncul di beberapa kelompok (karena tumpang tindih kata kunci). Script `clear_duplicate.py` akan:

- Mendeteksi hubungan subset antar kelompok berdasarkan keyword (misal kelompok dengan keyword lebih banyak adalah superset)
- Memindahkan artikel duplikat ke kelompok yang paling spesifik (superset)
- Jika tidak ada hubungan subset, membuat kelompok gabungan baru (misal `"LSTM Bitcoin + LSTM Bitcoin XGBoost"`)

**Cara menjalankan:**

```bash
python clear_duplicate.py
```

Secara default, script membaca `openalex_results.json` dan menghasilkan `openalex_results_hierarchy.json`. Anda bisa mengubah nama file input/output di dalam `main()`.

Output akhir tidak memiliki artikel yang sama di dua kelompok berbeda.

## Contoh Alur Lengkap

```bash
# 1. Clone repo
git clone git@github.com:farisalfatih/find_references_scopus.git
cd find_references_scopus

# 2. Setup venv
python -m venv venv
source venv/bin/activate   # Linux
pip install requests

# 3. Ekstrak ISSN (misal untuk Computer Science, Q1 dan Q2)
python get_issn_electronic.py
# Masukkan: journal-lists/scimago_split/subject_area_Computer_Science.json
# Pilih: Q1,Q2
# Copy output set ISSN

# 4. Tempel ke openalex_fetch.py, lalu jalankan
python openalex_fetch.py

# 5. Bersihkan duplikat
python clear_duplicate.py

# Hasil akhir: openalex_results_hierarchy.json
```

## Struktur Direktori

```
find_references_scopus/
├── get_issn_electronic.py
├── openalex_fetch.py
├── clear_duplicate.py
├── journal-lists/
│   ├── scimagojr_2025.json
│   └── scimago_split/
│       ├── subject_area_Computer_Science.json
│       └── ...
├── venv/
└── README.md
```

## Catatan Penting

- **API Key**: OpenAlex tidak memerlukan API key untuk penggunaan dasar, namun untuk volume besar disarankan menambahkan `mailto` atau `api_key` di header. Bisa ditambahkan di `requests.get(..., headers={'User-Agent': 'mailto:email@domain.com'})`.
- **Rate Limit**: Script sudah menyertakan `time.sleep(REQUEST_DELAY)` untuk menghormati batas 10 request per detik. Jangan kurangi delay jika tidak perlu.
- **Biaya**: Parameter `search` dikenakan biaya $1 per 1000 request (vs $0.1 untuk filter biasa). Namun dengan batching dan filter ISSN, jumlah request tetap terkendali.
- **DOI sebagai identifier**: Duplikasi dideteksi berdasarkan DOI. Artikel tanpa DOI akan diabaikan dalam proses pembersihan.

## Troubleshooting

- **`ImportError: No module named requests`** → jalankan `pip install requests`
- **URL too long** → kurangi `ISSN_BATCH_SIZE` (misal jadi 30)
- **Tidak ada hasil** → periksa apakah ISSN yang digunakan benar dan rentang tahun menghasilkan data. Coba perbesar tahun atau gunakan `semua` kuartil.
- **File JSON tidak ditemukan** → pastikan path file benar dan Anda berada di direktori yang tepat.

Dengan mengikuti panduan di atas, Anda dapat mengambil artikel dari ribuan jurnal terindeks SCImargo, memfilternya dengan kata kunci, dan mendapatkan dataset tanpa duplikasi lintas kelompok. Selamat mencoba!
