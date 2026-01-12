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

CATEGORY_RIZ = "https://www.e.leclerc/cat/pates-riz-feculents-sauces-marque-repere#type_de_produit=P%25C3%25A2tes"
OUTPUT_CSV = "leclerc_riz.csv"

# Exemple de magasin (Leclerc fonctionne surtout par région)
MAGASIN = {
    "nom": "E.Leclerc France"
}

# =========================
# CONFIG SELENIUM
# =========================

def configure_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

# =========================
# SCRAPING RIZ
# =========================

def scrape_riz(driver, magasin):
    """
    Récupère les produits de riz (nom + prix) sur E.Leclerc
    """
    print("[INFO] Accès à la catégorie riz")
    driver.get(CATEGORY_RIZ)
    time.sleep(random.uniform(6, 8))

    soup = BeautifulSoup(driver.page_source, "html.parser")
    produits = []

    # Bloc principal contenant le prix
    price_blocks = soup.find_all(
        "div",
        class_="block-price-and-availability"
    )

    for block in price_blocks:
        try:
            # =========================
            # NOM DU PRODUIT
            # =========================
            label = block.find_previous(
                "a",
                class_="product-label"
            )
            nom = label.text.strip() if label else "N/A"

            # =========================
            # PRIX
            # =========================
            euros = block.find("div", class_="price-unit")
            cents = block.find("span", class_="price-cents")

            if euros and cents:
                prix = euros.text.strip() + "€" + cents.text.strip()
            else:
                prix = "N/A"

            produits.append({
                "produit": nom,
                "prix": prix,
                "categorie": "Riz",
                "magasin": magasin["nom"]
            })

        except Exception:
            continue

    print(f"[OK] {len(produits)} produits récupérés")
    return produits

# =========================
# SAUVEGARDE CSV
# =========================

def save_csv(data, filename):
    if not data:
        print("[ERREUR] Aucune donnée à sauvegarder")
        return

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"[OK] Fichier CSV créé : {filename}")

# =========================
# PROGRAMME PRINCIPAL
# =========================

if __name__ == "__main__":

    driver = configure_selenium()
    all_products = []

    try:
        produits = scrape_riz(driver, MAGASIN)
        all_products.extend(produits)

    finally:
        driver.quit()

    save_csv(all_products, OUTPUT_CSV)
