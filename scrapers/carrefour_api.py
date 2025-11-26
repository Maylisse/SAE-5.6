from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

def scrape_carrefour_shadow():
    url = "https://www.carrefour.fr/s?q=Oeufs"

    options = Options()
    # IMPORTANT : pas de headless
    # options.add_argument("--headless")  # ❌ NE PAS activer
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    print("🔄 Ouverture de la page…")
    driver.get(url)
    time.sleep(5)

    # 🍪 cookies
    try:
        cookie_btn = driver.find_element("css selector", "#onetrust-accept-btn-handler")
        cookie_btn.click()
        print("🍪 Cookies acceptés.")
        time.sleep(3)
    except:
        print("⚠️ Pas de popup cookies détecté")

    # Attendre le JS Carrefour
    time.sleep(4)

    print("🧠 Injection JS pour lire le Shadow DOM…")

    script = """
    function deepQuerySelectorAll(selector) {
        const result = [];
        function collect(node) {
            if (node.nodeType === 1) { 
                try {
                    node.querySelectorAll(selector).forEach(el => result.push(el));
                } catch(e) {}
                if (node.shadowRoot) collect(node.shadowRoot);
                node.childNodes.forEach(child => collect(child));
            }
        }
        collect(document);
        return result;
    }

    const cards = deepQuerySelectorAll("[data-testid='product-card']");
    const out = [];

    for (let c of cards) {
        let name = "";
        let price = "";
        let img = "";

        try {
            let n = c.querySelector("[data-testid='product-card-title']");
            if (n) name = n.innerText.trim();
        } catch(e) {}

        try {
            let p = c.querySelector("[data-testid='product-card-price-amount']");
            if (p) price = p.innerText.trim();
        } catch(e) {}

        try:
            let i = c.querySelector("img");
            if (i) img = i.src;
        } catch(e) {}

        out.push({name, price, img});
    }

    return JSON.stringify(out);
    """

    data = driver.execute_script(script)
    products = json.loads(data)

    print(f"📦 Produits trouvés : {len(products)}")

    for p in products:
        print("\n-----")
        print("🛒 Nom :", p["name"])
        print("💶 Prix :", p["price"])
        print("🖼️ Image :", p["img"])

    driver.quit()


scrape_carrefour_shadow()
