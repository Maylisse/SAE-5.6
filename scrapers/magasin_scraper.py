from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

def configure_selenium():
    """Configure Selenium pour simuler un navigateur Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    return driver

def scrape_magasins_carrefour():
    """Scrape la liste des magasins Carrefour en France."""
    driver = configure_selenium()

    try:
        url = "https://www.carrefour.fr/magasins"
        print(f"[INFO] Accès à la page des magasins : {url}")
        driver.get(url)
        time.sleep(5)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        magasins = []

        # Trouver les éléments contenant les magasins
        magasin_elements = soup.find_all("div", class_="store-card")

        for element in magasin_elements:
            try:
                nom = element.find("h3").text.strip()
                adresse = element.find("p", class_="store-address").text.strip()
                magasins.append({"nom": nom, "adresse": adresse})
            except Exception as e:
                print(f"[ERREUR] Erreur lors de l'extraction d'un magasin : {e}")

        print(f"[SUCCÈS] {len(magasins)} magasins extraits.")
        return magasins

    except Exception as e:
        print(f"[ERREUR] Une erreur est survenue : {e}")
        return []

    finally:
        driver.quit()
