import streamlit as st
import pdfplumber
import re
import pandas as pd
import json
import streamlit.components.v1 as components

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

    st.write(f"**মোট চালান পাওয়া গেছে:** {len(challans)} টি")
    
    challans_json = json.dumps(challans)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ font-family: sans-serif; padding: 10px; }}
        button {{
            background-color: #ff4b4b; color: white; border: none; padding: 10px 20px;
            font-size: 16px; border-radius: 5px; cursor: pointer; margin-bottom: 15px;
        }}
        button:hover {{ background-color: #d33333; }}
        #progress {{ font-weight: bold; margin-bottom: 10px; color: #1f77b4; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even){{ background-color: #f9f9f9; }}
    </style>
    </head>
    <body>

    <button onclick="startVerification()">▶️ ভেরিফিকেশন শুরু করুন (ব্রাউজার মোড)</button>
    <div id="progress">প্রসেসিং শুরুর জন্য প্রস্তুত...</div>
    
    <div style="overflow-x:auto;">
        <table id="resultTable">
            <thead>
                <tr>
                    <th>#</th>
                    <th>চালান নং</th>
                    <th>যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে</th>
                    <th>যার মাধ্যমে টাকা আদায় হলো</th>
                    <th>যার পক্ষ হতে টাকা প্রদান হলো</th>
                    <th>চালান নং (ওয়েবসাইট)</th>
                    <th>কি বাবদ জমা দেওয়া হলো</th>
                    <th>জমার পরিমাণ</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        </table>
    </div>

    <script>
    const challanList = {challans_json};

    async function verifyChallan(clean_chl) {{
        let chl_clean_str = clean_chl.replace(/\\D/g, '');
        let c1 = "", c2 = "";
        if (chl_clean_str.length >= 15) {{
            c1 = chl_clean_str.substring(0, 4);
            c2 = chl_clean_str.substring(4, 15);
        }} else {{
            let parts = clean_chl.split('-');
            c1 = parts[0].trim();
            c2 = parts[1] ? parts[1].trim() : "";
        }}

        let formData = new URLSearchParams();
        formData.append('challanNo1', c1);
        formData.append('challanNo2', c2);

        try {{
            let response = await fetch('https://challanverification.finance.gov.bd/echalan/verifyChallan', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                }},
                body: formData.toString()
            }});

            if (response.ok) {{
                let text = await response.text();
                let parser = new DOMParser();
                let doc = parser.parseFromString(text, 'text/html');
                let table = doc.querySelector('table');
                
                if (table) {{
                    let rows = table.querySelectorAll('tr');
                    let cellsData = [];
                    rows.forEach(r => {{
                        r.querySelectorAll('td').forEach(c => cellsData.push(c.innerText.trim()));
                    }});
                    
                    if (cellsData.length >= 6 && !cellsData[0].includes("ডাটা পাওয়া যায়নি")) {{
                        return {{
                            chl: clean_chl,
                            org: cellsData[0],
                            via: cellsData[1],
                            by: cellsData[2],
                            web_chl: cellsData[3],
                            desc: cellsData[4],
                            amount: cellsData[5]
                        }};
                    }}
                }}
            }}
        }} catch (e) {{
            console.error(e);
        }}

        return {{
            chl: clean_chl,
            org: "ডাটা পাওয়া যায়নি/সঠিক নয়",
            via: "N/A",
            by: "N/A",
            web_chl: clean_chl,
            desc: "N/A",
            amount: "N/A"
        }};
    }}

    async function startVerification() {{
        let tbody = document.querySelector("#resultTable tbody");
        tbody.innerHTML = "";
        let progressDiv = document.getElementById("progress");
        
        for (let i = 0; i < challanList.length; i++) {{
            let chl = challanList[i];
            progressDiv.innerText = `প্রসেসিং চলছে: ${{i + 1}} / ${{challanList.length}} (চালান: ${{chl}})`;
            
            let res = await verifyChallan(chl);
            
            let tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${{i + 1}}</td>
                <td>${{res.chl}}</td>
                <td>${{res.org}}</td>
                <td>${{res.via}}</td>
                <td>${{res.by}}</td>
                <td>${{res.web_chl}}</td>
                <td>${{res.desc}}</td>
                <td>${{res.amount}}</td>
            `;
            tbody.appendChild(tr);
            
            // 200ms delay to prevent server overload
            await new Promise(r => setTimeout(r, 200));
        }}
        
        progressDiv.innerText = `প্রসেসিং সম্পন্ন: ${{challanList.length}} / ${{challanList.length}} টি চালান সাকসেসফুলি ভেরিফাইড!`;
    }}
    </script>
    </body>
    </html>
    """

    components.html(html_code, height=600, scrolling=True)
