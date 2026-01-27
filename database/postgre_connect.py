import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# =========================
# CONFIG DB (à mettre en variables d'environnement idéalement)
# =========================
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB   = os.getenv("PG_DB", "postgres")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASS = os.getenv("PG_PASS", "postgres")

CSV_PATH = "carrefour_premiere_necessite.csv"



def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )


def ensure_category(cur, nom_categorie: str) -> int:
    cur.execute("""
        INSERT INTO categorie (nom_categorie)
        VALUES (%s)
        ON CONFLICT (nom_categorie) DO UPDATE SET nom_categorie = EXCLUDED.nom_categorie
        RETURNING id_categorie;
    """, (nom_categorie,))
    return cur.fetchone()[0]


def upsert_magasin(cur, nom_magasin: str, enseigne: str, url_magasin: str) -> int:
    # nécessite la colonne magasin.url_magasin + unique index uq_magasin_url
    cur.execute("""
        INSERT INTO magasin (nom_magasin, enseigne, url_magasin)
        VALUES (%s, %s, %s)
        ON CONFLICT (url_magasin) DO UPDATE
          SET nom_magasin = EXCLUDED.nom_magasin,
              enseigne = EXCLUDED.enseigne
        RETURNING id_magasin;
    """, (nom_magasin, enseigne, url_magasin))
    return cur.fetchone()[0]


def upsert_produit(cur, nom_produit: str, marque: str, code_barres: str, id_categorie: int) -> int:
    # 1) si code_barres connu -> upsert sur code_barres
    if code_barres:
        cur.execute("""
            INSERT INTO produit (nom_produit, marque, code_barres, id_categorie)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code_barres) DO UPDATE
              SET nom_produit = EXCLUDED.nom_produit,
                  marque = EXCLUDED.marque,
                  id_categorie = EXCLUDED.id_categorie
            RETURNING id_produit;
        """, (nom_produit, marque, code_barres, id_categorie))
        return cur.fetchone()[0]

    # 2) sinon fallback: unique nom+marque+cat (index uq_produit_nom_marque_cat_when_no_barcode)
    cur.execute("""
        INSERT INTO produit (nom_produit, marque, code_barres, id_categorie)
        VALUES (%s, %s, NULL, %s)
        ON CONFLICT (nom_produit, marque, id_categorie)
        WHERE produit.code_barres IS NULL
        DO UPDATE SET nom_produit = EXCLUDED.nom_produit
        RETURNING id_produit;
    """, (nom_produit, marque, id_categorie))
    return cur.fetchone()[0]


def insert_observation(cur, id_produit: int, id_magasin: int, prix: float, source: str = "carrefour_scrape"):
    cur.execute("""
        INSERT INTO observation_prix (id_produit, id_magasin, prix, source)
        VALUES (%s, %s, %s, %s);
    """, (id_produit, id_magasin, prix, source))


def main():
    df = pd.read_csv(CSV_PATH)

    # Normalisation minimale
    df["prix_num"] = pd.to_numeric(df.get("prix_num"), errors="coerce")
    df = df.dropna(subset=["url_magasin", "magasin", "categorie", "produit"])
    df = df[df["prix_num"].notna()]  # on n'importe que les prix exploitables

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Important: ON CONFLICT(nom_categorie) nécessite une contrainte unique.
            # Si tu n'en as pas, ajoute-la:
            cur.execute("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes WHERE indexname = 'uq_categorie_nom'
                  ) THEN
                    CREATE UNIQUE INDEX uq_categorie_nom ON categorie(nom_categorie);
                  END IF;
                END $$;
            """)

            # Import ligne par ligne (simple et fiable)
            for _, r in df.iterrows():
                cat_name = str(r["categorie"]).strip()
                id_cat = ensure_category(cur, cat_name)

                nom_mag = str(r["magasin"]).strip()
                url_mag = str(r["url_magasin"]).strip()
                id_mag = upsert_magasin(cur, nom_mag, "Carrefour", url_mag)

                nom_prod = str(r["produit"]).strip()
                marque = None if pd.isna(r.get("marque")) else str(r.get("marque")).strip()
                code_barre = None if pd.isna(r.get("code_barre")) else str(r.get("code_barre")).strip()

                id_prod = upsert_produit(cur, nom_prod, marque, code_barre, id_cat)

                prix = float(r["prix_num"])
                insert_observation(cur, id_prod, id_mag, prix)

        conn.commit()

    print("[OK] Import terminé.")


if __name__ == "__main__":
    main()
