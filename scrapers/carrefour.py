# carrefour_premiere_necessite.py
# Scrape Carrefour: magasin -> catégories (ta liste "première nécessité") -> bouton "Produits suivants"
# + extraction prix + marque + code_barre (EAN depuis URL) + dédup + export CSV
# + option: 1 fichier .py par produit

# Dépendances:
# pip install selenium webdriver-manager beautifulsoup4 pandas

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

BASE_URL = "https://www.carrefour.fr"

# ✅ Catégories Carrefour correspondant à TA liste
CATEGORIES = {
    # Alimentaire
    "alimentaire_pain": "https://www.carrefour.fr/r/pains-et-patisseries",
    "alimentaire_riz": "https://www.carrefour.fr/r/epicerie-salee/pates-riz-feculents/riz",
    "alimentaire_pates": "https://www.carrefour.fr/r/epicerie-salee/pates",
    "alimentaire_oeufs": "https://www.carrefour.fr/r/cremerie/oeufs",
    "alimentaire_fruits_legumes": "https://www.carrefour.fr/r/fruits-et-legumes",
    "alimentaire_conserves_simples": "https://www.carrefour.fr/r/epicerie-salee/conserves-et-bocaux",
    "alimentaire_huile": "https://www.carrefour.fr/r/epicerie-salee/huiles-vinaigres-et-vinaigrettes/huiles",
    "alimentaire_sucre": "https://www.carrefour.fr/r/epicerie-sucree/sucres-farines-coulis-et-preparation-gateaux/sucres-et-edulcorants",
    "alimentaire_farine": "https://www.carrefour.fr/r/epicerie-sucree/sucres-farines-coulis-et-preparation-gateaux/farines",

    # Hygiène perso
    "hygiene_savon": "https://www.carrefour.fr/r/hygiene-et-beaute/le-corps/savons",
    "hygiene_dentifrice": "https://www.carrefour.fr/r/hygiene-et-beaute/hygiene-dentaire/dentifrices",
    "hygiene_brosse_a_dents": "https://www.carrefour.fr/r/hygiene-et-beaute/hygiene-dentaire/brosses-a-dents",
    "hygiene_protections_feminines": "https://www.carrefour.fr/r/hygiene-et-beaute/hygiene-feminine-incontinence/serviettes-hygieniques",
    "hygiene_shampooing": "https://www.carrefour.fr/r/hygiene-et-beaute/les-cheveux/les-shampoings",

    # Entretien
    "entretien_liquide_vaisselle": "https://www.carrefour.fr/r/entretien-et-nettoyage/nettoyants-vaisselle/liquides-vaisselle",
    "entretien_lessive_linge": "https://www.carrefour.fr/r/entretien-et-nettoyage/lessives",
    "entretien_eau_de_javel": "https://www.carrefour.fr/r/entretien-et-nettoyage/produits-nettoyants/eaux-javel",
}

DEBUG = True
MAX_STORES = 1
MAX_LOAD_MORE_CLICKS = 40
SCROLL_PAUSE = 0.9
SCROLL_MAX_ROUNDS = 20

# ✅ Option: créer 1 fichier python par produit
WRITE_ONE_FILE_PER_PRODUCT = True

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILENAME = f"carrefour_premiere_necessite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
OUTPUT_PATH = SCRIPT_DIR / OUTPUT_FILENAME

PRODUCT_CODE_DIR = SCRIPT_DIR / "produits_code"
PRODUCT_CODE_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# SELENIUM
# =========================

def configure_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.set_page_load_timeout(60)
    return driver


# =========================
# OUTILS PRIX / CODE_BARRE / MARQUE
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


def extract_code_barre_from_url(url_produit: str):
    # ex: https://www.carrefour.fr/p/...-3560070553990
    if not url_produit:
        return None
    m = re.search(r"-(\d{8,14})(?:\?|$)", url_produit)
    return m.group(1) if m else None


def guess_marque_from_name(nom_produit: str):
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


def extract_price_from_full_card(card):
    main = card.select_one('[data-testid="product-price__amount--main"]')
    if main:
        parts = [p.get_text(strip=True) for p in main.select("p") if p.get_text(strip=True)]
        if parts:
            txt = " ".join(parts).replace("  ", " ").strip().replace(" ,", ",")
            return txt

    any_price = card.select_one('[data-testid^="product-price__amount"]')
    if any_price:
        parts = [p.get_text(strip=True) for p in any_price.select("p") if p.get_text(strip=True)]
        if parts:
            txt = " ".join(parts).replace("  ", " ").strip().replace(" ,", ",")
            return txt

    text = card.get_text(" ", strip=True)
    m = re.search(r"\d+(?:[.,]\d{1,2})?\s*€", text)
    return m.group(0) if m else None


# =========================
# MAGASINS
# =========================

def get_all_carrefour_stores(driver):
    print("[INFO] Récupération des magasins Carrefour...")
    driver.get(f"{BASE_URL}/magasin?sq=magasin&noRedirect")
    time.sleep(6)

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(4)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    stores = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/magasin/") and (
            "market-" in href or "carrefour-" in href or "contact-" in href
        ):
            stores.append({"nom": href.replace("/magasin/", "").replace("-", " ").title(),
                           "url": BASE_URL + href})

    unique = {s["url"]: s for s in stores}
    stores = list(unique.values())
    print(f"[OK] {len(stores)} magasins trouvés")
    return stores


def set_store(driver, store):
    print(f"[MAGASIN] Activation : {store['nom']}")
    driver.get(store["url"])
    time.sleep(random.uniform(3, 5))


# =========================
# SCROLL LAZY-LOAD
# =========================

def count_visible_products(driver) -> int:
    return len(driver.find_elements(By.CSS_SELECTOR, "a.product-card-click-wrapper[href]"))


def scroll_to_stabilize(driver):
    last = count_visible_products(driver)
    stable = 0

    if DEBUG:
        print(f"    [SCROLL] départ: {last} produits visibles")

    for i in range(SCROLL_MAX_ROUNDS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE + random.uniform(0.2, 0.6))
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
# EXTRACTION PRODUITS
# =========================

def extract_products_from_current_page(page_source, store, category_name):
    soup = BeautifulSoup(page_source, "html.parser")

    raw_cards = soup.select("div.product-list-card-plp-grid-new, div[class*='product-list-card'], article")
    product_cards = []
    for c in raw_cards:
        if c.select_one("a.product-card-click-wrapper[href]") and c.select_one("h3.product-card-title__text"):
            product_cards.append(c)

    rows = []
    for card in product_cards:
        nom_el = card.select_one("h3.product-card-title__text")
        nom = nom_el.get_text(strip=True) if nom_el else "N/A"

        marque = guess_marque_from_name(nom)

        a = card.select_one("a.product-card-click-wrapper[href]")
        href = a["href"] if a else ""
        url_produit = (BASE_URL + href) if href.startswith("/") else href

        code_barre = extract_code_barre_from_url(url_produit)

        prix_txt = extract_price_from_full_card(card) or "N/A"
        prix_num = parse_price_to_float(prix_txt)

        rows.append({
            "produit": nom,
            "marque": marque,
            "code_barre": code_barre,
            "prix": prix_txt,
            "prix_num": prix_num,
            "categorie": category_name,
            "magasin": store["nom"],
            "url_magasin": store["url"],
            "url_produit": url_produit
        })

    return rows


# =========================
# BOUTON "PRODUITS SUIVANTS"
# =========================

def click_load_more_products(driver) -> bool:
    old_count = count_visible_products(driver)

    selectors = [
        (By.CSS_SELECTOR, 'button[aria-label*="produits suivants" i]'),
        (By.XPATH, "//button[contains(., 'Produits suivants')]"),
        (By.CSS_SELECTOR, 'button[aria-label*="Afficher les produits" i]'),
        (By.XPATH, "//button[contains(., 'produits suivants')]"),
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

    try:
        disabled = btn.get_attribute("disabled")
        aria_disabled = btn.get_attribute("aria-disabled")
        if disabled is not None or (aria_disabled and aria_disabled.lower() == "true"):
            return False
    except Exception:
        pass

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", btn)

    try:
        WebDriverWait(driver, 25).until(lambda d: count_visible_products(d) > old_count)
        return True
    except Exception:
        return False


# =========================
# DEDUP
# =========================

def deduplicate_rows(rows):
    best = {}
    for r in rows:
        key = (r.get("url_magasin"), r.get("url_produit"))
        if key not in best:
            best[key] = r
            continue
        old = best[key]
        if old.get("prix_num") is None and r.get("prix_num") is not None:
            best[key] = r
    return list(best.values())


# =========================
# 1 FICHIER PAR PRODUIT (OPTION)
# =========================

PRODUCT_TEMPLATE = """\
# Auto-généré: {generated_at}
PRODUCT = {product_dict}

def get_product():
    return PRODUCT

if __name__ == "__main__":
    from pprint import pprint
    pprint(PRODUCT)
"""

def safe_slug(s: str, max_len=80) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_-]+", "_", s).strip("_")
    return s[:max_len] if s else "produit"

def write_product_code_file(product: dict):
    code_barre = product.get("code_barre")
    filename = f"{code_barre}.py" if code_barre else f"{safe_slug(product.get('produit'))}.py"
    path = PRODUCT_CODE_DIR / filename
    content = PRODUCT_TEMPLATE.format(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        product_dict=repr(product)
    )
    path.write_text(content, encoding="utf-8")


# =========================
# SCRAPER UNE CATÉGORIE
# =========================

def scrape_category_for_store(driver, category_url, store, category_name):
    print(f"  ↳ Catégorie : {category_name}")
    driver.get(category_url)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a.product-card-click-wrapper"))
    )
    time.sleep(random.uniform(1.0, 2.0))

    scroll_to_stabilize(driver)

    for i in range(MAX_LOAD_MORE_CLICKS):
        if DEBUG:
            print(f"    [LOAD_MORE] clic {i+1}/{MAX_LOAD_MORE_CLICKS} | visibles={count_visible_products(driver)}")
        ok = click_load_more_products(driver)
        if not ok:
            if DEBUG:
                print("    [LOAD_MORE] plus de bouton ou pas de nouveaux produits -> stop.")
            break
        scroll_to_stabilize(driver)
        time.sleep(random.uniform(0.6, 1.2))

    rows = extract_products_from_current_page(driver.page_source, store, category_name)

    before = len(rows)
    rows = deduplicate_rows(rows)
    after = len(rows)
    print(f"    → {after} produits après dédup (avant {before})")
    return rows


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print("[INFO] Le CSV sera écrit ici :", OUTPUT_PATH)
    if WRITE_ONE_FILE_PER_PRODUCT:
        print("[INFO] 1 fichier produit sera généré dans :", PRODUCT_CODE_DIR)

    driver = configure_selenium()
    all_products = []

    try:
        stores = get_all_carrefour_stores(driver)[:MAX_STORES]

        for store in stores:
            set_store(driver, store)

            for cat_name, cat_url in CATEGORIES.items():
                all_products.extend(scrape_category_for_store(driver, cat_url, store, cat_name))

            time.sleep(random.uniform(2, 4))

    finally:
        driver.quit()

    columns = ["produit", "marque", "code_barre", "prix", "prix_num",
               "categorie", "magasin", "url_magasin", "url_produit"]
    df = pd.DataFrame(all_products, columns=columns)

    if len(df) > 0:
        df = df[df["url_produit"].notna() & (df["url_produit"] != "")]
        df = df.sort_values(by=["prix_num"], na_position="last")
        df = df.drop_duplicates(subset=["url_magasin", "url_produit"], keep="first")

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print("[OK] CSV créé :", OUTPUT_PATH)
    print("[INFO] Lignes :", len(df))
    print(df.head(10))

    if WRITE_ONE_FILE_PER_PRODUCT and len(df) > 0:
        for _, row in df.iterrows():
            write_product_code_file(row.to_dict())
        print(f"[OK] {len(df)} fichiers .py générés dans: {PRODUCT_CODE_DIR}")
