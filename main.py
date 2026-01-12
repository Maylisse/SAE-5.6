from scrapers.carrefour import scrape_all, sauvegarder_dans_csv
from database.mongoDB import sauvegarder_dans_mongodb

def main():
    print("[INFO] Début du scraping...")
    produits = scrape_all()

    if produits:
        print(f"\n[INFO] {len(produits)} produits ont été récupérés.")

        # Sauvegarde dans un fichier CSV
        sauvegarder_dans_csv(produits, "carrefour_produits.csv")

        # Sauvegarde dans MongoDB
        sauvegarder_dans_mongodb(produits)
    else:
        print("[ERREUR] Aucune donnée n'a été récupérée.")

if __name__ == "__main__":
    main()
