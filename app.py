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

# --- Gestion compteur ---
def read_counter(sheet):
    today = datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_records()

    # Cherche la ligne du jour
    for record in records:
        if record.get("date") == today:
            return int(record.get("count", 0))
    # Si pas trouvé, créer une nouvelle ligne
    sheet.append_row([today, 0])
    return 0

def write_counter(sheet, count):
    today = datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_records()
    for i, record in enumerate(records, start=2):
        if record.get("date") == today:
            sheet.update_cell(i, 2, count)  # Colonne 2 = count
            return
    # Si pas trouvé, ajouter une nouvelle ligne
    sheet.append_row([today, count])

# --- Extraction emails ---
def extract_emails(text):
    return re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)

def filter_emails(emails):
    blacklist = ['noreply', 'no-reply', 'donotreply', 'admin', 'support', 'contactform']
    filtered = []
    for e in emails:
        if not any(b in e.lower() for b in blacklist):
            filtered.append(e)
    return list(set(filtered))

def scrape_sites(keyword, num_results):
    results = []
    for url in search(keyword, num_results=num_results):
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
    return results

# --- Streamlit interface ---
st.title("🛠️ Extracteur d'emails - Recherche Google")

keyword = st.text_input("Métier + Ville", value="plombier Paris")
nb_sites = st.slider("Nombre de sites à scraper", min_value=1, max_value=50, value=10)

# Connexion à la feuille Google
sheet = get_gsheet()

# Lecture du compteur actuel
counter = read_counter(sheet)
st.info(f"🔢 Requêtes aujourd'hui : {counter} / 100 (limite recommandée)")

if st.button("Lancer la recherche"):
    if counter >= 100:
        st.error("❌ Limite de 100 requêtes atteinte aujourd'hui, merci de réessayer demain.")
    else:
        with st.spinner('Recherche en cours...'):
            data = scrape_sites(keyword, nb_sites)
        if data:
            st.success(f"{len(data)} sites avec emails trouvés 👇")

            # Afficher le tableau
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

            # Mise à jour compteur
            write_counter(sheet, counter + 1)

        else:
            st.warning("Aucun email trouvé.")

