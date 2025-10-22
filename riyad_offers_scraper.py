import os
import json
import requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# --- CONFIG ---
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Offers"

def get_offers_from_page(url, category, card_type):
    """Fetches offers from a single page."""
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    offers = []
    # Find "Learn more" links to locate offer blocks
    links = soup.find_all("a", string=lambda t: t and "Learn more" in t)
    for link in links:
        section = link.find_parent()
        text = section.get_text(" ", strip=True)
        merchant = ""
        offer = ""
        valid_until = ""
        description = ""

        # Simple heuristic to split out merchant and offer
        parts = text.split("Valid until")
        if len(parts) > 1:
            valid_until = parts[1].split()[0]
        if len(parts) > 0:
            main = parts[0]
            if "Off" in main:
                offer = main
            merchant = main.split("Off")[0].strip()

        offers.append({
            "Category": category,
            "Merchant": merchant,
            "Offer": offer,
            "Valid Until": valid_until,
            "Description": description,
            "Card Type": card_type,
            "Learn More": link["href"],
            "Source URL": url,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    return offers

def get_all_offers():
    """Scrapes all credit-card and mada-card offer pages."""
    base_credit = "https://www.riyadbank.com/personal-banking/credit-cards/offers/"
    categories = [
        "fashion", "lifestyle", "dining", "travel",
        "health", "entertainment", "hotels"
    ]
    offers = []
    for cat in categories:
        offers += get_offers_from_page(base_credit + cat, cat.title(), "Credit Card")

    # Add Mada offers page
    mada_url = "https://www.riyadbank.com/personal-banking/debit-card/offers"
    try:
        offers += get_offers_from_page(mada_url, "All", "Mada Debit")
    except Exception:
        pass

    return offers

def write_to_sheet(offers):
    """Writes the offers to the Google Sheet."""
    # Load service-account credentials from secret
    json_key = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not json_key:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON environment variable not set")
    creds_dict = json.loads(json_key)
    # Include scopes for Sheets and Drive API access
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)

    # Open the sheet by ID
    sh = gc.open_by_key(SHEET_ID)

    # Create or clear the target worksheet
    try:
        worksheet = sh.worksheet(SHEET_NAME)
        worksheet.clear()
    except Exception:
        worksheet = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=9)

    headers = [
        "Category", "Merchant", "Offer", "Valid Until", "Description",
        "Card Type", "Learn More", "Source URL", "Last Updated"
    ]
    worksheet.append_row(headers)

    for offer in offers:
        worksheet.append_row([
            offer["Category"],
            offer["Merchant"],
            offer["Offer"],
            offer["Valid Until"],
            offer["Description"],
            offer["Card Type"],
            offer["Learn More"],
            offer["Source URL"],
            offer["Last Updated"]
        ])

if __name__ == "__main__":
    offers = get_all_offers()
    if offers:
        write_to_sheet(offers)
        print(f"✅ {len(offers)} offers updated successfully!")
    else:
        print("⚠️ No offers found or scraping failed.")
