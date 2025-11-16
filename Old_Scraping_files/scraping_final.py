# scraping_final.py
# Unified scraper: PriceHistoryApp + Flipkart (Selenium) metadata & FULL reviews
# Saves:
#  - price_history/<slug>_price_history.csv
#  - output/<safe_product_name>_metadata_reviews.csv

import os
import re
import time
import json
import random
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Optional sentiment (TextBlob)
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except Exception:
    TEXTBLOB_AVAILABLE = False

# -------------------------------
# CONFIG - edit these values
# -------------------------------
PRODUCT_SLUG = "samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage"
PRICEHISTORY_AUTH_KEY = "aXCIt6HnaaQIwi8dWPuMygRxtPyBkTIQzEqyXmvRjqFgH2tFW0V+mHGdJV9+1IDv"   # put valid key or "" to skip price API
FLIPKART_SEARCH_KEYWORD = "Samsung Galaxy S24"

# optional: force product url if already known (set to None to use search)
FORCE_PRODUCT_URL = None

PRICE_HISTORY_DIR = "price_history"
OUTPUT_DIR = "output"

# Selenium settings
HEADLESS = True
PAGE_LOAD_TIMEOUT = 15
IMPLICIT_WAIT = 2
# -------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
]

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.flipkart.com/"
    }

def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^\w\s\-_]", "", name).strip().lower()
    return re.sub(r"[\s\-]+", "_", name)

def text_features(text: str):
    txt = (text or "").strip()
    chars = len(txt)
    words = len(txt.split())
    if words <= 5:
        length_category = "Very Short"
    elif words <= 15:
        length_category = "Short"
    elif words <= 50:
        length_category = "Medium"
    else:
        length_category = "Long"
    if TEXTBLOB_AVAILABLE and txt:
        try:
            pol = TextBlob(txt).sentiment.polarity
            if pol > 0.2:
                sentiment = "positive"
            elif pol < -0.2:
                sentiment = "negative"
            else:
                sentiment = "neutral"
        except Exception:
            sentiment = "N/A"
    else:
        sentiment = "N/A"
    return {
        "length_chars": chars,
        "word_count": words,
        "length_category": length_category,
        "sentiment": sentiment
    }

# -------------------------------
# Price history via PriceHistoryApp API
# -------------------------------
def scrape_price_history_api(slug: str, auth_key: str):
    os.makedirs(PRICE_HISTORY_DIR, exist_ok=True)
    if not auth_key:
        print("[price] No auth key provided — skipping PriceHistory API.")
        return None
    url = "https://django.prixhistory.com/api/product/history/updateFromSlug"
    headers = get_headers()
    headers["auth"] = auth_key
    print(f"[price] Fetching price history for slug: {slug}")
    try:
        resp = requests.post(url, headers=headers, data={"slug": slug}, timeout=20)
    except Exception as e:
        print(f"[price] Request error: {e}")
        return None
    if resp.status_code != 200:
        print(f"[price] API returned {resp.status_code}: {resp.text[:400]}")
        return None
    try:
        data = resp.json()
    except Exception as e:
        print(f"[price] JSON parse error: {e}")
        return None

    hist = data.get("history") or data.get("data") or {}
    rows = []
    if isinstance(hist, dict):
        for k, v in hist.items():
            rows.append({"date": k, "price": v})
    elif isinstance(hist, list):
        rows = hist
    if not rows:
        print("[price] No history rows found.")
        return None

    df = pd.DataFrame(rows)
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(pd.to_numeric(df["date"], errors='coerce'), unit='s', errors='coerce')
        except Exception:
            pass
    fname = os.path.join(PRICE_HISTORY_DIR, f"{safe_filename(slug)}_price_history.csv")
    df.to_csv(fname, index=False, encoding="utf-8-sig")
    print(f"[price] Saved price history → {fname}")
    return df

# -------------------------------
# Selenium helpers for Flipkart
# -------------------------------
def init_driver(headless=True):
    opts = Options()
    if headless:
        # newer Chrome accepts --headless=new; keep compatibility
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    # reduce logging
    opts.add_argument("--log-level=3")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver

# -------------------------------
# Flipkart metadata extraction (many fallbacks)
# -------------------------------
def scrape_flipkart_metadata(driver):
    print("[flipkart] Scraping product metadata...")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    # product name
    name = None
    name_selectors = ["span.B_NuCI", "span._35KyD6", "div._1Mh3u3 h1", "span._35KyD6"]
    for sel in name_selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            name = el.get_text(strip=True)
            break
    # brand fallback: first word or seller link
    brand = None
    try:
        brand_tag = soup.select_one("a._2whKao") or soup.select_one("span._2apC")
        if brand_tag:
            brand = brand_tag.get_text(strip=True)
    except Exception:
        brand = None
    # price
    price = None
    psel = soup.select_one("div._30jeq3._16Jk6d") or soup.select_one("div._30jeq3")
    if psel:
        price = psel.get_text(strip=True).replace("₹", "").replace(",", "")
    # MRP
    mrp = None
    mrpsel = soup.select_one("div._3I9_wc._2p6lqe") or soup.select_one("div._3I9_wc")
    if mrpsel:
        mrp = mrpsel.get_text(strip=True).replace("₹", "").replace(",", "")
    # discount
    discount = None
    dsel = soup.select_one("div._3Ay6Sb._31Dcoz") or soup.select_one("div._3Ay6Sb")
    if dsel:
        discount = dsel.get_text(strip=True)
    # rating
    rating = None
    rat = soup.select_one("div._3LWZlK") or soup.select_one("span._2_R_DZ")
    if rat:
        rating = rat.get_text(strip=True)
    # reviews count
    reviews_count = None
    rc = soup.select_one("span._2_R_DZ") or soup.select_one("span._2s6RMp")
    if rc:
        reviews_count = rc.get_text(strip=True)

    # seller & stock
    seller = None
    stock = None
    # seller often in 'a._2whKao' or 'div._3k-BhJ'
    seller_tag = soup.select_one("a._2whKao") or soup.select_one("div._3k-BhJ")
    if seller_tag:
        seller = seller_tag.get_text(strip=True)
    # stock availability
    stock_tag = soup.select_one("div._16FRp0") or soup.select_one("div._2o7WAb")
    if stock_tag:
        stock = stock_tag.get_text(strip=True)

    # Product ASIN or product id in URL often; we try to parse from meta or scripts
    product_asin = None
    try:
        # try JSON-LD
        script = soup.find("script", type="application/ld+json")
        if script:
            jd = json.loads(script.string)
            product_asin = jd.get("sku") or jd.get("mpn") or jd.get("productID")
    except Exception:
        product_asin = None

    metadata = {
        "product_name": name or "N/A",
        "brand": brand or "N/A",
        "price": price or "N/A",
        "mrp": mrp or "N/A",
        "discount": discount or "N/A",
        "rating_value": rating or "N/A",
        "reviews_count": reviews_count or "N/A",
        "seller": seller or "N/A",
        "stock_status": stock or "N/A",
        "product_asin": product_asin or "N/A",
        "product_url": driver.current_url,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    print(f"[flipkart] Metadata extracted: {metadata['product_name']}")
    return metadata

# -------------------------------
# Flipkart reviews pagination & extraction
# -------------------------------
def scrape_flipkart_reviews_full(driver):
    """
    Assumes driver is on the product page.
    Clicks 'View all reviews' or scrolls to review section and paginates through Next(s).
    Returns DataFrame of reviews.
    """
    print("[flipkart] Starting full reviews scrape (may take time)...")
    reviews = []
    # Try to open 'See all reviews' link
    try:
        # common anchor: "View All" link or "See all reviews"
        # Buttons can be dynamic; search for anchors containing 'All reviews'
        anchors = driver.find_elements(By.TAG_NAME, "a")
        found_link = None
        for a in anchors:
            try:
                text = a.text.strip().lower()
                if "all reviews" in text or "see all" in text or "view all reviews" in text:
                    found_link = a.get_attribute("href")
                    break
            except Exception:
                continue
        if found_link:
            driver.get(found_link)
            time.sleep(2)
        else:
            # try to scroll to reviews section on same page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1.5)
    except Exception:
        pass

    # now on reviews listing (or still on product page)
    while True:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Flipkart review text selectors have varied. Try several:
        review_blocks = soup.select("div._16PBlm") or soup.select("div._27M-vq") or soup.select("div._1AtVbE div[class*='col-']")

        if not review_blocks:
            # alternative: find review containers by data-test attributes
            review_blocks = soup.select("div._2kS5Gq") or soup.select("div.dhYmqp")

        if not review_blocks:
            # fallback: try to find short review text nodes
            text_items = soup.select("div.t-ZTKy div") or soup.select("div._1c3YSN")
            for t in text_items:
                txt = t.get_text(" ", strip=True)
                if txt:
                    feats = text_features(txt)
                    reviews.append({"review": txt, "rating": "N/A", **feats})
        else:
            for rb in review_blocks:
                # try to extract rating
                r_text = None
                r_rating = None
                # possible text ele
                t1 = rb.select_one("div.t-ZTKy div") or rb.select_one("div._3LWZlK") or rb.select_one("div.qwjRop")
                if t1:
                    r_text = t1.get_text(" ", strip=True)
                # rating may be in span._3LWZlK or div._3LWZlK
                r_rat = rb.select_one("div._3LWZlK") or rb.select_one("span._2_R_DZ")
                if r_rat:
                    r_rating = r_rat.get_text(strip=True)
                # review date
                date_tag = rb.select_one("p._2sc7ZR._2V5EHH") or rb.select_one("div._2fxQ4u")
                r_date = date_tag.get_text(strip=True) if date_tag else "N/A"

                # clean text
                if r_text:
                    feats = text_features(r_text)
                    reviews.append({
                        "review": r_text,
                        "rating": r_rating or "N/A",
                        "date": r_date or "N/A",
                        **feats
                    })

        # Try to click 'Next' button
        try:
            next_btn = None
            # Try locating by aria-label or text
            next_btn_elem = driver.find_elements(By.XPATH, "//a[contains(text(),'Next') or contains(text(),'next') or contains(@aria-label,'Next')]")
            if next_btn_elem:
                # filter visible
                clicked = False
                for el in next_btn_elem:
                    try:
                        if el.is_displayed():
                            el.click()
                            clicked = True
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue
                if not clicked:
                    break
            else:
                # try pagination button with class
                np = driver.find_elements(By.CSS_SELECTOR, "a._1LKTO3")
                clicked = False
                for el in np:
                    try:
                        if el.is_displayed() and 'Next' in el.text:
                            el.click()
                            clicked = True
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue
                if not clicked:
                    break
        except Exception:
            break

    if not reviews:
        print("[flipkart] No reviews collected by selectors.")
        return None

    df = pd.DataFrame(reviews)
    print(f"[flipkart] Collected {len(df)} reviews.")
    return df

# -------------------------------
# Merge & save final CSVs
# -------------------------------
def merge_and_save_final(metadata: dict, reviews_df: pd.DataFrame, slug: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = safe_filename(metadata.get("product_name") or slug)
    # ensure standard columns from screenshot
    # reviews part columns: text, rating, length, date, platform, sentiment, word_count, char_count, length_category
    if reviews_df is None or reviews_df.empty:
        print("[merge] No reviews to merge; creating metadata-only CSV.")
        meta_df = pd.DataFrame([metadata])
        out_meta = os.path.join(OUTPUT_DIR, f"{safe_name}_metadata.csv")
        meta_df.to_csv(out_meta, index=False, encoding="utf-8-sig")
        print(f"[merge] Saved metadata-only CSV → {out_meta}")
        return out_meta

    # normalize column names to match screenshot
    reviews_df = reviews_df.rename(columns={
        "review": "text",
        "rating": "rating_value",
        "length_chars": "char_count",
        "word_count": "word_count",
        "length_category": "length_category",
    })
    # ensure text, rating, char_count, word_count exist
    for col in ["text", "rating_value", "char_count", "word_count", "length_category", "sentiment"]:
        if col not in reviews_df.columns:
            reviews_df[col] = "N/A"

    # add date column if missing
    if "date" not in reviews_df.columns:
        reviews_df["date"] = datetime.now().strftime("%Y-%m-%d")

    # add platform
    reviews_df["platform"] = "flipkart"

    # add metadata columns to every row
    for k, v in metadata.items():
        # map metadata keys to required output names
        mapped_key = k
        # keep metadata keys as-is (product_name, brand, price, mrp, discount, rating_value, reviews_count, seller, stock_status, product_url, scraped_at)
        reviews_df[mapped_key] = v

    # reorder columns roughly like screenshot
    cols_order = ["text", "rating_value", "length_category", "date", "platform", "sentiment", "word_count", "char_count",
                  "product_name", "brand", "price", "mrp", "discount", "rating_value", "reviews_count", "seller", "stock_status",
                  "product_url", "scraped_at"]
    # keep only existing
    cols_existing = [c for c in cols_order if c in reviews_df.columns]
    # append any other columns
    final_df = reviews_df[cols_existing + [c for c in reviews_df.columns if c not in cols_existing]]

    out_file = os.path.join(OUTPUT_DIR, f"{safe_name}_metadata_reviews.csv")
    final_df.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"[merge] Saved merged metadata + reviews → {out_file}")
    return out_file

# -------------------------------
# MAIN flow
# -------------------------------
def main():
    print("=== scraping_final.py started ===")

    # 1) Fetch price history
    price_df = scrape_price_history_api(PRODUCT_SLUG, PRICEHISTORY_AUTH_KEY)

    # 2) Ask user for Flipkart product link
    product_url = input("\nPaste the Flipkart product URL for this product:\n> ").strip()

    if not product_url.startswith("https://www.flipkart.com"):
        print("[flipkart] Invalid Flipkart URL. Exiting...")
        return

    driver = init_driver(headless=HEADLESS)
    driver.get(product_url)
    time.sleep(2)

    # 3) Scrape metadata
    metadata = scrape_flipkart_metadata(driver)

    # 4) Scrape reviews
    reviews_df = scrape_flipkart_reviews_full(driver)

    driver.quit()

    # 5) Merge and export
    merged_path = merge_and_save_final(metadata, reviews_df, PRODUCT_SLUG)

    print("\n=== Finished ===")
    print(f"Price history saved: {price_df is not None}")
    print(f"Metadata saved: {metadata is not None}")
    print(f"Final CSV saved: {merged_path}")


if __name__ == "__main__":
    main()
