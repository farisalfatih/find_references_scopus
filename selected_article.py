import json
import sys
import argparse
from typing import Dict, List

def load_references(json_path: str) -> Dict[str, Dict]:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    doi_to_paper = {}
    for category, papers in data.items():
        for paper in papers:
            doi = paper.get('doi')
            if doi:
                doi_to_paper[doi] = paper
    return doi_to_paper

def extract_papers_by_doi(doi_list: List[str], json_path: str) -> List[Dict]:
    doi_to_paper = load_references(json_path)
    results = []
    not_found = []
    
    for doi in doi_list:
        if doi in doi_to_paper:
            results.append(doi_to_paper[doi])
        else:
            not_found.append(doi)
    
    if not_found:
        print(f"Warning: {len(not_found)} DOI(s) not found in the JSON file:")
        for doi in not_found:
            print(f"  - {doi}")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract papers by DOI from JSON reference file.')
    parser.add_argument('output_file', nargs='?', default='selected_papers.json',
                        help='Output JSON file name (default: selected_papers.json)')
    parser.add_argument('--input', '-i', dest='input_file', default='final_references.json',
                        help='Input JSON reference file (default: final_references.json)')
    args = parser.parse_args()

    doi_list = [
        "10.1007/s44163-025-00519-y",
        "10.1007/s10614-025-10919-y",
        "10.3390/s22051740",
        "10.7717/peerj-cs.2626",
        "10.11591/ijeecs.v37.i3.pp1964-1975",
        "10.11591/ijeecs.v39.i3.pp1745-1754",
        "10.1109/access.2025.3556881",
        "10.1155/int/6674437",
        "10.3390/math11112415",
        "10.28991/hij-2024-05-04-013",
        "10.28991/hij-2025-06-01-017",
        "10.3390/math11061335",
        "10.2478/cait-2023-0020",
        "10.3390/math11051132",
        "10.1109/access.2021.3088999",
        "10.1109/access.2023.3318478",
        "10.3390/forecast8030040",
        "10.3390/a19020101",
        "10.1109/access.2024.3516490",
        "10.3390/fintech4040077",
        "10.1016/j.eswa.2025.127729",
        "10.3905/jfds.2026.1.217",
        "10.3390/math13233889",
        "10.1007/s10614-026-11338-3",
        "10.3390/electronics15061334",
        "10.1007/s42521-024-00123-2",
        "10.3390/math13101577"
    ]
    
    papers = extract_papers_by_doi(doi_list, args.input_file)
    
    with open(args.output_file, 'w', encoding='utf-8') as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    
    print(f"{len(papers)} dari {len(doi_list)} DOI ditemukan dan disimpan ke '{args.output_file}'")
    
    print("\nRingkasan paper yang ditemukan:")
    for i, paper in enumerate(papers, 1):
        title = paper.get('title', 'No title')
        authors = paper.get('authors', [])
        author_str = f"{authors[0]} et al." if authors else "Unknown"
        print(f"{i}. {title} ({paper.get('year', 'n.d.')}) - {author_str}")
