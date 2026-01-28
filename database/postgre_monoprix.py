# import_monoprix_csv_to_postgres.py
# Import du dernier CSV Monoprix (scrapers/monoprix_premiere_necessite_*.csv) dans PostgreSQL
# ✅ même logique que ton import Carrefour
# ✅ sans ON CONFLICT
#
# Dépendances:
# pip install pandas psycopg2

import os
import glob
import pandas as pd
import psycopg2

PG_HOST = "localhost"
PG_PORT = 5432
PG_DB   = "SAE5.6"
PG_USER = "postgres"
PG_PASS = "2005"


def find_latest_csv():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.abspath(os.path.join(base_dir, ".."))
    pattern = os.path.join(project_dir, "scrapers", "monoprix_premiere_necessite_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError("Aucun CSV Monoprix trouvé dans scrapers/ (monoprix_premiere_necessite_*.csv)")
    return files[-1]


def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )


# ---------- helpers sans ON CONFLICT ----------

def get_or_create_categorie(cur, nom_categorie: str) -> int:
    cur.execute("SELECT id_categorie FROM categorie WHERE nom_categorie = %s;", (nom_categorie,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO categorie (nom_categorie) VALUES (%s) RETURNING id_categorie;",
        (nom_categorie,)
    )
    return cur.fetchone()[0]


def get_or_create_magasin(cur, nom_magasin: str, enseigne: str, url_magasin: str) -> int:
    # on identifie un magasin par son url (logique)
    cur.execute("SELECT id_magasin FROM magasin WHERE url_magasin = %s;", (url_magasin,))
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO magasin (nom_magasin, enseigne, url_magasin)
        VALUES (%s, %s, %s)
        RETURNING id_magasin;
        """,
        (nom_magasin, enseigne, url_magasin)
    )
    return cur.fetchone()[0]


def get_or_create_produit(cur, nom_produit: str, marque: str, code_barre: str, id_categorie: int) -> int:
    # si code_barres existe -> meilleur identifiant
    if code_barre:
        cur.execute("SELECT id_produit FROM produit WHERE code_barres = %s;", (code_barre,))
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO produit (nom_produit, marque, code_barres, id_categorie)
            VALUES (%s, %s, %s, %s)
            RETURNING id_produit;
            """,
            (nom_produit, marque, code_barre, id_categorie)
        )
        return cur.fetchone()[0]

    # sinon fallback: nom + marque + categorie (code_barres NULL)
    cur.execute(
        """
        SELECT id_produit
        FROM produit
        WHERE nom_produit = %s
          AND (marque IS NOT DISTINCT FROM %s)
          AND id_categorie = %s
          AND code_barres IS NULL;
        """,
        (nom_produit, marque, id_categorie)
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO produit (nom_produit, marque, code_barres, id_categorie)
        VALUES (%s, %s, NULL, %s)
        RETURNING id_produit;
        """,
        (nom_produit, marque, id_categorie)
    )
    return cur.fetchone()[0]


def insert_observation(cur, id_produit: int, id_magasin: int, prix: float, source: str):
    cur.execute(
        """
        INSERT INTO observation_prix (id_produit, id_magasin, prix, source)
        VALUES (%s, %s, %s, %s);
        """,
        (id_produit, id_magasin, prix, source)
    )


def import_csv(conn, csv_path: str):
    df = pd.read_csv(csv_path)

    # Monoprix CSV attendu (depuis ton scraper):
    # produit, categorie, prix, prix_num, url_produit, magasin, url_magasin (+ éventuellement source/scraped_at)
    df["prix_num"] = pd.to_numeric(df.get("prix_num"), errors="coerce")
    df = df.dropna(subset=["produit", "categorie", "magasin", "url_magasin", "prix_num"])

    with conn.cursor() as cur:
        for _, r in df.iterrows():
            produit = str(r["produit"]).strip()
            categorie = str(r["categorie"]).strip()
            magasin = str(r["magasin"]).strip()
            url_magasin = str(r["url_magasin"]).strip()

            # Monoprix n'a pas marque/code_barre dans ton CSV -> on met None
            marque = None
            code_barre = None

            prix = float(r["prix_num"])

            id_cat = get_or_create_categorie(cur, categorie)
            id_mag = get_or_create_magasin(cur, magasin, "Monoprix", url_magasin)
            id_prod = get_or_create_produit(cur, produit, marque, code_barre, id_cat)

            insert_observation(cur, id_prod, id_mag, prix, source="monoprix_scrape")

    conn.commit()


def main():
    csv_path = find_latest_csv()
    print("CSV utilisé :", csv_path)

    with get_conn() as conn:
        print("✅ Connexion PostgreSQL OK")
        import_csv(conn, csv_path)

    print("✅ Import Monoprix terminé avec succès")


if __name__ == "__main__":
    main()
