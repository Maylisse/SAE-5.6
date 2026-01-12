from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import random

# =========================
# Configuration générale
# =========================

# Catégories et localisations à scraper
CATEGORIES = {
    "pates": "https://www.carrefour.fr/r/epicerie-salee/pates"
}

LOCALISATIONS = [
    "75000 Paris", "13000 Marseille", "69000 Lyon", "31000 Toulouse",
    "34000 Montpellier", "33000 Bordeaux", "59000 Lille", "67000 Strasbourg"
]

# Nom du fichier de sortie
OUTPUT_CSV = "carrefour_produits.csv"

def configure_selenium():
    """
    Configure Selenium pour simuler un vrai navigateur Chrome.
    """
    chrome_options = Options()

    # Mode headless : désactivez pour déboguer
    chrome_options.add_argument("--headless")

    # Options pour améliorer la stabilité
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    # User-agent pour imiter un vrai utilisateur
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    # Désactivation du chargement des images pour accélérer la page
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialisation du driver Chrome
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    return driver

def scrape_carrefour(url, localisation=None):
    """
    Récupère les noms et les prix des produits présents sur la page Carrefour.
    """
    driver = configure_selenium()

    try:
        print(f"[INFO] Accès à la page : {url}")
        driver.get(url)

        # Temps d'attente pour laisser la page se charger
        time.sleep(random.uniform(3, 5))

        # Récupération du code HTML de la page
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Liste des produits
        produits = []

        # Recherche des cartes produits
        product_cards = soup.find_all("a", class_="product-card-click-wrapper")

        for card in product_cards:
            try:
                # Récupération du nom du produit
                nom_element = card.find("h3", class_="product-card-title__text")
                nom = nom_element.text.strip() if nom_element else "N/A"

                # Récupération du prix du produit
                prix_element = card.find_next("span", class_="product-price__content")
                prix = prix_element.text.strip() if prix_element else "N/A"

                # Ajout du produit dans la liste
                produits.append({
                    "nom": nom,
                    "prix": prix,
                    "categorie": url.split("/")[-1],  # Extrait la catégorie depuis l'URL
                    "localisation": localisation if localisation else "Non spécifiée"
                })
            except Exception as e:
                print(f"[ERREUR] Erreur lors de l'extraction d'un produit : {e}")

        print(f"[SUCCÈS] {len(produits)} produits extraits pour {localisation if localisation else 'toutes les localisations'}.")
        return produits

    except Exception as e:
        print(f"[ERREUR] Une erreur est survenue : {e}")
        return []

    finally:
        # Fermeture du navigateur
        driver.quit()

def sauvegarder_dans_csv(donnees, nom_fichier):
    """
    Sauvegarde les données dans un fichier CSV.
    """
    if not donnees:
        print("[ERREUR] Aucune donnée à sauvegarder.")
        return

    df = pd.DataFrame(donnees)
    df.to_csv(nom_fichier, index=False, encoding="utf-8")
    print(f"[SUCCÈS] Données sauvegardées dans {nom_fichier}")

# =========================
# Programme principal
# =========================

if __name__ == "__main__":
    # Liste pour stocker tous les produits
    tous_les_produits = []

    # Scraping par catégorie
    for categorie, url in CATEGORIES.items():
        print(f"\n[SCRAPING] Catégorie : {categorie}")

        # Scraping sans localisation (par défaut)
        produits = scrape_carrefour(url)
        tous_les_produits.extend(produits)

        # Scraping par localisation
        for localisation in LOCALISATIONS:
            print(f"\n[SCRAPING] Localisation : {localisation}")
            produits_localises = scrape_carrefour(url, localisation)
            tous_les_produits.extend(produits_localises)
            time.sleep(random.uniform(2, 5))  # Délai entre les requêtes

    # Sauvegarde des données
    if tous_les_produits:
        sauvegarder_dans_csv(tous_les_produits, OUTPUT_CSV)
