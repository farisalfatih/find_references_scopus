import json

def proses_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if not isinstance(data, list):
            print("Error: JSON harus berupa array (list) dari objek.")
            return
        
        total_data = len(data)
        total_issn_print = 0
        total_issn_electronic = 0
        hanya_print = 0
        hanya_electronic = 0
        tidak_ada_keduanya = 0
        data_tanpa_issn = []
        
        print("Daftar ISSN Print dan ISSN Electronic:")
        print("---------------------------------------")
        for idx, item in enumerate(data, start=1):
            issn_print = item.get('issn_print')
            issn_electronic = item.get('issn_electronic')
            
            ada_print = bool(issn_print and issn_print.strip())
            ada_electronic = bool(issn_electronic and issn_electronic.strip())
            
            if ada_print:
                total_issn_print += 1
            if ada_electronic:
                total_issn_electronic += 1
            
            if ada_print and not ada_electronic:
                hanya_print += 1
            elif ada_electronic and not ada_print:
                hanya_electronic += 1
            elif not ada_print and not ada_electronic:
                tidak_ada_keduanya += 1
                data_tanpa_issn.append((idx, item))
            
            print(f"{idx}. ISSN Print: {issn_print or 'Tidak ada'} | ISSN Electronic: {issn_electronic or 'Tidak ada'}")
        
        print("\n" + "="*40)
        print("RINGKASAN TOTAL:")
        print(f"Total data (record) dalam JSON: {total_data}")
        print(f"Total record yang memiliki ISSN print: {total_issn_print}")
        print(f"Total record yang memiliki ISSN electronic: {total_issn_electronic}")
        print(f"Total record yang memiliki ISSN print SAJA (tidak punya electronic): {hanya_print}")
        print(f"Total record yang memiliki ISSN electronic SAJA (tidak punya print): {hanya_electronic}")
        print(f"Total record yang TIDAK memiliki kedua ISSN: {tidak_ada_keduanya}")
        print("="*40)
        
        if data_tanpa_issn:
            print("\n" + "="*40)
            print("DETAIL RECORD YANG TIDAK MEMILIKI ISSN PRINT DAN ISSN ELECTRONIC:")
            print("="*40)
            for urutan, record in data_tanpa_issn:
                print(f"\n--- Record ke-{urutan} ---")
                print(json.dumps(record, indent=2, ensure_ascii=False))
        else:
            print("\nTidak ada record yang tidak memiliki kedua ISSN.")
    
    except FileNotFoundError:
        print(f"File '{file_path}' tidak ditemukan.")
    except json.JSONDecodeError:
        print("Error: File tidak memiliki format JSON yang valid.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    proses_json('scimagojr_2025.json')
