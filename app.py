import streamlit as st
from googlesearch import search
import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Fonction pour se connecter à Google Sheet ---
def get_gsheet():
    creds_json = st.secrets["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(creds_json)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.Client(auth=creds)
    client.session = gspread.requests.Session()
    sheet_name = st.secrets["SHEET_NAME"]
    sheet = client.open(sheet_name).sheet1
    return sheet

# --- Compteur ---
def reset_counter_if_new_day(sheet):
    today_str = datetime.now().strftime("%Y-%m-%d")
    last_date = sheet.acell('B1').value
    if last_date != today_str:
        sheet.update('A1', '0')
        sheet.update('B1', today_str)

def get_counter(sheet):
    val = sheet.acell('A1').value
    return int(val) if val and val.isdigit() else 0

def increment_counter(sheet):
    count = get_counter(sheet)
    count += 1
    sheet.update('A1', str(count))
    return count

# --- Extraction d'emails ---
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
        st.progress(i / num_results)
    return results

# --- Streamlit UI ---
st.title("🛠️ Extracteur d'emails - Recherche Google avec compteur")

# Connexion Google Sheet
sheet = get_gsheet()
reset_counter_if_new_day(sheet)
count = get_counter(sheet)

st.markdown(f"**Nombre de requêtes aujourd’hui : {count} / 100**")
if count >= 100:
    st.warning("⚠️ Limite de 100 requêtes atteinte, merci de patienter jusqu’à demain.")
    st.stop()

keyword = st.text_input("Métier + Ville", value="plombier Paris")
nb_sites = st.slider("Nombre de sites à scraper", min_value=1, max_value=50, value=10)

if st.button("Lancer la recherche"):
    with st.spinner('Recherche en cours...'):
        data = scrape_sites(keyword, nb_sites)
        # Incrémenter compteur 1 fois par recherche lancée
        increment_counter(sheet)

    if data:
        st.success(f"{len(data)} sites avec emails trouvés 👇")

        df = pd.DataFrame(data)
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger les résultats en CSV",
            data=csv,
            file_name='emails.csv',
            mime='text/csv'
        )
    else:
        st.warning("Aucun email trouvé.")
