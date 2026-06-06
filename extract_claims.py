import re
import json
import sys
import os
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters

doi_pattern = r'10\.\d{4,9}/[-._;()/:A-Z0-9]+'

CUSTOM_ABBREVIATIONS = [
    'al', 'vs', 'etc', 'eg', 'ie', 'cf', 'approx', 'dept', 'ed', 'vol',
    'no', 'pp', 'fig', 'eq', 'dr', 'prof', 'inc', 'ltd',
    'dkk', 'dll', 'dsb', 'dst', 'sda', 'yb', 'nrb', 'hp', 'jl', 'rt', 'rw',
]

punkt_params = PunktParameters()
punkt_params.abbrev_types = set(CUSTOM_ABBREVIATIONS)
tokenizer = PunktSentenceTokenizer(punkt_params)




def extract_sentences_with_doi(text):
    # Hapus baris markdown heading (# , ## , ### , dst)
    text = re.sub(r'^#{1,6}\s+.*$', '', text, flags=re.MULTILINE)
    # Hapus baris yang cuma numbering heading (misal "1.1 Latar Belakang" di baris sendiri)
    text = re.sub(r'^\d+(\.\d+)*\s+[A-Z][^\n]*$', '', text, flags=re.MULTILINE)

    # Split per paragraf dulu, biar beda paragraf nggak nyatu jadi 1 kalimat
    paragraphs = re.split(r'\n\s*\n', text)
    results = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = tokenizer.tokenize(para)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            doi_list = re.findall(doi_pattern, sent, flags=re.IGNORECASE)
            if doi_list:
                results.append({
                    'sentence': sent,
                    'dois': doi_list,
                })
    return results


def run(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()

    hasil = extract_sentences_with_doi(text)

    # Kumpulkan semua DOI unik dari seluruh kalimat
    all_dois = []
    seen = set()
    for item in hasil:
        for doi in item['dois']:
            if doi.lower() not in seen:
                seen.add(doi.lower())
                all_dois.append(doi)

    output = {
        'results': hasil,
        'doi_list': all_dois,
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f'Tersimpan: {output_file}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python script.py <input.md> <output.json>')
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.isfile(input_file):
        print(f'Error: File "{input_file}" tidak ditemukan.')
        sys.exit(1)

    run(input_file, output_file)
