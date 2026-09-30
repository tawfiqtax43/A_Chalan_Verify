import os
import re
import time
import glob
import pandas as pd
import pdfplumber
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def find_pdf_file():
    """ফোল্ডারে থাকা যেকোনো PDF ফাইল খুঁজে বের করবে"""
    pdf_files = glob.glob("*.pdf")
    if not pdf_files:
        return None
    return pdf_files[0]

def convert_bn_to_en_num(bn_str):
    """বাংলা সংখ্যাকে ইংরেজিতে রূপান্তর করে"""
    if not bn_str:
        return ""
    bn_digits = "০১২৩৪৫৬৭৮৯"
    en_digits = "0123456789"
    trans = str.maketrans(bn_digits, en_digits)
    return str(bn_str).translate(trans)

def parse_date_to_comparable(date_str):
    """ভিন্ন ভিন্ন ফরম্যাটের তারিখকে YYYYMMDD এ রূপান্তর করে"""
    if not date_str:
        return None
    date_str = convert_bn_to_en_num(date_str).strip()
    
    # 10-Nov-25 বা 10-Nov-2025 ফরম্যাট
    try:
        match_mon = re.search(r'(\d{1,2})[-/\s]([A-Za-z]{3})[-/\s](\d{2,4})', date_str)
        if match_mon:
            day = match_mon.group(1).zfill(2)
            mon_str = match_mon.group(2).title()
            yr = match_mon.group(3)
            if len(yr) == 2:
                yr = "20" + yr
            dt = datetime.strptime(f"{day}-{mon_str}-{yr}", "%d-%b-%Y")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # DD/MM/YYYY বা DD-MM-YYYY ফরম্যাট
    parts = re.split(r'[\/\.-]', date_str)
    if len(parts) == 3:
        day, month, year = parts[0].zfill(2), parts[1].zfill(2), parts[2]
        if len(year) == 2:
            year = "20" + year
        return f"{year}{month}{day}"
    return None

def extract_challan_info_from_pdf(pdf_path):
    """
    PDF স্ক্যান করে চালান নম্বর, তারিখ ও টাকার পরিমাণ নিখুঁতভাবে বের করবে
    """
    challan_records = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            if not words:
                continue

            # শব্দগুলোকে Y-পজিশন অনুযায়ী সর্ট করা
            sorted_words = sorted(words, key=lambda w: w['top'])
            
            # CHL প্রাপ্তির ব্লক তৈরি করা
            chl_blocks = []
            for w in sorted_words:
                if "CHL:" in w['text']:
                    chl_blocks.append({'word': w, 'top': w['top']})
            
            if not chl_blocks:
                continue

            # প্রতিটি CHL চালানের জন্য উল্লম্ব রেঞ্জ (Vertical Region) নির্ধারণ করা
            for i in range(len(chl_blocks)):
                curr_block = chl_blocks[i]
                curr_top = curr_block['top'] - 5  # কিছুটা ছাড়
                
                # পরবর্তী চালান না আসা পর্যন্ত বা পেজের শেষ পর্যন্ত সীমানা
                if i + 1 < len(chl_blocks):
                    next_top = chl_blocks[i + 1]['top'] - 5
                else:
                    next_top = curr_top + 45  # এক রো-এর অনুমিত উচ্চতা

                # সীমানার ভেতরের সব শব্দ সংগ্রহ
                block_words = [w for w in sorted_words if curr_top <= w['top'] < next_top]
                block_text = " ".join([w['text'] for w in sorted_words if curr_top <= w['top'] < next_top])

                # চালান নম্বর মেলাতে
                match = re.search(r'CHL:\s*(\d{4})-(\d+)', block_text)
                if match:
                    part1, part2 = match.group(1), match.group(2)
                    full_no = f"{part1}-{part2}"
                    
                    date_found = None
                    amount_found = 0.0
                    
                    # তারিখ
                    d_match = re.search(r'(\d{1,2}[-/\s][A-Za-z]{3}[-/\s]\d{2,4}|\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})', block_text)
                    if d_match:
                        date_found = d_match.group(1)
                    
                    # টাকার পরিমাণ (যেমন: 200,000.00 বা 342,624.00)
                    amounts = re.findall(r'([\d,০-৯]+\.\d{2})', block_text)
                    if amounts:
                        # সাধারণত ডানদিকের টাকার সংখ্যাটি বড় হয়
                        for raw_amt in reversed(amounts):
                            clean_amt = convert_bn_to_en_num(raw_amt).replace(',', '')
                            try:
                                val = float(clean_amt)
                                if val > 0:
                                    amount_found = val
                                    break
                            except ValueError:
                                pass
                            
                    challan_records.append({
                        "part1": part1,
                        "part2": part2,
                        "full_no": full_no,
                        "pdf_date": date_found,
                        "pdf_amount": amount_found
                    })
                    
    return challan_records

def create_fresh_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def parse_popup_precise(html_source, full_challan_no):
    soup = BeautifulSoup(html_source, 'html.parser')
    
    col1, col2, col3, col4, col5, col6, challan_date = "", "", "", full_challan_no, "", "", ""
    section_info = ""

    full_text = soup.get_text()
    
    date_match = re.search(r'তারিখ\s*:\s*([\d\/]+)', full_text)
    if date_match:
        challan_date = date_match.group(1)

    # "আয়কর" কথাটি বাদ দিয়ে কেবল "ধারা..." অংশ এক্সট্র্যাক্ট করা
    section_match = re.search(r'(?:আয়কর\s*)?(ধারা\s*[\d\w\s]+অনুগামী|ধারা\s*[\d\w\s]+অনুযায়ী)', full_text)
    if section_match:
        section_info = section_match.group(1).strip()
    else:
        remark_match = re.search(r'অন্যান্য বিবরণ\/মন্তব্য\s*\(যদি থাকে\)\s*:\s*(.*?)(?=\s*মোট|\s*টাকা|\s*তারিখ|$)', full_text)
        if remark_match:
            text_val = remark_match.group(1).strip()
            section_info = re.sub(r'আয়কর\s*', '', text_val).strip()

    tables = soup.find_all('table')
    target_row = None
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            tds = row.find_all('td')
            if len(tds) == 6:
                row_text = row.get_text()
                if "যে সরকারি প্রতিষ্ঠানের" not in row_text and "জমার পরিমাণ" not in row_text:
                    target_row = tds
                    break
        if target_row:
            break

    if target_row and len(target_row) == 6:
        col1 = target_row[0].get_text(separator="\n", strip=True)
        col2 = target_row[1].get_text(separator="\n", strip=True)
        col3 = target_row[2].get_text(separator="\n", strip=True)
        col4 = target_row[3].get_text(separator="\n", strip=True)
        col5 = target_row[4].get_text(separator="\n", strip=True)
        col6 = target_row[5].get_text(separator="\n", strip=True)

    return {
        "col1": col1,
        "col2": col2,
        "col3": col3,
        "col4": col4,
        "col5": col5,
        "col6": col6,
        "date": challan_date,
        "section": section_info
    }

def process_single_challan(driver, part1, part2):
    full_challan_no = f"{part1}-{part2}"
    driver.get("https://challanverification.finance.gov.bd/echalan/")
    main_window = driver.current_window_handle

    WebDriverWait(driver, 12).until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if len(iframes) > 0:
        driver.switch_to.frame(iframes[0])

    inputs = driver.find_elements(By.XPATH, '//input[@type="text"]')
    if len(inputs) < 2:
        return None

    box1 = inputs[-2]
    box2 = inputs[-1]

    box1.clear()
    box1.send_keys(part1)
    box2.clear()
    box2.send_keys(part2)

    btn = driver.find_element(By.XPATH, '(//input[@value="Verify"])[last()]')
    driver.execute_script("arguments[0].click();", btn)

    WebDriverWait(driver, 12).until(lambda d: len(d.window_handles) > 1)

    all_windows = driver.window_handles
    if len(all_windows) > 1:
        for win in all_windows:
            if win != main_window:
                driver.switch_to.window(win)
                break

        time.sleep(2.5)

        if "conflict" in driver.page_source.lower():
            return None

        popup_iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if len(popup_iframes) > 0:
            driver.switch_to.frame(popup_iframes[0])

        try:
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        except Exception:
            pass

        html_content = driver.page_source
        parsed_data = parse_popup_precise(html_content, full_challan_no)
        
        if parsed_data and parsed_data["col1"]:
            return parsed_data

    return None

def process_challan_with_smart_retry(part1, part2, max_retries=4):
    full_challan_no = f"{part1}-{part2}"
    
    for attempt in range(1, max_retries + 1):
        driver = None
        try:
            driver = create_fresh_driver()
            res = process_single_challan(driver, part1, part2)
            if res:
                return res
        except Exception:
            pass
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
        
        if attempt < max_retries:
            wait_time = attempt * 2.5
            print(f"    -> [চালান {full_challan_no}] পুনঃচেষ্টা করা হচ্ছে ({attempt}/{max_retries}) - {wait_time}s বিরতি...")
            time.sleep(wait_time)

    return None

def run_automation():
    source_pdf_path = find_pdf_file()
    
    if not source_pdf_path:
        print("\n[ERROR] ফোল্ডারে কোনো PDF ফাইল পাওয়া যায়নি!")
        print("দয়া করে চালানের PDF ফাইলটি এই ফোল্ডারে রেখে আবার run.bat চালু করুন।")
        return

    print(f"\nপাওয়া গেছে PDF ফাইল: '{source_pdf_path}'")
    print("PDF ফাইল স্ক্যান করে চালানের তথ্য বিশ্লেষণ করা হচ্ছে...")
    
    records = extract_challan_info_from_pdf(source_pdf_path)
    total_challans = len(records)
    
    if total_challans == 0:
        print("[ERROR] এই PDF ফাইল থেকে কোনো চালানের নম্বর পাওয়া যায়নি।")
        return

    print(f"\n---> স্ক্যান সম্পন্ন! মোট {total_challans} টি চালান পাওয়া গেছে। <---")
    
    dates_found = [r['pdf_date'] for r in records if r['pdf_date']]
    amounts_found = [r['pdf_amount'] for r in records if r['pdf_amount'] > 0]
    
    if dates_found:
        print(f"পাওয়া গেছে তারিখের নমুনা: {', '.join(list(set(dates_found))[:5])} ...")
    if amounts_found:
        print(f"সর্বনিম্ন টাকার পরিমাণ: {min(amounts_found):,.2f} | সর্বোচ্চ টাকার পরিমাণ: {max(amounts_found):,.2f}")

    print("\n" + "="*50)
    print("ভেরিফিকেশন ফিল্টার অপশন সিলেক্ট করুন:")
    print("১. তারিখ (Date) অনুযায়ী ফিল্টার")
    print("২. জমার পরিমাণ (Amount) অনুযায়ী ফিল্টার")
    print("৩. কোনো ফিল্টার ছাড়া (সবগুলো চালান ভেরিফাই করবেন)")
    print("="*50)
    
    choice = input("আপনার পছন্দ টাইপ করুন (1/2/3): ").strip()
    
    selected_records = []
    
    if choice == '1':
        print("\n[তারিখ ফিল্টার নির্বাচিত]")
        start_date_in = input("শুরুর তারিখ লিখুন (যেমন: 10-Nov-25 বা 10/11/2025): ").strip()
        end_date_in = input("শেষের তারিখ লিখুন (যেমন: 30-Nov-25 বা 30/11/2025): ").strip()
        
        start_cmp = parse_date_to_comparable(start_date_in)
        end_cmp = parse_date_to_comparable(end_date_in)
        
        for r in records:
            r_cmp = parse_date_to_comparable(r['pdf_date'])
            if r_cmp and start_cmp and end_cmp:
                if start_cmp <= r_cmp <= end_cmp:
                    selected_records.append(r)
            else:
                selected_records.append(r)
                
    elif choice == '2':
        print("\n[এমাউন্ট ফিল্টার নির্বাচিত]")
        try:
            min_amt = float(input("সর্বনিম্ন টাকার পরিমাণ (Min Amount): ").strip())
            max_amt = float(input("সর্বোচ্চ টাকার পরিমাণ (Max Amount): ").strip())
            
            for r in records:
                if min_amt <= r['pdf_amount'] <= max_amt:
                    selected_records.append(r)
        except ValueError:
            print("[WARNING] ভুল সংখ্যা ইনপুট দিয়েছেন! ফিল্টার ছাড়া সবগুলো চালান ধরা হচ্ছে।")
            selected_records = records
            
    else:
        print("\n[সবগুলো চালান ভেরিফাই করা হবে]")
        selected_records = records

    filtered_count = len(selected_records)
    if filtered_count == 0:
        print("\n[INFO] ফিল্টারের শর্ত অনুযায়ী কোনো চালান পাওয়া যায়নি। প্রোগ্রাম শেষ হচ্ছে।")
        return

    print(f"\nফিল্টার অনুযায়ী মোট {filtered_count} টি চালান ভেরিফাই করা হবে। শুরু হচ্ছে...\n")

    final_data = []

    for idx, r in enumerate(selected_records, start=1):
        part1, part2 = r['part1'], r['part2']
        full_challan_no = r['full_no']
        print(f"[{idx}/{filtered_count}] চালান {full_challan_no} প্রসেস হচ্ছে...")
        
        parsed = process_challan_with_smart_retry(part1, part2)

        if parsed and parsed["col1"]:
            row = {
                "চালান নম্বর": full_challan_no,
                "চালানের তারিখ": parsed["date"],
                "১. যে সরকারি প্রতিষ্ঠানের অনুকূলে অর্থ জমা হচ্ছে": parsed["col1"],
                "২. যার মাধ্যমে টাকা প্রদত্ত হলো তার নাম, সনাক্তকরণ নম্বর ও ঠিকানা": parsed["col2"],
                "৩. যে ব্যক্তির/প্রতিষ্ঠানের পক্ষ হতে টাকা প্রদত্ত হলো তার নাম, সনাক্তকরণ নম্বর ও ঠিকানা": parsed["col3"],
                "৪. চালান নং": parsed["col4"],
                "৫. কি বাবদ জমা দেওয়া হলো তার বিবরণ": parsed["col5"],
                "৬. জমার পরিমাণ": parsed["col6"],
                "ধারার তথ্য / মন্তব্য": parsed["section"]
            }
            final_data.append(row)
            print(f"    ✓ চালান {full_challan_no} সফলভাবে সংগৃহীত (তারিখ: {parsed['date']}, ধারা: {parsed['section']})")
        else:
            print(f"    ✗ চালান {full_challan_no} ডাটা পাওয়া যায়নি বা ভ্যালিড নয়।")

        time.sleep(2)

    if final_data:
        output_excel_path = "Verified_Challan_Data.xlsx"
        try:
            df = pd.DataFrame(final_data)
            df.to_excel(output_excel_path, index=False)
            print(f"\nকাজ সফলভাবে সম্পন্ন হয়েছে! ফাইল সেভ করা হয়েছে: {output_excel_path}")
        except PermissionError:
            backup_file = "Verified_Challan_Data_Fixed.xlsx"
            df.to_excel(backup_file, index=False)
            print(f"\nমেইন ফাইল খোলা থাকায় ব্যাকআপ ফাইলে সেভ করা হয়েছে: {backup_file}")

if __name__ == "__main__":
    run_automation()
