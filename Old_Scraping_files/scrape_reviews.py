import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

def init_driver():
    options = Options()
    options.add_argument("--headless")  # you can remove to visually debug
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def scrape_flipkart_reviews(driver, product_url, max_pages=3):
    driver.get(product_url)
    time.sleep(3)

    # Try to get product title
    try:
        title = driver.find_element(By.CSS_SELECTOR, "span.B_NuCI").text.strip()
    except:
        title = "Unknown Product"

    print(f"📦 Scraping reviews for product: {title}")

    reviews = []
    for page_num in range(1, max_pages + 1):
        review_page_url = f"{product_url}&page={page_num}"
        driver.get(review_page_url)
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Each review is inside div._27M-vq or div._1AtVbE
        review_blocks = soup.select("div._27M-vq, div._1AtVbE")

        # Filter blocks that actually contain review text
        valid_blocks = [rb for rb in review_blocks if rb.select_one("div.t-ZTKy")]
        if not valid_blocks:
            print(f"⚠️ No reviews found on page {page_num}")
            continue

        for rb in valid_blocks:
            rating = rb.select_one("div._3LWZlK")
            title_r = rb.select_one("p._2-N8zT")
            body = rb.select_one("div.t-ZTKy > div > div")
            reviewer = rb.select_one("p._2sc7ZR._2V5EHH")
            date = rb.select_one("p._2sc7ZR")

            reviews.append({
                "product": title,
                "rating": rating.text.strip() if rating else "",
                "review_title": title_r.text.strip() if title_r else "",
                "review_body": body.text.strip() if body else "",
                "reviewer": reviewer.text.strip() if reviewer else "",
                "date": date.text.strip() if date else "",
                "page": page_num
            })

        print(f"✅ Page {page_num} done — total reviews: {len(reviews)}")
        time.sleep(2)

    return reviews

if __name__ == "__main__":
    driver = init_driver()

    # Ask user for input
    product_url = input("Enter Flipkart product URL: ").strip()
    if not product_url:
        print("❌ No URL provided. Exiting.")
        driver.quit()
        exit()

    try:
        max_pages = int(input("Enter number of review pages (default=3): ") or 3)
    except ValueError:
        max_pages = 3

    reviews = scrape_flipkart_reviews(driver, product_url, max_pages)

    if reviews:
        df = pd.DataFrame(reviews)
        filename = "flipkart_reviews.csv"
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print(f"✅ Saved {len(reviews)} reviews to {filename}")
    else:
        print("⚠️ No reviews scraped.")

    driver.quit()
