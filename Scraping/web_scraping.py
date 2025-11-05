import pandas as pd 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import time
import csv
import re

# Setup Chrome WebDriver
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # run browser invisibly
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=en-IN")

    #Automatically downloads the correct ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# ✅ Helper: clean text safely
def clean_text(text):
    if not text:
        return None
    return re.sub(r'\s+', ' ', text).strip()

# ✅ Extract data from individual product cards
def parse_product(card):
    try:
        name_tag = card.find("h2", class_="a-size-medium")
        name = clean_text(name_tag.text) if name_tag else None

        link_tag = card.find("a", class_="a-link-normal s-no-outline")
        link = "https://www.amazon.in" + link_tag["href"] if link_tag else None

        asin = card.get("data-asin")
        brand = name.split()[0] if name else None

        # ✅ Price and MRP
        price_tag = card.select_one("span.a-price span.a-offscreen")
        price = clean_text(price_tag.text.replace("₹", "").replace(",", "")) if price_tag else None

        mrp_tag = card.select_one("span.a-price.a-text-price span.a-offscreen")
        mrp = clean_text(mrp_tag.text.replace("₹", "").replace(",", "")) if mrp_tag else None

        # ✅ Discount (if visible)
        discount_tag = card.find("span", string=re.compile(r"%"))
        discount = clean_text(discount_tag.text) if discount_tag else None

        # ✅ Rating and Reviews
        rating_tag = card.find("span", class_="a-icon-alt")
        rating = clean_text(rating_tag.text.split()[0]) if rating_tag else None

        reviews_tag = card.find("span", {"aria-label": re.compile(r"\d+ ratings?")})
        reviews = clean_text(reviews_tag["aria-label"].split()[0]) if reviews_tag else None

        # ✅ Default placeholders
        stock_status = "Unknown"
        seller = None

        # ✅ Visit product page to extract seller & stock info
        if link:
            seller, stock_status = scrape_product_page(link)

        data = {
            "Product_Name": name,
            "Product_ASIN": asin,
            "Brand": brand,
            "Price": price,
            "MRP": mrp,
            "Discount": discount,
            "Stock_Status": stock_status,
            "Rating": rating,
            "Reviews": reviews,
            "Seller": seller,
            "Product_Link": link,
            "Reviews_Link": f"{link}#customerReviews" if link else None,
            "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return data

    except Exception as e:
        print(f"Error parsing product: {e}")
        return None

# ✅ Scrape individual product pages for Seller & Stock
def scrape_product_page(url):
    try:
        driver = init_driver()
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Seller info
        seller_tag = soup.find("a", id="bylineInfo")
        seller = clean_text(seller_tag.text) if seller_tag else "Not Available"

        # Stock info
        stock_tag = soup.find("div", id="availability")
        stock_status = clean_text(stock_tag.text) if stock_tag else "Not Available"

        driver.quit()
        return seller, stock_status

    except Exception:
        driver.quit()
        return "Not Available", "Not Available"

# ✅ Scrape Search Results
def scrape_amazon_search(keyword, num_pages=2):
    base_url = f"https://www.amazon.in/s?k={keyword.replace(' ', '+')}"
    driver = init_driver()
    all_products = []

    try:
        for page in range(1, num_pages + 1):
            url = f"{base_url}&page={page}"
            print(f"🔍 Scraping page {page}: {url}")
            driver.get(url)

            # Wait for page to load fully
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.s-main-slot"))
            )
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            product_cards = soup.find_all("div", {"data-component-type": "s-search-result"})

            for card in product_cards:
                product_data = parse_product(card)
                if product_data:
                    all_products.append(product_data)

            time.sleep(3)

    finally:
        driver.quit()

    return all_products

# ✅ Main Execution
if __name__ == "__main__":
    import os
    keyword = "laptops"
    print(f"\n🚀 Starting the scrape for: {keyword}")
    products = scrape_amazon_search(keyword, num_pages = 4)

    if products:
        df = pd.DataFrame(products)
        df.fillna("N/A", inplace=True)
        df.replace(r'\s+', ' ', regex=True, inplace=True)

        # ✅ Path to Scraping folder
        output_dir = os.path.join(os.path.dirname(__file__), "Scraping")

        # ✅ Check if folder exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print("📁 'Scraping' folder was not found, so it has been created.")
        else:
            print("📂 'Scraping' folder already exists — saving file inside it.")

        # ✅ Define simple, fixed filename
        filename = f"amazon_products_{keyword}.csv"
        filepath = os.path.join(output_dir, filename)

        # ✅ Save CSV inside existing Scraping folder
        df.to_csv(filepath, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)

        print(f"\n✅ Scraped {len(products)} products saved to: {filepath}")
    else:
        print("❌ No products scraped. CSV not created.")

