# Panduan Lengkap: Fetch & Filter Artikel dari OpenAlex

Repository ini berisi enam script Python untuk mengambil artikel ilmiah dari API OpenAlex berdasarkan daftar ISSN (dari SCImago), memfilter dengan kata kunci di judul/abstrak, menghapus DOI tertentu, dan melihat distribusi akhir.

## Daftar Script

| Script | Fungsi |
|--------|--------|
| `get_issn_electronic.py` | Ekstrak daftar ISSN dari file JSON SCImago berdasarkan kuartil |
| `openalex_fetch.py` | Mengambil artikel dari OpenAlex per kelompok query |
| `filter_keywords_abstrac.py` | Filter lanjutan berdasarkan judul+abstrak dengan query boolean |
| `clear_duplicate.py` | Hapus artikel berdasarkan daftar DOI, buang kategori kosong |
| `remove_doi_list.py` | Versi sederhana clear_duplicate (hanya hapus DOI) |
| `cek_distribusi_artikel.py` | Lihat jumlah artikel per kategori |

## Prasyarat

```bash
# Python 3.8+
git clone git@github.com:farisalfatih/find_references_scopus.git
cd find_references_scopus
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install requests
```

---

## 1. Ekstrak ISSN dari SCImago (`get_issn_electronic.py`)

Script ini membaca file JSON hasil SCImago (bisa dari `journal-lists/scimagojr_2025.json` atau file per bidang di `journal-lists/scimago_split/`).

**Cara menjalankan:**

```bash
python get_issn_electronic.py
```

**Input yang diminta:**
- Path file JSON → contoh: `journal-lists/scimago_split/subject_area_Computer_Science.json`
- Pilihan quartile → `semua`, `Q1`, `Q2`, `Q3`, `Q4` (bisa kombinasi, misal `Q1,Q2`)

**Output:** Set ISSN Python, contoh:
```
{"2157-846X", "2365-9440", "2666-920X", ...}
```
**Simpan output ini** (copy) untuk digunakan di `openalex_fetch.py`.

---

## 2. Fetch Artikel dari OpenAlex (`openalex_fetch.py`)

### 2.1 Konfigurasi Dasar

Buka `openalex_fetch.py` dan atur variabel berikut:

| Variabel | Deskripsi | Contoh |
|----------|-----------|--------|
| `ISSN_ELECTRONIC` | Set ISSN dari langkah 1 | `{"2157-846X", ...}` |
| `YEAR_FROM`, `YEAR_TO` | Rentang tahun publikasi | `2021`, `2026` |
| `LANGUAGE` | Filter bahasa (ISO 639-1) | `["en"]` atau `[]` untuk semua |
| `OUTPUT_FILE` | Nama file output | `"openalex_results.json"` |
| `PER_PAGE` | Maks hasil per halaman (max 200) | `200` |
| `REQUEST_DELAY` | Jeda antar request (detik) | `1.0` |
| `MAX_RESULTS` | Batas maks per kelompok (0 = tak terbatas) | `0` |
| `ISSN_BATCH_SIZE` | Jumlah ISSN per request (max ~200) | `50` |

### 2.2 Mendefinisikan Kelompok Pencarian (`SEARCH_GROUPS`)

Struktur `SEARCH_GROUPS` adalah dictionary dengan format:

```python
SEARCH_GROUPS = {
    "Nama Kelompok": {
        "query": "string query OpenAlex search syntax"
    },
    ...
}
```

**Syntax Query OpenAlex** (dokumentasi: https://docs.openalex.org/api/get-lists-of-works/search-works)

- Gunakan `AND`, `OR`, tanda kurung `( )`, dan kutip `"` untuk frasa eksak.
- Contoh:
  - `"machine learning" AND "cryptocurrency"`
  - `(Bitcoin OR Ethereum) AND "price prediction"`
  - `("LSTM" OR "GRU") AND "XGBoost" AND (MACD OR RSI)`

**Contoh SEARCH_GROUPS yang sudah disediakan:**

```python
SEARCH_GROUPS = {
    "XGBoost Cryptocurrency": {
        "query": '(Cryptocurrency OR Solana OR Bitcoin OR ETH OR XRP) AND "XGBoost"'
    },
    "HMM XGBoost": {
        "query": '("Hidden Markov Model" OR HMM) AND "XGBoost"'
    },
    "HMM Cryptocurrency": {
        "query": '("Hidden Markov Model" OR HMM) AND (Cryptocurrency OR Solana OR Bitcoin OR ETH OR XRP)'
    },
    "XGBoost Technical Indicators": {
        "query": '"XGBoost" AND (MACD OR RSI OR ADX OR Stochastic OR CCI OR ATR OR "Bollinger Bands" OR Ichimoku OR OBV OR MFI)'
    },
    "XGBoost Sharpe Sortino Profit Factor": {
        "query": '("Sharpe ratio" OR "Sortino ratio" OR "profit factor") AND "XGBoost"'
    },
}
```

### 2.3 Menjalankan Fetch

```bash
python openalex_fetch.py
```

Proses akan:
- Melakukan request ke API OpenAlex dengan filter ISSN dan query search.
- Menggabungkan hasil per kelompok.
- Menyimpan ke file JSON (contoh struktur di bawah).

**Output JSON (`openalex_results.json`):**

```json
{
  "XGBoost Cryptocurrency": [
    {
      "doi": "10.1016/j.eswa.2022.117497",
      "title": "Bitcoin price prediction using XGBoost...",
      "abstract": "This study applies XGBoost to forecast Bitcoin...",
      "authors": ["John Doe", "Jane Smith"],
      "year": 2022,
      "pub_date": "2022-03-15",
      "volume": "45",
      "issue": "2",
      "first_page": "100",
      "last_page": "115",
      "publisher": "Elsevier",
      "journal": "Expert Systems with Applications",
      "issn_electronic": "2157-846X",
      "open_access": "No"
    },
    ...
  ],
  "HMM XGBoost": [...]
}
```

---

## 3. Filter Lanjutan Berdasarkan Judul+Abstrak (`filter_keywords_abstrac.py`)

Script ini menerapkan filter **setelah fetch** menggunakan logika boolean yang sama seperti `SEARCH_GROUPS` tetapi diterapkan pada teks `title + abstract` (karena API OpenAlex hanya mencari di seluruh metadata, tidak spesifik di title/abstract). Ini berguna untuk menyaring lebih ketat.

### 3.1 Konfigurasi

Di dalam `filter_keywords_abstrac.py`, variabel `SEARCH_GROUPS` didefinisikan dengan format yang **sama persis** seperti di `openalex_fetch.py`. Pastikan query-nya sesuai dengan kebutuhan filter Anda.

**Contoh query yang bisa digunakan:**

| Tujuan | Contoh Query |
|--------|--------------|
| Frasa eksak | `"machine learning"` |
| Kombinasi AND | `LSTM AND bitcoin AND volatility` |
| Kombinasi OR | `(LSTM OR GRU OR RNN) AND (bitcoin OR ethereum)` |

### 3.2 Cara Kerja

- Untuk setiap artikel, script menggabungkan `title` dan `abstract`.
- Mengevaluasi apakah teks tersebut memenuhi query (case-insensitive).
- Artikel yang tidak memenuhi akan dihapus dari kelompoknya.

### 3.3 Menjalankan

```bash
python filter_keywords_abstrac.py
```

**Input:** `openalex_results.json` (default)  
**Output:** `openalex_results_filtered.json`

---

## 4. Pembersihan: Hapus DOI Tertentu & Buang Kategori Kosong

### Opsi A: Menggunakan `clear_duplicate.py` (direkomendasikan)

Script ini membaca `excluded_dois.txt` (satu DOI per baris, tanpa `https://doi.org/`) dan menghapus artikel yang DOI-nya tercantum. Kategori yang menjadi kosong akan dihapus dari output.

**Persiapan:**

```bash
# Buat file excluded_dois.txt
nano excluded_dois.txt
# Isi dengan DOI, contoh:
10.1016/j.eswa.2022.117497
10.1109/TKDE.2021.3078515
```

**Rename file hasil filter agar sesuai dengan yang dibaca script:**

```bash
cp openalex_results_filtered.json openalex_results_deduplicated.json
```

**Jalankan:**

```bash
python clear_duplicate.py
```

**Output:** `cleaned_results.json`

### Opsi B: Menggunakan `remove_doi_list.py` (lebih sederhana)

Script ini hanya menghapus DOI tanpa menghapus kategori kosong. Cara pakai sama:

```bash
cp openalex_results_filtered.json openalex_results_deduplicated.json
python remove_doi_list.py
```

---

## 5. Cek Distribusi Akhir (`cek_distribusi_artikel.py`)

Menampilkan jumlah artikel per kategori dan total keseluruhan.

```bash
python cek_distribusi_artikel.py
```

**Contoh output:**

```
Distribusi jumlah artikel per kategori:

XGBoost Cryptocurrency: 45 artikel
HMM XGBoost: 12 artikel
HMM Cryptocurrency: 8 artikel
XGBoost Technical Indicators: 23 artikel
XGBoost Sharpe Sortino Profit Factor: 5 artikel

Total semua artikel: 93
```

---

## Alur Lengkap (Copy-Paste Commands)

```bash
# 1. Ekstrak ISSN
python get_issn_electronic.py
# -> copy output set ISSN

# 2. Tempel ISSN ke openalex_fetch.py, lalu jalankan
python openalex_fetch.py

# 3. Filter dengan keyword di abstract (sesuaikan query di dalam script jika perlu)
python filter_keywords_abstrac.py

# 4. Rename untuk input pembersihan
cp openalex_results_filtered.json openalex_results_deduplicated.json

# 5. Buat daftar DOI yang ingin dikecualikan (opsional)
echo "10.1016/j.eswa.2022.117497" > excluded_dois.txt
echo "10.1109/TKDE.2021.3078515" >> excluded_dois.txt

# 6. Hapus DOI dan bersihkan kategori kosong
python clear_duplicate.py

# 7. Lihat distribusi
python cek_distribusi_artikel.py
```

---

## Penjelasan Query Boolean untuk `SEARCH_GROUPS`

### Aturan Dasar

| Simbol | Arti | Contoh |
|--------|------|--------|
| `AND` | Kedua sisi harus ada | `LSTM AND bitcoin` |
| `OR` | Salah satu sisi ada | `(LSTM OR GRU)` |
| `" "` | Frasa eksak (spasi dianggap satu kesatuan) | `"hidden markov model"` |
| `( )` | Mengelompokkan | `(bitcoin OR ethereum) AND lstm` |

### Contoh Query Umum

**1. Mencari topik dengan dua kata kunci wajib:**
```
"machine learning" AND cryptocurrency
```

**2. Mencari salah satu dari beberapa model:**
```
(LSTM OR GRU OR Transformer) AND "price prediction"
```

**3. Kombinasi kompleks:**
```
("technical analysis" OR "trading strategy") AND (Sharpe OR "Sortino ratio") AND XGBoost
```

**4. Mencari frasa dengan AND di dalamnya (gunakan kutip):**
```
"profit factor" AND "walk forward"
```

### Catatan Penting

- **Case-insensitive:** `xGBoost` sama dengan `XGBoost`.
- **Tidak ada wildcard** (seperti `*`). Harus kata utuh.
- **Tidak ada negasi** (NOT). Jika perlu eksklusi, lakukan pasca-filter secara manual.
- **Setiap query akan diterapkan pada hasil fetch yang sudah dibatasi oleh ISSN dan tahun.** Gunakan query yang lebih spesifik jika ingin hasil lebih sedikit.

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `ImportError: No module named 'requests'` | `pip install requests` |
| `URL too long` error | Kurangi `ISSN_BATCH_SIZE` (misal 30) |
| Tidak ada hasil dari API | Periksa:
  - Apakah ISSN valid? Coba dengan satu ISSN dulu.
  - Apakah tahun publikasi terlalu sempit? Ubah `YEAR_FROM` ke 2015.
  - Apakah query terlalu spesifik? Gunakan kata kunci yang lebih umum.
| `FileNotFoundError: openalex_results_deduplicated.json` | Jalankan `cp openalex_results_filtered.json openalex_results_deduplicated.json` |
| `excluded_dois.txt` tidak ditemukan | Buat file kosong: `touch excluded_dois.txt` atau hapus baris di script yang membaca file tersebut. |
| Hasil filter kosong semua | Query di `filter_keywords_abstrac.py` terlalu ketat. Coba gunakan query yang lebih longgar atau hapus filter. |

---

## Kesimpulan

Dengan mengikuti panduan ini, Anda dapat:
1. Mengambil artikel dari ribuan jurnal terindeks SCImago.
2. Memfilter berdasarkan topik tertentu menggunakan query boolean.
3. Membersihkan hasil dari artikel yang tidak diinginkan (berdasarkan DOI).
4. Melihat statistik distribusi akhir.

Selamat mencoba!
