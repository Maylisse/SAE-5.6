from flask import Flask, request
import psycopg2
from psycopg2.extras import RealDictCursor
import html, time

APP_VERSION = f"PRODUITS_MARQUE_MAGASIN_{int(time.time())}"
PORT = 5055

PG_HOST = "localhost"
PG_PORT = 5432
PG_DB   = "SAE5.6"
PG_USER = "postgres"
PG_PASS = "2005"

app = Flask(__name__)

def esc(x):
    return html.escape("" if x is None else str(x))

def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )

@app.get("/")
def home():
    nom = (request.args.get("nom") or "").strip()
    marque = (request.args.get("marque") or "").strip()
    cat_id = (request.args.get("cat_id") or "").strip()
    magasin_id = (request.args.get("magasin_id") or "").strip()
    sort = (request.args.get("sort") or "prix_asc").strip()

    order_map = {
        "prix_asc":  "prix ASC NULLS LAST",
        "prix_desc": "prix DESC NULLS LAST",
        "nom_asc":   "nom_produit ASC",
        "nom_desc":  "nom_produit DESC",
    }
    order_by = order_map.get(sort, "prix ASC NULLS LAST")

    try:
        with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # catégories
            cur.execute("SELECT id_categorie, nom_categorie FROM categorie ORDER BY nom_categorie;")
            categories = cur.fetchall()

            # marques (dropdown)
            cur.execute("""
                SELECT DISTINCT TRIM(marque) AS marque
                FROM produit
                WHERE marque IS NOT NULL AND TRIM(marque) <> ''
                ORDER BY TRIM(marque);
            """)
            marques = [r["marque"] for r in cur.fetchall()]

            # ✅ magasins (dropdown)
            cur.execute("""
                SELECT id_magasin, nom_magasin
                FROM magasin
                ORDER BY nom_magasin;
            """)
            magasins = cur.fetchall()

            # requête produits
            # prix = MIN(op.prix) (simple) mais si magasin_id sélectionné => MIN dans ce magasin
            sql = f"""
            SELECT
              p.nom_produit,
              p.marque,
              c.id_categorie,
              c.nom_categorie,
              MIN(op.prix) AS prix
            FROM produit p
            JOIN categorie c ON c.id_categorie = p.id_categorie
            LEFT JOIN observation_prix op ON op.id_produit = p.id_produit
            WHERE 1=1
            """
            params = []

            if nom:
                sql += " AND p.nom_produit ILIKE %s"
                params.append(f"%{nom}%")

            if marque:
                sql += " AND TRIM(COALESCE(p.marque,'')) = %s"
                params.append(marque)

            if cat_id:
                try:
                    cid = int(cat_id)
                    sql += " AND c.id_categorie = %s"
                    params.append(cid)
                except ValueError:
                    cat_id = ""

            if magasin_id:
                try:
                    mid = int(magasin_id)
                    sql += " AND op.id_magasin = %s"
                    params.append(mid)
                except ValueError:
                    magasin_id = ""

            sql += f"""
            GROUP BY p.nom_produit, p.marque, c.id_categorie, c.nom_categorie
            ORDER BY {order_by}
            LIMIT 200;
            """

            cur.execute(sql, params)
            produits = cur.fetchall()

    except Exception as e:
        return f"""
        <h1>Erreur SQL/Connexion</h1>
        <pre>{esc(e)}</pre>
        <p>VERSION: {APP_VERSION}</p>
        """, 500

    # dropdown catégories
    cat_opts = ['<option value="">Toutes catégories</option>']
    for c in categories:
        sel = "selected" if str(c["id_categorie"]) == str(cat_id) else ""
        cat_opts.append(f'<option value="{c["id_categorie"]}" {sel}>{esc(c["nom_categorie"])}</option>')

    # dropdown marques
    marque_opts = ['<option value="">Toutes marques</option>']
    for m in marques:
        sel = "selected" if m == marque else ""
        marque_opts.append(f'<option value="{esc(m)}" {sel}>{esc(m)}</option>')

    # ✅ dropdown magasins
    magasin_opts = ['<option value="">Tous magasins</option>']
    for m in magasins:
        sel = "selected" if str(m["id_magasin"]) == str(magasin_id) else ""
        magasin_opts.append(
            f'<option value="{m["id_magasin"]}" {sel}>{esc(m["nom_magasin"])}</option>'
        )

    # tri
    def opt(v, label):
        sel = "selected" if sort == v else ""
        return f'<option value="{v}" {sel}>{label}</option>'

    sort_opts = "\n".join([
        opt("prix_asc", "Prix ↑"),
        opt("prix_desc", "Prix ↓"),
        opt("nom_asc", "Nom A→Z"),
        opt("nom_desc", "Nom Z→A"),
    ])

    # tableau
    rows = []
    for p in produits:
        prix = p["prix"]
        prix_txt = f"{prix:.2f} €" if prix is not None else "—"
        rows.append(
            "<tr>"
            f"<td>{esc(p['nom_produit'])}</td>"
            f"<td>{esc(p['marque'])}</td>"
            f"<td>{esc(p['nom_categorie'])}</td>"
            f"<td style='text-align:right'>{esc(prix_txt)}</td>"
            "</tr>"
        )
    if not rows:
        rows = ["<tr><td colspan='4'>Aucun résultat</td></tr>"]

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Produits</title>
<style>
body {{ font-family: system-ui, Arial; margin: 24px; }}
form {{ display:flex; gap:10px; flex-wrap:wrap; margin: 14px 0 18px; }}
input, select, button {{ padding: 8px 10px; }}
table {{ width:100%; border-collapse: collapse; }}
th, td {{ border-bottom: 1px solid #ddd; padding: 10px; text-align:left; }}
.muted {{ color:#666; font-size:0.9em; }}
.badge {{ display:inline-block; padding:4px 8px; border:1px solid #ddd; border-radius:999px; }}
</style>
</head>
<body>
  <h1>Produits</h1>
  <div class="muted"><span class="badge">VERSION: {APP_VERSION}</span> — max 200 — prix = MIN(prix)</div>

  <form method="get">
    <input name="nom" placeholder="Filtre nom produit" value="{esc(nom)}"/>
    <select name="marque">{''.join(marque_opts)}</select>
    <select name="magasin_id">{''.join(magasin_opts)}</select>
    <select name="cat_id">{''.join(cat_opts)}</select>
    <select name="sort">{sort_opts}</select>
    <button type="submit">Filtrer</button>
  </form>

  <table>
    <thead>
      <tr>
        <th>Produit</th><th>Marque</th><th>Catégorie</th><th style="text-align:right">Prix</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=PORT)
