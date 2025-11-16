import sys
sys.stdout.reconfigure(encoding='utf-8')

import pickle
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

COOKIE_FILE = "amazon_cookies.pkl"

def setup_driver():
    options = Options()
    # Headless disabled so you can log in manually
    # options.add_argument("--headless=new")  # Optional if you want headless later
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    return driver

if __name__ == "__main__":
    print("🔄 Opening Amazon login page...")
    driver = setup_driver()
    driver.get("https://www.amazon.in/")

    print("\n🔐 Please log in manually (enter OTP if required).")
    print("➡️ Make sure your account name appears in the top-right corner.")
    input("\n👉 Press ENTER **only after you are logged in**... ")

    # Get cookies after login
    cookies = driver.get_cookies()

    if len(cookies) < 10:  # Amazon normally sets 30–40 cookies
        print("❌ Login not detected! Cookies look incomplete.")
        print("Please log in fully and try again.")
        driver.quit()
        sys.exit()

    # Save cookies
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)

    print(f"\n✅ Cookies saved successfully → {COOKIE_FILE}")
    print("🎉 You can now run your Amazon review scraper using these cookies!")

    driver.quit()
