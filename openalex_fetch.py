import json
import os
import time
import sys
import requests
from datetime import datetime

ISSN_ELECTRONIC = {"2157-846X", "2365-9440", "2666-920X", "2522-5839", "0733-8716", "1557-7341", "1935-8237", "0268-4012", "2470-9476", "1047-7047", "0730-0301", "0018-9219", "1552-7379", "0272-6963", "2691-3399", "1759-0884", "1939-3539", "2638-6100", "1536-1284", "0360-1315", "1949-3053", "2667-3452", "2662-8457", "2196-7091", "1744-4292", "2398-6352", "1566-2535", "0958-8221", "2168-6831", "2162-9730", "0963-8687", "1558-2523", "2329-9274", "1567-2328", "1526-5463", "2168-2267", "0924-2716", "1367-5788", "1558-2248", "1548-7660", "1573-7462", "1745-493X", "1572-2740", "2097-3330", "1361-8423", "2573-5144", "2662-1363", "1574-0137", "1365-2575", "0736-5845", "2653-6226", "0278-6125", "1552-3098", "1476-9344", "1560-4306", "0742-1222", "2162-2388", "1941-0034", "1573-1405", "0747-5632", "1941-0484", "1089-778X", "1558-2191", "1941-0050", "1057-7149", "1096-7516", "2096-0433", "2057-3960", "0163-6804", "2666-5573", "2379-8858", "0278-0046", "2168-2232","1935-8261", "2056-6387", "2666-6510", "1556-1615", "1474-0109", "1524-9050", "1558-156X", "1536-9323", "1942-4787", "1387-3326", "2692-7632", "1367-4803", "2667-2375", "1558-254X", "2589-7217", "1949-3045", "2666-4127", "0735-6331", "0268-3962", "1134-3060", "1558-0660", "0968-090X", "0377-2217", "2332-7731", "1096-1216", "2363-7005", "0045-7825", "2950-1628", "1467-5463", "2332-7383", "1744-5191", "0378-7206", "0736-5853", "1556-6013", "0166-3615", "1539-1523", "0168-1699", "1093-9687", "0266-4909", "0031-3203", "2327-4662", "2307-387X", "1019-6781", "1568-4539", "0025-5610", "1438-8871", "1558-0792", "1941-014X", "2056-3051", "0167-9236", "2325-5870", "2709-4723", "2157-6904", "2667-2413", "1571-0645", "2510-2044", "1939-9359", "3006-5429", "2666-5468", "2053-9517", "1366-5871", "1741-3176", "1474-0346", "0095-8956", "1532-4435", "1941-0077", "1526-5528", "2196-1115", "1873-7633", "0959-3845", "1549-8328", "0957-4174", "1558-2868", "1615-3375", "2052-4463", "2095-8099", "2731-5398", "1939-1382", "0956-5515", "1867-2957", "1943-4294", "2327-4697", "1045-9219", "0306-4573", "1530-9312", "1873-4774", "2634-4416", "1053-587X", "2169-5180", "1757-9899", "2667-0968", "0952-1976", "2772-4859", "1574-9541", "2150-8097","2956-2384", "1941-0018", "0950-7051", "2210-6502", "0749-596X", "2197-9987", "2473-2400", "0010-0285", "1471-7727", "1932-8354", "2644-125X", "2691-1957", "1084-8045", "1536-8734", "2666-1659", "1745-2759", "2379-5077", "1095-7189", "1741-0398", "1873-2860", "2471-285X", "2471-2825", "2168-2194", "0364-765X", "1758-8510", "1558-2558", "1551-3955", "0167-4048", "1939-1374", "1049-331X", "2772-9184", "2377-3766", "0360-8352", "1873-765X", "1556-603X", "0094-114X", "0098-5589", "1741-038X", "0010-4655", "1094-3501", "2666-6030", "2949-8554", "2542-6605", "0021-9991", "2504-4990", "1879-2782", "2665-9085", "0001-0782", "2332-7790", "1558-0210", "0737-8831", "2667-2952", "1944-2866", "0308-5961", "2631-9268", "1000-1026", "1572-8439", "0020-0255", "8756-3894", "1435-5655", "0929-5593", "2998-4157", "2378-0967", "1549-9618", "0167-739X", "2666-3074", "2687-9743", "2050-1587", "1553-734X", "1872-8286", "1469-848X", "2096-0654", "0019-0578", "1568-4946", "0268-1102", "3006-5437", "2643-6817", "2472-1751", "1572-8641", "2451-9588", "0921-8890", "1319-1578", "1549-9596", "1684-8799", "2811-0854", "2049-8772", "2198-4026", "2576-3180", "2956-7068", "2632-1009", "1096-0899", "2211-1670", "1932-4537", "2047-217X", "1044-7318","1879-0534", "2468-5925", "1557-735X", "1567-4223", "2168-7161", "2644-1268", "2640-4567", "2666-9900", "1758-2946", "2635-0041", "2641-8770", "2667-1026", "1365-8824", "1364-8152", "2949-6780", "1746-8094", "2097-0242", "1557-9654", "1532-0464", "2634-4386", "1556-4681", "0741-9058", "1661-6596", "1573-7691", "1939-1390", "2001-0370", "2056-7189", "2666-9536", "1573-689X", "0167-6911", "2452-3100", "0004-3702", "2528-1410", "2379-8939", "2662-4745", "1864-6956", "2831-316X", "2509-3312", "2949-7191", "2590-0056", "0263-5577", "1932-8184", "0949-877X", "0894-4393", "1558-223X", "2573-9522", "2673-253X", "1869-1919", "0895-6111", "1756-0381", "0045-7949", "1557-9956", "2373-776X", "2214-3173", "1872-7565", "2468-2322", "2330-1635", "2666-8270", "1472-6947", "1931-7891", "0178-7675", "2543-9251", "0967-0661", "2329-924X", "2364-1185", "2474-9567", "1058-0530", "0195-6698", "0142-694X", "1573-756X", "2168-2305", "1753-8947", "2095-2236", "1866-9956", "2691-4581", "1453-8245", "2624-6511", "1756-8757", "2096-496X", "2731-0809", "1932-2917", "1570-8713", "3009-4267", "2772-3755", "1933-169X", "2950-550X", "0965-9978", "2153-3539", "2687-7813", "2197-6775", "2288-4300", "2332-8886", "1389-1286", "2168-6750", "2667-3053","1556-4959", "1552-8251", "0144-929X", "2666-7649", "1071-5819", "2666-3783", "1751-570X", "2673-2688", "1875-4791", "1943-0620", "2639-0213", "2152-2723", "1746-725X", "2730-7239", "1076-9757", "1471-2105", "1751-1577", "2731-6963", "0045-7906", "2192-113X", "2405-8866", "0378-2166", "1943-5487", "2772-5030", "0006-3835", "2198-6053", "1547-9714", "2958-6631", "0065-2458", "1793-6462", "0138-9130", "1615-147X", "2192-662X", "2210-5379", "1383-7621", "1433-3058", "2637-6407", "2333-9403", "2523-3246", "2192-5372", "2056-4880", "1540-3467", "1572-9362", "0950-5849", "2792-0232", "1994-2060", "2212-473X", "2504-446X", "1533-5399", "1874-5482", "2694-2445", "1063-8210", "0140-3664", "1359-4338", "2972-3841", "2472-5749", "2504-2289", "0098-3004", "0272-1732", "0885-6125", "1464-5319", "2377-3782", "1946-6226", "2770-9019", "2212-8689", "2634-1964", "0920-5489", "1615-5262", "2576-3202", "1947-5683", "1573-7543", "2689-0208", "2624-8212", "1479-4403", "2771-5892", "1570-8268", "0378-4754", "2666-0539", "2730-616X", "2055-2076", "2168-0566", "1547-2442", "2090-4754", "3005-365X", "1861-2776", "2577-6207", "0098-3500", "0306-4379", "1386-145X", "1551-6709", "1077-2626", "1087-6537", "0887-4417", "2405-9595", "0177-0667","1550-4867", "0146-4833", "1927-0321", "1325-4340", "1569-190X", "2520-2316", "2666-6596", "2215-0986", "1467-8659", "2364-4168", "1476-072X", "0164-1212", "2694-085X", "1555-4120", "1947-315X", "1475-3995", "2689-3967", "1758-0463", "2689-1808", "1941-1294", "1098-2418", "2073-431X", "2509-498X", "1435-568X", "1937-4151", "2475-1421", "0167-9473", "0266-5611", "1551-6857", "1573-7616", "2158-656X", "1929-7750", "1555-3434", "1572-8382", "2214-2134", "0010-4485", "0899-3408", "2667-1336", "0884-8173", "1475-939X", "8755-4615", "1559-0089", "2578-1863", "1463-5011", "2164-2583", "3009-3481", "2577-6193", "2688-299X", "1468-4535", "1471-4175", "2948-2933", "2161-783X", "2059-5891", "2224-2708", "1757-9961", "1469-2163", "2569-2925", "2169-3536", "2329-9290", "2227-9709", "1362-3052", "1064-7570", "0262-8856", "2227-7102", "1096-0848", "0959-1524", "2476-1249", "0098-1354", "2708-6240", "2950-4635", "2162-2248", "1559-114X", "2666-5441", "1460-7425", "0219-3116", "2790-7511", "1976-5541", "2198-5804", "2524-4906", "1866-749X", "1462-6268", "2624-800X", "2096-7527", "2666-2825", "2199-4676", "2752-8200", "0924-1868", "1936-2455", "1554-0677", "1861-8219", "1097-1440", "1999-5903", "1095-7111", "2469-7281", "2214-580X","1941-0131", "3059-3220", "1673-5447", "1435-5566", "2511-2112", "1873-7668", "2576-3156", "2197-6503", "1246-0125", "1944-3900", "1574-1192", "1573-1375", "0045-7930", "2511-9044", "1050-0472", "1090-235X", "1573-272X", "2057-2093", "2730-6852", "2810-9570", "1573-2916", "0016-0032", "2813-2084", "0718-1876", "2003-184X", "1424-8220", "2791-8564", "1573-7721", "1936-1955", "0165-1684", "2571-5577", "0167-8655", "2227-7080", "2213-7467", "0883-9514", "1093-023X", "1687-9732", "2950-306X", "1000-2383", "1751-7575", "2576-9898", "1875-6883", "0957-4158", "2475-4269", "2673-8732", "2471-2574", "1558-2361", "1741-6485", "2050-3814", "1748-7188", "2304-6775", "3079-0875", "2837-7842", "2095-283X", "2730-5392", "2590-1974", "0168-874X", "1874-4753", "2624-831X", "2155-7098", "1868-6478", "2673-7426", "2071-1050", "1526-6133", "2470-1475", "1533-7995", "1619-4500", "0031-868X", "2673-4192", "1931-2431", "2666-7207", "2218-6581", "1866-1505", "2378-962X", "1877-7503", "1477-996X", "1943-7544", "1558-7959", "1138-2783", "1522-9602", "1061-3773", "1047-8310", "0162-6434", "2083-2567", "0927-0256", "0165-0114", "2398-5348", "0921-0296", "1528-8935", "2171-7966", "1477-4593", "1573-7667", "1573-7586", "2050-3385", "1648-5831","1433-3015", "2631-7176", "1556-4673", "2836-3310", "1864-5909", "1753-9137", "2210-9706", "2571-9394", "0022-0418", "1530-9827", "2330-2682", "1868-6346", "2752-9991", "2755-077X", "2769-0911", "1365-893X", "1869-5469", "1570-5838", "1230-1612", "1296-2074", "1940-1493", "1099-1425", "2163-5226", "0942-4962", "2632-3249", "2352-7285", "0163-0563", "1364-6885", "1469-8668", "1528-7033", "0368-492X", "0925-3467", "2468-6964", "1540-7993", "0040-5833", "1572-9095", "0740-8188", "2674-1032", "2398-6247", "2576-5337", "2212-0548", "1745-3755", "0167-6393", "1355-8250", "1989-9947", "1469-8404", "2631-7680", "2542-386X", "1574-0218", "1095-9076", "1046-8781", "2059-5824", "1832-4215", "1986-3497", "1941-0166", "2056-9017", "2509-9515", "1396-0466", "2001-7480", "2977-0424", "1572-9583", "2588-2872", "1465-363X", "2949-6845", "1572-8110", "1991-3761", "1059-7123", "2514-8362", "2195-2957", "2055-768X", "2187-9036", "2239-4303", "2063-4269", "2392-2397", "2371-4549", "1934-5275", "1135-5948", "2283-2998", "2681-4617", "1946-2174", "0929-0907", "1531-5169", "1460-6925", "2008-0387", "1695-5951", "1469-8153", "2014-9298", "2603-3364", "1752-7066", "1226-8046", "2604-6032", "1414-526X", "1738-8074", "0957-9656"}

YEAR_FROM = 2021
YEAR_TO = 2026

LANGUAGE = ["en"]

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

OUTPUT_FILE = "openalex_results.json"
PER_PAGE = 200
REQUEST_DELAY = 1.0
MAX_RESULTS = 0
ISSN_BATCH_SIZE = 50

def reconstruct_abstract(abstract_inverted_index):
    if not abstract_inverted_index:
        return None
    try:
        word_positions = []
        for word, positions in abstract_inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions).strip()
    except Exception:
        return None

def format_date(date_str):
    if not date_str:
        return ""
    if len(date_str) >= 10:
        return date_str[:10]
    elif len(date_str) >= 7:
        return date_str + "-01"
    elif len(date_str) >= 4:
        return date_str + "-01-01"
    return date_str

def extract_article_data(work, issn_electronic_set):
    try:
        doi = work.get("doi", "")
        if doi:
            doi = doi.replace("https://doi.org/", "")

        biblio = work.get("biblio", {}) or {}
        primary_location = work.get("primary_location", {}) or {}
        source = primary_location.get("source", {}) or {}
        oa_status = work.get("open_access", {}) or {}

        issn_electronic = ""
        for src_issn in (source.get("issn") or []):
            if src_issn in issn_electronic_set:
                issn_electronic = src_issn
                break

        authors = []
        for authorship in (work.get("authorships") or []):
            display_name = (authorship.get("author") or {}).get("display_name", "")
            if display_name:
                authors.append(display_name)

        is_oa = oa_status.get("is_oa", False)
        oa_url = oa_status.get("oa_url", "")
        if is_oa:
            open_access = "Yes"
        elif oa_url:
            open_access = "Partial"
        else:
            open_access = "No"

        volume = biblio.get("volume")
        issue = biblio.get("issue")
        first_page = biblio.get("first_page")
        last_page = biblio.get("last_page")

        return {
            "doi": doi,
            "title": work.get("title", ""),
            "abstract": reconstruct_abstract(work.get("abstract_inverted_index")) or "",
            "authors": authors,
            "year": work.get("publication_year", ""),
            "pub_date": format_date(work.get("publication_date", "")),
            "volume": "" if volume is None else str(volume),
            "issue": "" if issue is None else str(issue),
            "first_page": "" if first_page is None else str(first_page),
            "last_page": "" if last_page is None else str(last_page),
            "publisher": source.get("host_organization_name", "") or "",
            "journal": source.get("display_name", ""),
            "issn_electronic": issn_electronic,
            "open_access": open_access,
        }
    except Exception as e:
        print(f"  Warning: Gagal extract data - {e}")
        return None

def fetch_group(group_name, group_config, issn_list, year_from, year_to, lang_list, per_page, delay, max_results):
    search_query = group_config.get("query", "")
    if not search_query:
        print(f"  Kelompok '{group_name}' tidak memiliki query, dilewati.")
        return [], 0

    lang_filter = ""
    if lang_list:
        lang_filter = f",language:{'|'.join(lang_list)}"

    issn_batches = [issn_list[i:i + ISSN_BATCH_SIZE] for i in range(0, len(issn_list), ISSN_BATCH_SIZE)]

    base_url = "https://api.openalex.org/works"
    all_articles = []
    seen_dois = set()
    total_fetched = 0

    for batch_idx, batch in enumerate(issn_batches):
        print(f"    Batch ISSN {batch_idx+1}/{len(issn_batches)} ({len(batch)} ISSN)")

        params = {
            "filter": (
                f"primary_location.source.issn:{'|'.join(batch)},"
                f"from_publication_date:{year_from}-01-01,"
                f"to_publication_date:{year_to}-12-31,"
                f"has_doi:true,"
                f"has_abstract:true{lang_filter}"
            ),
            "search": search_query,
            "per_page": per_page,
        }

        cursor = "*"
        page = 0
        batch_fetched = 0

        while cursor:
            page += 1
            params["cursor"] = cursor

            try:
                response = requests.get(base_url, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                meta = data.get("meta", {})

                if page == 1:
                    estimated = meta.get("count", 0)
                    print(f"      Estimasi artikel: ~{estimated}")

                for work in results:
                    if max_results > 0 and total_fetched >= max_results:
                        cursor = None
                        break

                    doi = work.get("doi", "")
                    if doi:
                        doi_clean = doi.replace("https://doi.org/", "")
                        if doi_clean in seen_dois:
                            continue
                        seen_dois.add(doi_clean)

                    entry = extract_article_data(work, set(issn_list))
                    if not entry:
                        continue

                    all_articles.append(entry)
                    total_fetched += 1
                    batch_fetched += 1

                next_cursor = meta.get("next_cursor")
                if not next_cursor or next_cursor == "null" or not results:
                    cursor = None
                else:
                    cursor = next_cursor

                print(f"      Page {page}: {len(results)} hasil, total group ini: {batch_fetched} artikel matched")
                if max_results > 0 and total_fetched >= max_results:
                    break

                time.sleep(delay)

            except requests.exceptions.Timeout:
                print(f"      Timeout page {page}, ulang...")
                time.sleep(delay * 2)
                continue
            except requests.exceptions.HTTPError as e:
                print(f"      HTTP Error: {e}")
                if e.response is not None:
                    print(f"      Response: {e.response.text[:500]}")
                break
            except Exception as e:
                print(f"      Error: {e}")
                break

        print(f"    Batch {batch_idx+1} selesai → {batch_fetched} artikel untuk group ini")
        if max_results > 0 and total_fetched >= max_results:
            break
        time.sleep(delay)

    return all_articles, total_fetched

def main():
    print("=" * 60)
    print("  OpenAlex Article Fetcher — dengan Query Langsung (tanpa keywords/mode)")
    print("=" * 60)
    print()

    if not ISSN_ELECTRONIC:
        print("Error: ISSN_ELECTRONIC kosong!")
        sys.exit(1)

    if not SEARCH_GROUPS:
        print("Error: SEARCH_GROUPS kosong!")
        sys.exit(1)

    print("Konfigurasi:")
    print(f"  ISSN count      : {len(ISSN_ELECTRONIC)}")
    print(f"  Year range      : {YEAR_FROM} - {YEAR_TO}")
    print(f"  Language        : {LANGUAGE if LANGUAGE else '(semua)'}")
    print(f"  Output file     : {OUTPUT_FILE}")
    print(f"  Max results/group: {MAX_RESULTS if MAX_RESULTS > 0 else 'tanpa batas'}")
    print()

    print("Daftar kelompok pencarian:")
    for idx, (name, config) in enumerate(SEARCH_GROUPS.items(), 1):
        print(f"  {idx}. {name} → query: {config['query']}")
    print()

    print("=" * 60)
    print("  Mulai fetch data per kelompok...")
    print("=" * 60)
    print()

    issn_list = list(ISSN_ELECTRONIC)
    grouped_results = {}
    group_counts = {}

    for group_name, group_config in SEARCH_GROUPS.items():
        print(f"\n>>> Memproses kelompok: {group_name}")
        articles, count = fetch_group(
            group_name=group_name,
            group_config=group_config,
            issn_list=issn_list,
            year_from=YEAR_FROM,
            year_to=YEAR_TO,
            lang_list=LANGUAGE,
            per_page=PER_PAGE,
            delay=REQUEST_DELAY,
            max_results=MAX_RESULTS,
        )
        grouped_results[group_name] = articles
        group_counts[group_name] = count
        print(f"  <<< Kelompok '{group_name}' selesai → {count} artikel ditemukan.")
        time.sleep(REQUEST_DELAY)

    out_dir = os.path.dirname(os.path.abspath(OUTPUT_FILE))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(grouped_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print("  RINGKASAN HASIL")
    print("=" * 60)
    for name, count in group_counts.items():
        print(f"  {name:<40} : {count} artikel")
    print(f"\n  Total artikel (dengan duplikasi antar kelompok): {sum(group_counts.values())}")
    print(f"  Output file: {os.path.abspath(OUTPUT_FILE)}")
    print(f"  Selesai pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
