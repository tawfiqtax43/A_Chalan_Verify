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

def create_challan_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
        'Referer': 'https://challanverification.finance.gov.bd/echalan/'
    })
    return session

def fetch_single_challan(chl):
    clean_chl = chl.strip()
    parts = clean_chl.split('-')
    c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
    c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

    session = create_challan_session()
    
    # পপ-আপ পাতার সরাসরি ইউআরএল এবং মেইন সার্চ পোস্ট মেথড দুইটাই ট্রাই করা হবে
    urls = [
        f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={clean_chl}",
        f"https://challanverification.finance.gov.bd/echalan/details.php?c1={c1}&c2={c2}"
    ]

    for url in urls:
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200 and len(res.text) > 200:
                res.encoding = 'utf-8'
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # প্রেজেন্টেশনের ৪ নম্বর স্লাইড অনুযায়ী টেবিলের TD ডাটা নেওয়া
                tds = soup.find_all('td')
                if len(tds) >= 6:
                    texts = [td.get_text(strip=True) for td in tds]
                    return {
                        "চালান নং": clean_chl,
                        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": texts[0] if texts[0] else "N/A",
                        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": texts[1] if texts[1] else "N/A",
                        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": texts[2] if texts[2] else "N/A",
                        "চালান নং (ওয়েবসাইট)": texts[3] if texts[3] else clean_chl,
                        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": texts[4] if texts[4] else "N/A",
                        "জমার পরিমাণ": texts[5] if texts[5] else "N/A"
                    }
        except Exception:
            pass

    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "N/A",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "ডাটা পাওয়া যায়নি/সঠিক নয়",
        "জমার পরিমাণ": "N/A"
    }

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
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
        
        # থ্রেড সংখ্যা ২ এ রেখে হালকা রিকোয়েস্ট পাঠানো হচ্ছে যেন সার্ভার ব্লক না করে
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in challans}
            
            for future in as_completed(future_to_chl):
                data = future.result()
                results.append(data)
                completed_count += 1
                
                progress_bar.progress(completed_count / total_challans)
                status_text.text(f"প্রসেস হচ্ছে: {completed_count}/{total_challans}")
        
        st.success("সকল চালান ভেরিফিকেশন সম্পন্ন হয়েছে!")
        
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
