import json
import re

def normalize_name(name: str) -> str:
    if not name:
        return ""
    if name.isupper():
        parts = re.split(r'([-\s]+)', name)
        normalized_parts = []
        for part in parts:
            if part and part[0].isalpha():
                normalized_parts.append(part.capitalize())
            else:
                normalized_parts.append(part)
        return ''.join(normalized_parts)
    return name

def extract_last_name(full_name: str) -> str:
    """Extract last name from a full name string and normalize it."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    last = parts[-1]
    last = last.rstrip(',.')
    return normalize_name(last)

def format_authors(authors_list):
    if not authors_list:
        return "Unknown"
    last_names = [extract_last_name(author) for author in authors_list]
    if len(last_names) == 1:
        return last_names[0]
    elif len(last_names) == 2:
        return f"{last_names[0]} and {last_names[1]}"
    else:
        return f"{last_names[0]} et al."

def main(json_file_path):
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for category, papers in data.items():
        for paper in papers:
            doi = paper.get('doi', 'No DOI')
            authors = paper.get('authors', [])
            abstract = paper.get('abstract', 'No abstract')
            
            formatted_authors = format_authors(authors)
            
            print(f"# {doi}")
            print(f"## {formatted_authors}")
            print(f"### {abstract}")
            print()

if __name__ == "__main__":
    json_file = "final_references.json"
    main(json_file)
