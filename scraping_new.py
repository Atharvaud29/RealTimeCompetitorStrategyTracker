import requests
import pandas as pd

url = "https://django.prixhistory.com/api/product/history/updateFromSlug"

headers = {
    #"auth": "47WCcaWa8VxglK5Xnlg9fkmtfdlslttYxIVxAzIKzFlwb1TiWgB5yCnaUgrHfF54", #For S24
    "auth": "Zc1ZIap6Si3NYm30dYFZBR76kNU+qOIgW7Jj2E6vSCOyxPKHmH913vMoJgXMbXRT", #For S23
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Origin": "https://pricehistoryapp.com",
    "Referer": "https://pricehistoryapp.com/",
}

data = {
    "slug": "samsung-galaxy-s23-5g-green-256-gb"
}

res = requests.post(url, headers=headers, data=data)

if res.status_code == 200:
    json_data = res.json()
    print("API Keys:", json_data.keys())  # check fields
   
    if "history" in json_data:
        hist = json_data["history"]
       
        if isinstance(hist, dict):
            hist = [{"date": k, "price": v} for k, v in hist.items()]

        df = pd.DataFrame(hist)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], unit="s")

        df = df.sort_values("date")
        filename = "samsung_galaxy_s23_price_history.csv"
        df.to_csv(filename, index=False)

        print(f"Saved clean dataset to {filename}")
        print(df.head(10))  
    else:
        print("No 'history' field found. Response:")
        print(json_data)
else:
    print(f"Error {res.status_code}:")
    print(res.text)

