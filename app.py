import streamlit as st
import pdfplumber
import re
import pandas as pd
import time
import io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন প্ল্যাটফর্ম", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন প্ল্যাটফর্ম")
st.write("পিডিএফ আপলোড করুন, ব্যাকএন্ড ব্রাউজার থেকে তথ্য সংগ্রহ করে এক্সেল প্রস্তুত করে দেবে।")

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.binary_location = "/usr/bin/chromium"
    service = Service("/usr/bin/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def verify_single(driver, clean_chl):
    parts = clean_chl.split('-')
    c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
    c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

    try:
        driver.get("https://challanverification.finance.gov.bd/echalan/")
        time.sleep(1.5)

        inputs = driver.find_elements(By.TAG_NAME, "input")
        text_inputs = [i for i in inputs if i.get_attribute("type") == "text"]

        if len(text_inputs) >= 2:
            text_inputs[0].clear()
            text_inputs[0].send_keys(c1)
            text_inputs[1].clear()
            text_inputs[1].send_keys(c2)

            verify_btns = [i for i in inputs if i.get_attribute("value") == "Verify"]
            if verify_btns:
                verify_btns[0].click()
            
            time.sleep(2.5)

            tds = driver.find_elements(By.TAG_NAME, "td")
            texts = [td.text.strip() for td in tds[:10]]

            if len(texts) >= 6:
                return {
                    "চালান নং": clean_chl,
                    "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": texts[0],
                    "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": texts[1],
                    "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": texts[2],
                    "চালান নং (ওয়েবসাইট)": texts[3],
                    "কি বাবদ জমা দেওয়া হলো তার বিবরণ": texts[4],
                    "জমার পরিমাণ": texts[5]
                }
    except Exception:
        pass

    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "N/A",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "ডাটা পাওয়া যায়নি",
        "জমার পরিমাণ": "N/A"
    }

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
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        driver = create_driver()

        try:
            for idx, chl in enumerate(challans):
                data = verify_single(driver, chl)
                results.append(data)
                
                prog = (idx + 1) / len(challans)
                progress_bar.progress(prog)
                status_text.text(f"প্রসেসিং চলছে: {idx+1}/{len(challans)} (চালান: {chl})")

        finally:
            driver.quit()

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
