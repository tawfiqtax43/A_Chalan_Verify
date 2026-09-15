import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

st.title("এ-চালান ভেরিফিকেশন,কর অঞ্চল-৩(চট্টগ্রাম)")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

def fetch_single_challan(chl):
    url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={chl}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tds = soup.find_all('td')
        
        collector = tds[1].get_text(strip=True) if len(tds) > 1 else "N/A"
        payer = tds[2].get_text(strip=True) if len(tds) > 2 else "N/A"
        section = tds[4].get_text(strip=True) if len(tds) > 4 else "N/A"
        
        return {
            "চালান নং": chl,
            "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": collector,
            "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": payer,
            "যে ধারায় আদায় হয়েছে": section
        }
    except Exception:
        return {
            "চালান নং": chl,
            "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": "N/A",
            "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": "N/A",
            "যে ধারায় আদায় হয়েছে": "Error/Timeout"
        }

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
    pattern = r'2627-\d{11}'
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(pattern, text)
            for m in matches:
                if m not in challans:
                    challans.append(m)
                    
    st.write(f"মোট চালান নম্বর পাওয়া গেছে: {len(challans)} টি")
    
    if st.button("স্বয়ংক্রিয় ভেরিফিকেশন শুরু করুন"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        completed_count = 0
        total_challans = len(challans)
        
        # একসাথে ১০টি থ্রেডে সমান্তরালভাবে ভেরিফাই হবে
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in challans}
            
            for future in as_completed(future_to_chl):
                data = future.result()
                results.append(data)
                completed_count += 1
                
                # প্রোগ্রেস আপডেট
                progress_bar.progress(completed_count / total_challans)
                status_text.text(f"প্রসেস হচ্ছে: {completed_count}/{total_challans}")
        
        status_text.text("সকল চালান ভেরিফিকেশন সম্পন্ন হয়েছে!")
        
        # চালানের ক্রমানুসারে সাজানো
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
