import os
import re
import json
import requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# =========================
# CONFIGURATION
# =========================
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Offers"

BASE_CREDIT_URL = "https://www.riyadbank.com/personal-banking/credit-cards/offers/"
CATEGORIES = [
    "fashion",
    "lifestyle",
    "dining",
    "travel",
    "health",
    "entertainment",
    "hotels"
]
MADA_URL = "https://www.riyadbank.com/personal-banking/debit-card/offers"


# =========================
# FUNCTIONS
# =========================

def fetch_page(url):
    """Fetches and returns a BeautifulSoup object for a given URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
        return None


def extract_offers_from_page(soup, category, card_type):
    """Extracts offers data from a given category page."""
    offers = []
    if not soup:
        return offers

    offer_blocks = soup.find_all(["div", "article"], class_=re.compile("(offer|promo|card|merchant)", re.I))
    if not offer_blocks:
        offer_blocks = soup.find_all("a", string=re.compile("Learn more", re.I))

    for block in offer_blocks:
        text = block.get_text(" ", strip=True)
        if not text:
            continue

        merchant = None
        offer_text = None
        validity = None

        # Extract merchant name
        match_merchant = re.search(r"([A-Z][A-Za-z&'\- ]{2,})", text)
        if match_merchant:
            merchant = match_merchant.group(1).strip()

        # Extract discount or deal
        match_offer = re.search(r"(\d+%|\$\d+|off|discount|cashback)", text, re.I)
        if match_offer:
            offer_text = match_offer.group(0).strip()

        # Extract validity
        match_valid = re.search(r"Valid\s+until\s+([\d\-/\.A-Za-z]+)", text)
        if match_valid:
            validity = match_valid.group(1).strip()

        link_tag = block.find("a", href=True)
        link = link_tag["href"] if link_tag else ""

        offers.append({
            "Category": category.title(),
            "Merchant": merchant or "N/A",
            "Offer": offer_text or text[:60] + "...",
            "Valid Until": validity or "N/A",
            "Description": text,
            "Card Type": card_type,
            "Learn More": link,
            "Source URL": soup.base.get("href") if soup.base else "",
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    print(f"✅ {len(offers)} offers found in {category} ({card_type})")
    return offers


def scrape_all_offers():
    """Scrapes all Credit and Mada offers."""
    all_offers = []
    for category in CATEGORIES:
        url = BASE_CREDIT_URL + category
        soup = fetch_page(url)
        offers = extract_offers_from_page(soup, category, "Credit Card")
        all_offers.extend(offers)

    # Mada Debit Offers
    mada_soup = fetch_page(MADA_URL)
    all_offers.extend(extract_offers_from_page(mada_soup, "Mada", "Mada Debit"))
    print(f"🔍 Total offers scraped: {len(all_offers)}")
    return all_offers


def write_to_sheet(offers):
    """Writes offers to Google Sheet."""
    if not offers:
        print("⚠️ No offers to write.")
        return

    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise ValueError("Missing GOOGLE_CREDENTIALS_JSON environment variable")

    creds_dict = json.loads(creds_json)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=9)

    headers = [
        "Category", "Merchant", "Offer", "Valid Until", "Description",
        "Card Type", "Learn More", "Source URL", "Last Updated"
    ]
    ws.append_row(headers)
    ws.append_rows([
        [
            o["Category"], o["Merchant"], o["Offer"], o["Valid Until"],
            o["Description"], o["Card Type"], o["Learn More"],
            o["Source URL"], o["Last Updated"]
        ]
        for o in offers
    ])
    print(f"✅ Sheet updated successfully with {len(offers)} offers.")


if __name__ == "__main__":
    offers = scrape_all_offers()
    write_to_sheet(offers)
