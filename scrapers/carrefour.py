from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# =========================
# CONFIGURATION
# =========================

CATEGORIES = {
    "beurre": "https://www.carrefour.fr/s?q=beurre++"
}

OUTPUT_CSV = "carrefour_prix_par_magasin.csv"
BASE_URL = "https://www.carrefour.fr"


# =========================
# SELENIUM
# =========================

def configure_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    # User-agent réaliste
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )


# =========================
# 1️⃣ RÉCUPÉRER TOUS LES MAGASINS
# =========================

def get_all_carrefour_stores(driver):
    print("[INFO] Récupération des magasins Carrefour...")
    driver.get(f"{BASE_URL}/magasin?sq=magasin&noRedirect")
    time.sleep(8)

    # Scroll pour forcer le chargement JS
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(6)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    stores = []

    links = soup.find_all("a", href=True)

    for a in links:
        href = a["href"]

        # Filtrage strict sur les URLs des magasins
        if href.startswith("/magasin/") and (
            "market-" in href or "carrefour-" in href or "contact-" in href
        ):
            url = BASE_URL + href
            nom = href.replace("/magasin/", "").replace("-", " ").title()
            stores.append({
                "nom": nom,
                "url": url
            })

    # Supprimer doublons
    unique = {s["url"]: s for s in stores}
    stores = list(unique.values())

    print(f"[OK] {len(stores)} magasins trouvés")
    return stores


# =========================
# 2️⃣ ACTIVER UN MAGASIN
# =========================

def set_store(driver, store):
    print(f"[MAGASIN] Activation : {store['nom']}")
    driver.get(store["url"])
    time.sleep(random.uniform(4, 6))


# =========================
# 3️⃣ SCRAPER UNE CATÉGORIE POUR UN MAGASIN
# =========================

def scrape_category_for_store(driver, category_url, store, category_name):
    print(f"  ↳ Catégorie : {category_name}")
    driver.get(category_url)
    time.sleep(random.uniform(4, 6))

    soup = BeautifulSoup(driver.page_source, "html.parser")
    produits = []

   def scrape_category_for_store(driver, category_url, store, category_name):
    print(f"  ↳ Catégorie : {category_name}")
    driver.get(category_url)
    time.sleep(random.uniform(4, 6))

    soup = BeautifulSoup(driver.page_source, "html.parser")
    produits = []

    cards = soup.find_all("a", class_="product-card-click-wrapper")

    for card in cards:
        # NOM DU PRODUIT
        nom = card.find(
            "p",
            class_="product-card-title__text"
        )

        # PRIX PRINCIPAL
        prix = card.find(
            "span",
            class_="product-price__amount product-price__amount--main"
        )

        produits.append({
            "produit": nom.text.strip() if nom else "N/A",
            "prix": prix.text.strip() if prix else "N/A",
            "categorie": category_name,
            "magasin": store["nom"],
            "url_magasin": store["url"]
        })

    print(f"    → {len(produits)} produits récupérés")
    return produits

        produits.append({
            "produit": nom.text.strip() if nom else "N/A",
            "prix": prix.text.strip() if prix else "N/A",
            "categorie": category_name,
            "magasin": store["nom"],
            "url_magasin": store["url"]
        })

    print(f"    → {len(produits)} produits récupérés")
    return produits


# =========================
# PROGRAMME PRINCIPAL
# =========================

if __name__ == "__main__":

    driver = configure_selenium()
    all_products = []

    try:
        # 1️⃣ Récupérer tous les magasins
        stores = get_all_carrefour_stores(driver)

        # ⚠️ Limiter pour test rapide (éviter blocage IP)
        stores = stores[:5]

        # 2️⃣ Parcourir chaque magasin
        for store in stores:
            set_store(driver, store)

            # 3️⃣ Scraper chaque catégorie
            for cat_name, cat_url in CATEGORIES.items():
                produits = scrape_category_for_store(
                    driver,
                    cat_url,
                    store,
                    cat_name
                )
                all_products.extend(produits)

            # Pause anti-blocage
            time.sleep(random.uniform(6, 10))

    finally:
        driver.quit()

    # =========================
    # SAUVEGARDE CSV
    # =========================

    if all_products:
        df = pd.DataFrame(all_products)
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
        print(f"\n[OK] CSV généré : {OUTPUT_CSV}")
    else:
        print("[ERREUR] Aucune donnée récupérée")
