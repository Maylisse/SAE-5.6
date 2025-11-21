import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.mongoDB_connection import get_database
import time

db = get_database()
products = db["products"]

def save_product(product_data):
    products.insert_one(product_data)

def main():
    product_name = "Pâtes Barilla 500g"
    product_price = 1.25
    store_name = "Carrefour"
    store_address = "Athis-Mons"
    lat = 48.706
    lng = 2.391
    category = "Epicerie"
    today_date = time.strftime("%Y-%m-%d")

    data = {
        "name": product_name,
        "price": product_price,
        "store": store_name,
        "address": store_address,
        "location": {"lat": lat, "lng": lng},
        "category": category,
        "updated_at": today_date
    }

    save_product(data)
    print("Produit ajouté ✔")

if __name__ == "__main__":
    main()
