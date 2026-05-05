import os
import string
import random
import time
import requests
import concurrent.futures
import datetime
from camoufox.sync_api import Camoufox

# Mengaktifkan mode ANSI color di Windows Terminal / CMD
os.system('')

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"

def log(tipe, pesan):
    waktu = datetime.datetime.now().strftime("%H:%M:%S")
    if tipe == "INFO":
        prefix = f"{CYAN}[INFO]{RESET}"
    elif tipe == "PROSES":
        prefix = f"{MAGENTA}[PROSES]{RESET}"
    elif tipe == "SUKSES":
        prefix = f"{GREEN}[SUKSES]{RESET}"
    elif tipe == "ERROR":
        prefix = f"{RED}[ERROR]{RESET}"
    elif tipe == "PROXY":
        prefix = f"{BLUE}[PROXY]{RESET}"
    elif tipe == "WARNING":
        prefix = f"{YELLOW}[WARNING]{RESET}"
    else:
        prefix = f"{BOLD}[{tipe}]{RESET}"
        
    print(f"[{waktu}] {prefix} {pesan}")

def check_proxy(proxy_line):
    parsed_proxy = proxy_line
    if "://" not in proxy_line:
        if proxy_line.count(":") == 3:
            ip, port, user, pwd = proxy_line.split(":")
            parsed_proxy = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            parsed_proxy = f"http://{proxy_line}"
    
    proxies_dict = {"http": parsed_proxy, "https": parsed_proxy}
    try:
        start_time = time.time()
        # Test koneksi sekaligus mengecek lokasi IP
        resp = requests.get("http://ip-api.com/json/", proxies=proxies_dict, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            country = data.get("country", "Unknown")
            latency = time.time() - start_time
            log("SUKSES", f"Proxy {proxy_line.split(':')[0]} -> Lokasi: {country} | Latensi: {latency:.2f}s")
            return proxy_line, latency, country
    except Exception:
        pass
    log("ERROR", f"Proxy {proxy_line.split(':')[0]} -> Mati/Timeout")
    return proxy_line, 999.0, "Unknown"

def get_best_proxy(proxies):
    log("PROXY", f"Menguji {len(proxies)} proxy secara bersamaan untuk mencari yang tercepat...")
    best_proxy = None
    best_time = 999.0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check_proxy, proxies))
        
    best_country = "Unknown"
    for proxy_line, response_time, country in results:
        if response_time < best_time:
            best_time = response_time
            best_proxy = proxy_line
            best_country = country
            
    if best_time == 999.0:
        log("WARNING", "Semua proxy lambat/gagal merespons! Menggunakan proxy pertama sebagai default.")
        return proxies[0]
        
    log("PROXY", f"Proxy tercepat dipilih: {best_proxy.split(':')[0]} (Lokasi: {best_country}, Latensi: {best_time:.2f}s)")
    return best_proxy

def move_to_done(email, password, status="SUKSES"):
    try:
        with open("mail.txt", "r") as f:
            lines = f.readlines()
        with open("mail.txt", "w") as f:
            for line in lines:
                if not line.strip().startswith(f"{email}:") and not line.strip().startswith(f"//{email}:"):
                    f.write(line)
        with open("done.txt", "a") as f:
            f.write(f"{email}:{password} | Status: {status}\n")
    except Exception as ex:
        log("WARNING", f"Gagal memindahkan {email} ke done.txt: {ex}")

def run():
    print(f"\n{CYAN}=== PENGATURAN BROWSER ==={RESET}")
    while True:
        jawaban = input(f"Apakah Anda ingin menjalankan bot tanpa menampilkan layar (Headless)? [y/n]: ").strip().lower()
        if jawaban in ['y', 'yes', 'ya']:
            is_headless = True
            log("INFO", "Mode Headless DIAKTIFKAN (Browser tersembunyi).")
            break
        elif jawaban in ['n', 'no', 'tidak']:
            is_headless = False
            log("INFO", "Mode Headless DINONAKTIFKAN (Browser akan tampil).")
            break
        else:
            print(f"{RED}Input tidak valid. Harap masukkan 'y' atau 'n'.{RESET}")
    print(f"{CYAN}=========================={RESET}\n")

    with open("mail.txt", "r") as f:
        # Mengabaikan baris kosong dan baris yang diawali '//' (sudah sukses)
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("//")]

    if not lines:
        log("WARNING", "Tidak ada akun baru yang perlu diproses di mail.txt!")
        return

    log("INFO", f"Total akun yang akan diproses: {len(lines)}")

    proxies = []
    if os.path.exists("proxy.txt"):
        with open("proxy.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
            
    if proxies:
        log("INFO", f"Ditemukan {len(proxies)} proxy. Akan dievaluasi sebelum digunakan.")
    else:
        log("WARNING", "Tidak ada proxy yang digunakan (proxy.txt kosong atau tidak ada).")

    for idx, line in enumerate(lines):
        if ":" not in line:
            continue
            
        email, password = line.split(":", 1)
        print("") # Baris kosong sebagai pemisah antar akun
        log("INFO", f"Memulai proses untuk email: {BOLD}{email}{RESET}")

        proxy_settings = None
        if proxies:
            proxy_line = get_best_proxy(proxies)
            if "://" in proxy_line:
                proxy_settings = {"server": proxy_line}
            elif proxy_line.count(":") == 3:
                ip, port, user, pwd = proxy_line.split(":")
                proxy_settings = {
                    "server": f"http://{ip}:{port}",
                    "username": user,
                    "password": pwd
                }
            elif proxy_line.count(":") == 1:
                proxy_settings = {"server": f"http://{proxy_line}"}
            else:
                proxy_settings = {"server": proxy_line}
                
            log("PROXY", f"Menjalankan dengan proxy: {proxy_settings['server']}")

        kwargs = {"headless": is_headless, "humanize": True}
        if proxy_settings:
            kwargs["proxy"] = proxy_settings
            kwargs["geoip"] = True

        with Camoufox(**kwargs) as browser:
            context = browser.new_context()
            page = context.new_page()
            registered = False
            
            try:
                log("PROSES", "Membuka halaman Codebuddy...")
                page.goto("https://www.codebuddy.ai/login")
                
                log("PROSES", "Menekan tombol Sign up with Google di dalam iframe...")
                frame = page.frame_locator('iframe[title="login-iframe"]')
                frame.get_by_role("link", name="Sign up with Google").click(timeout=15000)
                
                log("PROSES", "Menekan tombol Confirm di dalam iframe...")
                try:
                    frame.get_by_role("button", name="Confirm").click(timeout=5000)
                except Exception:
                    pass
                
                log("PROSES", "Mengisi email Google...")
                page.wait_for_selector('input[type="email"]', timeout=30000)
                page.locator('input[type="email"]').fill(email)
                page.locator('input[type="email"]').press("Enter")
                
                log("PROSES", "Mengisi password Google...")
                page.wait_for_selector('input[type="password"]', state="visible", timeout=30000)
                page.locator('input[type="password"]').fill(password)
                page.locator('input[type="password"]').press("Enter")
                
                log("PROSES", "Menunggu persetujuan Google dan redirect ke Codebuddy...")
                for _ in range(30):
                    if "codebuddy.ai" in page.url and "google.com" not in page.url:
                        break
                        
                    try:
                        # Metode 1: Tekan Enter
                        page.keyboard.press("Enter")
                    except:
                        pass
                        
                    try:
                        # Metode 2: Klik tombol utama (class visual)
                        primary_btn = page.locator('button.VfPpkd-LgbsSe-OWXEXe-k8QpJ')
                        if primary_btn.count() > 0 and primary_btn.last.is_visible():
                            primary_btn.last.click(timeout=1000)
                    except:
                        pass
                        
                    try:
                        btn_understand = page.get_by_role("button", name="I understand")
                        if btn_understand.count() > 0 and btn_understand.first.is_visible():
                            btn_understand.first.click(timeout=1000)
                    except:
                        pass
                        
                    try:
                        btn_continue = page.get_by_role("button", name="Continue")
                        if btn_continue.count() > 0 and btn_continue.first.is_visible():
                            btn_continue.first.click(timeout=1000)
                    except:
                        pass
                        
                    page.wait_for_timeout(500)
                
                page.wait_for_url(lambda url: "codebuddy.ai" in url and "google.com" not in url, timeout=60000)
                registered = True
                
                log("PROSES", "Memproses Region dan memuat Profil...")
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                except:
                    pass
                    
                profil_diklik = False
                for _ in range(60):
                    try:
                        if page.locator(".t-input").count() > 0 and page.locator(".t-input").first.is_visible():
                            log("PROSES", "Memilih region (Singapura)...")
                            page.locator(".t-input").first.click(force=True)
                            page.wait_for_timeout(500)
                            page.get_by_text("Singapore", exact=False).first.click(force=True)
                            page.wait_for_timeout(500)
                            page.get_by_text("Submit", exact=False).first.click(force=True)
                            log("INFO", "Selesai submit region, jeda 3 detik...")
                            page.wait_for_timeout(3000)
                            
                        btn_email = page.get_by_role("button", name=email.lower())
                        if btn_email.count() > 0 and btn_email.first.is_visible():
                            btn_email.first.click(force=True)
                            profil_diklik = True
                            break
                            
                        btn_text = page.get_by_text(email.lower(), exact=False)
                        if btn_text.count() > 0 and btn_text.first.is_visible():
                            btn_text.first.click(force=True)
                            profil_diklik = True
                            break
                            
                        btn_avatar = page.locator(".user-dropdown, .avatar, img[alt*='avatar']")
                        if btn_avatar.count() > 0 and btn_avatar.first.is_visible():
                            btn_avatar.first.click(force=True)
                            profil_diklik = True
                            break
                            
                    except Exception:
                        pass
                        
                    page.wait_for_timeout(1000)
                    
                if not profil_diklik:
                    raise Exception("Gagal menemukan tombol profil setelah ditunggu.")
                    
                # Gunakan force=True agar tidak diblokir oleh halaman loading atau overlay
                try:
                    page.get_by_text("Profile", exact=False).first.click(timeout=5000, force=True)
                except:
                    pass
                
                log("PROSES", "Membuka menu Access Key...")
                try:
                    page.get_by_role("link", name="Access Keys").click(timeout=5000, force=True)
                except:
                    page.locator("a[href*='key'], a[href*='access']").first.click(timeout=5000, force=True)
                
                log("PROSES", "Membuat Access Key baru...")
                page.get_by_role("button", name="Create Key").click(force=True)
                
                random_name = ''.join(random.choices(string.ascii_letters, k=8))
                
                page.get_by_role("textbox", name="Enter Chinese, English,").fill(random_name)
                page.get_by_role("combobox").select_option("-1")
                page.get_by_role("button", name="Confirm").click(force=True)
                
                page.wait_for_timeout(3000)
                
                log("PROSES", "Mengekstrak Access Key...")
                key = ""
                try:
                    # Tunggu input kotak access key muncul
                    page.wait_for_selector('.create-success-dialog-key-input', timeout=15000)
                    key = page.locator('.create-success-dialog-key-input').input_value()
                except Exception:
                    pass
                
                # Fallback Regex jika struktur class berubah
                if not key:
                    try:
                        import re
                        page.wait_for_timeout(2000)
                        raw_html = page.content()
                        # Cari ck_ dengan panjang minimal 40 karakter
                        match = re.search(r'(ck_[A-Za-z0-9_\-\.]{40,})', raw_html)
                        if match:
                            key = match.group(1)
                    except:
                        pass
                
                # Eksekusi tombol copy
                try:
                    page.locator('.create-success-dialog-copy-btn').click(timeout=2000)
                except:
                    pass
                
                with open("result.txt", "a") as rf:
                    rf.write(f"{email}:{key}\n")
                
                log("SUKSES", f"Key tersimpan untuk {email}")
                move_to_done(email, password, "SUKSES")
                    
            except Exception as e:
                log("ERROR", f"Gagal memproses {email} | Error: {e}")
                if registered:
                    log("WARNING", f"Akun {email} sudah menembus tahap Login. Dipindahkan ke done.txt agar tidak error berulang.")
                    move_to_done(email, password, "GAGAL_SEBAGIAN (Sudah Terdaftar)")
            
            finally:
                context.close()

    print("")
    log("INFO", "Semua proses selesai.")

if __name__ == "__main__":
    run()
