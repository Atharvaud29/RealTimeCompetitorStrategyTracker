import pandas as pd 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import re

from webdriver_manager.chrome import ChromeDriverManager

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

# Extract product data
def parse_product(card):
    try:
        name_tag = card.find("h2", class_="a-size-medium")
        name = name_tag.text.strip() if name_tag else None

        link_tag = card.find("a", class_="a-link-normal s-no-outline")
        link = "https://www.amazon.in" + link_tag["href"] if link_tag else None

        asin = card.get("data-asin")

        brand = None
        if name:
            brand = name.split()[0]

        price_tag = card.find("span", class_="a-price-whole")
        price = price_tag.text.replace(",", "").strip() if price_tag else None

        mrp_tag = card.find("span", class_="a-text-price")
        mrp = mrp_tag.text.replace("₹", "").replace(",", "").strip() if mrp_tag else None

        discount = None
        discount_span = card.find("span", class_="a-letter-space")
        if discount_span:
            discount_next = discount_span.find_next_sibling("span")
            discount = discount_next.text.strip() if discount_next else None

        rating_tag = card.find("span", class_="a-icon-alt")
        rating = rating_tag.text.split()[0] if rating_tag else None

        reviews_tag = card.find("span", class_="a-size-base s-underline-text")
        reviews = reviews_tag.text.strip() if reviews_tag else None

        stock_status = "Available" if "Get it" in card.text else "Unknown"

        seller = None  # Not visible on listing pages

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
            "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return data
    except Exception as e:
        print(f"Error parsing product: {e}")
        return None

# Scrape function
def scrape_amazon_search(keyword, num_pages=2):
    base_url = f"https://www.amazon.com/s?k=laptops"
    driver = init_driver()
    all_products = []

    try:
        for page in range(1, num_pages + 1):
            url = f"{base_url}&page={page}"
            print(f"Scraping page {page}: {url}")
            driver.get(url)
            time.sleep(0)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            product_cards = soup.find_all("div", {"data-component-type": "s-search-result"})

            for card in product_cards:
                product_data = parse_product(card)
                if product_data:
                    all_products.append(product_data)
            #wait before next page
            time.sleep(0)
    finally:
        driver.quit()
    return all_products

# Main execution
if __name__ == "__main__":
    keyword = " "
    print(f"--> Starting the scrape for: {keyword}")
    products = scrape_amazon_search(keyword, num_pages=4)

    # ✅ Save results only to CSV
    if products:
        df = pd.DataFrame(products)
        df.to_csv("amazon_product_selenium.csv", index=False, encoding="utf-8-sig")
        print(f"--> Scraped {len(products)} products saved to 'amazon_product_selenium.csv'")
    else:
        print("!! No products scraped. CSV not created.")




