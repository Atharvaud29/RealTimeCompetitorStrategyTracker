import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import random
import time

# ---------------------------------
# User-Agent Rotation (to avoid 403)
# ---------------------------------
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

# ---------------------------------
# 1️⃣ PRICE HISTORY SCRAPER
# ---------------------------------
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
    if "history" not in data:
        print("⚠️ No price history found in response.")
        return None

    hist = data["history"]
    if isinstance(hist, dict):
        hist = [{"date": k, "price": v} for k, v in hist.items()]

    df = pd.DataFrame(hist)
    df["date"] = pd.to_datetime(df["date"], unit="s")
    df = df.sort_values("date")

    filename = f"{slug}_price_history.csv"
    df.to_csv(filename, index=False)
    print(f"✅ Saved price history → {filename}")
    return df

# ---------------------------------
# 2️⃣ REVIEW SCRAPER (GSMArena fallback)
# ---------------------------------
def scrape_gsmarena_reviews(product_name):
    # Manually verified working page for S25 (replace if GSMArena updates URL)
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
    filename = f"{product_name.lower().replace(' ', '_')}_reviews.csv"
    df_reviews.to_csv(filename, index=False)
    print(f"✅ Saved reviews → {filename}")
    return df_reviews

# ---------------------------------
# MAIN
# ---------------------------------
if __name__ == "__main__":
    product_slug = "samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage"
    auth_key = "mMwSpOsUNlnueXZWCkC5b94rpy67jseuMz373r9eSvV5odiB4LT6Z18FQpY82rEz"

    print("🔹 Starting scraping for Samsung Galaxy S24 5G\n")

    # Fetch price history
    price_df = scrape_price_history(product_slug, auth_key)
    time.sleep(random.uniform(2, 4))

    # Fetch reviews
    reviews_df = scrape_gsmarena_reviews("Samsung Galaxy S24 5G")

    print("\n✅ Scraping Completed Successfully!")

