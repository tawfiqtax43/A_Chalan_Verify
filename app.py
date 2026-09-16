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

# সেসন স্টেট ইনিশিয়ালাইজেশন (রিসিউম এবং লাইভ ডেটার জন্য)
if 'results' not in st.session_state:
    st.session_state.results = {}  # {challan_no: dict_data}

def fetch_single_challan(clean_chl):
    parts = clean_chl.split('-')
    c1 = parts[0].strip() if len(parts) >= 2 else clean_chl[:4]
    c2 = "-".join(parts[1:]).strip() if len(parts) >= 2 else clean_chl[4:]

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://challanverification.finance.gov.bd/echalan/'
    })

    # ১ম চেষ্টা: পপ-আপ সরাসরি ইউআরএল (দ্রুততম)
    url = f"https://challanverification.finance.gov.bd/echalan/details.php?challanNo={clean_chl}"
    try:
        res = session.get(url, timeout=5)
        if res.status_code == 200 and len(res.text) > 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
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

    # ২য় চেষ্টা: c1 ও c2 প্যারামিটার
    url2 = f"https://challanverification.finance.gov.bd/echalan/details.php?c1={c1}&c2={c2}"
    try:
        res = session.get(url2, timeout=5)
        if res.status_code == 200 and len(res.text) > 200:
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
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

        # সমান্তরাল ১০টি থ্রেড একসাথে দ্রুত কাজ করবে
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_chl = {executor.submit(fetch_single_challan, chl): chl for chl in remaining_challans}
            
            for future in as_completed(future_to_chl):
                chl = future_to_chl[future]
                data = future.result()
                
                # ফলাফল লাইভ মেমরিতে সেভ হচ্ছে
                st.session_state.results[chl] = data
                completed_count += 1
                
                # অগ্রগতি আপডেট
                progress = completed_count / total_found
                progress_bar.progress(progress)
                status_text.text(f"প্রসেসিং চলছে: {completed_count}/{total_found} (বাকি {total_found - completed_count}টি)")
                
                # প্রতি ৩টি শেষ হলে স্ক্রিনে লাইভ টেবিল আপডেট দেখানো
                if completed_count % 3 == 0 or completed_count == total_found:
                    df_live = pd.DataFrame(list(st.session_state.results.values()))
                    table_holder.dataframe(df_live.tail(5), use_container_width=True)

        st.success("ভেরিফিকেশন সম্পন্ন হয়েছে/যেটুকু সফল হয়েছে তা নিচে প্রস্তুত!")

    # যেকোনো মুহূর্তে ডাউনলোড সুবিধা (আংশিক অথবা সম্পূর্ণ)
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
```কাজ মাঝখানে থেমে গেলে বা স্লো হলে ফাইল দেখা না যাওয়ার মূল কারণ হলো **Excel সাধারণত ফাইল পুরোপুরি সেভ (Save) না হওয়া পর্যন্ত Disk-এ Output ফাইল লেখে না, অথবা Python script চলাকালীন Memory (RAM)-তেই ডেটা ধরে রাখে।**

Script শেষ হওয়ার আগে যাতে আপনি তৈরি হওয়া **আংশিক ডেটা (Partial Data)** সাথে সাথেই দেখে নিতে পারেন, তার জন্য নিচে **২টি সেরা সমাধান** দেওয়া হলো:

---

### সমাধান ১: ডেটা প্রসেস করার পর অটোমেটিক সাথে সাথেই সেভ করা (추천)

স্ক্রিপ্টের কোডে এমন লজিক যোগ করুন যাতে প্রতি **১০টি বা ২০টি SL** প্রসেস হওয়ার পর ফাইলটি **অটো-সেভ (Auto-save)** হতে থাকে। এতে কাজ মাঝখানে আটকে গেলেও আপনি ফাইলের প্রসেস হওয়া অংশটুকু Excel-এ দেখতে পাবেন।

Python (Pandas / Openpyxl) ব্যবহার করলে আপনার মূল `loop`-এর ভেতরে নিচের কোডটি যোগ করতে পারেন:

```python
# উদাহরণ: প্রতি ১০টি SL প্রসেস হওয়ার পর ফাইল সেভ হবে
for index, row in enumerate(data_list):
    # --- আপনার ডেটা আলাদা করার মূল কোড ---

    # প্রতি ১০টা প্রসেস শেষ হলে ফাইল অটো সেভ হবে
    if (index + 1) % 10 == 0:
        df_output.to_excel("separated_tax_data.xlsx", index=False)
        print(f"{index + 1} টি SL প্রসেস সম্পন্ন এবং ফাইল সেভ করা হয়েছে।")

# সব কাজ শেষ হলে চূড়ান্ত সেভ
df_output.to_excel("separated_tax_data.xlsx", index=False)
