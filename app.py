import streamlit as st
import requests
import re
import json
import pandas as pd

from bs4 import BeautifulSoup
from datetime import datetime
from duckduckgo_search import DDGS

import gspread
from google.oauth2.service_account import Credentials


# ---------------------------
# Google Sheets
# ---------------------------
def get_gsheet():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    sheet_name = st.secrets["SHEET_NAME"]

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )

    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1


def read_counter(sheet):
    try:
        return int(sheet.acell("C1").value)
    except:
        return 0


def increment_counter(sheet, nb):
    today = datetime.now().strftime("%Y-%m-%d")
    sheet.append_row([today, nb])


# ---------------------------
# Email extraction
# ---------------------------
def extract_emails(soup):
    emails = set()

    # Emails dans le texte
    text = soup.get_text(" ")
    emails.update(
        re.findall(
            r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            text
        )
    )

    # Emails dans mailto:
    for a in soup.select("a[href^=mailto]"):
        href = a.get("href", "")
        email = href.replace("mailto:", "").split("?")[0]
        if "@" in email:
            emails.add(email)

    blacklist = [
        "noreply", "no-reply", "donotreply",
        "admin", "support", "contactform"
    ]

    return [
        e.lower() for e in emails
        if not any(b in e.lower() for b in blacklist)
    ]


# ---------------------------
# Pages candidates par site
# ---------------------------
def get_candidate_urls(base_url):
    base = base_url.rstrip("/")
    paths = [
        "",
        "/contact",
        "/contactez-nous",
        "/mentions-legales",
        "/legal",
        "/impressum"
    ]
    return [base + p for p in paths]


# ---------------------------
# Scrape un site (multi-pages)
# ---------------------------
def scrape_site(url):
    emails_found = set()
    title = url

    for page in get_candidate_urls(url):
        try:
            r = requests.get(
                page,
                timeout=8,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code != 200:
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            emails_found.update(extract_emails(soup))

            if soup.title and title == url:
                title = soup.title.string.strip()

        except Exception as e:
            st.write("Erreur page :", page, e)

    return title, list(emails_found)


# ---------------------------
# Scraping principal
# ---------------------------
def scrape_sites(keyword, num_results):
    results = []
    progress = st.progress(0)

    # 🔑 SOURCE URLS FIABLE
    with DDGS() as ddgs:
        raw_results = list(ddgs.text(keyword, max_results=num_results))

    search_results = [r for r in raw_results if "href" in r]

    if not search_results:
        st.error("Aucune URL récupérée depuis DuckDuckGo.")
        return []

    for i, r in enumerate(search_results, start=1):
        url = r["href"]

        if any(x in url for x in [
            "pagesjaunes", "yelp", "facebook",
            "linkedin", "instagram", "twitter"
        ]):
            continue

        title, emails = scrape_site(url)

        if emails:
            results.append({
                "Site": url,
                "Nom": title,
                "Emails": ", ".join(emails)
            })

        progress.progress(i / num_results)

    return results


# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Extracteur Emails", layout="wide")
st.title("🛠️ Extracteur d'emails – Recherche Web")

keyword = st.text_input("Métier + Ville", "plombier Paris")
nb_sites = st.slider("Nombre de sites à analyser", 1, 50, 10)

sheet = get_gsheet()
counter = read_counter(sheet)

st.info(f"🔢 Requêtes aujourd'hui : {counter} / 100")

if st.button("Lancer la recherche"):
    if counter + nb_sites > 100:
        st.error("❌ Limite journalière dépassée.")
    else:
        with st.spinner("Scraping en cours..."):
            data = scrape_sites(keyword, nb_sites)

        if data:
            df = pd.DataFrame(data)
            st.success(f"{len(df)} sites avec emails trouvés")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger en CSV",
                csv,
                "emails.csv",
                "text/csv"
            )

            increment_counter(sheet, nb_sites)
        else:
            st.warning("Aucun email trouvé.")
