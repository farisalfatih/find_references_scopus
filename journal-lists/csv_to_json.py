import csv
import json
import sys
import os


def format_issn(issn_str):
    if not issn_str:
        return ""
    digits = issn_str.strip()
    digits = digits.replace("-", "")
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return digits


def parse_issns(issn_field):
    if not issn_field:
        return ("", "")

    parts = [p.strip() for p in issn_field.split(",")]

    if len(parts) == 1:
        issn_single = format_issn(parts[0])
        return ("", issn_single)
    elif len(parts) >= 2:
        issn_print = format_issn(parts[0])
        issn_electronic = format_issn(parts[1])
        return (issn_print, issn_electronic)

    return ("", "")


def determine_open_access(oa_value, oa_diamond_value):
    oa = oa_value.strip() if oa_value else ""
    oa_diamond = oa_diamond_value.strip() if oa_diamond_value else ""

    if oa_diamond.upper() == "YES":
        return "Diamond OA"
    elif oa.upper() == "YES":
        return "Yes"
    else:
        return "No"


def extract_sub_categories(categories_field):
    if not categories_field:
        return []

    categories = [c.strip() for c in categories_field.split(";")]
    result = []

    for cat in categories:
        cleaned = cat
        for q in [" (Q1)", " (Q2)", " (Q3)", " (Q4)", " (Q0)", " (Not covered)"]:
            cleaned = cleaned.replace(q, "")
        cleaned = cleaned.strip()
        if cleaned:
            result.append(cleaned)

    return result


def extract_subject_areas(areas_field):
    if not areas_field:
        return []

    areas = [a.strip() for a in areas_field.split(";")]
    return [a for a in areas if a]


def process_csv_to_json(csv_filepath, json_filepath):
    if not os.path.exists(csv_filepath):
        print(f"Error: File CSV tidak ditemukan: {csv_filepath}")
        sys.exit(1)

    with open(csv_filepath, "r", encoding="utf-8") as f:
        header_line = f.readline()
        headers = [h.strip() for h in header_line.strip().split(";")]

        expected_fields = {
            "Title": None,
            "Issn": None,
            "Open Access": None,
            "Open Access Diamond": None,
            "SJR Best Quartile": None,
            "Categories": None,
            "Areas": None,
        }

        for idx, h in enumerate(headers):
            if h in expected_fields:
                expected_fields[h] = idx

        missing = [k for k, v in expected_fields.items() if v is None]
        if missing:
            print(f"Warning: Kolom berikut tidak ditemukan di CSV: {missing}")
            print(f"Header yang tersedia: {headers}")

        idx_title = expected_fields["Title"]
        idx_issn = expected_fields["Issn"]
        idx_oa = expected_fields["Open Access"]
        idx_oa_diamond = expected_fields["Open Access Diamond"]
        idx_quartile = expected_fields["SJR Best Quartile"]
        idx_categories = expected_fields["Categories"]
        idx_areas = expected_fields["Areas"]

        reader = csv.reader(f, delimiter=";")
        result = []

        for row in reader:
            if not row or all(cell.strip() == "" for cell in row):
                continue

            title = row[idx_title].strip('"').strip() if idx_title is not None and idx_title < len(row) else ""
            issn_field = row[idx_issn].strip('"').strip() if idx_issn is not None and idx_issn < len(row) else ""
            oa_value = row[idx_oa].strip() if idx_oa is not None and idx_oa < len(row) else ""
            oa_diamond_value = row[idx_oa_diamond].strip() if idx_oa_diamond is not None and idx_oa_diamond < len(row) else ""
            quartile_value = row[idx_quartile].strip() if idx_quartile is not None and idx_quartile < len(row) else ""
            categories_field = row[idx_categories].strip('"').strip() if idx_categories is not None and idx_categories < len(row) else ""
            areas_field = row[idx_areas].strip('"').strip() if idx_areas is not None and idx_areas < len(row) else ""

            issn_print, issn_electronic = parse_issns(issn_field)
            open_access = determine_open_access(oa_value, oa_diamond_value)
            sub_categories = extract_sub_categories(categories_field)
            subject_areas = extract_subject_areas(areas_field)

            entry = {
                "journal": title,
                "issn_print": issn_print,
                "issn_electronic": issn_electronic,
                "quartile": quartile_value,
                "open_access": open_access,
                "subject_area": subject_areas,
                "sub_category": sub_categories,
            }

            result.append(entry)

    os.makedirs(os.path.dirname(os.path.abspath(json_filepath)), exist_ok=True)

    with open(json_filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Berhasil! {len(result)} entri jurnal telah dikonversi.")
    print(f"Output disimpan di: {json_filepath}")

    if len(result) > 0:
        print("\n--- Preview 3 entri pertama ---")
        for entry in result[:3]:
            print(json.dumps(entry, indent=2, ensure_ascii=False))
            print()


if __name__ == "__main__":
    input_csv = "scimagojr_2025.csv"
    output_json = "scimagojr_2025.json"

    if len(sys.argv) >= 2:
        input_csv = sys.argv[1]
    if len(sys.argv) >= 3:
        output_json = sys.argv[2]

    print(f"Input CSV  : {input_csv}")
    print(f"Output JSON: {output_json}")
    print()

    process_csv_to_json(input_csv, output_json)
