from database.mongoDB_connection import get_database

# Connexion
db = get_database()

# Collection "products"
collection = db["produit"]

# Test d'insertion
test_doc = {"name": "Produit Test", "price": 2.50}
result = collection.insert_one(test_doc)

print("Insertion OK, ID du document :", result.inserted_id)
