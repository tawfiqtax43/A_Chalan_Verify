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

    # JavaScript Engine to fetch directly from user's browser (Bypasses Geo-block)
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
                const formData = new URLSearchParams();
                formData.append('challanNo1', c1);
                formData.append('challanNo2', c2);

                const response = await fetch('https://challanverification.finance.gov.bd/echalan/verifyChallan', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest'
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
                            "যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)": tds[2] || "N/A",
                            "চালান নং (ওয়েবসাইট)": tds[3] || cleanChl,
                            "কি বাবদ জমা দেওয়া হলো তার বিবরণ": tds[4] || "N/A",
                            "জমার পরিমাণ": tds[5] || "N/A"
                        }};
                    }}
                }}
            }} catch (e) {{
                console.error(e);
            }}

            results.push(rowData);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="padding: 8px;">${{rowData['চালান নং']}}</td>
                <td style="padding: 8px;">${{rowData['যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে']}}</td>
                <td style="padding: 8px;">${{rowData['যার মাধ্যমে টাকা আদায় হলো (নাম ও সনাক্তকরণ)']}}</td>
                <td style="padding: 8px;">${{rowData['যার পক্ষ হতে টাকা প্রদান হলো (নাম ও ঠিকানা)']}}</td>
                <td style="padding: 8px;">${{rowData['চালান নং (ওয়েবসাইট)']}}</td>
                <td style="padding: 8px;">${{rowData['কি বাবদ জমা দেওয়া হলো তার বিবরণ']}}</td>
                <td style="padding: 8px;">${{rowData['জমার পরিমাণ']}}</td>
            `;
            tbody.appendChild(tr);
        }}

        document.getElementById('status').innerText = `ভেরিফিকেশন সম্পূর্ণ সফল হয়েছে! (মোট: ${{challans.length}} টি)`;
        document.getElementById('start-btn').style.display = 'none';
        document.getElementById('download-btn').style.display = 'inline-block';
    }});

    document.getElementById('download-btn').addEventListener('click', () => {{
        const worksheet = XLSX.utils.json_to_sheet(results);
        const workbook = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(workbook, worksheet, "Report");
        XLSX.writeFile(workbook, "Challan_Report.xlsx");
    }});
    </script>
    """
    components.html(js_code, height=600, scrolling=True)
