import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://challanverification.finance.gov.bd/echalan/'
}

def fetch_single_challan(chl):
    clean_chl = chl.strip()
    
    # ৩ নম্বর স্লাইডে দেখানো পপ-আপ উইন্ডোর সরাসরি লিংক URL
    url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={clean_chl}"

    try:
        response = session.get(url, headers=headers, timeout=12)
        if response.status_code == 200 and len(response.text) > 300:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tds = soup.find_all('td')
            
            # ৪ নম্বর স্লাইড অনুযায়ী কলাম ১ থেকে ৬ এর ডাটা নেওয়া
            if len(tds) >= 6:
                col1 = tds[0].get_text(strip=True) # ১নং কলাম: সরকারি প্রতিষ্ঠান
                col2 = tds[1].get_text(strip=True) # ২নং কলাম: যার মাধ্যমে টাকা আদায় হয়েছে
                col3 = tds[2].get_text(strip=True) # ৩নং কলাম: যার পক্ষ হতে টাকা আদায় হয়েছে
                col4 = tds[3].get_text(strip=True) # ৪নং কলাম: চালান নং
                col5 = tds[4].get_text(strip=True) # ৫নং কলাম: বিবরণ/ধারা
                col6 = tds[5].get_text(strip=True) # ৬নং কলাম: জমা পরিমাণ

                return {
                    "চালান নং": clean_chl,
                    "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": col1 if col1 else "N/A",
                    "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": col2 if col2 else "N/A",
                    "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": col3 if col3 else "N/A",
                    "চালান নং (ওয়েবসাইট)": col4 if col4 else clean_chl,
                    "কি বাবদ জমা দেওয়া হলো তার বিবরণ": col5 if col5 else "N/A",
                    "জমার পরিমাণ": col6 if col6 else "N/A"
                }
    except Exception:
        pass
            
    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "N/A",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "ডাটা পাওয়া যায়নি/সঠিক নয়",
        "জমার পরিমাণ": "N/A"
    }

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
    # ১ম স্লাইডের CHL: এর পরের ১৫ ডিজিটের নম্বর ধরার প্যাটার্ন
    pattern = r'CHL:\s*(\d{4}-\d{11})'
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(pattern, text)
            for m in matches:
                if m not in challans:
                    challans.append(m)
                    
    st.write(f"মোট চালান নম্বর পাওয়া গেছে: {len(challans)} টি")
    
    if len(challans) > 0:
        st.write("নমুনা চালান নম্বর:", challans[:3])

    if st.button("স্বয়ংক্রিয় ভেরিফিকেশন শুরু করুন"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        completed_count = 0
        total_challans = len(challans)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
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
