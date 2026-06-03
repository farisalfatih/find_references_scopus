import json
import os
import sys
import re


def sanitize_filename(name):
    sanitized = re.sub(r'[,]', '', name)
    sanitized = re.sub(r'[/\\]', '_', sanitized)
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    return sanitized


def split_by_subject_area(json_filepath, output_dir):
    if not os.path.exists(json_filepath):
        print(f"Error: File JSON tidak ditemukan: {json_filepath}")
        sys.exit(1)

    with open(json_filepath, "r", encoding="utf-8") as f:
        journals = json.load(f)

    print(f"Total jurnal: {len(journals)}")

    area_dict = {}
    area_count = {}

    for journal in journals:
        subject_areas = journal.get("subject_area", [])
        for area in subject_areas:
            if area not in area_dict:
                area_dict[area] = []
                area_count[area] = 0
            area_dict[area].append(journal)
            area_count[area] += 1

    os.makedirs(output_dir, exist_ok=True)

    for area, journal_list in sorted(area_dict.items()):
        safe_name = sanitize_filename(area)
        filename = f"subject_area_{safe_name}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(journal_list, f, indent=2, ensure_ascii=False)

    summary = []
    for area in sorted(area_dict.keys()):
        safe_name = sanitize_filename(area)
        filename = f"subject_area_{safe_name}.json"
        summary.append({
            "subject_area": area,
            "file": filename,
            "total_journals": area_count[area]
        })

    summary_path = os.path.join(output_dir, "_index.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nTotal subject_area ditemukan: {len(area_dict)}")
    print(f"File JSON disimpan di: {os.path.abspath(output_dir)}\n")

    print(f"{'No.':<5} {'Subject Area':<60} {'Jumlah Jurnal':<15} {'File'}")
    print("-" * 140)

    for idx, item in enumerate(summary, 1):
        print(f"{idx:<5} {item['subject_area']:<60} {item['total_journals']:<15} {item['file']}")

    print(f"\nFile index disimpan di: {summary_path}")
    print(f"Total {len(summary)} file JSON + 1 file index berhasil dibuat.")


if __name__ == "__main__":
    input_json = "scimagojr_2025.json"
    output_dir = "scimago_split"

    if len(sys.argv) >= 2:
        input_json = sys.argv[1]
    if len(sys.argv) >= 3:
        output_dir = sys.argv[2]

    print(f"Input JSON : {input_json}")
    print(f"Output Dir : {output_dir}")
    print()

    split_by_subject_area(input_json, output_dir)
