import streamlit as st
from googlesearch import search
import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime

# --- Connexion à Google Sheets via Streamlit Secrets ---
def get_gsheet():
    creds_json = st.secrets["GOOGLE_CREDENTIALS_JSON"]
    sheet_name = st.secrets["SHEET_NAME"]

    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet

# --- Lire le compteur du jour depuis la cellule C1 ---
def read_counter(sheet):
    try:
        return int(sheet.acell("C1").value)
    except:
        return 0

# --- Ajouter une ligne avec le nombre de requêtes ---
def increment_counter(sheet, nb):
    today = datetime.now().strftime("%Y-%m-%d")
    sheet.append_row([today, nb])  # Col A = date, Col B = nb requêtes

# --- Extraction emails ---
def extract_emails(text):
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def filter_emails(emails):
    blacklist = ['noreply', 'no-reply', 'donotreply', 'admin', 'support', 'contactform']
    filtered = [e for e in emails if not any(b in e.lower() for b in blacklist)]
    return list(set(filtered))

# --- Scraping avec barre de progression ---
def scrape_sites(keyword, num_results):
    results = []
    progress_bar = st.progress(0)

    for i, url in enumerate(search(keyword, num_results=num_results), start=1):
        try:
            response = requests.get(url, timeout=7, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            emails_raw = extract_emails(text)
            emails = filter_emails(emails_raw)
            title = soup.title.string.strip() if soup.title else url
            if emails:
                results.append({
                    'Site': url,
                    'Nom': title,
                    'Emails': ', '.join(emails)
                })
        except Exception:
            continue
        progress_bar.progress(i / num_results)

    return results

# --- Streamlit interface ---
st.title("🛠️ Extracteur d'emails - Recherche Google")

keyword = st.text_input("Métier + Ville", value="plombier Paris")
nb_sites = st.slider("Nombre de sites à scraper", min_value=1, max_value=50, value=10)

# Connexion à la feuille Google
sheet = get_gsheet()

# Lecture du compteur depuis la cellule C1
counter = read_counter(sheet)

st.info(f"🔢 Requêtes aujourd'hui : {counter} / 100 (limite recommandée)")

if st.button("Lancer la recherche"):
    if counter + nb_sites > 100:
        st.error("❌ Lancer cette recherche dépasserait la limite de 100 requêtes aujourd'hui.")
    else:
        with st.spinner('Recherche en cours...'):
            data = scrape_sites(keyword, nb_sites)

        if data:
            st.success(f"{len(data)} sites avec emails trouvés 👇")
            df = pd.DataFrame(data)
            st.dataframe(df)

            # Télécharger le CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Télécharger les résultats en CSV",
                data=csv,
                file_name='emails.csv',
                mime='text/csv'
            )

            # Incrémenter le compteur avec le nombre de sites analysés
            increment_counter(sheet, nb_sites)
        else:
            st.warning("Aucun email trouvé.")


