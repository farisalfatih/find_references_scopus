import json
import re
from collections import defaultdict

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_tokens(query):
    tokens = []
    quoted = re.findall(r'"([^"]+)"', query)
    tokens.extend(quoted)
    temp = re.sub(r'"[^"]+"', '', query)
    words = re.findall(r'\b[a-zA-Z0-9]+\b', temp)
    stop = {'and', 'or', 'not'}
    tokens.extend([w.lower() for w in words if w.lower() not in stop])
    return set(t.lower() for t in tokens)

def is_subset(query1, query2):
    return extract_tokens(query1).issubset(extract_tokens(query2))

def build_hierarchy(groups_config):
    names = list(groups_config.keys())
    subset_relations = {}
    for i, name1 in enumerate(names):
        q1 = groups_config[name1]['query']
        subset_relations[name1] = []
        for j, name2 in enumerate(names):
            if i == j:
                continue
            q2 = groups_config[name2]['query']
            if is_subset(q1, q2):
                subset_relations[name1].append(name2)
    return subset_relations

def deduplicate_based_on_hierarchy(data, groups_config):
    subset_map = build_hierarchy(groups_config)
    print("Relasi subset (group -> superset):")
    for g, supers in subset_map.items():
        print(f"  {g} -> {supers if supers else '(tidak ada)'}")

    doi_to_groups = defaultdict(list)
    doi_to_article = {}
    for group, articles in data.items():
        for art in articles:
            doi = art.get('doi')
            if not doi:
                continue
            if doi not in doi_to_article:
                doi_to_article[doi] = art
            if group not in doi_to_groups[doi]:
                doi_to_groups[doi].append(group)

    final_group_for_doi = {}
    for doi, groups in doi_to_groups.items():
        if len(groups) == 1:
            final_group_for_doi[doi] = groups[0]
            continue

        superset_candidates = []
        for g in groups:
            is_superset_of_all = True
            for other in groups:
                if other == g:
                    continue
                if g not in subset_map.get(other, []):
                    is_superset_of_all = False
                    break
            if is_superset_of_all:
                superset_candidates.append(g)

        if superset_candidates:
            best = max(superset_candidates, key=lambda x: len(extract_tokens(groups_config[x]['query'])))
            final_group_for_doi[doi] = best
        else:
            sorted_groups = sorted(groups)
            combined_name = " + ".join(sorted_groups)
            final_group_for_doi[doi] = combined_name

    new_data = defaultdict(list)
    for doi, target_group in final_group_for_doi.items():
        new_data[target_group].append(doi_to_article[doi])

    return dict(new_data)

def main():
    input_file = "openalex_results.json"
    output_file = "openalex_results_deduplicated.json"

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

    data = load_json(input_file)
    print("Data awal:")
    for g, arts in data.items():
        print(f"  {g}: {len(arts)} artikel")

    cleaned_data = deduplicate_based_on_hierarchy(data, SEARCH_GROUPS)

    print("\nSetelah deduplikasi berbasis hierarki (berdasarkan query):")
    for g, arts in cleaned_data.items():
        print(f"  {g}: {len(arts)} artikel")

    save_json(cleaned_data, output_file)
    print(f"\nHasil disimpan ke {output_file}")

if __name__ == "__main__":
    main()