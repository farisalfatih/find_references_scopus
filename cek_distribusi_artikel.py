import json

with open('cleaned_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Distribusi jumlah artikel per kategori:\n")
for category, articles in data.items():
    count = len(articles)
    print(f"{category}: {count} artikel")

total = sum(len(articles) for articles in data.values())
print(f"\nTotal semua artikel: {total}")
