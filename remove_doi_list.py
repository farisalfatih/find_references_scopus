import json

with open('openalex_results_deduplicated.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('excluded_dois.txt', 'r', encoding='utf-8') as f:
    excluded_dois = set(line.strip() for line in f if line.strip())

cleaned_data = {}
total_removed = 0

for category, papers in data.items():
    original_count = len(papers)
    filtered_papers = [paper for paper in papers if paper.get('doi') not in excluded_dois]
    removed_count = original_count - len(filtered_papers)
    total_removed += removed_count
    cleaned_data[category] = filtered_papers
    print(f"Kategori '{category}': {original_count} -> {len(filtered_papers)} (dihapus {removed_count})")

print(f"\nTotal paper dihapus: {total_removed}")

with open('cleaned_results.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print("File cleaned_results.json berhasil dibuat.")
