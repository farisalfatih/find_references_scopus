# Panduan Lengkap: Fetch & Filter Artikel dari OpenAlex

Repository ini berisi sebelas script Python dan tiga panduan prompt AI untuk mengambil artikel ilmiah dari API OpenAlex berdasarkan daftar ISSN (dari SCImago), memfilter dengan kata kunci di judul/abstrak, menyaring artikel secara semantik dengan AI, menghapus DOI tertentu, melihat distribusi akhir, menulis latar belakang penelitian dengan AI, menambah informasi quartile & open access, mengekstrak klaim DOI dari markdown, memendekkan data referensi, memverifikasi klaim latar belakang dengan AI, memilih artikel berdasarkan DOI, serta mengonversi JSON ke format BibTeX.

## Daftar Script

| Script | Fungsi |
|--------|--------|
| `get_issn_electronic.py` | Ekstrak daftar ISSN dari file JSON SCImago berdasarkan kuartil |
| `openalex_fetch.py` | Mengambil artikel dari OpenAlex per kelompok query |
| `filter_keywords_abstrac.py` | Filter lanjutan berdasarkan judul+abstrak dengan query boolean |
| `clear_duplicate.py` | Hapus artikel berdasarkan daftar DOI, buang kategori kosong |
| `remove_doi_list.py` | Versi sederhana clear_duplicate (hanya hapus DOI) |
| `cek_distribusi_artikel.py` | Lihat jumlah artikel per kategori |
| `marge_article_journal.py` | Menambahkan informasi quartile dan open access ke JSON artikel |
| `extract_claims.py` | Ekstrak kalimat berisi DOI dari file Markdown untuk verifikasi klaim |
| `extract_references.py` | Mengambil hanya DOI, author, dan abstract untuk memperpendek teks |
| `selected_article.py` | Mengambil hanya artikel yang diinginkan berdasarkan daftar DOI |
| `confert_bib.py` | Mengubah JSON menjadi file .bib untuk keperluan referensi di LaTeX |
| **Prompt Filter** (bukan script) | Filter semantik dengan AI — menyaring artikel yang tidak sesuai kritis prediksi finance |
| **Prompt Latar Belakang** (bukan script) | Menulis latar belakang penelitian dengan AI berdasarkan data referensi JSON |
| **Prompt Verifikasi** (bukan script) | Memverifikasi kebenaran klaim dalam latar belakang terhadap abstract asli |

## Prasyarat

```bash
# Python 3.8+
git clone git@github.com:farisalfatih/find_references_scopus.git
cd find_references_scopus
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install requests nltk
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

## 4. Filter Semantik dengan AI (Prompt Filter)

Langkah ini **bukan script Python**, melainkan prompt yang diberikan ke AI (LLM) untuk membaca setiap abstract secara mendalam dan menentukan apakah artikel benar-benar sesuai dengan kriteria penelitian. Filter keyword boolean di langkah 3 hanya mencocokkan keberadaan kata tertentu, tetapi tidak memahami konteks. Prompt filter ini mengatasi kelemahan tersebut dengan meminta AI memahami makna abstract secara keseluruhan.

**Mengapa langkah ini penting?** Hasil fetch dan filter keyword sering kali masih mengandung artikel yang secara teknis mengandung kata kunci tetapi tidak sesuai secara substansi. Misalnya, artikel yang menggunakan XGBoost untuk klasifikasi sentimen (bukan prediksi harga) tetap lolos filter keyword "XGBoost" dan "Cryptocurrency". Prompt filter ini menyaring artikel tersebut secara semantik.

**Cara penggunaan:**

1. Jalankan `extract_references.py` terlebih dahulu untuk memperpendek teks (hanya DOI, author, abstract), sehingga token yang dikirim ke AI lebih sedikit dan lebih hemat.
   ```bash
   python extract_references.py > references_summary.txt
   ```
2. Salin output ke AI (ChatGPT, Claude, dll) bersama prompt berikut.
3. AI akan mengembalikan daftar DOI yang **tidak sesuai** kriteria.
4. Salin daftar DOI tersebut ke `excluded_dois.txt` untuk langkah 5 (pembersihan).

**Prompt Filter:**

```
Buatkan saya list doi dalam 1 block code yang tidak sesuai dengan kriteria journal yang saya cari yang mana tentang prediksi finence entah itu clasifikasi atau (HARUS PREDIKSI ARAH HARGA FINEANCENYA), regresi baca setiap abstrack secara mendalam
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

**Kriteria yang digunakan AI untuk menyaring:**
- Artikel **harus** tentang prediksi finance (klasifikasi arah harga atau regresi harga).
- Artikel yang hanya menggunakan metode ML untuk analisis sentimen, deteksi anomaly, portofolio optimasi, clustering, dll — **tidak sesuai** dan DOI-nya akan dimasukkan ke daftar.
- AI membaca setiap abstract secara mendalam, bukan sekadar mencocokkan keyword.

**Hasil yang diharapkan:** AI mengembalikan block code berisi daftar DOI yang tidak sesuai, siap disalin ke `excluded_dois.txt`.

---

## 5. Pembersihan: Hapus DOI Tertentu & Buang Kategori Kosong

### Opsi A: Menggunakan `clear_duplicate.py` (direkomendasikan)

Script ini membaca `excluded_dois.txt` (satu DOI per baris, tanpa `https://doi.org/`) — yang bisa diisi dari hasil Prompt Filter langkah 4 — dan menghapus artikel yang DOI-nya tercantum. Kategori yang menjadi kosong akan dihapus dari output.

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

## 6. Cek Distribusi Akhir (`cek_distribusi_artikel.py`)

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

## 7. Penulisan Latar Belakang dengan AI (Prompt Latar Belakang)

Langkah ini **bukan script Python**, melainkan prompt yang diberikan ke AI (LLM) untuk menulis **latar belakang penelitian** secara otomatis berdasarkan data referensi JSON yang sudah dikumpulkan. Prompt ini dirancang agar latar belakang yang dihasilkan memiliki struktur piramida terbalik (umum → spesifik), setiap klaim disertai sitasi DOI, dan diakhiri dengan research gap serta pertanyaan penelitian.

**Mengapa langkah ini penting?** Menulis latar belakang penelitian yang baik membutuhkan sintesis dari puluhan artikel, pencarian data evaluasi numerik (RMSE, MAE, akurasi, Sharpe ratio), dan perumusan gap penelitian — proses yang memakan waktu berjam-jam jika dilakukan manual. Dengan prompt ini, AI dapat mengolah seluruh data referensi sekaligus dan menghasilkan draf latar belakang yang terstruktur dalam hitungan menit.

**Prasyarat sebelum menggunakan prompt ini:**
- File JSON referensi sudah final (`final_references.json`), yaitu sudah melewati langkah 1-6 (fetch, filter, pembersihan, merge quartile).
- Jalankan `extract_references.py` terlebih dahulu untuk memperpendek teks sehingga token yang dikirim ke AI lebih hemat.
  ```bash
  python extract_references.py > references_summary.txt
  ```

**Cara penggunaan:**

1. Salin output `references_summary.txt` ke AI (ChatGPT, Claude, dll).
2. Salin juga kode Python eksperimen Anda (metode, data, fitur, target, horizon, metrik evaluasi).
3. Berikan prompt berikut.
4. Isi parameter `[isi bidang]` dan `[isi jumlah kata]` sesuai kebutuhan.
5. AI akan menghasilkan draf latar belakang penelitian yang terstruktur.

**Prompt Latar Belakang:**

```
Anda adalah asisten peneliti akademik. Tulis **latar belakang penelitian** dengan struktur piramida terbalik (umum → spesifik) berdasarkan data yang saya berikan.
## Aturan mutlak:
1. Setiap paragraf wajib memiliki minimal 1 sitasi DOI `[10.xxxx/xxxx]`.
2. Setiap klaim faktual (contoh: akurasi 92%, RMSE 67,18) harus disertai DOI dari file JSON.
3. Gunakan bahasa Indonesia akademik formal (baku, tanpa kata "saya", "kita").
4. Tulisan dalam bentuk **paragraf utuh mengalir**, bukan poin-poin.
5. Sertakan data evaluasi numerik dari penelitian terdahulu (RMSE, MAE, akurasi, Sharpe ratio, dll.).
6. Jangan mengarang informasi yang tidak ada dalam JSON/kode Python.
7. Akhiri dengan perumusan **research gap minimal 3 poin** dan **pertanyaan penelitian** (3-5 pertanyaan).

## Input dari saya:
- File JSON: daftar artikel dengan DOI, abstrak, dll.
- Kode Python: metode, data, fitur, target, horizon, metrik evaluasi.
- Bidang penelitian: [isi bidang, misal: Cryptocurrency]
- Panjang target: [isi jumlah kata, misal: 2000 kata]

## Contoh penggunaan untuk bidang lain:
Jika bidang = **Kesehatan (prediksi penyakit jantung)**, JSON berisi artikel tentang XGBoost, Random Forest, SVM dengan akurasi 92-95%. Kode Python menggunakan data rekam medis (usia, tekanan darah, kolesterol) dengan target klasifikasi biner (berisiko/tidak). Gap: belum ada yang menggunakan data longitudinal dan evaluasi clinical net benefit. Maka latar belakang akan: (a) tingginya angka kematian jantung, (b) keterbatasan model konvensional, (c) studi XGBoost dengan akurasi X%, (d) gap data longitudinal, (e) pertanyaan penelitian tentang pengaruh time-series features dan net benefit curve.

Mulai tulis setelah saya memberikan data.
```

**Struktur output yang dihasilkan AI:**
1. **Pembukaan umum** — konteks bidang penelitian (misal: perkembangan pasar cryptocurrency).
2. **Permasalahan** — tantangan yang dihadapi (volatilitas, ketidakpastian, dll).
3. **Studi terdahulu** — ringkasan metode dan hasil penelitian dari JSON, lengkap dengan data numerik dan sitasi DOI.
4. **Research gap** — minimal 3 poin kesenjangan yang belum diteliti.
5. **Pertanyaan penelitian** — 3-5 pertanyaan yang menjadi fokus penelitian.

**Tips untuk hasil optimal:**
- Semakin banyak data referensi yang diberikan, semakin kaya latar belakang yang dihasilkan.
- Sertakan kode Python eksperimen agar AI memahami konteks metode dan metrik yang digunakan.
- Jika hasil terlalu panjang/dpendek, sesuaikan parameter `Panjang target`.
- Setelah AI menghasilkan draf, gunakan `extract_claims.py` (langkah 9) untuk memverifikasi bahwa setiap DOI yang disitasi memang merujuk ke klaim yang benar.

---

## 8. Menambahkan Informasi Quartile & Open Access (`marge_article_journal.py`)

Script ini menggabungkan data artikel JSON dengan data jurnal (hasil SCImago) untuk menambahkan informasi **quartile** dan **open_access** ke setiap artikel. Dengan informasi tambahan ini, Anda dapat menilai kualitas jurnal dan aksesibilitas artikel secara langsung dari file JSON.

**Cara menjalankan:**

```bash
python marge_article_journal.py <articles_json> <journals_json>
```

**Parameter:**

| Parameter | Deskripsi | Contoh |
|-----------|-----------|--------|
| `articles_json` | Path file JSON berisi data artikel | `cleaned_results.json` |
| `journals_json` | Path file JSON berisi data jurnal SCImago | `journal-lists/scimagojr_2025.json` |

**Cara kerja:**
1. Membangun indeks jurnal berdasarkan `issn_electronic` dari file jurnal.
2. Untuk setiap artikel, mencocokkan `issn_electronic` dengan indeks jurnal.
3. Menambahkan field `quartile` dan `open_access` ke artikel yang cocok.
4. Artikel yang ISSN-nya tidak ditemukan di data jurnal akan mendapat nilai `null` untuk kedua field.

**Output:** `final_references.json`

**Contoh:**

```bash
python marge_article_journal.py cleaned_results.json journal-lists/scimagojr_2025.json
# Output: final_references.json
```

---

## 9. Ekstrak Klaim DOI dari Markdown (`extract_claims.py`)

Script ini mengekstrak kalimat-kalimat yang mengandung DOI dari file Markdown (`.md`), misalnya draf artikel atau skripsi. Tujuannya agar lebih mudah memverifikasi klaim (claim) yang dibuat dalam tulisan dengan jurnal rujukan aslinya. Output berupa daftar kalimat beserta DOI yang terkandung di dalamnya, serta daftar DOI unik yang bisa langsung digunakan oleh `selected_article.py`.

**Cara menjalankan:**

```bash
python extract_claims.py <input.md> <output.json>
```

**Parameter:**

| Parameter | Deskripsi | Contoh |
|-----------|-----------|--------|
| `input.md` | Path file Markdown yang berisi klaim dengan DOI | `draft_artikel.md` |
| `output.json` | Path file JSON output | `claims_extracted.json` |

**Cara kerja:**
1. Membaca teks dari file Markdown.
2. Menghapus baris heading (`#`, `##`, dll.) dan numbering heading.
3. Memecah teks menjadi paragraf, lalu memecah setiap paragraf menjadi kalimat menggunakan `nltk.PunktSentenceTokenizer`.
4. Mencari pola DOI (format `10.xxxx/...`) di setiap kalimat.
5. Kalimat yang mengandung DOI dikumpulkan beserta daftar DOI-nya.
6. Menghasilkan daftar DOI unik dari seluruh kalimat.

**Output JSON:**

```json
{
  "results": [
    {
      "sentence": "Metode ini menunjukkan akurasi 95% (10.1016/j.eswa.2022.117497).",
      "dois": ["10.1016/j.eswa.2022.117497"]
    }
  ],
  "doi_list": ["10.1016/j.eswa.2022.117497"]
}
```

**Catatan:** Field `doi_list` pada output dapat langsung disalin ke variabel `doi_list` di `selected_article.py` untuk mengambil artikel yang relevan.

**Dependensi tambahan:**

```bash
pip install nltk
```

---

## 10. Ringkas Data Referensi (`extract_references.py`)

Script ini mengambil hanya field **DOI**, **author**, dan **abstract** dari file JSON referensi, membuang field lainnya seperti title, journal, year, volume, dll. Tujuannya adalah memperpendek teks sehingga AI lebih mudah mengolahnya karena output token yang dihasilkan lebih sedikit, terutama saat menggunakan LLM untuk menganalisis atau meringkas referensi.

**Cara menjalankan:**

```bash
python extract_references.py
```

**Konfigurasi:**

Di dalam script, variabel `json_file` menentukan file input:

```python
json_file = "final_references.json"
```

Ubah sesuai kebutuhan jika file input Anda berbeda.

**Cara kerja:**
1. Membaca file JSON referensi (struktur: kategori → daftar paper).
2. Untuk setiap paper, mengekstrak hanya `doi`, `authors`, dan `abstract`.
3. Memformat nama author: jika 1 author → nama lengkap, 2 author → "A and B", lebih dari 2 → "A et al."
4. Mencetak hasil ke terminal (bukan file) dalam format:
   - `# <DOI>`
   - `## <formatted_authors>`
   - `### <abstract>`

**Catatan:** Script ini mencetak ke stdout. Jika ingin menyimpan ke file, gunakan redirect:

```bash
python extract_references.py > references_summary.txt
```

---

## 11. Verifikasi Klaim Latar Belakang dengan AI (Prompt Verifikasi)

Langkah ini **bukan script Python**, melainkan prompt yang diberikan ke AI (LLM) untuk memverifikasi bahwa setiap klaim dalam draf latar belakang penelitian (hasil langkah 7) benar-benar didukung oleh abstract artikel rujukannya. Prompt ini adalah langkah quality control yang memastikan tidak ada klaim yang keliru atau mengarang data (hallucination) dalam latar belakang.

**Mengapa langkah ini penting?** Meskipun Prompt Latar Belakang (langkah 7) sudah meminta AI untuk tidak mengarang informasi, LLM tetap bisa menghasilkan klaim yang tidak sepenuhnya akurat — misalnya mengutip akurasi 92% padahal abstract menyebutkan 89%, atau menyatakan sebuah studi menggunakan LSTM padahal sebenarnya menggunakan GRU. Prompt Verifikasi ini mengecek setiap klaim satu per satu terhadap abstract asli.

**Prasyarat sebelum menggunakan prompt ini:**
- Draf latar belakang sudah disimpan dalam format JSON sebagai `latar-belakang.json` (hasil dari langkah 7).
- File `selected_papers.json` sudah tersedia (hasil dari `selected_article.py` di langkah 12).
- Kedua file harus berada dalam sesi AI yang sama agar AI dapat membaca keduanya.

**Cara penggunaan:**

1. Pastikan AI sudah memiliki akses ke kedua file: `latar-belakang.json` dan `selected_papers.json`.
2. Berikan prompt berikut.
3. AI akan membaca setiap klaim, mencocokkan dengan abstract, dan menambahkan field `verification_klaim`.
4. Periksa hasil verifikasi — fokus pada item yang `sesuai: false`.
5. Untuk klaim yang tidak sesuai, perbaiki draf latar belakang sesuai saran AI.

**Prompt Verifikasi:**

```
Ambil semua **abstract** dan **DOI** serta **penulis** dari `selected_papers.json`.
Kemudian, tambahkan ke dalam `latar-belakang.json` sebuah field baru bernama `verification_klaim` dengan struktur berikut:

{
  "verification_klaim": [
    {
      "doi": "10.11591/ijeecs.v39.i3.pp1745-1754",
      "penulis": ["Nrusingha Tripathy", "Yugandhar Manchala", ...],
      "penggalan_kalimat": "penggalan kalimat dari abstract yang mendukung klaim terkait",
      "sesuai": true / false
    }
  ]
}

Lakukan langkah-langkah berikut:
1. Evaluasi apakah setiap klaim dalam `latar-belakang.json` **sesuai** dengan abstract yang diambil.
2. Jika ada klaim yang dinilai **tidak sesuai**, baca ulang abstract dari referensi tersebut, lalu pertimbangkan kembali apakah sebenarnya klaim tersebut sesuai atau tidak.
3. Jika ternyata sesuai setelah pertimbangan ulang, perbarui `penggalan_kalimat` dengan kutipan yang lebih tepat dari abstract.
4. Jika tetap tidak sesuai, biarkan `sesuai` bernilai `false` dan isi `penggalan_kalimat` dengan kutipan yang relevan (jika ada) atau biarkan kosong.
Setelah selesai, kirimkan kepada saya file `latar-belakang.json` yang sudah ditambahkan field `verification_klaim` sesuai format di atas.
```

**Struktur output yang dihasilkan AI:**

File `latar-belakang.json` yang sama, ditambah field baru `verification_klaim` berisi:
- `doi` — DOI artikel rujukan.
- `penulis` — daftar penulis artikel.
- `penggalan_kalimat` — kutipan dari abstract yang mendukung atau menyangkal klaim.
- `sesuai` — `true` jika klaim sesuai dengan abstract, `false` jika tidak.

**Contoh hasil verifikasi:**

```json
{
  "verification_klaim": [
    {
      "doi": "10.11591/ijeecs.v39.i3.pp1745-1754",
      "penulis": ["Nrusingha Tripathy", "Yugandhar Manchala"],
      "penggalan_kalimat": "The proposed XGBoost model achieved an accuracy of 92.3% for Bitcoin price direction prediction.",
      "sesuai": true
    },
    {
      "doi": "10.1016/j.eswa.2022.117497",
      "penulis": ["John Doe", "Jane Smith"],
      "penggalan_kalimat": "",
      "sesuai": false
    }
  ]
}
```

**Tindak lanjut setelah verifikasi:**
- Untuk klaim dengan `sesuai: false`, hapus atau perbaiki klaim tersebut di draf latar belakang.
- Untuk klaim dengan `sesuai: true` tapi `penggalan_kalimat` berbeda dari apa yang ditulis, sesuaikan wording klaim agar lebih akurat.
- Ulangi proses verifikasi jika melakukan perubahan signifikan pada draf.

---

## 12. Pilih Artikel Berdasarkan DOI (`selected_article.py`)

Script ini mengambil hanya artikel yang diinginkan dari file JSON referensi berdasarkan daftar DOI. Dapat dikombinasikan dengan hasil `doi_list` yang dihasilkan oleh `extract_claims.py` — sehingga Anda bisa mengekstrak hanya artikel yang dirujuk dalam draf tulisan Anda.

**Cara menjalankan:**

```bash
python selected_article.py [output_file] [--input input_file]
```

**Parameter:**

| Parameter | Deskripsi | Default |
|-----------|-----------|---------|
| `output_file` | Nama file JSON output | `selected_papers.json` |
| `--input`, `-i` | Path file JSON referensi input | `final_references.json` |

**Konfigurasi DOI:**

Di dalam script, variabel `doi_list` berisi daftar DOI yang ingin diambil:

```python
doi_list = [
    "10.1007/s44163-025-00519-y",
    "10.1007/s10614-025-10919-y",
    ...
]
```

Ubah daftar ini sesuai kebutuhan. Anda juga bisa menyalin daftar DOI dari field `doi_list` pada output `extract_claims.py`.

**Cara kerja:**
1. Membaca file JSON referensi dan membangun mapping DOI → paper.
2. Mencari setiap DOI dalam daftar.
3. Menyimpan paper yang ditemukan ke file output.
4. Menampilkan peringatan untuk DOI yang tidak ditemukan.
5. Mencetak ringkasan paper yang ditemukan ke terminal.

**Contoh:**

```bash
# Menggunakan default
python selected_article.py

# Menentukan file output dan input
python selected_article.py my_papers.json --input cleaned_results.json
```

**Output JSON:** Array berisi paper yang ditemukan:

```json
[
  {
    "doi": "10.1016/j.eswa.2022.117497",
    "title": "Bitcoin price prediction using XGBoost...",
    "authors": ["John Doe", "Jane Smith"],
    "abstract": "This study applies XGBoost...",
    ...
  }
]
```

---

## 13. Konversi JSON ke BibTeX (`confert_bib.py`)

Script ini mengubah file JSON referensi menjadi file BibTeX (`.bib`) untuk keperluan input referensi ke LaTeX atau manajer referensi seperti di Windows (Zotero, Mendeley, JabRef, dll). Semua field yang relevan (author, title, journal, year, volume, issue, pages, doi, publisher) akan dikonversi ke format BibTeX standar.

**Cara menjalankan:**

```bash
python confert_bib.py
```

**Konfigurasi:**

Di dalam script, variabel berikut menentukan file input dan output:

```python
input_json = "final_references.json"
output_bib = "references.bib"
```

Ubah sesuai kebutuhan jika file input/output Anda berbeda.

**Cara kerja:**
1. Membaca file JSON referensi (struktur: kategori → daftar paper).
2. Menggabungkan semua artikel dari berbagai kategori menjadi satu daftar.
3. Untuk setiap artikel, membuat entry `@article` dalam format BibTeX dengan field:
   - `author` — nama author digabung dengan "and"
   - `title`, `journal`, `year`, `month`
   - `volume`, `number` (issue), `pages`
   - `doi`, `publisher`
4. Citation key dihasilkan otomatis dari nama belakang author pertama + tahun + indeks (contoh: `Doe2022_0`).
5. Karakter khusus BibTeX (`&`, `%`, `$`, `_`, dll.) di-escape secara otomatis.
6. Field `abstract` sengaja tidak disertakan untuk menjaga file `.bib` tetap ringkas.

**Output:** `references.bib`

**Contoh output BibTeX:**

```bibtex
@article{Doe2022_0,
  author = {John Doe and Jane Smith},
  title = {Bitcoin price prediction using XGBoost},
  journal = {Expert Systems with Applications},
  year = {2022},
  month = mar,
  volume = {45},
  number = {2},
  pages = {100--115},
  doi = {10.1016/j.eswa.2022.117497},
  publisher = {Elsevier}
}
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

# 4. Filter semantik dengan AI (Prompt Filter)
# a. Ringkas referensi dulu agar token lebih hemat
python extract_references.py > references_summary.txt
# b. Salin output + prompt ke AI (lihat section 4 untuk prompt lengkapnya)
# c. Salin daftar DOI yang tidak sesuai ke excluded_dois.txt

# 5. Rename untuk input pembersihan
cp openalex_results_filtered.json openalex_results_deduplicated.json

# 6. Buat daftar DOI yang ingin dikecualikan (dari hasil Prompt Filter langkah 4)
echo "10.1016/j.eswa.2022.117497" > excluded_dois.txt
echo "10.1109/TKDE.2021.3078515" >> excluded_dois.txt

# 7. Hapus DOI dan bersihkan kategori kosong
python clear_duplicate.py

# 8. Lihat distribusi
python cek_distribusi_artikel.py

# 9. Tambahkan informasi quartile & open access
python marge_article_journal.py cleaned_results.json journal-lists/scimagojr_2025.json
# -> Output: final_references.json

# 10. Tulis latar belakang penelitian dengan AI (Prompt Latar Belakang)
# a. Ringkas referensi dulu agar token lebih hemat
python extract_references.py > references_summary.txt
# b. Salin output + kode Python + prompt ke AI (lihat section 7 untuk prompt lengkapnya)
# c. Isi parameter bidang dan panjang target
# d. AI menghasilkan draf latar belakang terstruktur

# 11. (Opsional) Ekstrak klaim DOI dari draf Markdown
python extract_claims.py draft_artikel.md claims_extracted.json
# -> Salin doi_list dari output ke selected_article.py

# 12. (Opsional) Pilih artikel berdasarkan DOI
# Salin doi_list dari extract_claims.py ke variabel doi_list di selected_article.py
python selected_article.py
# -> Output: selected_papers.json

# 13. Verifikasi klaim latar belakang dengan AI (Prompt Verifikasi)
# a. Siapkan latar-belakang.json (draf dari langkah 10) dan selected_papers.json (langkah 12)
# b. Berikan kedua file + prompt ke AI (lihat section 11 untuk prompt lengkapnya)
# c. AI menambahkan field verification_klaim ke latar-belakang.json
# d. Perbaiki klaim yang sesuai: false

# 14. (Opsional) Ringkas referensi untuk AI (hanya DOI, author, abstract)
python extract_references.py > references_summary.txt

# 15. Konversi ke BibTeX untuk referensi LaTeX / manajer referensi
python confert_bib.py
# -> Output: references.bib
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
3. Menyaring artikel secara semantik dengan AI menggunakan prompt filter yang membaca abstract secara mendalam.
4. Membersihkan hasil dari artikel yang tidak diinginkan (berdasarkan DOI dari hasil prompt filter).
5. Melihat statistik distribusi akhir.
6. Menulis latar belakang penelitian dengan AI secara otomatis berdasarkan data referensi.
7. Menambahkan informasi quartile dan open access ke data artikel.
8. Mengekstrak klaim DOI dari draf Markdown untuk verifikasi rujukan.
9. Memendekkan data referensi agar lebih efisien untuk diproses AI.
10. Memverifikasi kebenaran klaim dalam latar belakang terhadap abstract asli menggunakan AI.
11. Memilih artikel tertentu berdasarkan daftar DOI.
12. Mengonversi data referensi ke format BibTeX untuk keperluan LaTeX atau manajer referensi.

Selamat mencoba!
