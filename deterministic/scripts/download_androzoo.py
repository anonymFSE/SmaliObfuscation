import requests
import time
import os


HASH_FILE     = "hash_banking_trojan.txt" 
BASE_DIR      = "Malware_Downloads_BankingTrojan" 
ANDROZOO_API_KEY = ""
ANDROZOO_URL  = "https://androzoo.uni.lu/api/download"
DELAY_SECONDS = 5 

def download_from_androzoo(sha256, save_path):
    params = {
        'apikey': ANDROZOO_API_KEY,
        'sha256': sha256
    }
    try:
        
        response = requests.get(ANDROZOO_URL, params=params, stream=True, timeout=60)
        
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192): 
                    if chunk:
                        f.write(chunk)
            return True, "Downloaded successfully (.apk)"
        elif response.status_code == 404:
            return False, "404 error: hash not found on AndroZoo."
        elif response.status_code == 403:
            return False, "403 error: invalid API key or quota exceeded."
        else:
            return False, f"HTTP error: {response.status_code}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"

def main():
    
    if not os.path.exists(HASH_FILE):
        print(f"[ERROR] File '{HASH_FILE}' not found.")
        return

    
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
        print(f"[INFO] Folder '{BASE_DIR}' created.")

    
    try:
        with open(HASH_FILE, 'r', encoding='utf-8') as file:
            hashes = []
            for line in file:
                parts = line.strip().split()
                for part in parts:
                    if len(part) == 64: 
                        hashes.append(part)
    except Exception as e:
        print(f"[ERROR] Unable to read file: {e}")
        return

    
    unique_hashes = list(dict.fromkeys(hashes))
    total_samples = len(unique_hashes)

    if total_samples == 0:
        print("[WARNING] No valid hashes found in the file.")
        return

    print(f"[INFO] Searching for missing samples on AndroZoo")
    print(f"[INFO] Found {total_samples} unique hashes to process.\n")

    
    ok = 0; skip = 0; fail = 0

    
    for index, sha256 in enumerate(unique_hashes):
        
        file_path_zip = os.path.join(BASE_DIR, f"{sha256}.zip")
        file_path_apk = os.path.join(BASE_DIR, f"{sha256}.apk")

        
        if os.path.exists(file_path_zip) or os.path.exists(file_path_apk):
            print(f"[{index + 1}/{total_samples}] [SKIP] {sha256} already present locally.")
            skip += 1
            continue

        print(f"[{index + 1}/{total_samples}] Download: {sha256}")
        
        
        success, message = download_from_androzoo(sha256, file_path_apk)

        if success:
            print(f"  -> [OK] {message}")
            ok += 1
        else:
            print(f"  -> [NO] {message}")
            fail += 1

        
        if index < total_samples - 1:
            time.sleep(DELAY_SECONDS)

    
    print(f"\n[INFO] AndroZoo download completed.")
    print(f"       New downloads: {ok}  |  Skipped (already present): {skip}  |  Not found/Failed: {fail}")
    print(f"       Total files currently in folder '{BASE_DIR}': {len(os.listdir(BASE_DIR))}")

if __name__ == "__main__":
    main()
