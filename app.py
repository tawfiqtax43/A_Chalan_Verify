import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

st.set_page_config(page_title="এ-চালান ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

if 'results' not in st.session_state:
    st.session_state.results = {}

def fetch_single_challan(clean_chl):
    parts = clean_chl.split('-')
    c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
    c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

    session = requests.Session()
    
    # পোর্টের অফিসিয়াল ফর্ম সাবমিশন হেডার
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Content-Type': 'application/x-www-form-encoding',
        'Origin': 'https://challanverification.finance.gov.bd',
        'Referer': 'https://challanverification.finance.gov.bd/echalan/'
    }

    try:
        # ১. আগে মূল পেজ ভিউ করে কুকি ও সেশন নেওয়া
        init_res = session.get("https://challanverification.finance.gov.bd/echalan/", headers=headers, timeout=10)
        
        # ২. সরাসরি সার্চ ফর্মে POST রিকোয়েস্ট পাঠানো (যেভাবে ব্রাউজার পাঠায়)
        post_url = "https://challanverification.finance.gov.bd/echalan/"
        payload = {
            'c1': c1,
            'c2': c2,
            'txtChallanNo': clean_chl,
            'btnVerify': 'Verify',
            'submit': 'Verify'
        }
        
        res = session.post(post_url, data=payload, headers=headers, timeout=10)
        
        # ৩. পপ-আপ পেজ বা রেসপন্স পেজ থেকে টেবিল ডাটা রিড করা
        if res.status_code == 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # টেবিল খোঁজা
            tds = soup.find_all('td')
            if len(tds) < 6:
                # যদি মূল পাতায় না পেয়ে পপ-আপ ইউআরএল থাকে
                popup_url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={clean_chl}"
                res_pop = session.get(popup_url, headers=headers, timeout=10)
                if res_pop.status_code == 200:
                    res_pop.encoding = 'utf-8'
                    soup = BeautifulSoup(res_pop.text, 'html.parser')
                    tds = soup.find_all('td')

            if len(tds) >= 6:
                texts = [td.get_text(strip=True) for td in tds]
                
                # নিশ্চিত হওয়া যে এটি ভ্যালিড চালান রেজাল্ট
                if len(texts[0]) > 0 and "নয়" not in texts[0]:
                    return {
                        "চালান নং": clean_chl,
                        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": texts[0],
                        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": texts[1] if len(texts) > 1 else "N/A",
                        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": texts[2] if len(texts) > 2 else "N/A",
                        "চালান নং (ওয়েবসাইট)": texts[3] if len(texts) > 3 else clean_chl,
                        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": texts[4] if len(texts) > 4 else "N/A",
                        "জমার পরিমাণ": texts[5] if len(texts) > 5 else "N/A"
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

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

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
                    
    total_found = len(challans)
    processed_already = len([c for c in challans if c in st.session_state.results])
    remaining_challans = [c for c in challans if c not in st.session_state.results]

    col1, col2, col3 = st.columns(3)
    col1.metric("মোট চালান পাওয়া গেছে", f"{total_found} টি")
    col2.metric("সম্পন্ন হয়েছে", f"{processed_already} টি")
    col3.metric("বাকি আছে", f"{len(remaining_challans)} টি")

    btn_col1, btn_col2 = st.columns([2, 1])
    
    start_btn = btn_col1.button("▶️ ভেরিফিকেশন শুরু / বাকিগুলো সম্পন্ন করুন")
    reset_btn = btn_col2.button("🔄 সমস্ত ডাটা রিসেট করুন")

    if reset_btn:
        st.session_state.results = {}
        st.rerun()

    if start_btn and len(remaining_challans) > 0:
        progress_bar = st.progress(0)
        status_text = st.empty()
        table_holder = st.empty()
        
        completed_count = processed_already

        # সার্ভার ব্লক এড়াতে থ্রেড সংখ্যা ৪ রাখা হয়েছে
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in remaining_challans}
            
            for future in as_completed(future_to_chl):
                chl = future_to_chl[future]
                data = future.result()
                
                st.session_state.results[chl] = data
                completed_count += 1
                
                progress = completed_count / total_found
                progress_bar.progress(progress)
                status_text.text(f"প্রসেসিং চলছে: {completed_count}/{total_found}")
                
                if completed_count % 2 == 0 or completed_count == total_found:
                    df_live = pd.DataFrame(list(st.session_state.results.values()))
                    table_holder.dataframe(df_live.tail(5), use_container_width=True)

        st.success("ভেরিফিকেশন সম্পন্ন হয়েছে!")

    if len(st.session_state.results) > 0:
        st.write("---")
        st.subheader("📊 ফলাফল এবং এক্সেল ডাউনলোড")
        
        df_current = pd.DataFrame(list(st.session_state.results.values()))
        st.dataframe(df_current, use_container_width=True)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_current.to_excel(writer, index=False, sheet_name='Verification_Report')
        
        st.download_button(
            label=f"📥 এক্সেল ফাইল ডাউনলোড করুন ({len(df_current)} টি চালানের তথ্য)",
            data=buffer.getvalue(),
            file_name="Challan_Verification_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
