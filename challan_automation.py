import os
import re
import time
import glob
import pandas as pd
import pdfplumber
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

def extract_challan_numbers(pdf_path):
    """PDF থেকে সমস্ত চালানের নম্বর বের করবে"""
    challan_list = []
    pattern = r'CHL:\s*(\d{4})-(\d+)'
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                matches = re.findall(pattern, text)
                for part1, part2 in matches:
                    challan_list.append((part1, part2))
    return challan_list

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
    
    # চালানের তারিখ খুঁজে বের করা
    date_match = re.search(r'তারিখ\s*:\s*([\d\/]+)', full_text)
    if date_match:
        challan_date = date_match.group(1)

    # ধারা খুঁজে বের করা ("আয়কর" কথাটি বাদ দিয়ে কেবল ধারা অংশ)
    section_match = re.search(r'(?:আয়কর\s*)?(ধারা\s*[\d\w\s]+অনুগামী|ধারা\s*[\d\w\s]+অনুযায়ী)', full_text)
    if section_match:
        section_info = section_match.group(1).strip()
    else:
        # বিকল্প হিসেবে "অন্যান্য বিবরণ/মন্তব্য" অংশ থেকে এক্সট্র্যাক্ট করা
        remark_match = re.search(r'অন্যান্য বিবরণ\/মন্তব্য\s*\(যদি থাকে\)\s*:\s*(.*?)(?=\s*মোট|\s*টাকা|\s*তারিখ|$)', full_text)
        if remark_match:
            text_val = remark_match.group(1).strip()
            # 'আয়কর' শব্দ থাকলে তা মুছে ফেলা
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
    challans = extract_challan_numbers(source_pdf_path)
    
    total_challans = len(challans)
    if total_challans == 0:
        print("[ERROR] এই PDF ফাইল থেকে কোনো চালানের নম্বর পাওয়া যায়নি।")
        return

    print(f"সম্পূর্ণ প্রসেস শুরু হচ্ছে: মোট {total_challans} টি চালান...\n")

    final_data = []

    for idx, (part1, part2) in enumerate(challans, start=1):
        full_challan_no = f"{part1}-{part2}"
        print(f"[{idx}/{total_challans}] চালান {full_challan_no} প্রসেস হচ্ছে...")
        
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
