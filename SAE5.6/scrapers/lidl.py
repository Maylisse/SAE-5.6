import requests
from bs4 import BeautifulSoup
import time

def scraper_lidl():
    url = "https://www.lidl.fr/c/catalogue-semaine/"

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

    if response.status_code != 200:
        print("Erreur HTML Lidl:", response.status_code)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    produits_html = soup.select(".product-grid__item")

    produits = []

    for item in produits_html:
        nom = item.select_one(".product-title")
        prix = item.select_one(".price")
        image = item.select_one("img")

        produit = {
            "nom": nom.text.strip() if nom else None,
            "prix": prix.text.strip() if prix else None,
            "image": image["src"] if image else None,
            "source": "lidl",
            "timestamp": time.time()
        }

        produits.append(produit)

    return produits


if __name__ == "__main__":
    print(scraper_lidl())
# scraper_lidl.py