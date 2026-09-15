import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.title("ই-চালান স্বয়ংক্রিয় ভেরিফিকেশন ও এক্সেল জেনারেটর")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে! ডাটা এক্সট্র্যাক্ট করা হচ্ছে...")
    
    # PDF থেকে চালান নম্বর সংগ্রহ
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
    
    if st.button("যাচাইকরণ শুরু করুন"):
        progress_bar = st.progress(0)
        results = []
        
        # Requests Session চালুকরণ
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        for idx, chl in enumerate(challans):
            url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={chl}"
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # চালানের টেবিল থেকে কলামগুলো বের করা
                tds = soup.find_all('td')
                
                # কলাম ডাটা নিরাপদভাবে এক্সট্র্যাক্ট করা
                collector = tds[1].get_text(strip=True) if len(tds) > 1 else "N/A"
                payer = tds[2].get_text(strip=True) if len(tds) > 2 else "N/A"
                section = tds[4].get_text(strip=True) if len(tds) > 4 else "N/A"
                
                results.append({
                    "চালান নং": chl,
                    "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": collector,
                    "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": payer,
                    "যে ধারায় আদায় হয়েছে": section
                })
            except Exception as e:
                results.append({
                    "চালান নং": chl,
                    "যার মাধ্যমে টাকা আদায় হয়েছে (নাম ও সনাক্তকরণ)": "N/A",
                    "যার পক্ষ হতে টাকা আদায় হয়েছে (নাম ও ঠিকানা)": "N/A",
                    "যে ধারায় আদায় হয়েছে": "Error/Not Found"
                })
            
            progress_bar.progress((idx + 1) / len(challans))
            
        # এক্সেল ফাইল প্রস্তুতকরণ
        df = pd.DataFrame(results)
        excel_file = "Challan_Verification_Report.xlsx"
        df.to_excel(excel_file, index=False)
        
        st.success("সকল চালান ভেরিফিকেশন সম্পন্ন হয়েছে!")
        
        with open(excel_file, "rb") as f:
            st.download_button(
                label="📥 এক্সেল ফাইল ডাউনলোড করুন",
                data=f,
                file_name=excel_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
