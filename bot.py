import requests
import json
import os
from eth_account import Account
from colorama import init, Fore, Style
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


init()


def read_proxies(file_path="proxy.txt"):
    try:
        with open(file_path, 'r') as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except FileNotFoundError:
        print(Fore.RED + "Error: proxy.txt file not found!" + Style.RESET_ALL)
        return []


def generate_wallet():
    account = Account.create()
    return account.address, account._private_key.hex()


def send_faucet_request(wallet_data, proxy, max_retries=3, retry_delay=2):
    address, private_key, index, total = wallet_data
    url = "https://faucet.mars.movachain.com/api/faucet/v1/transfer"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://faucet.mars.movachain.com",
        "priority": "u=1, i",
        "referer": "https://faucet.mars.movachain.com/",
        "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    }
    data = {"to": address}
    
    
    if proxy:
        proxy_parts = proxy.split('@')
        if len(proxy_parts) == 2:
            auth, ip_port = proxy_parts
            proxy_dict = {
                "http": f"http://{auth}@{ip_port}",
                "https": f"http://{auth}@{ip_port}"
            }
        else:
            proxy_dict = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
    else:
        proxy_dict = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=data, proxies=proxy_dict, timeout=10)
            
            print(Fore.MAGENTA + f"\n[{index}/{total}] Debug: Attempt {attempt} for {address}" + Style.RESET_ALL)
            print(Fore.MAGENTA + f"Status Code: {response.status_code}" + Style.RESET_ALL)
            print(Fore.MAGENTA + f"Headers: {json.dumps(dict(response.headers), indent=2)}" + Style.RESET_ALL)
            try:
                response_body = response.json()
                print(Fore.MAGENTA + f"Body: {json.dumps(response_body, indent=2)}" + Style.RESET_ALL)
            except ValueError:
                response_body = None
                print(Fore.MAGENTA + f"Body (non-JSON): {response.text}" + Style.RESET_ALL)

            
            if response.status_code == 200 and response_body and response_body.get("data") != "false" and "err_msg" not in response_body:
                print(Fore.GREEN + f"[{index}/{total}] Success: Faucet request sent to {address} (Attempt {attempt})" + Style.RESET_ALL)
                return private_key
            else:
                error_msg = response_body.get("err_msg", "Unknown error") if response_body else f"Status code {response.status_code}"
                print(Fore.YELLOW + f"[{index}/{total}] Failed: {error_msg} for {address} (Attempt {attempt})" + Style.RESET_ALL)
                if attempt < max_retries:
                    print(Fore.YELLOW + f"Retrying in {retry_delay} seconds..." + Style.RESET_ALL)
                    time.sleep(retry_delay)
        except requests.RequestException as e:
            
            print(Fore.MAGENTA + f"\n[{index}/{total}] Debug: Attempt {attempt} for {address}" + Style.RESET_ALL)
            print(Fore.MAGENTA + f"Error: {str(e)}" + Style.RESET_ALL)
            print(Fore.YELLOW + f"[{index}/{total}] Error: Request failed for {address}: {str(e)} (Attempt {attempt})" + Style.RESET_ALL)
            if attempt < max_retries:
                print(Fore.YELLOW + f"Retrying in {retry_delay} seconds..." + Style.RESET_ALL)
                time.sleep(retry_delay)
    
    print(Fore.RED + f"[{index}/{total}] Failed: All {max_retries} attempts failed for {address}" + Style.RESET_ALL)
    return None


def save_private_key(private_key):
    
    formatted_private_key = f"0x{private_key.lstrip('0x')}"
    with open("privatekey.txt", "a") as file:
        file.write(formatted_private_key + "\n")
    print(Fore.CYAN + f"Saved private key to privatekey.txt: {formatted_private_key}" + Style.RESET_ALL)


def main():
    proxies = read_proxies()
    if not proxies:
        print(Fore.RED + "No proxies available. Exiting..." + Style.RESET_ALL)
        return

    try:
        wallet_count = int(input(Fore.YELLOW + "Enter the number of wallets to create: " + Style.RESET_ALL))
        if wallet_count <= 0:
            print(Fore.RED + "Please enter a positive number!" + Style.RESET_ALL)
            return
    except ValueError:
        print(Fore.RED + "Invalid input! Please enter a number." + Style.RESET_ALL)
        return

    
    wallets = [(generate_wallet()[0], generate_wallet()[1], i+1, wallet_count) for i in range(wallet_count)]
    
    
    max_workers = 10
    batches = [wallets[i:i + max_workers] for i in range(0, len(wallets), max_workers)]
    
    for batch in batches:
        print(Fore.YELLOW + f"\nProcessing batch of {len(batch)} wallets" + Style.RESET_ALL)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            
            future_to_wallet = {executor.submit(send_faucet_request, wallet, random.choice(proxies)): wallet for wallet in batch}
            for future in as_completed(future_to_wallet):
                wallet = future_to_wallet[future]
                address = wallet[0]
                private_key = future.result()
                if private_key:
                    save_private_key(private_key)
                else:
                    print(Fore.RED + f"Skipping private key save for {address} due to failed faucet request" + Style.RESET_ALL)

if __name__ == "__main__":
    main()
