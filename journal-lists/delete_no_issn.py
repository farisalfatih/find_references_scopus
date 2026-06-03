import json

def proses_json(file_path, output_path='data_clean.json'):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if not isinstance(data, list):
            print("Error: JSON harus berupa array (list) dari objek.")
            return
        
        total_awal = len(data)
        
        data_baru = []
        record_dihapus = []
        
        for idx, item in enumerate(data, start=1):
            issn_electronic = item.get('issn_electronic')
            ada_electronic = bool(issn_electronic and issn_electronic.strip())
            
            if ada_electronic:
                data_baru.append(item)
            else:
                record_dihapus.append((idx, item))
        
        total_akhir = len(data_baru)
        jumlah_dihapus = total_awal - total_akhir
        
        with open(output_path, 'w', encoding='utf-8') as outfile:
            json.dump(data_baru, outfile, indent=2, ensure_ascii=False)
        
        print("="*50)
        print("HASIL PENGHAPUSAN RECORD TANPA ISSN ELECTRONIC")
        print("="*50)
        print(f"Total record awal : {total_awal}")
        print(f"Total record dihapus: {jumlah_dihapus}")
        print(f"Total record akhir  : {total_akhir}")
        print(f"File bersih disimpan sebagai: {output_path}")
        print("="*50)
        
        if record_dihapus:
            print("\nDaftar record yang dihapus (nomor urut asli):")
            for urutan, rec in record_dihapus:
                print(f"- Record ke-{urutan}: {rec.get('journal', 'Tidak ada judul')}")
    
    except FileNotFoundError:
        print(f"File '{file_path}' tidak ditemukan.")
    except json.JSONDecodeError:
        print("Error: File tidak memiliki format JSON yang valid.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    proses_json('scimagojr_2025.json', 'scimagojr_2025_ok.json')
