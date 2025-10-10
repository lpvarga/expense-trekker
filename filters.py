import pandas as pd
from pathlib import Path

import re
import sys

import argparse
from colorama import Fore, Style, init

BANKS = ["revolut", "ing"]

CATEGORIES = {
    1: "Groceries, food, household",
    2: "For fun spendings (going out, etc.)",
    3: "Utilities, health, rent, obligations",
    4: "Clothes",
    5: "Travel",
    6: "Wasted, lost, fined",
    7: "idk",
    8: "Income"
}

COMMON_SELLERS = {
    "VISA EREICHELT 12247 BERLIN": (1, "Edeka Siemensstr."),
    "VISA DM DROGERIE MARKT": (1, "Self-Care, Haushalt"),
    "Eszter Fischer": (3, "pszichológus"),
    "VISA JAPANRABBIT.COM": (4, "Japan Proxy Service"),
    "VISA SCHNEIDEREI KARATAS": (4, "Schneider Lankwitz"),
    "VISA TRATTORIA DA REMO": (1, "Italiener (aus Kosovo) in Lichterfelde"),
    "VISA WOLT WOLT": (1, "Lieferservice"),
    "VISA NAH UND GUT VOELKER": (1, "Edeka Rathaus Steglitz"),
    "VISA RUEYA": (1, "Döner direkt an der TU"),
    "VISA EASYPARK": (3, "Parkgebühren"),
    "VISA S2K FOOD STORE": (1, "Edeka SüdX"),
    "VISA ULLRICH BERLIN-ZOO": (1, "Number 1 Chillerspot"),
    "VISA STEINECKE S HEIDEBROT": (1, "Bäcker Rathaus Lankwitz"),
    "VISA PAYPAL *MILES": (2, "Mietwagen"),
    "TU Berlin": (3, "Studiengebühren"),
    "VISA LIDL SAGT DANKE": (1, "TOP Backware"),
    "VISA EDEKA 5518": (1, ""),
    "BOLCSKEI IMRENE": (8, ""),
    "VISA ARAL TANKSTELLE 286057": (3, "Tanke Lankwitz"),
    "VISA E-REICHELT HADERSBECK": (1, "Edeka Lankwitz (nicht geil)"),
    "VISA REVIER SUEDOST": (2, "RSO"),
    "Eric Meintrup": (3, "Miete"),
    "VISA REWE MARKT GMBH-ZW": (1, ""),
    "DB Vertrieb GmbH": (3, "Zugkarten/D-Ticket"),
    "Transfer to KRISZTIAN BERKI": (3, "Fodrász"),
    "Transfer to BENCE LASZLO MANYOKI KANTOR": (3, "Fodrász"),
}

FILTERS = {
    (1, "Groceries"): [r"REWE", r"LIDL", r"KAUFLAND",  r"EDEKA",  r"ALDI", r"ROSSMANN"],
    (1, "Fast Food / Lieferservice"): [r"LIEFERANDO", r"BURGERMEISTER", r"MCDONALD"],
    (2, "TAXI"): [r"BOLT.EU"],
    (3, "health"): [r"APOTHEKE"],
    (3, "Auto / Tanken"): [r"SHELL", r"ARAL"],
    (4, "Clothes"): [r"UNIQLO", r"H&M", r"COS", r"C&A", r"ZALANDO",r"VINTED", r"MATCHES", r"WEEKDAY", r"IRONIC GALLERY"],
    (4, "Shipping"): [r"DHL"],
    5: [r"AIRBNB"]
}

G = Fore.GREEN
C = Fore.CYAN
R = Fore.RED
M = Fore.MAGENTA
Y = Fore.YELLOW
S = Style.RESET_ALL


def match_issuer(issuer):
    for tup, regex_list in FILTERS.items():
        for regex in regex_list:
            if re.search(regex, issuer, re.IGNORECASE): return tup
    return None
            
def categorize(df: pd.DataFrame): 
    new_categories = []
    new_notes = []
    for row in df.itertuples():
        # automatic fill
        value_tuple = COMMON_SELLERS.get(row.Issuer)
        if value_tuple := COMMON_SELLERS.get(row.Issuer):
            cat, note = value_tuple
            new_categories.append(cat)
            new_notes.append(note)
        elif tup := match_issuer(row.Issuer):
            cat, note = tup
            new_categories.append(cat)
            new_notes.append(note)
        elif row.Type == "Gehalt/Rente" or row.Type == "Deposit":
            new_categories.append(7)
            new_notes.append("")
        elif row.Type == "Lastschrift" and (row.Issuer == "VISA VATTENFALL GMBH" or row.Issuer == "Vattenfall"):
            new_categories.append(1)
            new_notes.append("Vattenfallkantine")
        # manual fill
        else:
            print("Please enter a category (number) for each transaction\n")
            for k, v in CATEGORIES.items():
                print(k, v)
            print()
            print(
                f"{G}Index: {row.Index}, {S}"
                f"{M}Datum: {row.Transaction_Date}, {S}"
                f"{C}Auftraggeber: {row.Issuer}, {S}"
                f"{R}Betrag: {row.Amount} {row.Currency}, {S}"
                f"{Y}Verwendungszweck: {row.Note}{S}"
            )
            print()
            while True:
                user_input = input("Category: ")
                print()
                if not user_input.isdigit():
                    print("Enter valid category...\n")
                elif int(user_input) > 8 or int(user_input)  < 1:
                    print("Enter valid category...\n")
                else:
                    new_categories.append(user_input)
                    new_note = input("Note: ")
                    new_notes.append(new_note)
                    break
    df["Category"] = new_categories
    df["Note"] = new_notes
    return df

def read_csv(file_path: Path):
    bank_code = file_path.parent.name 
    if bank_code not in BANKS:
        print("Bank not found")
        return
    try:
        if bank_code == "ing":
            df = pd.read_csv(file_path, delimiter=";", skiprows=12, encoding="utf-8")
            df.rename(columns={
                "Wertstellungsdatum": "Transaction_Date",
                "Auftraggeber/Empfänger": "Issuer",
                "Auftraggeber/Empf�nger": "Issuer",
                "Betrag": "Amount",
                "Währung": "Currency",
                "W�hrung": "Currency",
                "Verwendungszweck": "Note",
                "Buchungstext": "Type"
            }, inplace=True)
        else:
            df = pd.read_csv(file_path, delimiter=",", encoding="latin-1")
            df.rename(columns={
                "Completed Date": "Transaction_Date",
                "Description": "Issuer",
                "Amount": "Amount",
                "Currency": "Currency"
            }, inplace=True)
            df["Note"] = ""
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return
    except Exception as e:
        print("Error during file handling:", e, "\n")
        return
    df["Category"] = None
    df["Bank"] = bank_code

    print(df.columns)
    df_categorized = categorize(df)
    return df_categorized

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter test"
    )
    parser.add_argument(
        "input_csv", type=Path, help="Path to the input csv file"
    )
    
    # debugger
    # args = parser.parse_args(['auskunft_folder/new/ing/ing2023sept.csv'])

    args = parser.parse_args()

    df = read_csv(args.input_csv)
    print(df.to_string())

    