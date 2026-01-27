# auchan_farine.py
# Auchan (recherche farine -> pagination bouton "Suivante") + extraction prix + dédup + export CSV
#
# ✅ Mêmes changements que Carrefour :
# - Ajoute "marque" (déduite du nom produit)
# - Ajoute "code_barre" (si détectable, souvent pas dans l'URL Auchan -> None)
# - Ajoute "prix_num"
# - CSV écrit dans le MÊME dossier que ce script (chemin basé sur __file__)
# - Pagination robuste via bouton "Suivante" (click JS + attente changement)
# - Dédup garde la ligne avec prix_num si possible
#
# Dépendances:
# pip install selenium webdriver-manager beautifulsoup4 pandas

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import pandas as pd
import time
import random
import re
import os
from datetime import datetime


# =========================
# CONFIG
# =========================

ENSEIGNE = "Auchan"
CATEGORY_NAME = "farine"
BASE_URL = "https://www.auchan.fr"
CATEGORY_URL_PAGE1 = "https://www.auchan.fr/recherche?text=farine&page=1"

DEBUG = True
MAX_PAGES = 30  # augmente si besoin

# CSV dans le même dossier que ce script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILENAME = f"auchan_{CATEGORY_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
OUTPUT_PATH = os.path.join(SCRIPT_DIR, OUTPUT_FILENAME)


# =========================
# SELENIUM
# =========================

def configure_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # passe à commenté si tu veux voir
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )


# =========================
# OUTILS
# =========================

def parse_price_to_float(price_txt):
    if not price_txt or price_txt == "N/A":
        return None
    t = price_txt.replace("\xa0", " ").strip()
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", t)
    if not m:
        return None
    val = m.group(1).replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def guess_marque_from_name(nom_produit: str):
    """
    Heuristique: derniers tokens en MAJUSCULE
    Ex: "Farine de blé T55 FRANCINE" -> FRANCINE
    """
    if not nom_produit or nom_produit == "N/A":
        return None

    s = nom_produit.replace("\u00a0", " ").strip()
    tokens = [t for t in s.split(" ") if t]

    tail = []
    for t in reversed(tokens):
        letters = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ]", "", t)
        if letters and letters.upper() == letters:
            tail.append(t)
            if len(tail) >= 3:
                break
        else:
            break

    if not tail:
        return None
    tail = list(reversed(tail))
    marque = " ".join(tail).strip(" ,;-")
    return marque if marque else None


def extract_code_barre_from_url(url_produit: str):
    """
    Auchan met rarement l'EAN dans l'URL.
    On tente d'extraire un bloc 8-14 chiffres si présent, sinon None.
    """
    if not url_produit:
        return None
    m = re.search(r"(\d{8,14})", url_produit)
    return m.group(1) if m else None


def scroll_page(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1.5, 2.5))


def count_cards(driver) -> int:
    return len(driver.find_elements(By.CLASS_NAME, "product-thumbnail"))


# =========================
# EXTRACTION PAGE
# =========================

def scrape_auchan_page(driver):
    # attendre cartes
    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "product-thumbnail"))
    )

    # scroll une fois (souvent lazy load)
    scroll_page(driver)

    cards = driver.find_elements(By.CLASS_NAME, "product-thumbnail")
    if DEBUG:
        print(f"[INFO] {len(cards)} produits trouvés sur la page.")

    products = []

    for card in cards:
        # Nom
        try:
            nom = card.find_element(By.CLASS_NAME, "product-thumbnail__description").text.strip()
        except Exception:
            nom = "N/A"

        # URL produit (si dispo)
        url_produit = None
        try:
            a = card.find_element(By.CSS_SELECTOR, "a[href]")
            href = a.get_attribute("href")
            url_produit = href
        except Exception:
            url_produit = None

        # Prix (plusieurs stratégies)
        prix = "N/A"

        # 1) bloc prix visible
        try:
            prix_element = card.find_element(By.CSS_SELECTOR, "div.product-price")
            txt = prix_element.text.strip()
            m = re.search(r"\d+(?:[.,]\d{1,2})?\s*€", txt)
            if m:
                prix = m.group(0)
            else:
                # parfois le texte du composant contient juste "1,35"
                if txt:
                    prix = txt
        except Exception:
            pass

        # 2) meta itemprop price
        if prix == "N/A":
            try:
                prix_meta = card.find_element(By.CSS_SELECTOR, "meta[itemprop='price']")
                val = prix_meta.get_attribute("content")
                if val:
                    prix = f"{val} €"
            except Exception:
                pass

        prix_num = parse_price_to_float(prix)
        marque = guess_marque_from_name(nom)
        code_barre = extract_code_barre_from_url(url_produit) if url_produit else None

        products.append({
            "produit": nom,
            "marque": marque,
            "code_barre": code_barre,
            "prix": prix,
            "prix_num": prix_num,
            "categorie": CATEGORY_NAME,
            "enseigne": ENSEIGNE,
            "url_produit": url_produit
        })

    return products


# =========================
# PAGINATION ("Suivante")
# =========================

def click_next_page(driver) -> bool:
    """
    Auchan: bouton "Suivante" (ou "Suivant") en bas.
    On clique via JS et on attend un changement de contenu (nb cartes / url).
    """
    old_url = driver.current_url
    old_count = count_cards(driver)

    selectors = [
        (By.XPATH, "//a[contains(., 'Suivante')]"),
        (By.XPATH, "//button[contains(., 'Suivante')]"),
        (By.XPATH, "//a[contains(., 'Suivant')]"),
        (By.XPATH, "//button[contains(., 'Suivant')]"),
        (By.CSS_SELECTOR, 'a[aria-label*="Suivant" i]'),
        (By.CSS_SELECTOR, 'button[aria-label*="Suivant" i]'),
        (By.CSS_SELECTOR, 'a[rel="next"]'),
    ]

    btn = None
    for by, sel in selectors:
        try:
            btn = WebDriverWait(driver, 6).until(EC.presence_of_element_located((by, sel)))
            break
        except Exception:
            continue

    if not btn:
        return False

    # si désactivé => stop
    try:
        if btn.get_attribute("disabled") is not None:
            return False
        aria_disabled = btn.get_attribute("aria-disabled")
        if aria_disabled and aria_disabled.lower() == "true":
            return False
    except Exception:
        pass

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(0.4)
    driver.execute_script("arguments[0].click();", btn)

    # attendre changement URL ou changement nombre de cartes
    try:
        WebDriverWait(driver, 20).until(
            lambda d: (d.current_url != old_url) or (count_cards(d) != old_count)
        )
        time.sleep(random.uniform(2.0, 3.5))
        return True
    except Exception:
        return False


# =========================
# DEDUP
# =========================

def deduplicate_rows(rows):
    """
    Dédup par (enseigne, url_produit) si url_produit dispo,
    sinon (enseigne, produit, prix)
    Priorité à prix_num non-null.
    """
    best = {}
    for r in rows:
        key = (r.get("enseigne"), r.get("url_produit")) if r.get("url_produit") else (r.get("enseigne"), r.get("produit"), r.get("prix"))
        if key not in best:
            best[key] = r
            continue
        old = best[key]
        if old.get("prix_num") is None and r.get("prix_num") is not None:
            best[key] = r
    return list(best.values())


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print("[INFO] CSV écrit ici :", OUTPUT_PATH)

    driver = configure_selenium()
    driver.set_page_load_timeout(60)

    all_products = []

    try:
        url = CATEGORY_URL_PAGE1
        for page in range(1, MAX_PAGES + 1):
            print(f"\n[PAGE {page}] {url}")
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            # extraire page
            products = scrape_auchan_page(driver)
            all_products.extend(products)

            if DEBUG:
                print(f"[INFO] cumul produits: {len(all_products)}")

            # page suivante
            if not click_next_page(driver):
                print("[INFO] Fin pagination (pas de 'Suivante').")
                break

            # si la pagination modifie directement l'URL ?page=...
            url = driver.current_url

            # petite pause anti-blocage
            time.sleep(random.uniform(1.5, 3.0))

    finally:
        driver.quit()

    # dataframe + dédup finale
    columns = ["produit", "marque", "code_barre", "prix", "prix_num", "categorie", "enseigne", "url_produit"]
    df = pd.DataFrame(all_products, columns=columns)

    if len(df) > 0:
        df = df.drop_duplicates(subset=["enseigne", "url_produit"], keep="first") if df["url_produit"].notna().any() else df
        df = df.sort_values(by=["prix_num"], na_position="last")
        df = df.drop_duplicates(subset=["enseigne", "url_produit"], keep="first")

    print("[INFO] Lignes à écrire :", len(df))
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print("[OK] CSV créé :", OUTPUT_PATH)
    print(df.head(10))
