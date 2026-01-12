from pymongo import MongoClient

class DatabaseManager:
    @staticmethod
    def sauvegarder_dans_mongodb(donnees, uri="mongodb://localhost:27017/", db_name="carrefour", collection_name="produits"):
        """Sauvegarde les données dans une base de données MongoDB."""
        if not donnees:
            print("[ERREUR] Aucune donnée à sauvegarder.")
            return

        try:
            client = MongoClient(uri)
            db = client[db_name]
            collection = db[collection_name]

            # Insertion des données
            result = collection.insert_many(donnees)
            print(f"[SUCCÈS] {len(result.inserted_ids)} données insérées dans MongoDB (Collection: {collection_name})")

            # Vérification des données insérées
            count = collection.count_documents({})
            print(f"[INFO] Nombre total de documents dans la collection : {count}")

            client.close()
        except Exception as e:
            print(f"[ERREUR] Erreur lors de l'insertion dans MongoDB : {e}")
