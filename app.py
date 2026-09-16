import streamlit as st
import pdfplumber
import re
import pandas as pd
import streamlit.components.v1 as components
import json

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

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

    st.info(f"মোট {total_count} টি চালান পাওয়া গেছে। নিচের বোতামে ক্লিক করে ভেরিফিকেশন শুরু করুন।")

    js_code = f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <div id="status" style="font-weight:bold; font-size: 16px; margin-bottom: 10px; color: #0d6efd;"></div>
    <div id="progress-bar-container" style="width: 100%; background-color: #e0e0e0; border-radius: 5px; margin-bottom: 15px;">
        <div id="progress-bar" style="width: 0%; height: 20px; background-color: #198754; border-radius: 5px; transition: width 0.3s;"></div>
    </div>
    <button id="start-btn" style="padding: 10px 20px; font-size: 16px; background-color: #0d6efd; color: white; border: none; border-radius: 5px; cursor: pointer;">▶️ অটোমেটিক ভেরিফিকেশন শুরু করুন</button>
    <button id="download-btn" style="padding: 10px 20px; font-size: 16px; background-color: #198754; color: white; border: none; border-radius: 5px; cursor: pointer; display: none; margin-left: 10px;">📥 এক্সেল ফাইল ডাউনলোড করুন</button>
    <br/><br/>
    <table id="result-table" border="1" style="border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; text-align: left;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="padding: 8px;">চালান নং</th>
                <th style="padding: 8px;">যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে</th>
                <th style="padding: 8px;">যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)</th>
                <th style="padding: 8px;">যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)</th>
                <th style="padding: 8px;">চালান নং (ওয়েবসাইট)</th>
                <th style="padding: 8px;">কি বাবদ জমা দেওয়া হলো তার বিবরণ</th>
                <th style="padding: 8px;">জমার পরিমাণ</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>

    <script>
    const challans = {json.dumps(challans)};
    const results = [];

    document.getElementById('start-btn').addEventListener('click', async () => {{
        document.getElementById('start-btn').disabled = true;
        document.getElementById('start-btn').innerText = "প্রসেসিং চলছে...";
        const tbody = document.getElementById('result-table').querySelector('tbody');
        tbody.innerHTML = '';

        for (let i = 0; i < challans.length; i++) {{
            const cleanChl = challans[i];
            const cleanStr = cleanChl.replace(/\\D/g, '');
            const c1 = cleanStr.substring(0, 4);
            const c2 = cleanStr.substring(4, 15);

            document.getElementById('status').innerText = `প্রসেসিং চলছে: ${{i + 1}}/${{challans.length}} (চালান: ${{cleanChl}})`;
            document.getElementById('progress-bar').style.width = `${{((i + 1) / challans.length) * 100}}%`;

            let rowData = {{
                "চালান নং": cleanChl,
                "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "ডাটা পাওয়া যায়নি/সঠিক নয়",
                "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
                "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
                "চালান নং (ওয়েবসাইট)": cleanChl,
                "কি বাবদ জমা দেওয়া হলো তার বিবরণ": "N/A",
                "জমার পরিমাণ": "N/A"
            }};

            try {{
                const targetUrl = 'https://challanverification.finance.gov.bd/echalan/verifyChallan';
                const proxyUrl = 'https://api.allorigins.win/raw?url=' + encodeURIComponent(targetUrl);
                
                const formData = new URLSearchParams();
                formData.append('challanNo1', c1);
                formData.append('challanNo2', c2);

                const response = await fetch(proxyUrl, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                    }},
                    body: formData
                }});

                if (response.ok) {{
                    const htmlText = await response.text();
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(htmlText, 'text/html');
                    const tds = Array.from(doc.querySelectorAll('td')).map(td => td.innerText.trim()).filter(t => t);

                    if (tds.length >= 6) {{
                        rowData = {{
                            "চালান নং": cleanChl,
                            "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": tds[0] || "N/A",
                            "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": tds[1] || "N/A",
                            "সমস্যাটি মূলত **CORS (Cross-Origin Resource Sharing)** সিকিউরিটির জন্য হচ্ছে। ব্রাউজার থেকে সরাসরি সরকারি ওয়েবসাইটে রিকোয়েস্ট পাঠালে ব্রাউজার নিজেই তা ব্লক করে দেয় (যে কারণে সকল ঘরে N/A দেখাচ্ছে)। 

যেহেতু আপনি চান **কোনো প্রকার সমস্যা ছাড়া টিমের সকলেই যেন পাবলিক লিংক ব্যবহার করে ভেরিফাই করতে পারে**, তাই এর জন্য ক্লাউড সার্ভারেই একটি ছোট **Proxy Tunnel** বানিয়ে দেওয়া হয়েছে। এটি সরাসরি Render সার্ভার থেকে বাংলাদেশ সরকারের আসল ডোমেইনে সঠিক সেশন ও হেডার পাঠাবে।

নিচে আপডেট করা **`app.py`** কোডটি দেওয়া হলো। পুরো কোডটি রিপ্লেস করে Render-এ ডিপ্লয় করুন:

```python
import streamlit as st
import pdfplumber
import re
import pandas as pd
import requests
import io
import time

st.set_page_config(page_title="এ-চালান অটোমেটেড ভেরিফিকেশন", layout="wide")

st.title("এ-চালান অটোমেটেড ভেরিফিকেশন")
st.subheader("কর অঞ্চল-৩ (চট্টগ্রাম)")

if "results" not in st.session_state:
    st.session_state.results = []
if "processed_challans" not in st.session_state:
    st.session_state.processed_challans = set()

def fetch_challan_data(clean_chl):
    chl_clean_str = re.sub(r'\D', '', clean_chl)
    if len(chl_clean_str) >= 15:
        c1 = chl_clean_str[:4]
        c2 = chl_clean_str[4:15]
    else:
        parts = clean_chl.split('-')
        c1 = parts[0].strip()
        c2 = parts[1].strip() if len(parts) > 1 else ""

    url = "[https://challanverification.finance.gov.bd/echalan/verifyChallan](https://challanverification.finance.gov.bd/echalan/verifyChallan)"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "[https://challanverification.finance.gov.bd/echalan/](https://challanverification.finance.gov.bd/echalan/)",
        "Origin": "[https://challanverification.finance.gov.bd](https://challanverification.finance.gov.bd)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*"
    }
    
    payload = {
        "challanNo1": c1,
        "challanNo2": c2
    }

    try:
        session = requests.Session()
        # ১. প্রথমে হোম পেজে হিট করে কুকি/সেশন নেওয়া
        session.get("[https://challanverification.finance.gov.bd/echalan/](https://challanverification.finance.gov.bd/echalan/)", headers=headers, timeout=10)
        
        # ২. পোস্ট রিকোয়েস্ট পাঠানো
        response = session.post(url, data=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            html = response.text
            # যদি ডেটা টেবিলে থাকে
            dfs = pd.read_html(io.StringIO(html))
            if dfs:
                df_res = dfs[0]
                if not df_res.empty:
                    cells = df_res.values.flatten()
                    # যদি ডেটা সঠিকভাবে পাওয়া যায়
                    if len(cells) >= 6 and "ডাটা পাওয়া যায়নি" not in str(cells[0]):
                        return {
                            "চালান নং": clean_chl,
                            "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": str(cells[0]),
                            "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": str(cells[1]),
                            "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": str(cells[2]),
                            "চালান নং (ওয়েবসাইট)": str(cells[3]),
                            "কি বাবদ জমা দেওয়া হলো তার বিবরণ": str(cells[4]),
                            "জমার পরিমাণ": str(cells[5])
                        }
    except Exception as e:
        pass

    return {
        "চালান নং": clean_chl,
        "যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": "ডাটা পাওয়া যায়নি/সঠিক নয়",
        "যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)": "N/A",
        "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": "N/A",
        "চালান নং (ওয়েবসাইট)": clean_chl,
        "কি বাবদ জমা দেওয়া হলো
