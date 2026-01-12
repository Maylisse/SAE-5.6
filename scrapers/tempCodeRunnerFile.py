from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time

# =========================
# Configuration générale
# =========================

# URL de la page Carrefour à scrapper
URL = "https://www.carrefour.fr/r/epicerie-salee/pates"

# Nom du fichier de sortie
OUTPUT_CSV = "carrefour_pates.csv"


def configure_selenium():
    """
    Configure Selenium pour simuler un vrai navigateur Chrome.
    Cela permet d'éviter certains blocages liés au scraping.
    """
    chrome_options = Options()

    # Mode headless : le navigateur ne s'affiche pas à l'écran
    # (à commenter si on veut voir le navigateur pour déboguer)
    chrome_options.add_argument("--headless")

    # Options pour améliorer la stabilité
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Taille de la fenêtre pour simuler un écran classique
    chrome_options.add_argument("--window-size=1920,1080")

    # User-agent pour imiter un vrai utilisateur
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )

    # Désactivation du chargement des images pour accélérer la page
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialisation du driver Chrome avec webdriver-manager
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    return driver


def scrape_carrefour(url):
    """
    Récupère les noms et les prix des produits présents sur la page Carrefour.
    """
    driver = configure_selenium()

    try:
        print(f"[INFO] Accès à la page : {url}")
        driver.get(url)

        # Temps d'attente pour laisser la page se charger complètement
        time.sleep(5)

        # Récupération du code HTML de la page
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Liste qui contiendra tous les produits
        produits = []

        # Recherche de toutes les cartes produits
        product_cards = soup.find_all("a", class_="product-card-click-wrapper")

        for card in product_cards:
            # Récupération du nom du produit
            nom_element = card.find("h3", class_="product-card-title__text")
            nom = nom_element.text.strip() if nom_element else "N/A"

            # Récupération du prix du produit
            prix_element = card.find_next("span", class_="product-price__content")
            prix = prix_element.text.strip() if prix_element else "N/A"

            # Ajout du produit dans la liste
            produits.append({
                "nom": nom,
                "prix": prix
            })

        print(f"[SUCCÈS] {len(produits)} produits extraits.")
        return produits

    except Exception as e:
        print(f"[ERREUR] Une erreur est survenue : {e}")
        return []

    finally:
        # Fermeture du navigateur dans tous les cas
        driver.quit()


def sauvegarder_dans_csv(donnees, nom_fichier):
    """
    Sauvegarde les données récupérées dans un fichier CSV.
    """
    if not donnees:
        print("[ERREUR] Aucune donnée à sauvegarder.")
        return

    # Conversion des données en DataFrame pandas
    df = pd.DataFrame(donnees)

    # Export vers un fichier CSV
    df.to_csv(nom_fichier, index=False, encoding="utf-8")

    print(f"[SUCCÈS] Données sauvegardées dans {nom_fichier}")


# =========================
# Programme principal
# =========================

if __name__ == "__main__":
    # Lancement du scraping
    produits = scrape_carrefour(URL)

    # Sauvegarde des données si elles existent
    if produits:
        sauvegarder_dans_csv(produits, OUTPUT_CSV)
