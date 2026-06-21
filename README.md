# Find References Scopus

Pipeline Python + panduan prompt AI untuk **membantu pembuatan artikel jurnal dari nol sampai selesai**. Pipeline ini mengambil artikel dari OpenAlex (berbasis ISSN SCImago), lalu Anda memakai outputnya sebagai bahan referensi untuk menulis latar belakang, metode, hasil, diskusi, dan kesimpulan dengan bantuan AI.

Hasil akhir: **Markdown dengan citation `[DOI]`** yang siap dipakai di LaTeX/Word, plus file `.bib` untuk BibTeX.

---

## Daftar Isi

- [Filosofi Project](#filosofi-project)
- [Instalasi](#instalasi)
- [Tahap-Tahap Pipeline](#tahap-tahap-pipeline)
- [Prompt AI untuk Pembuatan Artikel](#prompt-ai-untuk-pembuatan-artikel)
  - [A. Jika Bingung Mau Topik Apa](#a-jika-bingung-mau-topik-apa)
  - [B. Memilih Jurnal yang Relevan](#b-memilih-jurnal-yang-relevan)
  - [C. Mencari Referensi Pendukung](#c-mencari-referensi-pendukung)
  - [D. Menulis Latar Belakang dengan [DOI]](#d-menulis-latar-belakang-dengan-doi)
  - [E. Menulis Metode](#e-menulis-metode)
  - [F. Menulis Hasil & Analisis](#f-menulis-hasil--analisis)
  - [G. Menulis Diskusi](#g-menulis-diskusi)
  - [H. Menulis Kesimpulan](#h-menulis-kesimpulan)
  - [I. Jika Sudah Punya Code Penelitian](#i-jika-sudah-punya-code-penelitian)
  - [J. Verifikasi Klaim [DOI]](#j-verifikasi-klaim-doi)
  - [K. Finalisasi & Export ke BibTeX](#k-finalisasi--export-ke-bibtex)
- [Daftar Command CLI](#daftar-command-cli)
- [Konfigurasi (config.yaml)](#konfigurasi-configyaml)
- [Struktur Folder](#struktur-folder)
- [Detail Setiap Step Pipeline](#detail-setiap-step-pipeline)
- [Migrasi dari Versi Lama](#migrasi-dari-versi-lama)

---

## Filosofi Project

Project ini **bukan pipeline otomatis end-to-end**. Ada banyak keputusan riset yang hanya bisa diambil oleh peneliti:

1. **Quartile mana** yang dipakai untuk filter jurnal? (Q1? Q1+Q2? semua?)
2. **DOI mana** yang harus di-exclude karena tidak relevan meski match keyword?
3. **Topik** apa yang mau diteliti?
4. **Jurnal** mana yang mau dituju?
5. **Klaim** mana yang benar-benar didukung referensi?

Pipeline hanya mengotomasi bagian mekanis (fetch, filter, deduplikasi). Sisanya — brainstorming, menulis, verifikasi — dilakukan peneliti dengan bantuan AI memakai prompt-prompt yang sudah disediakan di README ini.

### Output Akhir yang Diharapkan

```
data/
├── draft.md                  ← Artikel lengkap dengan citation [DOI]
├── 11_references.bib         ← File BibTeX untuk LaTeX
├── 09_references.md          ← Daftar referensi ringkas (DOI, author, abstrak)
└── 08_claims.json            ← Audit: setiap kalimat dengan [DOI] diekstrak
```

Format `draft.md`:
```markdown
## Latar Belakang

Pasar cryptocurrency bersifat sangat volatile dengan fluktuasi harga yang
sulit diprediksi [10.3390/fintech4040077]. XGBoost telah menunjukkan performa
unggul dalam prediksi time-series keuangan [10.1007/s10614-025-10919-y]...
```

**Format citation**: HARUS pakai `[DOI]` (literal DOI di dalam kurung siku), BUKAN `\cite{}` atau `(Author, 2024)`. Alasannya: step 08 (`extract-claims`) memakai regex `10\.\d{4,9}/...` untuk ekstrak DOI dari markdown — format `[DOI]` paling reliable untuk diparse otomatis.

**Konversi `[DOI]` → `\cite{key}`**: Tidak ada auto-convert di pipeline ini. Setelah Anda jalankan step 11 (`convert-bib`), file `.bib` berisi `@article{lastnameYYYY_abcde, ...}` akan ter-generate. Anda harus manual replace `[DOI]` di `draft.md` dengan `\cite{lastnameYYYY_abcde}` (atau pakai tool terpisah / regex find-replace di editor).

---

## Instalasi

### 1. Clone repository

```bash
git clone https://github.com/farisalfatih/find_references_scopus.git
cd find_references_scopus
```

### 2. Buat virtual environment (opsional)

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
source .venv/Scripts/activate # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install sebagai package (opsional)

```bash
pip install -e .
```

### Dependencies

- `requests` — HTTP client untuk OpenAlex API
- `nltk` — Tokenizer kalimat (untuk ekstrak klaim DOI)
- `pyyaml` — Parser config.yaml

---

## Tahap-Tahap Pipeline

Jalankan `find-refs guide` untuk lihat panduan singkat di terminal. Berikut penjelasan lengkap setiap tahap:

### TAHAP 0 — Persiapan Data SCImago (sekali saja)

```bash
find-refs csv-to-json
find-refs delete-no-issn
find-refs split-subject   # opsional
```
**Output**: `data/scimagojr_2025.json` + `data/scimagojr_2025_ok.json`

### TAHAP 1 — Pilih ISSN berdasarkan Quartile + Subject Area [MANUAL]

Putuskan:
1. **Subject area mana** yang mau dipakai? (mis. Computer Science saja, atau gabungan beberapa area)
2. **Quartile mana** yang mau dipakai? (mis. Q1+Q2 untuk jurnal top-tier)

```bash
# Lihat daftar subject area tersedia (27 area, masing-masing punya nomor)
find-refs get-issn --subject list

# Mode default: SCImago full (semua subject area)
find-refs get-issn -q Q1,Q2         # Q1+Q2 dari semua area
find-refs get-issn                  # semua quartile

# Mode subject area: pilih area spesifik
find-refs get-issn --subject 7              # Computer Science saja, semua quartile
find-refs get-issn --subject 7,8 -q Q1      # Computer Science + Decision Sciences, Q1
find-refs get-issn --subject Computer -q Q1,Q2  # semua area yg namanya ada "Computer"
find-refs get-issn --subject "Computer Science,Mathematics" -q Q1   # multi-name

# atau mode interaktif (prompt quartile via input()):
find-refs get-issn -i
```
**Output**: `data/01_issn_list.txt`

### TAHAP 2 — Fetch Artikel OpenAlex + Filter + Deduplikasi

```bash
find-refs fetch        # ambil artikel dari OpenAlex API (bisa lama)
find-refs filter       # filter berdasar keyword di judul+abstrak
find-refs deduplicate  # hapus DOI duplikat antar group
```
**Output**: `data/04_deduplicated.json`

### TAHAP 3 — REVIEW MANUAL: Tentukan DOI Exclude [MANUAL]

Buka `data/04_deduplicated.json`. Baca abstrak tiap artikel. Identifikasi DOI yang **tidak relevan** meski match keyword (false positive filter).

Tulis DOI tersebut ke `data/excluded_dois.txt` (satu per baris). Boleh kosong kalau tidak ada.

### TAHAP 4 — Hapus Exclude + Statistik + Merge Info Jurnal

```bash
find-refs remove-excluded
find-refs distribution
find-refs merge-journal
```
**Output**: `data/07_with_journal_info.json` ← **dataset final dengan quartile & open_access**

### TAHAP 5 — TULIS ARTIKEL dengan Bantuan AI [MANUAL]

Gunakan AI (ChatGPT/Gemini/Claude/dll) untuk menulis latar belakang, metode, hasil, diskusi, kesimpulan. Berikan `data/07_with_journal_info.json` sebagai konteks. Minta AI menyisipkan `[DOI]` di setiap klaim.

**Lihat bagian [Prompt AI untuk Pembuatan Artikel](#prompt-ai-untuk-pembuatan-artikel)** untuk kumpulan prompt siap pakai.

**Output**: `data/draft.md`

### TAHAP 6 — Verifikasi Klaim [DOI]

```bash
find-refs extract-claims --input data/draft.md
```
**Output**: `data/08_claims.json` — list kalimat yang mengandung [DOI] + DOI unik

**Regex DOI yang dipakai**: `10\.\d{4,9}/...` (registrant code 4-9 digit, suffix alfanumerik). DOI otomatis di:
- **Lowercase-normalize** (DOI case-insensitive per spesifikasi Crossref)
- **Strip trailing punctuation** (titik, koma, titik koma, kurung) agar tidak bocor dari akhir kalimat

Review: apakah setiap klaim di draf benar-benar didukung artikel yang DOI-nya di-claim? Hapus/ubah klaim yang tidak cocok.

### TAHAP 7 — PILIH DOI untuk Cite di Paper [MANUAL opsional]

Tentukan DOI mana yang akan Anda cite di paper akhir (subset dari 07). Edit `config.yaml`, isi `selected_dois`. Lalu:

```bash
find-refs select-articles
```
**Output**: `data/10_selected.json`

### TAHAP 8 — Export ke Markdown & BibTeX

```bash
find-refs extract-references       # Markdown ringkas semua artikel
find-refs convert-bib              # BibTeX dari SEMUA artikel (step 07)
# ATAU pakai subset (step 10):
find-refs convert-bib --input data/10_selected.json
```
**Output**: `data/09_references.md` + `data/11_references.bib`

---

## Prompt AI untuk Pembuatan Artikel

Berikut kumpulan prompt siap pakai untuk AI assistant (ChatGPT, Gemini, Claude, GLM, dll). Copy-paste dan sesuaikan bagian dalam `[...]` dengan konteks Anda.

### A. Jika Bingung Mau Topik Apa

**Prompt eksplorasi topik**:
```
Saya ingin menulis artikel jurnal tapi belum punya topik pasti. Background saya:
- Bidang: [mis. machine learning / finance / kesehatan / pendidikan]
- Tool yang saya kuasai: [mis. Python, XGBoost, PyTorch, R]
- Minat khusus: [mis. cryptocurrency, NLP, computer vision, time-series]

Bantu saya:
1. Beri 10 ide topik penelitian yang feasible untuk jurnal Q1/Q2 (bukan topik
   yang sudah terlalu jenuh).
2. Untuk setiap topik, jelaskan: novelty-nya apa, mengapa penting, apa
   gap penelitian yang bisa di-isi, dan tool/toolchain yang cocok.
3. Untuk topik yang menurut Anda paling promising, beri 5 keyword pencarian
   yang bisa saya pakai di OpenAlex/Google Scholar.

Format jawaban: tabel markdown dengan kolom (Topik, Novelty, Gap, Keyword).
```

**Prompt validasi topik**:
```
Saya sedang mempertimbangkan topik penelitian: "[topik Anda]".

Bantu evaluasi:
1. Apakah topik ini sudah terlalu jenuh? Cek berapa banyak paper serupa
   dalam 3 tahun terakhir (estimasi berdasarkan keyword).
2. Apa angle yang bisa membuat topik ini jadi novel? Beri 3 saran angle.
3. Jurnal Q1/Q2 apa yang cocok untuk topik ini? Sebutkan 3 jurnal + ISSN.
4. Apa risiko utama saat eksekusi topik ini (data, method, dll.)?
```

---

### B. Memilih Jurnal yang Relevan

**Prompt pencarian jurnal**:
```
Saya menulis artikel dengan topik: "[topik Anda]".
Method utama: [mis. XGBoost + HMM untuk prediksi harga cryptocurrency].

Saya punya akses ke dataset SCImago 2025 (file JSON berisi 32,000+ jurnal
dengan field: journal, issn_print, issn_electronic, quartile, open_access,
subject_area, sub_category).

Bantu saya:
1. Tentukan subject_area SCImago yang paling cocok untuk topik saya
   (mis. Computer Science, Decision Sciences, Economics Econometrics and Finance).
2. Beri kriteria filter jurnal yang harus dipakai:
   - Quartile minimum: [Q1/Q2/Q3/Q4]
   - Open access: [Yes/No/Diamond/semua]
   - Subject area prioritas: [uraian]
3. Saya akan memakai pipeline find_references_scopus untuk filter jurnal.
   Beri query boolean OpenAlex untuk search_groups di config.yaml.

PENTING — Aturan query (parser recursive-descent, DIDUKUNG):
- "quoted phrase" untuk frasa literal (mis. "XGBoost", "Hidden Markov Model")
- (a OR b OR c) untuk alternatif
- X AND Y untuk wajib keduanya
- X AND NOT Y untuk exclude (mis. "XGBoost" AND NOT survey)
- Nested parens DIDUKUNG: ((A OR B) AND C) OR D
- Word-boundary match: "eth" TIDAK match "method"/"version"

Format output:
  "Group Name 1":
    query: '(keyword1 OR keyword2) AND "phrase"'
  "Group Name 2":
    query: '...'

Buat 3-5 group query yang mencakup aspek berbeda dari topik saya.
JANGAN fabricate ISSN — saya akan ambil ISSN dari SCImago via step 01
(find-refs get-issn), bukan dari output AI.
```

**Prompt validasi jurnal tujuan**:
```
Saya mau submit ke jurnal: [nama jurnal + ISSN].

Bantu analisis:
1. Apakah scope jurnal ini cocok dengan topik saya? (cek di description jurnal)
2. Quartile jurnal ini apa? (SJR/Scopus)
3. Berapa biasanya waktu review & publication?
4. Apakah jurnal ini open access atau berbayar? Berapa APC-nya?
5. Beri 3 contoh artikel di jurnal ini (5 tahun terakhir) yang mirip topik
   saya — untuk saya jadikan referensi struktur penulisan.
```

---

### C. Mencari Referensi Pendukung

**Prompt setelah dataset didapat** (setelah TAHAP 4):

```
Saya punya dataset artikel hasil filter (file JSON 07_with_journal_info.json)
dengan struktur:
{
  "kategori_1": [
    {
      "doi": "...", "title": "...", "abstract": "...",
      "authors": [...], "year": ..., "journal": "...",
      "quartile": "Q1/Q2/...", "open_access": "Yes/No/Diamond OA"
    },
    ...
  ],
  "kategori_2": [...]
}

Tugas: bantu saya identifikasi referensi yang paling relevan untuk topik
saya: "[topik]". Method yang saya pakai: [uraian singkat method].

Untuk setiap kategori, beri:
1. Top 5 artikel yang PALING relevan (dengan alasan singkat 1 kalimat).
2. 1-2 artikel yang harus jadi referensi UTAMA (karena paling foundational).
3. 1-2 artikel yang harus di-cite karena CONTRASTING view (membandingkan).

Format output: tabel markdown dengan kolom (DOI, Title, Year, Why-relevant,
Role: main/supporting/contrast).

JANGAN gunakan artikel di luar dataset yang saya berikan.
```

---

### D. Menulis Latar Belakang dengan [DOI]

**Prompt menulis latar belakang** (paling penting!):

```
Bantu saya menulis bagian "Latar Belakang" untuk artikel jurnal dengan
topik: "[topik Anda]".

Konteks artikel:
- Method yang diajukan: [uraian singkat, mis. "XGBoost + HMM untuk prediksi
  harga cryptocurrency dengan dynamic labeling berbasis ATR"]
- Kontribusi utama: [3 bullet point novelty]
- Target jurnal: [nama jurnal, quartile]

Dataset referensi yang TERSEDIA (boleh di-cite, beri [DOI] di akhir kalimat
yang merujuk):
[copy-paste bagian dari 07_with_journal_info.json yang sudah Anda kurasi,
 atau attach file dan minta AI baca]

Aturan penulisan:
1. Setiap klaim faktual HARUS diakhiri dengan [DOI] sumbernya.
   Format WAJIB: kurung siku + DOI literal, contoh:
   "Pasar cryptocurrency memiliki volatilitas 5x lebih tinggi dari
   saham [10.3390/fintech4040077]."

2. PENTING — Format DOI yang benar:
   - Pakai literal DOI: 10.xxxx/yyyy (registrant 4-9 digit)
   - JANGAN pakai placeholder seperti [DOI-A] atau [DOI-B] — ganti dengan
     DOI aktual dari dataset di atas
   - JANGAN pakai \cite{} atau (Author, 2024) — HANYA [DOI]
   - Letakkan DOI di AKHIR kalimat sebelum tanda baca akhir
     (titik/koma), supaya regex step 08 bisa ekstrak dengan bersih
   - Contoh BENAR: "...5x lebih tinggi [10.3390/fintech4040077]."
   - Contoh SALAH: "...5x lebih tinggi. [10.3390/fintech4040077]"
     (titik sebelum bracket akan menyebabkan DOI ter-ekstrak dengan titik)

3. Jika ada kontradiksi antar referensi, sebutkan keduanya:
   "Studi A menemukan X [DOI-A], namun studi B menemukan Y [DOI-B]."
   (Ganti [DOI-A] dan [DOI-B] dengan DOI aktual dari dataset)

4. JANGAN cite artikel di luar dataset di atas.

5. Struktur latar belakang (4-5 paragraf):
   - Paragraf 1: konteks luas topik + kenapa penting
   - Paragraf 2: state-of-the-art saat ini (cite 3-5 paper foundational)
   - Paragraf 3: gap penelitian yang belum di-isi
   - Paragraf 4: kontribusi paper ini (3 bullet point)
   - Paragraf 5: struktur paper (opsional)
6. Panjang: 600-800 kata.
7. Bahasa: [Indonesia/English].

Output: tulis langsung dalam format Markdown, siap di-paste ke draf.
```

**Tips**:
- Jika dataset terlalu besar untuk di-paste, pecah per kategori dan minta AI tulis latar belakang bertahap per topik.
- Selalu minta `[DOI]` di akhir kalimat — jangan `\cite{}` atau `(Author, Year)` karena pipeline extract-claims (TAHAP 6) hanya mengenali pola `10.xxxx/yyyy` (literal DOI).
- Setelah AI generate, jalankan `find-refs extract-claims --input data/draft.md` untuk verifikasi semua DOI yang di-claim benar-benar ada di dataset (TAHAP 6).

---

### E. Menulis Metode

```
Bantu saya menulis bagian "Metode" untuk artikel yang sama.

Method yang saya pakai:
- Algoritma: [mis. XGBoost untuk klasifikasi, HMM untuk state detection]
- Data: [sumber, periode, fitur]
- Evaluasi: [metric, mis. Sharpe ratio, Sortino ratio, profit factor, accuracy]
- Train/test split: [walk-forward / k-fold / chronological]

Struktur yang diminta:
1. Overview Method (1 paragraf)
2. Data Preparation (1-2 paragraf, cite sumber data dengan [DOI])
3. Feature Engineering (1-2 paragraf, cite teknik yang dipakai dengan [DOI])
4. Model Architecture (2-3 paragraf, cite algoritma asli dengan [DOI])
5. Evaluation Metrics (1 paragraf, definisi setiap metric + [DOI])
6. Backtesting Strategy (1 paragraf, cite metode backtest dengan [DOI])

Aturan:
- Setiap definisi/saya pakai rumus → cite sumber aslinya dengan [DOI].
- Format rumus pakai LaTeX inline: $\text{Sharpe} = \frac{\mu}{\sigma}$.
- Bahasa: [Indonesia/English].
- Panjang: 800-1200 kata.
```

---

### F. Menulis Hasil & Analisis

```
Bantu saya menulis bagian "Hasil dan Analisis".

Hasil eksperimen saya (rangkuman, sisipkan angka Anda):
- Model A (baseline): Sharpe = X, Sortino = Y, Profit Factor = Z
- Model B (proposed): Sharpe = X', Sortino = Y', Profit Factor = Z'
- Improvement: [persentase]
- Statistical test: [t-test/Mann-Whitney, p-value]

Struktur yang diminta:
1. Overview Hasil (1 paragraf, sebutkan temuan utama)
2. Performance Comparison (1-2 paragraf + 1 tabel markdown)
3. Ablation Study (1 paragraf, kontribusi tiap komponen method)
4. Analysis: kenapa model proposed lebih baik (2-3 paragraf,
   cite 2-3 referensi yang mendukung interpretasi Anda dengan [DOI])
5. Limitations (1 paragraf, sebutkan keterbatasan dengan jujur)

Aturan:
- Jangan over-claim. Pakai kata "menunjukkan" bukan "membuktikan".
- Bandingkan dengan hasil paper lain jika ada (cite [DOI]).
- Bahasa: [Indonesia/English].
- Panjang: 600-900 kata.
```

---

### G. Menulis Diskusi

```
Bantu saya menulis bagian "Diskusi".

Hasil utama paper saya: [1 kalimat temuan utama].
Method yang dipakai: [uraian singkat].

Struktur yang diminta:
1. Interpretasi hasil dalam konteks literatur (2-3 paragraf)
   - Bandingkan dengan 3-5 paper terkait (cite [DOI])
   - Kenapa hasil saya konsisten/berbeda dengan mereka?
2. Implikasi praktis (1-2 paragraf)
   - Untuk praktisi: apa manfaat method ini?
   - Untuk regulator: apa pertimbangan policy?
3. Implikasi teoretis (1 paragraf)
   - Apa kontribusi terhadap body of knowledge?
4. Future research (1 paragraf, 3-4 bullet point)

Aturan:
- Jangan ulangi Hasil — fokus pada "kenapa" dan "apa implikasinya".
- Cite minimal 5 referensi dari dataset.
- Bahasa: [Indonesia/English].
- Panjang: 700-1000 kata.
```

---

### H. Menulis Kesimpulan

```
Bantu saya menulis "Kesimpulan" (1 paragraf, 200-300 kata).

Konteks:
- Topik: [topik]
- Kontribusi utama: [3 bullet]
- Hasil utama: [1 kalimat dengan angka]

Struktur:
1. Restate problem (1 kalimat)
2. Restate method (1 kalimat)
3. Sebutkan 3 temuan utama (3 kalimat, dengan angka)
4. Implikasi praktis (1 kalimat)
5. Future work (1 kalimat)

JANGAN cite [DOI] di kesimpulan.
JANGAN perkenalkan ide baru.

Catatan: Walaupun step 08 (extract-claims) akan tetap mengekstrak DOI
dari section manapun di draft.md (termasuk kesimpulan), best practice
akademik adalah TIDAK cite di kesimpulan. Kalau AI tetap menambahkan
[DOI], hapus manual saat review.
```

---

### I. Jika Sudah Punya Code Penelitian

**Prompt translate code → artikel**:

```
Saya sudah punya code penelitian lengkap (Python). Saya ingin menulis
artikel jurnal dari code ini.

Code saya: [paste code, atau attach file]

Bantu saya:
1. Ekstrak struktur penelitian dari code:
   - Apa problem yang dipecahkan?
   - Apa method yang dipakai?
   - Apa dataset?
   - Apa metric evaluasi?
   - Apa hasil utama (dari output code)?
2. Identifikasi novelty-nya (apa yang baru dari code ini).
3. Beri saran topik & judul artikel (5 alternatif).
4. Beri saran 3-5 jurnal target (Q1/Q2) yang cocok.
5. Beri outline artikel (section + sub-section + perkiraan panjang tiap section).
6. Beri 5 keyword pencarian untuk cari referensi pendukung di OpenAlex.

Setelah ini saya akan:
- Pakai outline yang Anda buat untuk generate search_groups di config.yaml
  (ikuti sintaks di README bagian "Sintaks Query Boolean")
- Jalankan pipeline find_references_scopus untuk fetch referensi
- Pakai prompt "Menulis Latar Belakang dengan [DOI]" dengan dataset hasil

Catatan: Output prompt ini (outline, search_groups, keyword) TIDAK otomatis
ter-parse oleh pipeline. Anda harus copy-paste manual ke config.yaml.
```

**Prompt menulis method dari code**:

```
Bantu saya menulis bagian "Metode" berdasarkan code Python saya berikut.

Code: [paste code lengkap]

Tulis metode dalam format paper akademik:
1. Jangan translate code baris-per-baris. Abstraksikan jadi konsep.
2. Sebutkan library/version yang dipakai (mis. "XGBoost 1.7.6 [DOI-XGBoost-paper]").
3. Sebutkan hyperparameter penting (yang Anda pakai default vs yang di-tune).
4. Untuk setiap teknik yang dipakai, cite paper aslinya dengan [DOI].
   (Saya akan supply dataset referensi terpisah.)
5. Sertakan pseudo-code untuk algoritma utama (format LaTeX algorithm2e).

Bahasa: [Indonesia/English]. Panjang: 800-1200 kata.
```

**Prompt menulis hasil dari output eksperimen**:

```
Saya sudah jalankan eksperimen. Output log/CSV:

[paste output: mis. classification_report, sharpe ratio, equity curve summary, dst]

Bantu saya:
1. Rangkum hasil dalam tabel markdown (perbandingan model).
2. Identifikasi temuan utama (3 bullet point).
3. Sebutkan anomali/insight menarik yang perlu di-discuss.
4. Apa perlu uji statistik lanjutan? (sebutkan test apa + library Python)
5. Draft 1 paragraf "Overview Hasil" untuk paper.

JANGAN fabricate angka. Hanya pakai yang ada di output saya.
```

---

### J. Verifikasi Klaim [DOI]

Setelah Anda selesai menulis `draft.md` (TAHAP 5), jalankan:

```bash
find-refs extract-claims --input data/draft.md
```

Output `data/08_claims.json` berisi semua kalimat yang mengandung [DOI] + list DOI unik. Lalu pakai prompt ini di AI:

**Prompt verifikasi klaim**:
```
Saya punya daftar klaim dari draft artikel saya (format JSON):
{
  "results": [
    {"sentence": "...kalimat dengan [DOI]...", "dois": ["10.xxxx/yyyy"]},
    ...
  ],
  "doi_list": ["10.xxxx/yyyy", ...]
}

Dan saya punya dataset artikel (07_with_journal_info.json) dengan struktur:
{kategori: [{doi, title, abstract, ...}, ...]}

Tugas: untuk SETIAP klaim di draft, cek apakah klaim tersebut BENAR-BENAR
didukung oleh artikel yang di-claim (cek abstract/title artikel).

Output: tabel markdown dengan kolom:
| Klaim | DOI di-claim | Relevan? (Yes/Partial/No) | Catatan |

Jika ada klaim "No" atau "Partial", beri saran:
- Ganti DOI yang lebih cocok (dari dataset), ATAU
- Hapus klaim tersebut, ATAU
- Lemahklaim klaim (mis. dari "menunjukkan" jadi "mungkin menunjukkan")

Jangan fabricate DOI baru di luar dataset.
```

---

### K. Finalisasi & Export ke BibTeX

**Prompt finalisasi struktur artikel**:

```
Saya sudah punya draft artikel (file markdown) dengan struktur:
1. Latar Belakang
2. Metode
3. Hasil & Analisis
4. Diskusi
5. Kesimpulan

Draft: [paste atau attach]

Bantu saya:
1. Cek konsistensi istilah (mis. "model" vs "sistem" vs "framework" — pilih satu).
2. Cek flow antar section (apakah transisi mulus?).
3. Cek apakah ada klaim di Diskusi yang TIDAK didukung Hasil.
4. Beri saran judul akhir (5 alternatif, max 15 kata).
5. Beri 5 keyword untuk abstract.
6. Tulis abstract (200-250 kata) berdasarkan draft.

Bahasa: [Indonesia/English].
```

**Setelah final**, convert ke BibTeX:
```bash
find-refs convert-bib --input data/07_with_journal_info.json
# Output: data/11_references.bib (untuk LaTeX \bibliography{references})
```

Atau pakai subset DOI yang Anda cite di paper:
```bash
# Edit config.yaml, isi selected_dois dengan DOI yang benar-benar di-cite
find-refs select-articles
find-refs convert-bib --input data/10_selected.json
```

---

## Daftar Command CLI

Setelah `pip install -e .`:

```bash
find-refs list            # lihat semua command
find-refs guide           # panduan tahap-tahap pipeline
find-refs <command> -h    # bantuan command tertentu
```

### Pipeline Commands (11 step)

| # | Command | Type | Deskripsi |
|---|---------|------|-----------|
| 01 | `get-issn` | MANUAL | Ekstrak ISSN electronic dari SCImago per quartile + subject area |
| 02 | `fetch` | AUTO | Fetch artikel OpenAlex per search group |
| 03 | `filter` | AUTO | Filter keyword di judul+abstrak |
| 04 | `deduplicate` | AUTO | Hapus DOI duplikat antar group |
| 05 | `remove-excluded` | MANUAL | Hapus DOI yang ada di `excluded_dois.txt` |
| 06 | `distribution` | AUTO | Statistik artikel per kategori |
| 07 | `merge-journal` | AUTO | Tambah quartile & open_access dari SCImago |
| 08 | `extract-claims` | MANUAL | Ekstrak kalimat berisi [DOI] dari Markdown |
| 09 | `extract-references` | AUTO | Format artikel jadi Markdown ringkas |
| 10 | `select-articles` | MANUAL | Pilih subset artikel berdasar DOI |
| 11 | `convert-bib` | AUTO | Konversi JSON ke BibTeX |

### Utility Commands (preprocessing SCImago)

| Command | Deskripsi |
|---------|-----------|
| `csv-to-json` | Konversi SCImago CSV → JSON |
| `check-issn` | Audit kelengkapan ISSN print/electronic |
| `delete-no-issn` | Hapus jurnal tanpa ISSN electronic |
| `split-subject` | Pecah JSON per subject area |

### Special Commands

| Command | Deskripsi |
|---------|-----------|
| `list` | Tampilkan daftar command dengan tag AUTO/MANUAL |
| `guide` | Tampilkan panduan tahap-tahap pipeline + checkpoint |

---

## Konfigurasi (config.yaml)

Semua parameter terpusat di `config.yaml`. Edit file ini, **tidak perlu sentuh kode Python**.

```yaml
# Parameter umum fetch OpenAlex
year_from: 2021
year_to: 2026
language: ["en"]
per_page: 200
request_delay: 1.0
max_results_per_group: 0    # 0 = tanpa batas
issn_batch_size: 50

# Daftar ISSN electronic (kosongkan jika pakai output step 01)
issn_electronic: []

# Search groups — SATU sumber kebenaran
search_groups:
  "XGBoost Cryptocurrency":
    query: '(Cryptocurrency OR Solana OR Bitcoin OR ETH OR XRP) AND "XGBoost"'
  "HMM XGBoost":
    query: '("Hidden Markov Model" OR HMM) AND "XGBoost"'
  # ... tambah group sesuai kebutuhan

# DOI yang ingin dipilih di step 10
selected_dois: []

# Path file input/output (relatif terhadap root project)
paths:
  scimago_csv: "data/scimagojr_2025.csv"
  scimago_json: "data/scimagojr_2025.json"
  excluded_dois: "data/excluded_dois.txt"
  step_01_issn_list: "data/01_issn_list.txt"
  # ... dst
```

### Sintaks Query Boolean

Query di `search_groups` didukung oleh parser recursive-descent (sejak v1.1) dengan sintaks lengkap:

- `"quoted phrase"` — pencocokan substring literal (case-insensitive)
- `word` — pencocokan **word-boundary** (mis. `eth` TIDAK match `method`/`version`/`ethical`)
- `(a OR b OR c)` — salah satu harus ada
- `X AND Y` — keduanya harus ada
- `X AND NOT Y` — X harus ada, Y tidak boleh ada
- `((a OR b) AND c) OR d` — **nested parentheses didukung penuh**
- `"phrase with AND inside"` — AND/OR di dalam quote dianggap **literal**, tidak di-parse

**Validasi otomatis**: Jika query tidak valid (paren tidak seimbang, quote tidak tertutup, dll), step 03 akan log error dan skip group tersebut (artikel disalin apa adanya).

**Contoh query valid**:
```
("Hidden Markov Model" OR HMM) AND "XGBoost"
```
```
(Cryptocurrency OR Solana OR Bitcoin OR ETH OR XRP) AND "XGBoost" AND NOT "survey"
```
```
(("Sharpe ratio" OR "Sortino ratio") AND XGBoost) OR ("profit factor" AND LSTM)
```

**Limitasi**: Tidak ada wildcard (`*`), tidak ada regex, tidak ada proximity search (`~`). Untuk kebutuhan tersebut, gunakan search API OpenAlex langsung.

---

## Struktur Folder

```
find_references_scopus/
├── pyproject.toml
├── requirements.txt
├── config.yaml                 # Konfigurasi terpusat
├── README.md                   # Dokumentasi ini
├── data/                       # Semua file data
│   ├── scimagojr_2025.csv      # Sumber SCImago
│   ├── scimagojr_2025.json     # Konversi JSON
│   ├── excluded_dois.txt       # Daftar DOI exclude (manual)
│   ├── draft.md                # Draf artikel Anda (manual, dengan [DOI])
│   ├── 01_issn_list.txt        # Output step 01
│   ├── 02_openalex_raw.json    # Output step 02
│   ├── ...
│   └── 11_references.bib       # Output final untuk LaTeX
├── docs/
│   └── flowchart.svg           # Diagram alur
└── find_references_scopus/     # Package Python
    ├── __init__.py
    ├── __main__.py             # python -m find_references_scopus
    ├── cli.py                  # CLI dispatcher
    ├── config.py               # Loader config.yaml
    ├── utils.py                # Utility bersama
    ├── pipeline/               # 11 step
    │   ├── step_01_get_issn.py
    │   ├── ...
    │   └── step_11_convert_bib.py
    └── journal_lists/          # 4 utility SCImago
        ├── csv_to_json.py
        ├── check_issn.py
        ├── delete_no_issn.py
        └── split_by_subject_area.py
```

---

## Detail Setiap Step Pipeline

### Step 01 — get-issn

**Tujuan**: Ekstrak ISSN electronic dari SCImago, bisa per quartile dan/atau per subject area.

**Mode sumber data**:
1. **SCImago full** (default) — pakai `data/scimagojr_2025.json`
2. **Subject area pilihan** — pakai file di `data/scimago_split/subject_area_*.json` (hasil dari `find-refs split-subject`)

**Cara pakai**:
```bash
# Mode default: SCImago full
find-refs get-issn -q Q1,Q2         # Q1+Q2 dari semua subject area
find-refs get-issn                  # semua quartile
find-refs get-issn -i               # interaktif (prompt quartile)

# Mode subject area: lihat daftar dulu
find-refs get-issn --subject list   # tampilkan 27 subject area + nomor

# Pilih subject area berdasarkan nomor
find-refs get-issn --subject 7               # Computer Science saja
find-refs get-issn --subject 7,8             # Computer Science + Decision Sciences
find-refs get-issn --subject 7,8 -q Q1       # + filter Q1

# Pilih subject area berdasarkan nama/keyword (case-insensitive)
find-refs get-issn --subject Computer        # semua area yg namanya ada "Computer"
find-refs get-issn --subject "Computer Science,Mathematics"  # multi-name

# Gabung semua subject area (sama dengan SCImago full)
find-refs get-issn --subject all -q Q1,Q2
```

**Input**: `data/scimagojr_2025.json` (mode default) ATAU `data/scimago_split/subject_area_*.json` (mode subject)
**Output**: `data/01_issn_list.txt` (satu ISSN per baris)

**Catatan**: Subject area yang dipilih akan otomatis di-dedup (jurnal yang muncul di multiple subject area hanya dihitung sekali).

### Step 02 — fetch
```bash
find-refs fetch                 # pakai ISSN dari config atau output step 01
find-refs fetch --issn-file path/ke/issn.txt
```
**Input**: config.yaml (search_groups + ISSN)
**Output**: `data/02_openalex_raw.json`
**Catatan**: Proses bisa lama (menit-jam). OpenAlex rate limit ~100 req/menit.

### Step 03 — filter
```bash
find-refs filter
find-refs filter -i input.json -o output.json
```
**Input**: `02_openalex_raw.json`
**Output**: `03_filtered.json`

### Step 04 — deduplicate
```bash
find-refs deduplicate
```
**Input**: `03_filtered.json`
**Output**: `04_deduplicated.json`
**Algoritma**: Pindahkan DOI duplikat ke group yang paling spesifik (subset query).

### Step 05 — remove-excluded
```bash
find-refs remove-excluded
find-refs remove-excluded -e custom_excluded.txt
```
**Input**: `04_deduplicated.json` + `excluded_dois.txt`
**Output**: `05_cleaned.json`

### Step 06 — distribution
```bash
find-refs distribution
```
**Input**: `05_cleaned.json`
**Output**: `06_distribution.txt`

### Step 07 — merge-journal
```bash
find-refs merge-journal
```
**Input**: `05_cleaned.json` + `scimagojr_2025.json`
**Output**: `07_with_journal_info.json` ← **dataset final**

### Step 08 — extract-claims
```bash
find-refs extract-claims --input data/draft.md
```
**Input**: file Markdown (draft artikel Anda)
**Output**: `08_claims.json` (`{results: [{sentence, dois}], doi_list: [...]}`)
**Catatan**: Perlu package `nltk`.

### Step 09 — extract-references
```bash
find-refs extract-references
```
**Input**: `07_with_journal_info.json`
**Output**: `09_references.md` — format:
```markdown
# Kategori: XGBoost Cryptocurrency

Total: 25 artikel

---

## 10.1007/s44163-025-00519-y
**2024 | Journal of Finance**
### Smith et al.

Abstract text here...

---
```
Catatan: struktur per kategori → `## DOI` → `### Author` → abstract.

### Step 10 — select-articles
```bash
find-refs select-articles              # pakai selected_dois dari config
find-refs select-articles --dois-file dois.txt
```
**Input**: `07_with_journal_info.json` + `config.selected_dois`
**Output**: `10_selected.json`

### Step 11 — convert-bib
```bash
find-refs convert-bib                                      # dari step 07
find-refs convert-bib --input data/10_selected.json        # dari subset step 10
```
**Output**: `11_references.bib` (entry `@article{...}` valid untuk LaTeX)

---

## Migrasi dari Versi Lama

| Script Lama | Command Baru |
|-------------|--------------|
| `get_issn_electronic.py` | `find-refs get-issn` |
| `openalex_fetch.py` | `find-refs fetch` |
| `filter_keywords_abstrac.py` | `find-refs filter` |
| `clear_duplicate.py` | `find-refs deduplicate` |
| `remove_doi_list.py` | `find-refs remove-excluded` |
| `cek_distribusi_artikel.py` | `find-refs distribution` |
| `marge_article_journal.py` | `find-refs merge-journal` |
| `extract_claims.py` | `find-refs extract-claims` |
| `extract_references.py` | `find-refs extract-references` |
| `selected_article.py` | `find-refs select-articles` |
| `confert_bib.py` | `find-refs convert-bib` |
| `journal-lists/csv_to_json.py` | `find-refs csv-to-json` |
| `journal-lists/cek_issn.py` | `find-refs check-issn` |
| `journal-lists/delete_no_issn.py` | `find-refs delete-no-issn` |
| `journal-lists/split_by_subject_area.py` | `find-refs split-subject` |

### Mapping Output File Lama → Baru

| Output Lama | Output Baru |
|-------------|-------------|
| `openalex_results.json` | `data/02_openalex_raw.json` |
| `openalex_results_filtered.json` | `data/03_filtered.json` |
| `openalex_results_deduplicated.json` | `data/04_deduplicated.json` |
| `cleaned_results.json` | `data/05_cleaned.json` |
| `final_references.json` | `data/07_with_journal_info.json` |
| `selected_papers.json` | `data/10_selected.json` |
| `references.bib` | `data/11_references.bib` |

### Bug Fix Penting

Versi lama `confert_bib.py` menulis `## article{...}` (dengan prefix `## `) yang **merusak parser BibTeX/LaTeX**. Versi baru menulis `@article{...}` yang valid.

### Apa yang Perlu Dilakukan Setelah Migrasi

1. Copy `scimagojr_2025.csv`, `scimagojr_2025.json`, `excluded_dois.txt` ke folder `data/`
2. Edit `config.yaml`:
   - Isi `selected_dois` dengan 27 DOI yang sebelumnya hard-coded (lihat di bawah)
   - Sesuaikan `search_groups` jika perlu (default sudah memuat semua group lama)
3. Jalankan `find-refs guide` untuk lihat tahapan
4. Mulai dari TAHAP 0 (preprocess SCImago)

### Daftar 27 DOI (sebelumnya hard-coded di selected_article.py)

**Copy daftar ini ke `selected_dois` di `config.yaml`** jika Anda mau pakai 27 DOI yang sama dengan versi lama:

```yaml
selected_dois:
  - "10.1007/s44163-025-00519-y"
  - "10.1007/s10614-025-10919-y"
  - "10.3390/s22051740"
  - "10.7717/peerj-cs.2626"
  - "10.11591/ijeecs.v37.i3.pp1964-1975"
  - "10.11591/ijeecs.v39.i3.pp1745-1754"
  - "10.1109/access.2025.3556881"
  - "10.1155/int/6674437"
  - "10.3390/math11112415"
  - "10.28991/hij-2024-05-04-013"
  - "10.28991/hij-2025-06-01-017"
  - "10.3390/math11061335"
  - "10.2478/cait-2023-0020"
  - "10.3390/math11051132"
  - "10.1109/access.2021.3088999"
  - "10.1109/access.2023.3318478"
  - "10.3390/forecast8030040"
  - "10.3390/a19020101"
  - "10.1109/access.2024.3516490"
  - "10.3390/fintech4040077"
  - "10.1016/j.eswa.2025.127729"
  - "10.3905/jfds.2026.1.217"
  - "10.3390/math13233889"
  - "10.1007/s10614-026-11338-3"
  - "10.3390/electronics15061334"
  - "10.1007/s42521-024-00123-2"
  - "10.3390/math13101577"
```

Catatan: DOI lookup di step 10 sudah **case-insensitive** (sejak v1.1), jadi Anda boleh tulis dengan huruf besar/kecil campuran tanpa masalah.

---

## License

MIT — bebas dipakai untuk keperluan akademik.
