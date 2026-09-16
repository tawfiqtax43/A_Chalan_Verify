import streamlit as st
import pdfplumber
import re
import pandas as pd
import time
import io
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন প্ল্যাটফর্ম", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন প্ল্যাটফর্ম")
st.write("পিডিএফ আপলোড করুন, ব্যাকএন্ড ব্রাউজার থেকে তথ্য সংগ্রহ করে এক্সেল প্রস্তুত করে দেবে।")

def verify_all_challans(challans):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    with sync_playwright() as p:
        # Render-এ চালানোর জন্য হেডলেস ক্রোমিয়াম লঞ্চ
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for idx, clean_chl in enumerate(challans):
            parts = clean_chl.split('-')
            c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
            c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

            status_text.text(f"প্রসেসিং চলছে: {idx+1}/{len(challans)} (চালান: {clean_chl})")
            
            data_found = False
            try:
                page.goto("https://challanverification.finance.gov.bd/echalan/", timeout=30000)
                page.wait_for_timeout(1000)

                inputs = page.query_selector_all("input[type='text']")
                if len(inputs) >= 2:
                    inputs[0].fill(c1)
                    inputs[1].fill(c2)

                    verify_btn = page.query_selector("input[value='Verify']")
                    if verify_btn:
                        verify_btn.click()
                    else:
                        page.keyboard.press("Enter")

                    page.wait_for_timeout(2500)

                tds = page.query_selector_all("td")
                texts = [td.inner_text().strip() for td in tds[:10]]

                if len(texts) >= 6:
                    results.append({
                        "চালান নং": clean_chl,
                        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": texts[0],
                        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": texts[1],
                        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": texts[2],
                        "চালান নং (ওয়েবসাইট)": texts[3],
                        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": texts[4],
                        "জমার পরিমাণ": texts[5]
                    })
                    data_found = True
            except Exception:
                pass

            if not data_found:
                results.append({
                    "চালান নং": clean_chl,
                    "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "N/A",
                    "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
                    "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
                    "চালান নং (ওয়েবসাইট)": clean_chl,
                    "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "ডাটা পাওয়া যায়নি",
                    "জমার পরিমাণ": "N/A"
                })

            progress_bar.progress((idx + 1) / len(challans))

        browser.close()

    return results

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    challans = []
    pattern = r'CHL:\s*(\d{4}-\d{11})'
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(pattern, text)
            for m in matches:
                if m not in challans:
                    challans.append(m)

    st.info(f"মোট {len(challans)} টি চালান পাওয়া গেছে।")

    if st.button("▶️ অটোমেটিক ভেরিফিকেশন শুরু করুন"):
        with st.spinner("ব্রাউজার চালুর মাধ্যমে ডাটা ভেরিফাই করা হচ্ছে..."):
            results = verify_all_challans(challans)

        st.success("ভেরিফিকেশন সম্পন্ন হয়েছে!")
        df = pd.DataFrame(results)
        st.dataframe(df)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Report')

        st.download_button(
            label="📥 এক্সেল ফাইল ডাউনলোড করুন",
            data=buffer.getvalue(),
            file_name="Challan_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
