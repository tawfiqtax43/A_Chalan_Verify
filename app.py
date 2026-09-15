import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

st.title("ই-চালান স্বয়ংক্রিয় ভেরিফিকেশন ও এক্সেল জেনারেটর")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

def fetch_single_challan(chl):
    url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={chl}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    # ৩ বার চেষ্টা করবে যদি সার্ভার স্লো থাকে
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200 and len(response.text) > 500:
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                tds = soup.find_all('td')
                
                if len(tds) >= 4:
                    collector = tds[1].get_text(strip=True)
                    payer = tds[2].get_text(strip=True)
                    section = tds[4].get_text(strip=True) if len(tds) > 4 else tds[3].get_text(strip=True)
                    
                    return {
                        "চালান নং": chl,
                        "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": collector if collector else "N/A",
                        "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": payer if payer else "N/A",
                        "যে ধারায় আদায় হয়েছে": section if section else "N/A"
                    }
            time.sleep(1) # চেষ্টা ব্যর্থ হলে ১ সেকেন্ড অপেক্ষা
        except Exception:
            time.sleep(1)
            
    return {
        "চালান নং": chl,
        "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": "N/A",
        "যে ধারায় আদায় হয়েছে": "ডাটা পাওয়া যায়নি/সার্ভার স্লো"
    }

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
    # নিখুঁত চালান নম্বর ম্যাচিং
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
        
        # থ্রেড সংখ্যা ৫ এ রেখে সার্ভারে চাপ কমানো হলো যাতে ব্লক না করে
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in challans}
            
            for future in as_completed(future_to_chl):
                data = future.result()
                results.append(data)
                completed_count += 1
                
                progress_bar.progress(completed_count / total_challans)
                status_text.text(f"প্রসেস হচ্ছে: {completed_count}/{total_challans}")
        
        status_text.text("সকল চালান ভেরিফিকেশন সম্পন্ন হয়েছে!")
        
        # ডাটাফ্রেম তৈরি
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
