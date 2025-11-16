import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd
import time

# -------------------- WAYBACK --------------------
def scrape_wayback(url, limit=5):
    print(f"\n[INFO] Starting Wayback Machine scraping for: {url}\n")
    try:
        cdx_url = f"https://web.archive.org/cdx/search/cdx?url=*.amazon.in/*{url.split('/')[-1]}*&output=json&fl=timestamp,original&filter=statuscode:200"
        print(f"[DEBUG] Querying CDX API: {cdx_url}")
        response = requests.get(cdx_url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[ERROR] Wayback request failed: {e}")
        return []

    snapshots = data[1:limit + 1]
    scraped = []
    for snap in snapshots:
        timestamp = snap[0]
        snapshot_url = f"https://web.archive.org/web/{timestamp}/{url}"
        print(f"[INFO] Scraping snapshot: {snapshot_url}")

        try:
            page = requests.get(snapshot_url, timeout=20)
            soup = BeautifulSoup(page.text, 'html.parser')
            title = soup.find("span", {"id": "productTitle"})
            price = soup.find("span", {"class": "a-price-whole"})
            if title and price:
                scraped.append({
                    "timestamp": timestamp,
                    "title": title.get_text(strip=True),
                    "price": price.get_text(strip=True)
                })
        except Exception as e:
            print(f"[WARN] Failed at {snapshot_url}: {e}")
        time.sleep(1)

    return scraped


# -------------------- PRICEARCHIVE --------------------
def scrape_pricearchive(url):
    print(f"\n[INFO] Scraping PriceArchive data for: {url}\n")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[ERROR] Cannot load {url}: {e}")
        return []

    data = []
    rows = soup.select("table tbody tr")
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 2:
            data.append({
                "date": cols[0],
                "price": cols[1],
                "discount": cols[2] if len(cols) > 2 else None
            })
    return data


# -------------------- PRICEHISTORY APP (API-based) --------------------
def scrape_pricehistory(product_slug, pages=5):
    print("[INFO] Fetching Price History from pricehistoryapp.com API...")

    headers = {
        "Authorization": "Bearer DKDveMWWCJ1uurxlXJNwvsS3mm3VNJEgliVwONIzG94Nn9HIr/MPCGXfYDHCekJj",
        "User-Agent": "Mozilla/5.0"
    }

    api_url = f"https://pricehistoryapp.com/api/products/{product_slug}/history"
    all_data = []

    for page in range(1, pages + 1):
        try:
            response = requests.get(api_url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                history = data.get("data", [])
                if not history:
                    print(f"[WARN] No data found for page {page}.")
                    break

                for record in history:
                    all_data.append({
                        "date": record.get("date"),
                        "price": record.get("price"),
                        "source": record.get("source"),
                        "product": product_slug
                    })

                print(f"[INFO] Page {page} fetched successfully.")
                time.sleep(1)
            else:
                print(f"[ERROR] API returned {response.status_code}: {response.text}")
                break
        except Exception as e:
            print(f"[ERROR] Failed to fetch page {page}: {e}")
            break

    return all_data


# -------------------- REVIEWS --------------------
def scrape_reviews(url, limit=5):
    print(f"\n[INFO] Scraping reviews from: {url}\n")
    all_reviews = []
    for page_num in range(1, limit + 1):
        page_url = f"{url}?pageNumber={page_num}"
        try:
            response = requests.get(page_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            reviews = soup.select('.review-text-content span')
            for r in reviews:
                all_reviews.append({"page": page_num, "review": r.get_text(strip=True)})
        except Exception as e:
            print(f"[WARN] Skipped page {page_num}: {e}")
        time.sleep(1)
    return all_reviews


# -------------------- MAIN --------------------
if __name__ == "__main__":
    print("=== Product Data Scraper ===")
    print("Modes available:\n1. wayback\n2. pricearchive\n3. pricehistory (via API)\n4. reviews\n")

    mode = input("Enter scraping mode (wayback / pricearchive / pricehistory / reviews): ").strip().lower()
    url_input = input("Enter product URL or slug: ").strip()
    limit_input = input("Enter number of pages/snapshots to scrape (default=5): ").strip()
    limit = int(limit_input) if limit_input else 5
    output_csv = input("Enter output CSV filename (default=output.csv): ").strip() or "output.csv"

    if mode == "wayback":
        data = scrape_wayback(url_input, limit)
    elif mode == "pricearchive":
        data = scrape_pricearchive(url_input)
    elif mode == "pricehistory":
        data = scrape_pricehistory(url_input, limit)
    elif mode == "reviews":
        data = scrape_reviews(url_input, limit)
    else:
        print("[ERROR] Invalid mode selected.")
        exit()

    if not data:
        print("\n⚠️ No data scraped.")
    else:
        df = pd.DataFrame(data)
        df.to_csv(output_csv, index=False, encoding="utf-8-sig")
        print(f"\n✅ Data saved to {output_csv}.")

