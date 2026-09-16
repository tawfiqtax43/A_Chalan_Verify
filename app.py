import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

if "results" not in st.session_state:
    st.session_state.results = []
if "processed_challans" not in st.session_state:
    st.session_state.processed_challans = set()

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
            with sync_playwright() as p:
                # anti-bot detection এড়াতে প্রয়োজনীয় আর্গুমেন্ট
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )
                
                # আসল ব্রাউজারের মত ভান করার জন্য কনটেক্সট
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768}
                )
                page = context.new_page()

                # webdriver stealth ফ্ল্যাগ হাইড করা
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                for idx, clean_chl in enumerate(remaining_challans):
                    current_overall = len(st.session_state.results) + 1
                    status_text.text(f"প্রসেসিং চলছে: {current_overall}/{total_count} (চালান: {clean_chl})")
                    progress_container.progress(current_overall / total_count)

                    # ৪ ও ১১ সংখ্যাটি প্রপার আলাদা করা
                    chl_clean_str = re.sub(r'\D', '', clean_chl)
                    c1 = chl_clean_str[:4] if len(chl_clean_str) >= 4 else ""
                    c2 = chl_clean_str[4:15] if len(chl_clean_str) >= 15 else ""

                    row_data = None
                    try:
                        page.goto("https://challanverification.finance.gov.bd/echalan/", wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1000)

                        # আইফ্রেম থাকলে সেটি ধরা, না থাকলে মূল পেজ নেওয়া
                        frame = page.main_frame
                        if len(page.frames) > 1:
                            for f in page.frames:
                                if "echalan" in f.url or f.query_selector("input"):
                                    frame = f
                                    break

                        inputs = frame.query_selector_all("input[type='text']")
                        if len(inputs) >= 2:
                            inputs[0].click()
                            inputs[0].fill(c1)
                            inputs[1].click()
                            inputs[1].fill(c2)

                            page.wait_for_timeout(500)

                            # ফর্ম সাবমিট করা
                            verify_btn = frame.query_selector("input[value='Verify']")
                            if verify_btn:
                                verify_btn.click()
                            else:
                                inputs[1].press("Enter")

                            # ডাটা রেসপন্সের জন্য অপেক্ষা
                            page.wait_for_timeout(3500)

                        # রেজাল্ট টেবিল রিড করা
                        tds = frame.query_selector_all("td")
                        texts = [td.inner_text().strip() for td in tds if td.inner_text().strip()]

                        # ডাটা রিড নিশ্চিত করা
                        if len(texts) >= 5 and "N/A" not in texts[0]:
                            row_data = {
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

                    if not row_data:
                        row_data = {
                            "চালান নং": clean_chl,
                            "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "ডাটা পাওয়া যায়নি/সঠিক নয়",
                            "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
                            "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
                            "চালান নং (ওয়েবসাইট)": clean_chl,
                            "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "N/A",
                            "জমার পরিমাণ": "N/A"
                        }

                    st.session_state.results.append(row_data)
                    st.session_state.processed_challans.add(clean_chl)
                    table_placeholder.dataframe(pd.DataFrame(st.session_state.results), use_container_width=True)

                browser.close()

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
