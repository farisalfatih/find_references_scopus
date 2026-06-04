import json
import os
import re

def parse_simple_query(query_str):
    query_str = query_str.strip()
    if not query_str:
        return lambda text: True
    parts = re.split(r'\s+AND\s+', query_str, flags=re.IGNORECASE)
    conditions = []
    for part in parts:
        part = part.strip()
        if part.startswith('(') and part.endswith(')'):
            inner = part[1:-1]
            or_keywords = re.split(r'\s+OR\s+', inner, flags=re.IGNORECASE)
            or_keywords_clean = []
            for kw in or_keywords:
                kw = kw.strip()
                if kw.startswith('"') and kw.endswith('"'):
                    kw = kw[1:-1]
                or_keywords_clean.append(kw.lower())
            conditions.append(('or', or_keywords_clean))
        else:
            if part.startswith('"') and part.endswith('"'):
                part = part[1:-1]
            conditions.append(('and', part.lower()))
    def evaluate(text):
        text_lower = text.lower()
        for cond in conditions:
            if cond[0] == 'or':
                if not any(kw in text_lower for kw in cond[1]):
                    return False
            else:
                if cond[1] not in text_lower:
                    return False
        return True
    return evaluate

def main():
    INPUT_FILE = "openalex_results.json"
    OUTPUT_FILE = "openalex_results_filtered.json"

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
        "ATR Dynamic Labeling": {
            "query": '("Average True Range" OR ATR) AND "dynamic labeling"'
        },
        "HMM Forward Filtering": {
            "query": '"forward filtering" AND HMM'
        },
        "Walk-Forward Backtesting": {
            "query": '(walk-forward OR backtesting) AND "stop loss"'
        },
        "XGBoost Sharpe Sortino Profit Factor": {
            "query": '("Sharpe ratio" OR "Sortino ratio" OR "profit factor") AND "XGBoost"'
        },
    }

    if not os.path.exists(INPUT_FILE):
        print(f"File {INPUT_FILE} tidak ditemukan!")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    filtered_data = {}
    removal_summary = {}

    for group_name, articles in data.items():
        if group_name not in SEARCH_GROUPS:
            print(f"Peringatan: Grup '{group_name}' tidak dikenal, disalin apa adanya.")
            filtered_data[group_name] = articles
            removal_summary[group_name] = 0
            continue

        query_str = SEARCH_GROUPS[group_name]["query"]
        evaluator = parse_simple_query(query_str)

        kept = []
        removed_count = 0
        for article in articles:
            title = article.get("title", "") or ""
            abstract = article.get("abstract", "") or ""
            text = title + " " + abstract
            if evaluator(text):
                kept.append(article)
            else:
                removed_count += 1
        filtered_data[group_name] = kept
        removal_summary[group_name] = removed_count
        print(f"{group_name}: {len(articles)} -> {len(kept)} (hapus {removed_count})")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2, ensure_ascii=False)

    print(f"\nHasil disimpan ke {OUTPUT_FILE}")
    total_removed = sum(removal_summary.values())
    print(f"Total artikel dihapus: {total_removed}")

if __name__ == "__main__":
    main()
