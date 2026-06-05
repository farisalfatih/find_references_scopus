import json
import re
from datetime import datetime

def escape_bibtex(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = s.replace('\\', '\\\\')
    s = s.replace('{', '\\{')
    s = s.replace('}', '\\}')
    s = s.replace('&', '\\&')
    s = s.replace('%', '\\%')
    s = s.replace('$', '\\$')
    s = s.replace('#', '\\#')
    s = s.replace('_', '\\_')
    s = s.replace('^', '\\^{}')
    s = s.replace('~', '\\~{}')
    return s

def format_authors(authors_list):
    if not authors_list:
        return ""
    return " and ".join(authors_list)

def generate_citation_key(entry, index):
    authors = entry.get("authors", [])
    if authors:
        first_author = authors[0].strip()
        last_name = first_author.split()[-1] if " " in first_author else first_author
    else:
        last_name = "Unknown"
    year = entry.get("year", "")
    if not year and "pub_date" in entry:
        year = entry["pub_date"][:4]
    if not year:
        year = "nodate"
    last_name = re.sub(r'[^a-zA-Z]', '', last_name)
    return f"{last_name}{year}_{index}"

def convert_json_to_bib(json_file_path, bib_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = []
    for key, entry_list in data.items():
        if isinstance(entry_list, list):
            entries.extend(entry_list)

    bib_lines = []
    for idx, entry in enumerate(entries):
        title = entry.get("title", "").strip()
        if not title:
            continue

        authors = entry.get("authors", [])
        journal = entry.get("journal", "").strip()
        year = entry.get("year", "")
        pub_date = entry.get("pub_date", "")
        volume = entry.get("volume", "").strip()
        issue = entry.get("issue", "").strip()
        first_page = entry.get("first_page", "").strip()
        last_page = entry.get("last_page", "").strip()
        doi = entry.get("doi", "").strip()
        publisher = entry.get("publisher", "").strip()

        if not year and pub_date:
            year = pub_date[:4]

        month = ""
        if pub_date and len(pub_date) >= 7:
            month_num = pub_date[5:7]
            try:
                month = datetime(2000, int(month_num), 1).strftime("%b").lower()
            except:
                pass

        pages = ""
        if first_page and last_page and first_page != last_page:
            pages = f"{first_page}--{last_page}"
        elif first_page:
            pages = first_page

        cite_key = generate_citation_key(entry, idx)
        bib_lines.append(f"## article{{{cite_key},")

        if authors:
            auth_str = format_authors(authors)
            bib_lines.append(f"  author = {{{escape_bibtex(auth_str)}}},")

        bib_lines.append(f"  title = {{{escape_bibtex(title)}}},")

        if journal:
            bib_lines.append(f"  journal = {{{escape_bibtex(journal)}}},")

        if year:
            bib_lines.append(f"  year = {{{year}}},")
        else:
            bib_lines.append(f"  year = {{nodate}},")

        if month:
            bib_lines.append(f"  month = {month},")

        if volume:
            bib_lines.append(f"  volume = {{{volume}}},")

        if issue:
            bib_lines.append(f"  number = {{{issue}}},")

        if pages:
            bib_lines.append(f"  pages = {{{escape_bibtex(pages)}}},")

        if doi:
            bib_lines.append(f"  doi = {{{doi}}},")

        if publisher:
            bib_lines.append(f"  publisher = {{{escape_bibtex(publisher)}}},")

        # abstract intentionally omitted

        if bib_lines[-1].endswith(','):
            bib_lines[-1] = bib_lines[-1][:-1]
        bib_lines.append("}}")
        bib_lines.append("")

    with open(bib_file_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(bib_lines))

    print(f"Successfully converted {len(entries)} entries to {bib_file_path}")

if __name__ == "__main__":
    input_json = "final_references.json"
    output_bib = "references.bib"
    convert_json_to_bib(input_json, output_bib)
