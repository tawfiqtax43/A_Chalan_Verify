import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.title("এ-চালান ভেরিফাই")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)
session.mount('http://', adapter)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded'
}

def fetch_single_challan(chl):
    # চালান নম্বরকে ২ ভাগে ভাগ করা (যেমন: 2627 এবং বাকি অংশ)
    parts = chl.split('-')
    if len(parts) == 2:
        c1, c2 = parts[0], parts[1]
    else:
        c1, c2 = chl[:4], chl[4:].replace('-', '')

    url = "https://challanverification.finance.gov.bd/echalan/details.php"
    
    # ফর্মের ইনপুট ডাটা তৈরি (সরাসরি আপনার মার্ক করা ফর্মের সাবমিশন)
    payload = {
        'c1': c1,
        'c2': c2,
        'challanNo': chl,
        'btnVerify': 'Verify'
    }

    for attempt in range(2):
        try:
            # POST এবং GET দুটো পদ্ধতিই হ্যান্ডেল করবে
            response = session.post(url, data=payload, headers=headers, timeout=8)
            if response.status_code != 200 or len(response.text) < 300:
                response = session.get(f"{url}?challanNo={chl}&c1={c1}&c2={c2}", headers=headers, timeout=8)

            if response.status_code == 200:
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                tds = soup.find_all('td')
                
                # ওয়েবসাইট থেকে ডাটা পড়া
                if len(tds) >= 4:
                    collector = tds[1].get_text(strip=True)
                    payer = tds[2].get_text(strip=True)
                    section = tds[4].get_text(strip=True) if len(tds) > 4 else tds[3].get_text(strip=True)
                    
                    if collector or payer:
                        return {
                            "চালান নং": chl,
                            "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": collector if collector else "N/A",
                            "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": payer if payer else "N/A",
                            "যে ধারায় আদায় হয়েছে": section if section else "N/A"
                        }
        except Exception:
            pass
            
    return {
        "চালান নং": chl,
        "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": "N/A",
        "যে ধারায় আদায় হয়েছে": "ডাটা পাওয়া যায়নি/সঠিক নয়"
    }

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
    pattern = r'\b\d{4}-\d{10,11}\b'
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(pattern, text)
            for m in matches:
                if m not in challans:
                    challans.append(m)
                    
    st.write(f"মোট বৈধ চালান নম্বর পাওয়া গেছে: {len(challans)} টি")
    
    if st.button("স্বয়ংক্রিয় ভেরিফিকেশন শুরু করুন"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        completed_count = 0
        total_challans = len(challans)
        
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in challans}
            
            for future in as_completed(future_to_chl):
                data = future.result()
                results.append(data)
                completed_count += 1
                
                progress_bar.progress(completed_count / total_challans)
                status_text.text(f"প্রসেস হচ্ছে: {completed_count}/{total_challans}")
        
        status_text.text("সকল চালান ভেরিফিকেশন সম্পন্ন হয়েছে!")
        
        df = pd.DataFrame(results)
        excel_file = "Challan_Verification_Report.xlsx"
        df.to_excel(excel_file, index=False)
        
        with open(excel_file, "rb") as f:
            st.download_button(
                label="📥 এক্সেল ফাইল ডাউনলোড করুন",
                data=f,
                file_name=excel_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
