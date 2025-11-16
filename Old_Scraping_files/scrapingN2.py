import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import random
import time
import os

# -------------------------------
# User-Agent Rotation
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
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://pricehistoryapp.com",
        "Referer": "https://pricehistoryapp.com/",
    }

# -------------------------------
# 1️⃣ PRODUCT METADATA SCRAPER (PriceHistoryApp)
# -------------------------------
# -------------------------------
# 1️⃣ PRODUCT METADATA SCRAPER (HTML)
# -------------------------------
def scrape_product_metadata_html(product_url):
    print(f"\n📦 Fetching product metadata from page: {product_url}")
    headers = get_headers()
    res = requests.get(product_url, headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to fetch product page: {res.status_code}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")

    # Try to find JSON-LD data
    metadata = {}
    script_tag = soup.find("script", type="application/ld+json")
    if script_tag:
        import json
        try:
            data = json.loads(script_tag.string)
            metadata = {
                "Product_Name": data.get("name", "N/A"),
                "Brand": data.get("brand", {}).get("name", "N/A") if isinstance(data.get("brand"), dict) else "N/A",
                "Price": data.get("offers", {}).get("price", "N/A") if isinstance(data.get("offers"), dict) else "N/A",
                "MRP": data.get("offers", {}).get("price", "N/A") if isinstance(data.get("offers"), dict) else "N/A",
                "Discount": "N/A",
                "Stock_Status": data.get("offers", {}).get("availability", "N/A") if isinstance(data.get("offers"), dict) else "N/A",
                "Rating": data.get("aggregateRating", {}).get("ratingValue", "N/A") if isinstance(data.get("aggregateRating"), dict) else "N/A",
                "Product_Link": product_url,
                "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except json.JSONDecodeError:
            print("⚠️ Failed to parse JSON data from page")
    
    # fallback in case JSON-LD is not found
    if not metadata:
        metadata = {
            "Product_Name": "N/A",
            "Brand": "N/A",
            "Price": "N/A",
            "MRP": "N/A",
            "Discount": "N/A",
            "Stock_Status": "N/A",
            "Rating": "N/A",
            "Product_Link": product_url,
            "Scraped_At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    return metadata


# -------------------------------
# 2️⃣ PRICE HISTORY SCRAPER
# -------------------------------
def scrape_price_history(slug, auth_key):
    url = "https://django.prixhistory.com/api/product/history/updateFromSlug"
    headers = get_headers()
    headers["auth"] = auth_key

    print(f"\n📦 Fetching price history for: {slug}")
    res = requests.post(url, headers=headers, data={"slug": slug})
    if res.status_code != 200:
        print(f"❌ Failed to fetch price data: {res.status_code}")
        return None

    data = res.json()
    hist = data.get("history", {})
    if isinstance(hist, dict):
        hist = [{"date": k, "price": v} for k, v in hist.items()]

    df = pd.DataFrame(hist)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], unit="s")
        df = df.sort_values("date")
        filename = f"{slug}_price_history.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Saved price history → {filename}")
    return df

# -------------------------------
# 3️⃣ REVIEW SCRAPER (GSMArena)
# -------------------------------
def scrape_gsmarena_reviews(product_name):
    gsm_url = "https://www.gsmarena.com/samsung_galaxy_s24_reviews-12780.php"
    headers = get_headers()

    print(f"\n💬 Fetching reviews from GSMArena: {gsm_url}")
    res = requests.get(gsm_url, headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to fetch reviews: {res.status_code}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    reviews = [r.get_text(strip=True) for r in soup.find_all("p", class_="uopin")]
    ratings = [r.text.strip() for r in soup.find_all("span", class_="score")]

    if not reviews:
        print("⚠️ No reviews found on GSMArena.")
        return None

    df_reviews = pd.DataFrame({
        "review": reviews,
        "rating": ratings[:len(reviews)] if ratings else ["N/A"] * len(reviews)
    })
    return df_reviews

## Main function
if __name__ == "__main__":
    product_slug = "samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage"
    auth_key = "DSOiL7FRkRQO91AYMEx4nl04e5q415aG+oY810ogfnVA5+QWkwvZ8jhsFK7LLHMd"

    print("🔹 Starting scraping for Samsung Galaxy S24 5G\n")

    # 1️⃣ Product metadata
    product_url = f"https://pricehistoryapp.com/product/{product_slug}"
    product_details = scrape_product_metadata_html(product_url)
    time.sleep(random.uniform(1, 3))

    # Safe fallback if metadata fetch failed
    if product_details is None:
        print("⚠️ Skipping product metadata due to 404/403 error.")
        product_name_for_reviews = "Samsung Galaxy S24 5G"  # default name for reviews
    else:
        product_name_for_reviews = product_details.get("Product_Name", "Samsung Galaxy S24 5G")

    # 2️⃣ Price history (optional, uncomment if API is accessible)
    try:
        # price_df = scrape_price_history(product_slug, auth_key)
        pass
    except Exception as e:
        print(f"⚠️ Price history fetch failed: {e}")
    time.sleep(random.uniform(1, 3))

    # 3️⃣ Reviews
    reviews_df = scrape_gsmarena_reviews(product_name_for_reviews)

    # 4️⃣ Prepare output directory and safe filename
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    if product_details is not None and product_details.get("Product_Name") not in [None, "N/A"]:
        safe_name = product_details["Product_Name"].lower().replace(' ', '_')
    else:
        safe_name = "samsung_galaxy_s24_5g"

    # 5️⃣ Merge product metadata with reviews if available
    if reviews_df is not None and product_details is not None:
        for key, value in product_details.items():
            reviews_df[key] = value

        filename = os.path.join(output_dir, f"{safe_name}_full_data.csv")
        reviews_df.to_csv(filename, index=False)
        print(f"✅ Saved merged product + reviews → {filename}")
    elif reviews_df is not None:
        # Save reviews alone if metadata failed
        filename = os.path.join(output_dir, f"{safe_name}_reviews_only.csv")
        reviews_df.to_csv(filename, index=False)
        print(f"✅ Saved reviews only → {filename}")
    else:
        print("⚠️ No reviews available to save.")

    print("\n✅ Scraping Completed Successfully!")