import streamlit as st
from googlesearch import search
import requests
import re
from bs4 import BeautifulSoup

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
    for url in search(keyword, num=num_results, stop=num_results, pause=2):
        try:
            response = requests.get(url, timeout=7, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            emails_raw = extract_emails(text)
            emails = filter_emails(emails_raw)
            title = soup.title.string.strip() if soup.title else url
            if emails:
                results.append({
                    'site': url,
                    'title': title,
                    'emails': emails
                })
        except Exception:
            continue
    return results

st.title("🛠️ Extracteur d'emails - Recherche Google")

keyword = st.text_input("Métier + Ville", value="plombier Paris")

nb_sites = st.slider("Nombre de sites à scraper", min_value=1, max_value=50, value=10)

if st.button("Lancer la recherche"):
    with st.spinner('Recherche en cours...'):
        data = scrape_sites(keyword, nb_sites)

    if data:
        st.success(f"{len(data)} sites avec emails trouvés :")
        for item in data:
            st.markdown(f"**[{item['title']}]({item['site']})**")
            st.write(", ".join(item['emails']))
    else:
        st.warning("Aucun email trouvé.")
