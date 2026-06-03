import json
from collections import defaultdict

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_subset(keywords1, mode1, keywords2, mode2):
    """
    Cek apakah group1 (keywords1, mode1) adalah subset dari group2 (keywords2, mode2)
    Artinya: setiap artikel yang memenuhi group1 PASTI memenuhi group2.
    Untuk mode 'all', subset terjadi jika semua keyword group1 ada di keyword group2.
    Untuk mode 'any', lebih kompleks. Di sini kita sederhanakan hanya untuk mode 'all' semua.
    """
    if mode1 != 'all' or mode2 != 'all':
        return False  # hanya tangani kasus all-all untuk kemudahan
    set1 = set(k.lower() for k in keywords1)
    set2 = set(k.lower() for k in keywords2)
    return set1.issubset(set2)

def build_hierarchy(groups_config):
    """
    Membangun hubungan subset antar group berdasarkan keyword.
    Return: dict {group_name: set_of_supersets} atau list of edges.
    """
    names = list(groups_config.keys())
    subset_relations = {}  # group -> list of superset groups
    for i, name1 in enumerate(names):
        cfg1 = groups_config[name1]
        subset_relations[name1] = []
        for j, name2 in enumerate(names):
            if i == j:
                continue
            cfg2 = groups_config[name2]
            if is_subset(cfg1['keywords'], cfg1['mode'], cfg2['keywords'], cfg2['mode']):
                subset_relations[name1].append(name2)
    return subset_relations

def deduplicate_based_on_hierarchy(data, groups_config):
    """
    data: hasil fetch (dict: group_name -> list of articles)
    groups_config: SEARCH_GROUPS asli
    Menghasilkan data baru tanpa duplikasi dengan aturan:
    - Artikel yang ada di group subset dan juga di group superset akan dipindahkan ke superset saja.
    - Artikel yang muncul di dua group yang tidak memiliki hubungan subset akan digabung ke group baru.
    """
    # Bangun hubungan subset
    subset_map = build_hierarchy(groups_config)
    print("Hubungan subset (group -> superset):")
    for g, supers in subset_map.items():
        print(f"  {g} -> {supers if supers else '(tidak ada)'}")

    # Kumpulkan semua artikel per DOI
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

    # Tentukan untuk setiap DOI, group mana yang akan menjadi "target akhir"
    # Aturan: jika ada superset, pilih superset yang paling spesifik (terbanyak keyword)
    # Jika tidak ada hubungan subset, maka akan dibuat group gabungan.
    final_group_for_doi = {}
    for doi, groups in doi_to_groups.items():
        if len(groups) == 1:
            final_group_for_doi[doi] = groups[0]
            continue

        # Cek apakah ada hubungan subset di antara groups yang terlibat
        # Cari group yang menjadi superset dari semua group lain (paling spesifik)
        superset_candidates = []
        for g in groups:
            # cek apakah g adalah superset dari semua group lain dalam list
            is_superset_of_all = True
            for other in groups:
                if other == g:
                    continue
                # apakah g superset dari other? artinya other subset dari g
                if g not in subset_map.get(other, []):
                    is_superset_of_all = False
                    break
            if is_superset_of_all:
                superset_candidates.append(g)
        if superset_candidates:
            # pilih salah satu (misal yang paling panjang keyword-nya, atau pertama)
            # kita pilih yang keyword count terbesar
            best = max(superset_candidates, key=lambda x: len(groups_config[x]['keywords']))
            final_group_for_doi[doi] = best
        else:
            # tidak ada hubungan subset, buat group gabungan
            sorted_groups = sorted(groups)
            combined_name = " + ".join(sorted_groups)
            final_group_for_doi[doi] = combined_name

    # Bangun struktur baru
    new_data = defaultdict(list)
    for doi, target_group in final_group_for_doi.items():
        new_data[target_group].append(doi_to_article[doi])

    # Konversi ke dict biasa
    return dict(new_data)

def main():
    input_file = "openalex_results.json"
    output_file = "openalex_results_hierarchy.json"

    # Definisikan SEARCH_GROUPS (salin dari file fetch Anda)
    SEARCH_GROUPS = {
        "LSTM Bitcoin": {
            "keywords": ["LSTM", "bitcoin"],
            "mode": "all",
        },
        "LSTM Bitcoin XGBoost": {
            "keywords": ["LSTM", "bitcoin", "XGBoost"],
            "mode": "all",
        },
    }

    data = load_json(input_file)
    print("Data awal:")
    for g, arts in data.items():
        print(f"  {g}: {len(arts)} artikel")

    cleaned_data = deduplicate_based_on_hierarchy(data, SEARCH_GROUPS)

    print("\nSetelah deduplikasi berbasis hierarki:")
    for g, arts in cleaned_data.items():
        print(f"  {g}: {len(arts)} artikel")

    save_json(cleaned_data, output_file)
    print(f"\nHasil disimpan ke {output_file}")

if __name__ == "__main__":
    main()
