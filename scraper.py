import time
import re
import sys
import argparse
import os

from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pandas as pd

load_dotenv()

YELLO_EMAIL = os.getenv("YELLO_EMAIL", "")
YELLO_PASSWORD = os.getenv("YELLO_PASSWORD", "")

DELAY = 2
EMAIL_DELAY = 1.5

IS_CI = os.getenv("CI") == "true"


# --------------------------------------------------
# DRIVER
# --------------------------------------------------

def create_driver():

    if IS_CI:

        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        options = webdriver.ChromeOptions()

        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        service = Service(
            ChromeDriverManager().install()
        )

        return webdriver.Chrome(
            service=service,
            options=options
        )

    else:

        import undetected_chromedriver as uc

        options = uc.ChromeOptions()

        options.add_argument(
            "--start-maximized"
        )

        options.add_argument(
            "--disable-popup-blocking"
        )

        return uc.Chrome(
            options=options,
            version_main=147
        )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

def login(driver, wait):

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    driver.get(
        "https://www.yello.ae/sign-in"
    )

    time.sleep(4)

    try:

        email = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[name='data[Login][username]']"
                )
            )
        )

        email.clear()
        email.send_keys(
            YELLO_EMAIL
        )

        pwd = driver.find_element(
            By.CSS_SELECTOR,
            "input[name='data[Login][password]']"
        )

        pwd.clear()
        pwd.send_keys(
            YELLO_PASSWORD
        )

        btn = driver.find_element(
            By.CSS_SELECTOR,
            "input[type='submit']"
        )

        btn.click()

        time.sleep(4)

        return (
            "sign-in"
            not in driver.current_url
        )

    except Exception as e:

        print(
            f"Login error: {e}"
        )

        return False


# --------------------------------------------------
# URLS
# --------------------------------------------------

def build_url(
    keyword,
    location,
    page=1
):

    base = (
        f"https://www.yello.ae/"
        f"uae-business-search/"
        f"what:{keyword}/"
        f"where:{location}"
    )

    if page == 1:
        return base

    return (
        f"{base}/page:{page}"
    )


# --------------------------------------------------
# TOTAL PAGES
# --------------------------------------------------

def get_total_pages(
    driver,
    keyword,
    location
):

    driver.get(
        build_url(
            keyword,
            location
        )
    )

    time.sleep(3)

    soup = BeautifulSoup(
        driver.page_source,
        "html.parser"
    )

    text = soup.get_text()

    match = re.search(
        r"We found ([\d,]+)",
        text
    )

    if match:

        total = int(
            match.group(1)
            .replace(",", "")
        )

        pages = (
            total // 20
        ) + 1

        return pages, soup

    return 50, soup


# --------------------------------------------------
# COMPANY ID
# --------------------------------------------------

def extract_company_id(
    profile
):

    m = re.search(
        r"/company/(\d+)/",
        profile
    )

    if m:
        return m.group(1)

    return None


# --------------------------------------------------
# EMAIL
# --------------------------------------------------

def get_email(
    driver,
    company_id
):

    try:

        url = (
            f"https://www.yello.ae/"
            f"getlogin/"
            f"email:{company_id}"
        )

        driver.get(url)

        time.sleep(
            EMAIL_DELAY
        )

        soup = BeautifulSoup(
            driver.page_source,
            "html.parser"
        )

        txt = soup.get_text(
            " ",
            strip=True
        )

        match = re.search(
            r"[\w\.-]+@[\w\.-]+\.\w+",
            txt
        )

        if match:
            return match.group(0)

    except Exception:

        pass

    return ""


# --------------------------------------------------
# PARSE
# --------------------------------------------------

def parse_businesses(
    soup
):

    results = []

    cards = soup.select(
        "div.company"
    )

    print(
        f"Found cards: {len(cards)}"
    )

    for card in cards:

        try:

            tag = card.select_one(
                "h3 a"
            )

            if not tag:
                continue

            name = tag.get_text(
                strip=True
            )

            profile = (
                "https://www.yello.ae"
                + tag["href"]
            )

            addr = card.select_one(
                "div.address"
            )

            address = ""

            if addr:

                address = (
                    addr.get_text(
                        " ",
                        strip=True
                    )
                    .replace(
                        "Address:",
                        ""
                    )
                    .strip()
                )

            phone = ""

            tel = card.select_one(
                "a[href^='tel:']"
            )

            if tel:

                phone = tel.get_text(
                    strip=True
                )

            if not phone:

                text = card.get_text(
                    " ",
                    strip=True
                )

                m = re.search(
                    r"(\+?\d[\d\s\-\(\)]{6,20})",
                    text
                )

                if m:
                    phone = m.group(1)

            phone = str(phone)

            phone = re.sub(
                r"\s+",
                " ",
                phone
            ).strip()

            if phone.startswith("="):
                phone = "'" + phone

            if phone == "#ERROR!":
                phone = ""

            results.append(
                {
                    "Company Name": name,
                    "Address": address,
                    "Phone": phone,
                    "Email": "",
                    "Profile URL": profile
                }
            )

        except Exception as e:

            print(
                f"Parse error: {e}"
            )

    return results


# --------------------------------------------------
# CLEAN
# --------------------------------------------------

def clean_text(v):

    if not isinstance(
        v,
        str
    ):
        return v

    return re.sub(
        r"[\x00-\x1f]",
        "",
        v
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def scrape():

    from selenium.webdriver.support.ui import WebDriverWait

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--keyword",
        type=str
    )

    parser.add_argument(
        "--location",
        type=str
    )

    args = parser.parse_args()

    keyword = (
        args.keyword
        or input(
            "Keyword: "
        )
    )

    location = (
        args.location
        or input(
            "Location: "
        )
    )

    driver = create_driver()

    wait = WebDriverWait(
        driver,
        20
    )

    if not login(
        driver,
        wait
    ):

        print(
            "Login failed"
        )

        sys.exit(1)

    data = []

    seen = set()

    pages, first = get_total_pages(
        driver,
        keyword,
        location
    )

    first_records = parse_businesses(
        first
    )

    data.extend(
        first_records
    )

    for r in first_records:
        seen.add(
            r["Profile URL"]
        )

    for page in range(
        2,
        pages + 1
    ):

        url = build_url(
            keyword,
            location,
            page
        )

        print(
            url
        )

        driver.get(
            url
        )

        time.sleep(
            DELAY
        )

        soup = BeautifulSoup(
            driver.page_source,
            "html.parser"
        )

        rows = parse_businesses(
            soup
        )

        for row in rows:

            if (
                row["Profile URL"]
                not in seen
            ):

                seen.add(
                    row["Profile URL"]
                )

                data.append(
                    row
                )

    print(
        f"Fetching emails for {len(data)}"
    )

    for i, r in enumerate(
        data
    ):

        cid = extract_company_id(
            r["Profile URL"]
        )

        if not cid:
            continue

        r["Email"] = get_email(
            driver,
            cid
        )

        print(
            i + 1,
            r["Email"]
        )

    driver.quit()

    df = pd.DataFrame(
        data
    )

    df = df.fillna(
        ""
    )

    df["Phone"] = (
        df["Phone"]
        .astype(str)
        .replace(
            "#ERROR!",
            "",
            regex=False
        )
    )

    output = (
        f"yello_"
        f"{keyword}_"
        f"{location}.xlsx"
    )

    output = output.replace(
        " ",
        "_"
    ).lower()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            index=False
        )

        sheet = writer.sheets[
            "Sheet1"
        ]

        for cell in sheet["C"]:

            cell.number_format = "@"

    print(
        f"Saved: {output}"
    )


if __name__ == "__main__":

    scrape()
