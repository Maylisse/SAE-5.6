# monoprix_premiere_necessite.py
# ✅ Inspiré du code Carrefour : catégories -> scroll/load -> extraction -> dédup -> CSV
# ✅ Selenium ONLY (pas d'API)
# ✅ Le CSV sort avec LES MÊMES CATÉGORIES que Carrefour (alimentaire_riz, hygiene_savon, etc.)
#
# Dépendances:
# pip install selenium webdriver-manager beautifulsoup4 pandas

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from pathlib import Path
from datetime import datetime


# =========================
# CONFIGURATION
# =========================

BASE_URL = "https://courses.monoprix.fr"
DEBUG = True

MAGASIN_NOM = "Monoprix Courses (online)"
MAGASIN_URL = BASE_URL

# Grosses catégories Monoprix (tes URLs)
MONOPRIX_TOP_PAGES = {
    "fruits_legumes": "https://courses.monoprix.fr/categories/fruits-légumes/5671998e-3a4f-4eb5-af6f-1f8295463185",
    "laitiers_oeufs_fromages": "https://courses.monoprix.fr/categories/produits-laitiers-œufs-et-fromages/aa4d679d-2d26-441d-8423-071878880b3a",
    "epicerie_salee": "https://courses.monoprix.fr/categories/epicerie-salée/1c320224-97b2-4bd5-ab62-1d19c12e2787",
    "epicerie_sucree": "https://courses.monoprix.fr/categories/epicerie-sucrée/bd800ae5-5dde-488d-b187-0d9578581d61",
    "hygiene_beaute": "https://courses.monoprix.fr/categories/hygiène-beauté/728041ac-b078-4108-bb22-3637e8a6194e",
    "entretien_nettoyage": "https://courses.monoprix.fr/categories/entretien-nettoyage/da2bb227-2133-4c55-9fcd-9e4db6fb86e7",
}

# ✅ Catégories Carrefour (identiques à ton script Carrefour)
# Chaque produit Monoprix sera classé dans UNE de ces catégories.
CARREFOUR_CATEGORIES = {
    # Alimentaire
    "alimentaire_pain": ["pain", "baguette", "boulangerie"],
    "alimentaire_riz": ["riz"],
    "alimentaire_pates": ["pate", "pâtes", "pates", "spaghetti", "penne", "coquillettes", "macaroni", "tagliatelle"],
    "alimentaire_oeufs": ["oeuf", "oeufs", "œuf", "œufs"],
    # fallback si rien d'autre match (produits frais)
    "alimentaire_fruits_legumes": [],

    "alimentaire_conserves_simples": [
        "conserve", "conserves", "boite", "boîte", "bocal", "bocaux",
        "thon", "sardine", "maïs", "mais", "haricot", "lentille", "pois chiche"
    ],
    "alimentaire_huile": ["huile"],
    "alimentaire_sucre": ["sucre"],
    "alimentaire_farine": ["farine"],

    # Hygiène perso
    "hygiene_savon": ["savon", "gel douche", "gel-douche"],
    "hygiene_dentifrice": ["dentifrice"],
    "hygiene_brosse_a_dents": ["brosse a dents", "brosse à dents", "brosses a dents", "brosses à dents", "brosse", "brosses"],
    "hygiene_protections_feminines": ["serviette", "serviettes", "tampon", "tampons", "protection", "protections"],
    "hygiene_shampooing": ["shampooing", "shampoing"],

    # Entretien
    "entretien_liquide_vaisselle": ["liquide vaisselle", "vaisselle"],
    "entretien_lessive_linge": ["lessive"],
    "entretien_eau_de_javel": ["javel", "eau de javel"],
}

# Blacklist globale (évite l’inutile)
EXCLUDE_GLOBAL = [
    "jus", "smoothie", "nectar",
    "soupe", "veloute", "velouté",
    "compote", "confiture",
    "bonbon", "confiserie",
    "gateau", "gâteau", "dessert", "patisserie", "pâtisserie", "chocolat",
    "aperitif", "apéro", "snack", "chips",
    "parfum", "maquillage", "mascara", "vernis",
    "bougie", "maison", "textile",
]

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = SCRIPT_DIR / f"monoprix_premiere_necessite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


# =========================
# SELENIUM
# =========================

def configure_selenium():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(60)
    return driver


# =========================
# NORMALISATION / PRIX
# =========================

def normalize(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("œ", "oe")
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e") \
         .replace("à", "a").replace("ù", "u").replace("ô", "o") \
         .replace("î", "i").replace("ï", "i").replace("ç", "c")
    return s

def parse_price_to_float(txt: str):
    if not txt:
        return None
    t = txt.replace("\xa0", " ").strip()
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*€", t)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


# =========================
# CLASSIFICATION -> CATEGORIES CARREFOUR
# =========================

def classify_to_carrefour_category(product_name: str) -> str | None:
    n = normalize(product_name)

    # blacklist globale
    for bad in EXCLUDE_GLOBAL:
        if normalize(bad) in n:
            return None

    # 1) catégories avec keywords (priorité aux spécifiques)
    for cat, kws in CARREFOUR_CATEGORIES.items():
        if not kws:
            continue
        for kw in kws:
            if normalize(kw) in n:
                return cat

    # 2) fallback : fruits & légumes
    return "alimentaire_fruits_legumes"


# =========================
# POPUP COOKIES (best effort)
# =========================

def accept_cookies(driver):
    xpaths = [
        "//button[contains(., 'Tout accepter')]",
        "//button[contains(., 'Accepter')]",
        "//button[contains(., \"J'accepte\")]",
        "//button[contains(., 'OK')]",
    ]
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.8)
            if DEBUG:
                print("    [POPUP] cookies acceptés")
            return
        except Exception:
            pass


# =========================
# SCROLL (Carrefour-like)
# =========================

def count_visible_products(driver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, 'a[data-test="fop-product-link"][href]'))

def scroll_to_stabilize(driver, max_rounds=30, pause=0.75):
    last = count_visible_products(driver)
    stable = 0

    if DEBUG:
        print(f"    [SCROLL] départ: {last} produits visibles")

    for i in range(max_rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause + random.uniform(0.12, 0.35))

        cur = count_visible_products(driver)
        if DEBUG:
            print(f"    [SCROLL] tour {i+1}: {cur} produits visibles")

        if cur <= last:
            stable += 1
        else:
            stable = 0

        last = cur
        if stable >= 3:
            break


# =========================
# EXTRACTION PRODUITS (ROBUSTE)
# =========================

def extract_products_from_current_page(page_source: str):
    soup = BeautifulSoup(page_source, "html.parser")
    rows = []

    for a in soup.select('a[data-test="fop-product-link"][href]'):
        href = (a.get("href") or "").split("?")[0]
        url_produit = BASE_URL + href if href.startswith("/") else href

        title_el = a.select_one('h3[data-test="fop-title"]')
        nom = (title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)).strip()
        if not nom:
            continue

        # trouver le prix dans le même bloc (remonter parents)
        price_el = None
        parent = a
        for _ in range(12):
            if not parent:
                break
            price_el = parent.select_one('span[data-test="fop-price"]')
            if price_el:
                break
            parent = parent.parent

        if not price_el:
            continue

        prix_txt = price_el.get_text(" ", strip=True).replace("\xa0", " ").strip()
        prix_num = parse_price_to_float(prix_txt)
        if prix_num is None:
            continue

        # classification Carrefour
        cat_carrefour = classify_to_carrefour_category(nom)
        if not cat_carrefour:
            continue

        rows.append({
            "produit": nom,
            "categorie": cat_carrefour,          # ✅ mêmes catégories que Carrefour
            "prix": prix_txt,
            "prix_num": prix_num,
            "url_produit": url_produit,
            "magasin": MAGASIN_NOM,
            "url_magasin": MAGASIN_URL,
        })

    # dédup
    dedup = {}
    for r in rows:
        dedup.setdefault((r["categorie"], r["url_produit"]), r)
    return list(dedup.values())


# =========================
# SCRAPER UNE PAGE (grosse catégorie Monoprix)
# =========================

def scrape_top_page(driver, page_label: str, page_url: str):
    print(f"[SCRAPE] {page_label}")
    driver.get(page_url)

    accept_cookies(driver)

    WebDriverWait(driver, 25).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-test="fop-product-link"][href]'))
    )
    time.sleep(random.uniform(0.8, 1.3))

    scroll_to_stabilize(driver, max_rounds=30)

    rows = extract_products_from_current_page(driver.page_source)
    print(f"   -> {len(rows)} produits gardés (catégories Carrefour)")
    return rows


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print("[INFO] Le CSV sera écrit ici :", OUTPUT_FILE)

    driver = configure_selenium()
    all_rows = []

    try:
        for page_label, page_url in MONOPRIX_TOP_PAGES.items():
            all_rows.extend(scrape_top_page(driver, page_label, page_url))
            time.sleep(random.uniform(0.8, 1.4))
    finally:
        driver.quit()

    df = pd.DataFrame(all_rows)
    if len(df) > 0:
        df = df.drop_duplicates(subset=["categorie", "url_produit"], keep="first")
        df = df.sort_values(by=["categorie", "prix_num"], na_position="last")

    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print("[OK] CSV créé :", OUTPUT_FILE)
    print("[INFO] Lignes :", len(df))
    print(df.head(10))
