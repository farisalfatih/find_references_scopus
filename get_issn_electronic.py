import json

def main():
    print("="*50)
    print("AMBIL ISSN ELECTRONIC BERDASARKAN QUARTILE")
    print("="*50)
    
    file_path = input("Masukkan path file JSON: ").strip()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' tidak ditemukan.")
        return
    except json.JSONDecodeError:
        print("Error: File bukan JSON yang valid.")
        return
    
    if not isinstance(data, list):
        print("Error: JSON harus berupa array (list) objek.")
        return
    
    print("\nPilihan quartile:")
    print("  - semua")
    print("  - Q1, Q2, Q3, Q4 (bisa lebih dari satu, pisahkan koma)")
    print("  Contoh: Q1,Q2  atau  Q1, Q3, Q4")
    pilihan_input = input("Masukkan pilihan quartile: ").strip().lower()
    
    if pilihan_input == 'semua':
        quartile_yang_diinginkan = None
    else:
        # Pecah berdasarkan koma, bersihkan spasi, lalu uppercase
        parts = [p.strip().upper() for p in pilihan_input.split(',')]
        # Validasi setiap bagian harus Q1, Q2, Q3, atau Q4
        valid = all(p in ['Q1','Q2','Q3','Q4'] for p in parts)
        if not valid:
            print("Pilihan tidak valid. Gunakan: semua, atau kombinasi Q1,Q2,Q3,Q4 (pisah koma)")
            return
        quartile_yang_diinginkan = set(parts)
    
    issn_list = []
    for item in data:
        issn = item.get('issn_electronic')
        quartile = item.get('quartile')
        
        if not (issn and isinstance(issn, str) and issn.strip()):
            continue
        
        if quartile_yang_diinginkan is not None:
            if not quartile:
                continue
            q_clean = quartile.strip().upper()
            if q_clean not in quartile_yang_diinginkan:
                continue
        
        issn_list.append(issn.strip())
    
    print("\n" + "="*50)
    print("HASIL:")
    if issn_list:
        output = '{' + ', '.join(f'"{issn}"' for issn in issn_list) + '}'
        print(output)
    else:
        print("{}")
    
    print(f"\n(Jumlah ISSN yang ditemukan: {len(issn_list)})")
    print("="*50)

if __name__ == "__main__":
    main()
