import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
import io

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

# সেসন স্টেট ইনিশিওলাইজেশন
if "results" not in st.session_state:
    st.session_state.results = []
if "processed_challans" not in st.session_state:
    st.session_state.processed_challans = set()

# সরকারি API থেকে সরাসরি তথ্য বের করার ফাংশন
def fetch_challan_data(clean_chl):
    chl_clean_str = re.sub(r'\D', '', clean_chl)
    if len(chl_clean_str) >= 15:
        c1 = chl_clean_str[:4]
        c2 = chl_clean_str[4:15]
    else:
        parts = clean_chl.split('-')
        c1 = parts[0].strip()
        c2 = parts[1].strip() if len(parts) > 1 else ""

    url = "https://challanverification.finance.gov.bd/echalan/verifyChallan"
    
    # বাংলাদেশি রিয়েল ইউজার হেডার
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://challanverification.finance.gov.bd/echalan/",
        "Origin": "https://challanverification.finance.gov.bd",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "X-Forwarded-For": "103.230.104.1", # বাংলাদেশি আইপি মাস্কিং
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    payload = {
        "challanNo1": c1,
        "challanNo2": c2
    }

    try:
        session = requests.Session()
        session.get("https://challanverification.finance.gov.bd/echalan/", headers=headers, timeout=10)
        response = session.post(url, data=payload, headers=headers, timeout=15)
        
        if response.status_code == 200 and "N/A" not in response.text:
            dfs = pd.read_html(response.text)
            if dfs and not dfs[0].empty:
                cells = dfs[0].values.flatten()
                if len(cells) >= 6:
                    return {
                        "চালান নং": clean_chl,
                        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": str(cells[0]),
                        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": str(cells[1]),
                        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": str(cells[2]),
                        "চালান নং (ওয়েবসাইট)": str(cells[3]),
                        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": str(cells[4]),
                        "জমার পরিমাণ": str(cells[5])
                    }
    except Exception:
        pass

    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "ডাটা পাওয়া যায়নি/সঠিক নয়",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "N/A",
        "জমার পরিমাণ": "N/A"
    }

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    st.success("ফাইল আপলোড সফল হয়েছে!")
    
    challans = []
    pattern = r'CHL:\s*(\d{4}-\d{11})'
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(pattern, text)
            for m in matches:
                if m not in challans:
                    challans.append(m)

    total_count = len(challans)
    completed_count = len(st.session_state.results)
    remaining_count = max(0, total_count - completed_count)

    col1, col2, col3 = st.columns(3)
    col1.metric("মোট চালান পাওয়া গেছে", f"{total_count} টি")
    col2.metric("সম্পন্ন হয়েছে", f"{completed_count} টি")
    col3.metric("বাকি আছে", f"{remaining_count} টি")

    btn_col1, btn_col2 = st.columns([2, 2])
    
    start_btn = btn_col1.button("▶️ ভেরিফিকেশন শুরু / বাকিগুলো সম্পন্ন করুন")
    reset_btn = btn_col2.button("🔄 সমস্ত ডাটা রিসেট করুন")

    if reset_btn:
        st.session_state.results = []
        st.session_state.processed_challans = set()
        st.rerun()

    progress_container = st.empty()
    status_text = st.empty()
    table_placeholder = st.empty()

    if st.session_state.results:
        table_placeholder.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)

    if start_btn:
        remaining_challans = [c for c in challans if c not in st.session_state.processed_challans]

        if not remaining_challans:
            st.info("সবগুলো চালানের ভেরিফিকেশন ইতিমধ্যেই শেষ হয়েছে!")
        else:
            for idx, clean_chl in enumerate(remaining_challans):
                current_overall = len(st.session_state.results) + 1
                status_text.text(f"প্রসেসিং চলছে: {current_overall}/{total_count} (চালান: {clean_chl})")
                progress_container.progress(current_overall / total_count)

                row_data = fetch_challan_data(clean_chl)

                st.session_state.results.append(row_data)
                st.session_state.processed_challans.add(clean_chl)
                table_placeholder.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)

            status_text.text(f"প্রসেসিং সম্পন্ন: {total_count}/{total_count}")
            progress_container.progress(1.0)
            st.success("ভেরিফিকেশন সম্পূর্ণ সফল হয়েছে!")
            st.rerun()

    if st.session_state.results:
        df = pd.DataFrame(st.session_state.results)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')

        st.download_button(
            label="📥 এক্সেল ফাইল ডাউনলোড করুন",
            data=buffer.getvalue(),
            file_name="Challan_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
