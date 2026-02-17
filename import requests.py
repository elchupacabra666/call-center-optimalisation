import requests
from bs4 import BeautifulSoup
import csv
import time
from urllib.parse import urljoin

# ==========================================
# NASTAVENÍ (ZDE UPRAV)
# ==========================================

# 1. Sem vlož ten dlouhý řetězec Cookie z prohlížeče
MOJE_COOKIE = "safeDevice2FA=v1.1%3A179351%3A20260107194659%3A9aba0db21d51cc0b8a952b45fdc13469c5efade7; UISAuth=jhTaD0kGGZXx3qj1Ko3f8QfYrKwuLeMjCAGBOHqZtJPA"

# URL stránky se seznamem prací (Jana Sekničková)
BASE_URL = "https://insis.vse.cz/auth/lide/clovek.pl?id=51290;zalozka=13;lang=cz"

# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": MOJE_COOKIE
}

def vycisti_text(text):
    """Odstraní nadbytečné mezery a nové řádky."""
    if text:
        return " ".join(text.split())
    return ""

def ziskej_detail_prace(url):
    """Stáhne detail práce a vytáhne abstrakt a klíčová slova."""
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        info = {
            "url": url,
            "abstrakt": "Nenalezeno",
            "klicova_slova": "Nenalezeno"
        }

        # InSIS používá tabulky. Hledáme buňku <td> s nápisem "Abstrakt:"
        # a vezmeme obsah té vedlejší buňky.
        vsechny_td = soup.find_all('td')
        
        for i, td in enumerate(vsechny_td):
            text_bunky = td.get_text(strip=True)
            
            # Hledání Abstraktu
            if "Abstrakt:" in text_bunky:
                # Obsah je v následující buňce (i+1)
                if i + 1 < len(vsechny_td):
                    info["abstrakt"] = vycisti_text(vsechny_td[i+1].get_text())
            
            # Hledání Klíčových slov
            elif "Klíčová slova:" in text_bunky:
                if i + 1 < len(vsechny_td):
                    info["klicova_slova"] = vycisti_text(vsechny_td[i+1].get_text())

        return info

    except Exception as e:
        print(f"Chyba u {url}: {e}")
        return None

def main():
    print("Připojuji se k InSIS...")
    response = requests.get(BASE_URL, headers=HEADERS)
    
    # Kontrola přihlášení
    if "přihlášení" in response.text.lower() or "login" in response.url:
        print("CHYBA: Neplatné Cookie! Skript byl přesměrován na přihlášení.")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Najít tabulku se seznamem prací
    tabulka = soup.find('table', id='tmtab_1')
    if not tabulka:
        print("Tabulka prací nenalezena. Jsi na správné stránce?")
        return

    # 2. Najít všechny odkazy na detaily prací
    # Hledáme odkazy, které obsahují 'zp=' (závěrečná práce) a nejsou to soubory (download)
    odkazy_ke_stazeni = []
    radky = tabulka.find_all('tr')
    
    for radek in radky:
        # Hledáme ikonu lupy nebo odkazu na detail
        for odkaz in radek.find_all('a', href=True):
            href = odkaz['href']
            # Filtrujeme jen odkazy na detail (zp=) a ignorujeme stahování souborů
            if 'zp=' in href and 'download' not in href and 'zobraz_zp' not in href:
                full_url = urljoin("https://insis.vse.cz/auth/lide/", href)
                odkazy_ke_stazeni.append(full_url)

    # Odstraníme duplicity
    odkazy_ke_stazeni = list(set(odkazy_ke_stazeni))
    print(f"Nalezeno {len(odkazy_ke_stazeni)} prací. Začínám stahovat detaily...")

    # 3. Projít detaily a uložit
    vysledna_data = []
    
    for index, url in enumerate(odkazy_ke_stazeni):
        print(f"Zpracovávám ({index+1}/{len(odkazy_ke_stazeni)})...")
        detail = ziskej_detail_prace(url)
        
        # Abychom měli i název a autora (to se lépe tahá z detailu než ze seznamu)
        # Zkusíme to v rychlosti vytáhnout taky, pokud to tam je
        if detail:
            vysledna_data.append(detail)
        
        time.sleep(0.5) # Slušnost k serveru

    # 4. Uložení do CSV
    nazev_souboru = "call_centrum_data.csv"
    keys = ["url", "abstrakt", "klicova_slova"]
    
    with open(nazev_souboru, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(vysledna_data)

    print(f"\nHOTOVO! Data uložena do souboru: {nazev_souboru}")
    print("Teď můžeš otevřít CSV a hledat slova jako 'call centrum', 'směny', 'poptávka'.")

if __name__ == "__main__":
    main()