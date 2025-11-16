import requests
import pandas as pd
from urllib.parse import urlparse
from time import sleep

API_URL = "https://django.prixhistory.com/api/product/history/updateFromSlug"

# 🔹 UPDATED PRODUCT URL
PRODUCT_URL = "https://pricehistoryapp.com/product/samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage"

# 🔹 UPDATED AUTH TOKEN
AUTH_TOKEN = "jhBMLxsCCGNeVjnX8h54CNjBDrMo2sJOQZG9dnEVhLp7iGCBfIPzUCa0BB80WZKr"


def extract_slug(u: str) -> str:
    parts = [p for p in urlparse(u).path.split("/") if p]
    return parts[1] if len(parts) >= 2 and parts[0] == "product" else parts[-1]


slug = extract_slug(PRODUCT_URL)

sess = requests.Session()
# 1) Load homepage & product to pick up any cookies/CF tokens they might set
for warmup_url in ["https://pricehistoryapp.com/", PRODUCT_URL]:
    sess.get(warmup_url, timeout=20)

headers = {
    "name": "Amazon",
    "auth": AUTH_TOKEN,
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://pricehistoryapp.com",
    "Referer": PRODUCT_URL,
    "X-Requested-With": "XMLHttpRequest",
}

data = {"slug": slug}

# 2) Retry a few times on transient blocks
for attempt in range(4):
    res = sess.post(API_URL, headers=headers, data=data, timeout=(10, 40))
    if res.status_code == 200:
        payload = res.json()
        break
    elif res.status_code in (429, 503):  # rate limit / temporary
        sleep(2 * (attempt + 1))
        continue
    elif res.status_code == 403:
        raise RuntimeError(f"403 Forbidden. Likely invalid/expired auth or missing browser context. Body: {res.text}")
    else:
        raise RuntimeError(f"HTTP {res.status_code}: {res.text}")
else:
    raise RuntimeError("Gave up after retries.")

# 3) Normalize the history to a tidy DataFrame and save
hist = payload.get("history")
if hist is None:
    raise KeyError(f"No 'history' in response. Keys: {list(payload.keys())}")

if isinstance(hist, dict):
    rows = [{"date": k, "price": v} for k, v in hist.items()]
else:
    rows = hist

df = pd.DataFrame(rows).rename(columns={"ts": "date", "timestamp": "date", "amount": "price", "value": "price", "brand": "name"})
df['brand'] = "Amazon"

if "date" not in df.columns or "price" not in df.columns or "brand" not in df.columns:
    raise KeyError(f"Expected 'date' and 'price' columns, got {df.columns.tolist()}")

# parse date (sec/ms or ISO)
s = pd.to_numeric(df["date"], errors="coerce")
use_ms = (s.dropna() > 1e10).any()
try:
    df["date"] = pd.to_datetime(df["date"], unit=("ms" if use_ms else "s"), utc=True)
except Exception:
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

df["price"] = pd.to_numeric(df["price"], errors="coerce")
df = df.dropna(subset=["date", "price"]).sort_values("date").reset_index(drop=True)

csv_name = f"{slug}_amazon_price_history.csv"
df.to_csv(csv_name, index=False)

print(f"Saved: {csv_name}")
print(df.head(10))
