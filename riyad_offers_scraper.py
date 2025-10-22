import os
import requests
from bs4 import BeautifulSoup
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

# --- CONFIG ---
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Offers"

# Public access credentials using a service account JSON key
# (you can replace this with your own if you want private access later)
SERVICE_ACCOUNT_FILE = "service_account.json"  # Optional placeholder

def get_offers_from_page(url, category, card_type):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    offers = []
    blocks = soup.find_all("a", string=lambda t: t and "Learn more" in t)
    for block in blocks:
        section = block.find_parent()
        text = section.get_text(" ", strip=True)
        merchant = ""
        offer = ""
        valid_until = ""
        description = ""

        # simple parsing heuristic
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
            "Learn More": block["href"],
            "Source URL": url,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
    return offers


def get_all_offers():
    base_credit = "https://www.riyadbank.com/personal-banking/credit-cards/offers/"
    categories = [
        "fashion", "lifestyle", "dining", "travel",
        "health", "entertainment", "hotels"
    ]
    offers = []
    for cat in categories:
        offers += get_offers_from_page(base_credit + cat, cat.title(), "Credit Card")

    # Add Mada offers page if exists
    mada_url = "https://www.riyadbank.com/personal-banking/debit-card/offers"
    try:
        offers += get_offers_from_page(mada_url, "All", "Mada Debit")
    except Exception:
        pass

    return offers


def write_to_sheet(offers):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)
    sh = gc.open_by_key(SHEET_ID)

    # create or clear
    try:
        worksheet = sh.worksheet(SHEET_NAME)
        worksheet.clear()
    except:
        worksheet = sh.add_worksheet(title=SHEET_NAME, rows=1000, cols=9)

    headers = [
        "Category", "Merchant", "Offer", "Valid Until", "Description",
        "Card Type", "Learn More", "Source URL", "Last Updated"
    ]
    worksheet.append_row(headers)
    for offer in offers:
        worksheet.append_row(list(offer.values()))


if __name__ == "__main__":
    offers = get_all_offers()
    if offers:
        write_to_sheet(offers)
        print(f"✅ {len(offers)} offers updated successfully!")
    else:
        print("⚠️ No offers found or scraping failed.")
