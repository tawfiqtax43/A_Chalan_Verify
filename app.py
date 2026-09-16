import streamlit as st
import pdfplumber
import re
import pandas as pd
import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

# Playwright Chromium ব্রাউজার সার্ভারে ইন্সটল নিশ্চিত করা
@st.cache_resource
def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Playwright installation failed: {e}")

install_playwright_browsers()

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

uploaded_file = st.file_uploader("আপনার PDF ফাইলটি আপলোড করুন", type=["pdf"])

async def verify_challan_with_browser(clean_chl, page):
    parts = clean_chl.split('-')
    c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
    c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

    try:
        await page.goto("https://challanverification.finance.gov.bd/echalan/", timeout=30000)
        
        inputs = await page.query_selector_all("input[type='text']")
        if len(inputs) >= 2:
            await inputs[0].fill(c1)
            await inputs[1].fill(c2)
            
            verify_btn = await page.query_selector("input[value='Verify']")
            if verify_btn:
                async with page.expect_navigation(timeout=10000):
                    await verify_btn.click()
            else:
                await page.keyboard.press("Enter")
            
            await page.wait_for_timeout(2000)

        tds = await page.query_selector_all("td")
        texts = []
        for td in tds[:10]:
            t = await td.inner_text()
            texts.append(t.strip())

        if len(texts) >= 6:
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

async def process_all_challans(challan_list):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, chl in enumerate(challan_list):
            data = await verify_challan_with_browser(chl, page)
            results.append(data)
            progress_bar.progress((idx + 1) / len(challan_list))
            status_text.text(f"প্রসেস হচ্ছে: {idx + 1}/{len(challan_list)}")
            
        await browser.close()
    return results

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
        results = asyncio.run(process_all_challans(challans))
        
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
