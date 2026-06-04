import json

with open('openalex_results_deduplicated.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('excluded_dois.txt', 'r', encoding='utf-8') as f:
    excluded_dois = set(line.strip() for line in f if line.strip())

cleaned_data = {}
total_removed = 0
removed_categories = []

for category, papers in data.items():
    original_count = len(papers)
    filtered_papers = [paper for paper in papers if paper.get('doi') not in excluded_dois]
    removed_count = original_count - len(filtered_papers)
    total_removed += removed_count
    
    if filtered_papers:  # hanya simpan kategori yang tidak kosong
        cleaned_data[category] = filtered_papers
        print(f"Kategori '{category}': {original_count} -> {len(filtered_papers)} (dihapus {removed_count})")
    else:
        removed_categories.append(category)
        print(f"Kategori '{category}' menjadi kosong dan akan dihapus (dihapus {removed_count} paper)")

print(f"\nTotal paper dihapus: {total_removed}")
if removed_categories:
    print(f"Kategori yang dihapus karena kosong: {removed_categories}")

with open('cleaned_results.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

print("\nFile cleaned_results.json berhasil dibuat.")
