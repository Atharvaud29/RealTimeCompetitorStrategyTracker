import sys
sys.stdout.reconfigure(encoding='utf-8')
import pickle
import re
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests

# ---------------------------
# CONFIG
# ---------------------------
ASIN = "B0CS69DGSW"  # Samsung Galaxy S24 (Marble Gray, 8GB/128GB)
MAX_PAGES_AMAZON = 30
MAX_PAGES_FLIPKART = 10      
DELAY_RANGE = (1, 2)
FLIPKART_URL = "https://www.flipkart.com/samsung-galaxy-s24-5g-snapdragon-marble-grey-128-gb/product-reviews/itm8f6413060b707?pid=MOBHDVFKCP3DZG4G&lid=LSTMOBHDVFKCP3DZG4GNMA6GO"



def clean_text(t): 
    return ' '.join(t.strip().split()) if t else ""

# AMAZON SETUP
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def load_cookies(driver, path="amazon_cookies.pkl"):
    cookies = pickle.load(open(path, "rb"))
    driver.get("https://www.amazon.in/")
    for cookie in cookies:
        if 'expiry' in cookie:
            del cookie['expiry']  # avoid datetime serialization issues
        driver.add_cookie(cookie)
    print(f"✅ Loaded {len(cookies)} cookies.")
    time.sleep(2)

# AMAZON SCRAPER
def extract_product_metadata(driver):
    PRODUCT_URL = f"https://www.amazon.in/dp/{ASIN}"
    REVIEWS_URL = f"https://www.amazon.in/product-reviews/{ASIN}/?ie=UTF8&reviewerType=all_reviews"
    driver.get(PRODUCT_URL)
    time.sleep(random.uniform(*DELAY_RANGE))
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Helper function
    def safe_get(selector, attr="text"):
        try:
            if attr=="text":
                return soup.select_one(selector).get_text(strip=True)
            else:
                return soup.select_one(selector)[attr]
        except:
            return ""

    # Extract Price, MRP, Discount
    try:
        price_whole = soup.select_one(".a-price .a-price-whole")
        price_fraction = soup.select_one(".a-price .a-price-fraction")
        price = (price_whole.get_text(strip=True) if price_whole else "") + \
                (price_fraction.get_text(strip=True) if price_fraction else "")
    except:
        price = ""

    try:
        mrp_tag = soup.select_one(".a-text-strike")
        mrp = mrp_tag.get_text(strip=True) if mrp_tag else ""
    except:
        mrp = ""

    try:
        discount_tag = soup.select_one(".a-color-price")  # fallback if priceBlockSavingsString missing
        discount = discount_tag.get_text(strip=True) if discount_tag else ""
    except:
        discount = ""

    return {
        "Product_Name": safe_get("#productTitle"),
        "Product_ASIN": ASIN,
        "Brand": safe_get("#bylineInfo"),
        "Price": price,
        "MRP": mrp,
        "Discount": discount,
        "Stock_Status": safe_get("#availability"),
        "Rating": safe_get(".a-icon-alt"),
        "Reviews": safe_get("#acrCustomerReviewText"),
        "Seller": safe_get("#sellerProfileTriggerId"),
        "Product_Link": PRODUCT_URL,
        "Reviews_Link": REVIEWS_URL,
        "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def extract_amazon_reviews_from_page(soup):
    reviews = []
    blocks = soup.find_all(attrs={"data-hook": "review"})
    for blk in blocks:
        title = blk.find(attrs={"data-hook": "review-title"})
        body = blk.find(attrs={"data-hook": "review-body"})
        stars_tag = blk.find(attrs={"data-hook": "review-star-rating"}) or blk.find("i", class_="a-icon-alt")
        reviewer_tag = blk.find("span", class_="a-profile-name")
        date_tag = blk.find(attrs={"data-hook": "review-date"})
        stars = ""
        if stars_tag:
            m = re.search(r"[0-9\.]+", stars_tag.get_text(strip=True))
            if m: stars = m.group(0)
        reviews.append({
            "Review_Title": clean_text(title.get_text()) if title else "",
            "Review_Body": clean_text(body.get_text()) if body else "",
            "Review_Stars": stars,
            "Reviewer": clean_text(reviewer_tag.get_text()) if reviewer_tag else "",
            "Review_Date": clean_text(date_tag.get_text()) if date_tag else "",
            "Source": "Amazon"
        })
    return reviews

def scrape_amazon_reviews(driver, asin, max_pages=MAX_PAGES_AMAZON):
    all_reviews = []
    seen_hashes = set()
    for page in range(1, max_pages+1):
        print(f"\n--> Amazon-Page {page}")
        url = f"https://www.amazon.in/product-reviews/{asin}/?ie=UTF8&reviewerType=all_reviews&pageNumber={page}&sortBy=recent"
        driver.get(url)
        time.sleep(random.uniform(*DELAY_RANGE))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        revs = extract_amazon_reviews_from_page(soup)
        # deduplicate within amazon
        for r in revs:
            h = hash(r["Review_Title"] + r["Review_Body"])
            if h not in seen_hashes:
                seen_hashes.add(h)
                all_reviews.append(r)
        if not revs:
            print("No more Amazon reviews found.")
            break
        print(f"  → Found {len(revs)} reviews this page.")
    return all_reviews


# FLIPKART SCRAPER
def scrape_flipkart(review_url, existing_hashes=set(), max_pages=MAX_PAGES_FLIPKART):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    }

    all_reviews = []

    for page in range(1, max_pages + 1):
        url = f"{review_url}&page={page}"
        print(f"--> Flipkart-Page {page}")

        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        # NEW working review block selector
        blocks = soup.find_all("div", class_="_27M-vq")

        if not blocks:
            print("No more Flipkart reviews found.")
            break

        for blk in blocks:

            # Stars
            stars = blk.find("div", class_="_3LWZlK")
            stars = stars.get_text(strip=True) if stars else ""

            # Title
            title = blk.find("p", class_="_2-N8zT")
            title = title.get_text(strip=True) if title else ""

            # Body
            body = blk.find("div", class_="t-ZTKy")
            body = body.get_text(" ", strip=True) if body else ""

            # Reviewer + Date (2 elements)
            small_texts = blk.find_all("p", class_="_2sc7ZR")
            reviewer = small_texts[0].get_text(strip=True) if len(small_texts) > 0 else ""
            date = small_texts[1].get_text(strip=True) if len(small_texts) > 1 else ""

            # Dedupe key
            h = hash(title + body + date)

            if h not in existing_hashes:
                existing_hashes.add(h)
                all_reviews.append({
                    "Review_Title": title,
                    "Review_Body": body,
                    "Review_Stars": stars,
                    "Reviewer": reviewer,
                    "Review_Date": date,
                    "Source": "Flipkart"
                })

        print(f"  → Found {len(blocks)} reviews this page.")
        time.sleep(random.uniform(1, 2))

    return all_reviews

# ---------------------------
# Deduplicate Reviews
# ---------------------------
def deduplicate_reviews(reviews):
    seen = set()
    unique_reviews = []
    for r in reviews:
        key = (r.get("Review_Title"), r.get("Review_Body"))
        if key not in seen:
            seen.add(key)
            unique_reviews.append(r)
    return unique_reviews

# ---------------------------
# SAVE TO EXCEL
# ---------------------------
def save_to_excel(product_data, reviews):
    df = pd.DataFrame(reviews)
    for col in product_data:
        if col not in df.columns:
            df[col] = product_data[col]
    file = f"product_reviews_combined_{ASIN}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(file, index=False)
    print(f"✅ Saved {len(df)} reviews to {file}")

# ---------------------------
# MAIN FUNCTION
# ---------------------------
if __name__ == "__main__":
    driver = setup_driver()

    try:
        load_cookies(driver)

        amazon_data = extract_product_metadata(driver)
        amazon_reviews = scrape_amazon_reviews(driver, ASIN, MAX_PAGES_AMAZON)

        seen_hashes = set(hash(r["Review_Title"] + r["Review_Body"]) for r in amazon_reviews)

        flipkart_reviews = scrape_flipkart(
            FLIPKART_URL,
            existing_hashes=seen_hashes,
            max_pages=MAX_PAGES_FLIPKART
        )

        all_reviews = amazon_reviews + flipkart_reviews
        all_reviews = deduplicate_reviews(all_reviews)

        save_to_excel(amazon_data, all_reviews)

    finally:
        driver.quit()
