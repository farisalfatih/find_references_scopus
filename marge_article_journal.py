import json
import sys
from pathlib import Path

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def build_journal_index(journals_data):
    journal_index = {}
    for journal in journals_data:
        issn = journal.get('issn_electronic')
        if not issn:
            continue
        quartile = journal.get('quartile')
        open_access = journal.get('open_access')
        journal_index[issn] = {
            'quartile': quartile,
            'open_access': open_access
        }
    return journal_index

def merge_articles(articles_data, journal_index):
    if isinstance(articles_data, dict):
        if 'issn_electronic' in articles_data and ('doi' in articles_data or 'title' in articles_data):
            issn = articles_data['issn_electronic']
            if issn in journal_index:
                articles_data['quartile'] = journal_index[issn]['quartile']
                articles_data['open_access'] = journal_index[issn]['open_access']
            else:
                articles_data['quartile'] = None
                articles_data['open_access'] = None
        else:
            for key, value in articles_data.items():
                articles_data[key] = merge_articles(value, journal_index)
    elif isinstance(articles_data, list):
        for i, item in enumerate(articles_data):
            articles_data[i] = merge_articles(item, journal_index)
    return articles_data

def main():
    if len(sys.argv) != 3:
        print("Error: Incorrect number of arguments.")
        print("Usage: python merge_article_journal.py <articles_json> <journals_json>")
        sys.exit(1)

    articles_path = sys.argv[1]
    journals_path = sys.argv[2]

    if not Path(articles_path).is_file():
        print(f"Error: Articles file '{articles_path}' not found.")
        sys.exit(1)
    if not Path(journals_path).is_file():
        print(f"Error: Journals file '{journals_path}' not found.")
        sys.exit(1)

    articles = load_json(articles_path)
    journals = load_json(journals_path)

    journal_index = build_journal_index(journals)

    merged_articles = merge_articles(articles, journal_index)

    output_path = "final_references.json"
    save_json(merged_articles, output_path)
    print(f"Successfully merged. Output saved to '{output_path}'.")

if __name__ == "__main__":
    main()
