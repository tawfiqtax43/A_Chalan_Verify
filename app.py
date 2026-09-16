import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
import time
import asyncio
from playwright.async_api import async_playwright

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

if "results" not in st.session_state:
    st.session_state.results = []
if "processed_challans" not in st.session_state:
    st.session_state.processed_challans = set()

async def fetch_with_playwright(c1, c2):
    """Playwright দিয়ে সত্যিকারের ব্রাউজারের মতো ওয়েবসাইট ওপেন করে ডাটা এক্সট্র্যাক্ট করে"""
    async with async_playwright() as p:
        # Launch headless Chromium browser
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # চালানের মূল পেজে প্রবেশ
            await page.goto("https://challanverification.finance.gov.bd/echalan/", timeout=30000, wait_until="networkidle")
            
            # প্রথম ঘর ও দ্বিতীয় ঘরে মান ইনপুট দেওয়া
            await page.fill("#challanNo1", c1)
            await page.fill("#challanNo2", c2)

            # সাবমিট/ভেরিফাই বাটনে ক্লিক করা (বা ফর্ম সাবমিট করা)
            # এ-চালানের সাবমিট বাটন অথবা ফর্ম প্রেস
            submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], .btn-primary")
            if submit_btn:
                await submit_btn.click()
            else:
                await page.keyboard.press("Enter")

            # রেজাল্ট লোড হওয়া পর্যন্ত ২ সেকেন্ড অপেক্ষা
            await page.wait_for_timeout(2500)

            # পেজের টেবিল ডাটা বের করা
            cells = await page.query_selector_all("table tr td")
            texts = []
            for cell in cells:
                txt = await cell.inner_text()
                if txt.strip():
                    texts.append(txt.strip())

            await browser.close()

            if len(texts) >= 6 and "ডাটা পাওয়া যায়নি" not in texts[0]:
                return {
                    "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": texts[0],
                    "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": texts[1],
                    "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": texts[2],
                    "চালান নং (ওয়েবসাইট)": texts[3],
                    "কি বাবদ জমা দেওয়া হলো তার বিবরণ": texts[4],
                    "জমার পরিমাণ": texts[5]
                }
        except Exception as e:
            await browser.close()
            
    return None

def verify_single_challan(clean_chl):
    chl_clean_str = re.sub(r'\D', '', clean_chl)
    if len(chl_clean_str) >= 15:
        c1 = chl_clean_str[:4]
        c2 = chl_clean_str[4:15]
    else:
        parts = clean_chl.split('-')
        c1 = parts[0].strip()
        c2 = parts[1].strip() if len(parts) > 1 else ""

    try:
        data = asyncio.run(fetch_with_playwright(c1, c2))
        if data:
            data["চালান নং"] = clean_chl
            return data
    except Exception:
        pass

    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "ডাটা পাওয়া যায়নি/সঠিক নয়",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "N/A",
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
    
    start_btn = btn_col1.button("▶️ অটোমেটেড ভেরিফিকেশন শুরু করুন")
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
                status_text.text(f"ব্রাউজারে ভেরিফাই চলছে: {current_overall}/{total_count} (চালান: {clean_chl})")
                progress_container.progress(current_overall / total_count)

                row_data = verify_single_challan(clean_chl)

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
