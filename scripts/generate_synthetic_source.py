"""
generate_synthetic_source.py
Generates a fully synthetic customer support complaints workbook, mimicking
the shape and (deliberately) the messiness of the original real dataset --
mixed-type DOB values, region typos, inconsistent phone formats, swapped
TAT dates, a stray blank row, a few exact duplicates. This is what makes
the file useful as a test fixture: it exercises the same cleaning logic the
pipeline was actually built to handle, not a suspiciously clean dataset.

Run manually, once, before first use:
    python scripts/generate_synthetic_source.py

Writes data/source/CUSTOMER_SUPPORT-2025.xlsx
"""

import random
from datetime import date, timedelta

import pandas as pd

random.seed(7)  # different seed from the client generator, on purpose --
                 # avoids any accidental correlation between the two datasets

MONTHS = ["January", "February", "March", "April", "May", "June", "July"]
ROWS_PER_MONTH = {
    "January": 96, "February": 119, "March": 168, "April": 169,
    "May": 180, "June": 153, "July": 150,
}

REGIONS = [
    "Ashanti Region", "Greater Accra Region", "Northern Region", "Volta Region",
    "Central Region", "Western Region", "Upper West Region", "Upper East Region",
    "Oti Region", "Savannah Region", "Bono East Region", "Western North Region",
    "Brong Ahafo Region", "North East Region", "Ahafo Region", "Eastern Region",
]
REGION_VARIANTS = {
    "Greater Accra Region": ["Greater Accra", "greater accra region", "GA Region", "Accra"],
    "Ashanti Region": ["Ashanti", "ashanti region"],
    "Central Region": ["Central", "central region"],
}

GENDERS = ["Male", "Female"]
ACCOUNT_TYPES = ["Savings", "Current", "Mobile Wallet", "Fixed Deposit"]
BRANCHES = ["Accra Main", "Kumasi", "Takoradi", "Tamale", "Ho", "Sunyani", "Cape Coast"]
COMPLAINT_SOURCES = ["Phone Call", "Walk-in", "Email", "Social Media", "USSD"]
NATURE_OF_COMPLAINT = [
    "Transaction Failed", "Account Blocked", "Funds Not Received",
    "Reversal Request", "Wrong Debit", "App Not Working", "Card Issue",
]
STATUSES = ["Resolved", "Closed", "Pending Company"]
CC_REPS = ["Ama Boateng", "Kwesi Owusu", "Naa Adjeley", "Yaw Mensah", "Efua Tetteh"]

FIRST_NAMES = [
    "Kwame", "Ama", "Kofi", "Akosua", "Yaw", "Abena", "Kwabena", "Efua",
    "Kojo", "Adjoa", "Kwaku", "Akua", "Prince", "Comfort", "Emmanuel", "Grace",
]
SURNAMES = [
    "Mensah", "Owusu", "Boateng", "Asante", "Amoah", "Osei", "Adjei",
    "Tetteh", "Lartey", "Mahama", "Ackah",
]


def messy_region(region):
    roll = random.random()
    if roll < 0.85:
        return region
    if region in REGION_VARIANTS and roll < 0.97:
        return random.choice(REGION_VARIANTS[region])
    return None


def messy_phone():
    digits = f"{random.randint(20,59)}{random.randint(1000000,9999999)}"
    style = random.choice(["local", "local_spaced", "intl", "nine_digit"])
    if style == "local":
        return f"0{digits}"
    if style == "local_spaced":
        return f"0{digits[:2]} {digits[2:5]} {digits[5:]}"
    if style == "intl":
        return f"233{digits}"
    return digits


def messy_dob():
    roll = random.random()
    if roll < 0.7:
        start = date(1960, 1, 1)
        end = date(2005, 1, 1)
        return start + timedelta(days=random.randint(0, (end - start).days))
    if roll < 0.85:
        return None
    return random.choice(["N/A", "unknown", "-"])


def generate_month_sheet(month_name, row_count):
    rows = []
    for _ in range(row_count):
        log_date = date(2025, MONTHS.index(month_name) + 1, random.randint(1, 28))

        tat_bug_roll = random.random()
        if tat_bug_roll < 0.03:
            resolution_date = log_date - timedelta(days=random.randint(1, 5))
            tat = -random.randint(1, 5)
        elif tat_bug_roll < 0.05:
            resolution_date = log_date + timedelta(days=random.randint(0, 3))
            tat = None
        else:
            resolution_date = log_date + timedelta(days=random.randint(0, 3))
            tat = (resolution_date - log_date).days

        region = random.choice(REGIONS)
        status = random.choices(STATUSES, weights=[85, 10, 5])[0]

        rows.append({
            "NAME": f"{random.choice(FIRST_NAMES)} {random.choice(SURNAMES)}",
            "GENDER": random.choice(GENDERS),
            "NUMBER": messy_phone(),
            "NUMBER2": messy_phone() if random.random() < 0.15 else None,
            "ACCOUNT TYPE": random.choice(ACCOUNT_TYPES),
            "BRANCH": random.choice(BRANCHES),
            "LOCATION": random.choice(BRANCHES),
            "REGION": messy_region(region),
            "LOG DATE": log_date,
            "COMPLAINT SOURCE": random.choice(COMPLAINT_SOURCES),
            "NATURE OF COMPLAINT": random.choice(NATURE_OF_COMPLAINT),
            "SUBJECT": random.choice(NATURE_OF_COMPLAINT),
            "DETAILS OF COMPLAINT": "Customer reported an issue requiring review.",
            "COMMENT": "" if random.random() < 0.3 else "Followed up with customer.",
            "UPDATES": "" if random.random() < 0.5 else "Escalated to back office.",
            "STATUS": status,
            "TAT": tat,
            "RESOLUTION DATE": resolution_date if status != "Pending Company" else None,
            "REASON FOR REVERSAL REQUEST": "Duplicate transaction" if random.random() < 0.1 else None,
            "ASSIGN": random.choice(CC_REPS),
            "NAME OF CC REP": random.choice(CC_REPS),
            "DOB": messy_dob(),
        })

    df = pd.DataFrame(rows)

    if len(df) > 5:
        dup_rows = df.sample(n=2, random_state=random.randint(0, 10000))
        df = pd.concat([df, dup_rows], ignore_index=True)

    blank_row = {col: None for col in df.columns}
    df = pd.concat([df, pd.DataFrame([blank_row])], ignore_index=True)

    return df


def generate_unresolved_sheet():
    return generate_month_sheet("January", 15)


def main():
    output_path = "data/source/CUSTOMER_SUPPORT-2025.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for month in MONTHS:
            df = generate_month_sheet(month, ROWS_PER_MONTH[month])
            df.to_excel(writer, sheet_name=month, index=False)
        generate_unresolved_sheet().to_excel(writer, sheet_name="Unresolved", index=False)

    total_rows = sum(ROWS_PER_MONTH.values())
    print(f"Wrote {output_path}")
    print(f"Sheets: {', '.join(MONTHS)}, Unresolved (excluded by default)")
    print(f"Approx {total_rows} rows across all month sheets (plus duplicates/blank rows per sheet)")


if __name__ == "__main__":
    main()