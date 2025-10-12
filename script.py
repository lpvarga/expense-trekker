
from datetime import datetime
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from init_db import Transaction
from colorama import Fore, Style, init
try:
    import readline  # Linux / macOS
except ImportError:
    import pyreadline3 as readline # windows
import subprocess
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    PageBreak,
    Spacer,
    Image
)
from reportlab.lib import utils
import matplotlib.pyplot as plt
import textwrap
import re
from greeting import welcome

###################################################################
#                         CONSTANTS/DICTS                         #
###################################################################

CATEGORIES = {
    1: "Groceries, household",
    2: "Restaurant",
    3: "For fun, not necessary (going out, etc.)",
    4: "Utilities, health, rent, obligations",
    5: "Clothes",
    6: "Travel",
    7: "Wasted, lost, fined",
    8: "idk",
    9: "Income"
}

BANKS = ["revolut", "ing"]

COMMON_SELLERS = {
    "VISA EREICHELT 12247 BERLIN": (1, "Edeka Siemensstr."),
    "VISA DM DROGERIE MARKT": (1, "Self-Care, Haushalt"),
    "Eszter Fischer": (4, "pszichológus"),
    "VISA JAPANRABBIT.COM": (5, "Japan Proxy Service"),
    "VISA SCHNEIDEREI KARATAS": (5, "Schneider Lankwitz"),
    "VISA TRATTORIA DA REMO": (2, "Italiener (aus Kosovo) in Lichterfelde"),
    "VISA WOLT WOLT": (2, "Lieferservice"),
    "VISA NAH UND GUT VOELKER": (1, "Edeka Rathaus Steglitz"),
    "VISA RUEYA": (2, "Döner direkt an der TU"),
    "VISA EASYPARK": (4, "Parkgebühren"),
    "VISA S2K FOOD STORE": (1, "Edeka SüdX"),
    "VISA ULLRICH BERLIN-ZOO": (1, "Number 1 Chillerspot"),
    "VISA STEINECKE S HEIDEBROT": (1, "Bäcker Rathaus Lankwitz"),
    "VISA PAYPAL *MILES": (3, "Mietwagen"),
    "TU Berlin": (4, "Studiengebühren"),
    "VISA LIDL SAGT DANKE": (1, "TOP Backware"),
    "VISA EDEKA 5518": (1, ""),
    "BOLCSKEI IMRENE": (9, ""),
    "VISA ARAL TANKSTELLE 286057": (4, "Tanke Lankwitz"),
    "VISA E-REICHELT HADERSBECK": (1, "Edeka Lankwitz (nicht geil)"),
    "VISA REVIER SUEDOST": (3, "RSO"),
    "VISA REWE MARKT GMBH-ZW": (1, ""),
    "DB Vertrieb GmbH": (4, "Zugkarten/D-Ticket"),
    "Transfer to KRISZTIAN BERKI": (4, "Fodrász"),
    "Transfer to BENCE LASZLO MANYOKI KANTOR": (4, "Fodrász"),
}

FILTERS = {
    (1, "Groceries"): [r"REWE", r"LIDL", r"KAUFLAND",  r"EDEKA",  r"ALDI", r"ROSSMANN"],
    (2, "Fast Food / Lieferservice"): [r"LIEFERANDO", r"BURGERMEISTER", r"MCDONALD"],
    (3, "TAXI"): [r"BOLT.EU"],
    (4, "health"): [r"APOTHEKE"],
    (4, "Auto / Tanken"): [r"SHELL", r"ARAL"],
    (5, "Clothes"): [r"UNIQLO", r"H&M", r"COS", r"C&A", r"ZALANDO",r"VINTED", r"MATCHES", r"WEEKDAY", r"IRONIC GALLERY"],
    (5, "Shipping"): [r"DHL"],
    6: [r"AIRBNB"]
}

# REVOLUT
AVERAGE_RATES = {
    "GBP": 1.15,      # 1 GBP = 1.15 EUR, timeframe: 2023-10-01 to 2025-10-10
    "SEK": 0.09011,   # 1 SEK = 0.09011 EUR, timeframe: 2023-10-01 to 2025-10-10
    "USD": 0.907,     # 1 USD = 0.907 EUR, timeframe: 2023-11-08 to 2024-09-13
    "HUF": 0.002485   # 1 HUF ≈ 0.002485 EUR (1 EUR = 402.77 HUF), timeframe: 2023-06-01 to 2025-09-30
}

COMMANDS = {
    "import_single": BANKS,
    "exit": [],
    "view_db": [],
    "export_all": []
}

BASE_DIR = Path(__file__).parent
CSV_DIR = BASE_DIR / "auskunft_folder"
DB_PATH = (BASE_DIR / "auskunft.db")
REPORTS_DIR = BASE_DIR / "sumreport_folder"
IMG_PATH = BASE_DIR / "piechart.png"

ENGINE = create_engine(f"sqlite:///{DB_PATH.resolve()}")
Session = sessionmaker(bind=ENGINE)

G = Fore.GREEN
C = Fore.CYAN
R = Fore.RED
M = Fore.MAGENTA
Y = Fore.YELLOW
S = Style.RESET_ALL

###################################################################
#                        DATA IMPORT FUNCTIONS                    #
###################################################################

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
    df_categorized = categorize(df)
    print(df_categorized.to_string())
    return df_categorized

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
            new_categories.append(9)
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
                elif int(user_input) > 9 or int(user_input)  < 1:
                    print("Enter valid category...\n")
                else:
                    new_categories.append(user_input)
                    new_note = input("Note: ")
                    new_notes.append(new_note)
                    break
    df["Category"] = new_categories
    df["Note"] = new_notes
    return df

def insert_db(df: pd.DataFrame): 
    with Session.begin() as session:
        for row in df.itertuples(index = True):
            try:
                transaction = Transaction(
                    transaction_date=to_iso_date(row.Transaction_Date),
                    issuer=row.Issuer,
                    amount=row.Amount,
                    currency=row.Currency,
                    bank=row.Bank,
                    category=row.Category,
                    note=row.Note
                )
                session.add(transaction)
            except Exception as e:
                print(f"Error creating Transaction for row {row.Index}: {e}")
                return False
        try:
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database commit failed: {e}")
            return False
    return True

def view_db():
    print(f"Opening Squall for SQLite database: {DB_PATH}...\n")
    command = [
        "squall",
        "-f",
        DB_PATH
    ]
    try:
        subprocess.run(command, check=True)
        print("Changes saved.\n")
    except FileNotFoundError:
        print("Error: 'squall' command not found. Is it installed? Does the .db exist?")
    except subprocess.CalledProcessError as e:
        print(f"Squall exited with an error: {e}")

###################################################################
#                       PDF GENERATOR FUNCTIONS                   #
###################################################################

def generate_pdf(from_date, to_date, output_file, category):
    doc = SimpleDocTemplate(output_file, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    
    categories = {
        1: [],
        2: [],
        3: [],
        4: [],
        5: [],
        6: [],
        7: [],
        8: []
    }
    with Session.begin() as session:
        query = select(Transaction) \
            .where(Transaction.transaction_date >= from_date, Transaction.transaction_date <= to_date) \
            .order_by(Transaction.transaction_date.desc())
        if category: query = query.filter(Transaction.category == category)
        transactions = session.scalars(query).all()
        for t in transactions:
            categories[t.category].append(t.attr_list())
    category_sums = {
            cat: sum(
                r[3] if r[4] == "EUR" else r[3] * AVERAGE_RATES.get(r[4], 1)
                for r in items
            )
            for cat, items in categories.items()
        }
    elements.append(Paragraph("Transaction Report", styles["Title"]))
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph(f'<para alignment="center">{from_date}-{to_date}</para>', styles["Heading2"]))
    
    if not category:
        elements.append(Spacer(1, 2*cm))
        make_piechart(category_sums)
        elements.append(get_image(str(IMG_PATH), width = 15*cm))
    else:
        elements.append(Paragraph(f'<para alignment="center">{CATEGORIES.get(category)}</para>', styles["Heading2"]))
    elements.append(PageBreak())
        

    # === Category Pages ===
    for cat, items in categories.items():
        if items:
            tables = make_category_tables(items, styles, category_sums.get(cat))
            for idx, table in enumerate(tables):
                elements.append(Paragraph(f"<b> {CATEGORIES.get(cat)}</b>", styles["Heading2"]))
                elements.append(Spacer(1, 6))
                elements.append(table)
                if idx < len(tables) - 1:
                    elements.append(PageBreak())
            elements.append(PageBreak())
    doc.build(elements)

def make_category_tables(rows, styles, total):
    """Split category data into multiple tables (if needed)."""
    max_rows_per_page = 19
    tables = []

    for start in range(0, len(rows), max_rows_per_page):
        chunk = rows[start : start + max_rows_per_page]
        data = []
        row_colors = []

        # Transaction rows
        for idx, (transaction_id, transaction_date, issuer, amount, currency, bank, category, note) in enumerate(chunk):
            desc_text = f"Transaction #{transaction_id}, {transaction_date} - {issuer}<br/>&#10148; {note}"
            if currency != "EUR":
                amount_text = f" {amount:.2f}{currency} ≈ {amount*AVERAGE_RATES.get(currency):.2f}EUR"
            else:
                amount_text = f"{amount:.2f}{currency}"
            data.append([Paragraph(desc_text, styles["Normal"]), amount_text])
            bg_color = colors.white if idx % 2 else colors.whitesmoke
            row_colors.append(bg_color)

        # Sum row on last chunk only
        if start + max_rows_per_page >= len(rows):
            

            right_style = ParagraphStyle(
                "RightSum",
                parent=styles["Normal"],
                alignment=2  # 2 = TA_RIGHT
            )

            data.append([
                Paragraph("<b>Sum:</b>", styles["Normal"]),
                Paragraph(f"<b><font size=10>{total:.2f} EUR</font></b>", right_style),
            ])
            row_colors.append(colors.white)

        # Build table
        table = Table(data, colWidths=[13*cm, 3*cm])
        style_cmds = [
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]

        # Alternating background colors
        for i, bg in enumerate(row_colors):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        # Add space above sum row and right-align the sum cell
        if start + max_rows_per_page >= len(rows):
            style_cmds.append(("TOPPADDING", (0, -1), (-1, -1), 10))


        # No borders between cells
        style_cmds.append(("LINEBELOW", (0, 0), (-1, -1), 0, colors.white))

        table.setStyle(TableStyle(style_cmds))
        tables.append(table)

    return tables

def make_piechart(category_sums: dict):
    
    category_sums = {cat: total for cat, total in category_sums.items() if total <= 0} # filters for spendings only
    labels = [CATEGORIES.get(k) for k in category_sums.keys()]
    values = [abs(v) for v in category_sums.values()]
    
    colors = plt.cm.tab10.colors[:len(category_sums.keys())]
    color_map = dict(zip(category_sums.keys(), colors))

    custom_labels = ["" if value == 0 else f"{textwrap.fill(label, 20)}\n -{value:.1f}EUR" for label, value in zip(labels, values)]

    fig, ax = plt.subplots(figsize=(10, 7)) 
    wedges, texts, autotexts = ax.pie(
        values,
        labels=custom_labels,
        autopct= lambda pct, vals=values: f'{pct:1.1f}%' if vals.pop(0) != 0 else '',
        startangle=90,
        wedgeprops=dict(width=0.5),  # donut
        labeldistance=1.2
    )

    for text in texts:
        text.set_fontsize(12)
        text.set_fontweight('bold')

    for autotext in autotexts:
        autotext.set_fontsize(9)

    plt.tight_layout()
    plt.savefig(str(IMG_PATH), dpi=300, bbox_inches='tight')
    plt.close()

###################################################################
#                           UTIL FUNCTIONS                        #
###################################################################

def check_dates(date1, date2):
    fmt = "%Y-%m-%d"
    try:
        from_date = datetime.strptime(date1, fmt).date()
        to_date = datetime.strptime(date2, fmt).date()
    except:
        print("Error: invalid from and to date format. Usage: YYYY-MM-DD\n")
        return False
    
    if from_date > to_date:
        print("Error: To date is before from date.\n")
        return False
    
    return True

def to_iso_date(value):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date()
        except ValueError:
            continue
    return None

def match_issuer(issuer):
    for tup, regex_list in FILTERS.items():
        for regex in regex_list:
            if re.search(regex, issuer, re.IGNORECASE): return tup
    return None

def get_image(path, width):
    img = utils.ImageReader(path)
    iw, ih = img.getSize()
    aspect = ih / float(iw)
    return Image(path, width=width, height=(width * aspect))

def completer(text, state):
    """
    Context-aware tab completion:
    - Completes commands
    - Suggests args for import_single (and later input_bulk)
    - Lists CSV files in auskunftfolder
    """
    buffer = readline.get_line_buffer()
    parts = buffer.split()

    # No input yet -> suggest all commands
    if len(parts) == 0:
        options = [c for c in COMMANDS if c.startswith(text)]
    
    # First word typed -> completing the command
    elif len(parts) == 1:
        options = [c for c in COMMANDS if c.startswith(parts[0]) and c != parts[0]]
    else:
        cmd = parts[0]

        # Arguments for import_single
        if cmd == "import_single":
            # Determine which argument we're completing
            arg_index = len(parts) - 1
            # If the last character is space, we're starting a new argument
            if buffer.endswith(' '):
                arg_index += 1
                text = ''

            if arg_index == 1:  # completing bank name
                options = COMMANDS[cmd]
            elif arg_index == 2:  # completing CSV files
                target_dir = CSV_DIR / "new" / parts[1]
                options = [f.name for f in target_dir.glob("*.csv")]
            else:
                options = []
        else:
            if buffer.endswith(' '):
                arg_index += 1
                text = ''
            options = []

        # Filter by text if text is non-empty
        if text:
            options = [o for o in options if o.startswith(text)]

    # Return the correct state option
    if state < len(options):
        return options[state]
    return None

###################################################################
#                              MAIN                               #
###################################################################

def main():
    welcome.default_greeting(1)
    print()
    init(autoreset=True)
    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)
    readline.set_completer_delims(readline.get_completer_delims().replace('_', ''))
    readline.set_completer_delims(readline.get_completer_delims().replace('-', ''))
    while True:
        print("Available commands: "
              f"{G}import_single{S} {C}<bank> <input.csv>{S}, "
              f"{G}view_db{S}, "
              f"{G}export_all{S} {C}<from-date> <to-date>{S} {R}<optional: category>{S}, "
              f"{G}clear{S}, "
              f"{G}exit{S}\n")
        cmd = input("-> ").strip().lower()
        print() 
        if cmd == "exit":
            print("Limiting cash flow...")
            welcome.clear_terminal()
            break
        parts = cmd.split()
        if not parts:
            continue
        if parts[0] == "import_single":
            if len(parts) == 3:
                target_file = CSV_DIR / "new" / parts[1] / parts[2]
                df = read_csv(target_file)
                if not insert_db(df): break
                relocate_path = CSV_DIR / "old" / parts[1] / parts[2]
                target_file.rename(relocate_path)
            else:
                print("Usage: import_single <bank> <input.csv>\n")
        elif parts[0] == "view_db":
            view_db()
        elif parts[0] == "export_all":
            if len(parts) == 4 and int(parts[3]) not in CATEGORIES.keys():
                print("Category is not in following categories:\n")
                for k, v in CATEGORIES.items():
                    print(k, v)
                print()
            elif (len(parts) == 4 or len(parts) == 3) and check_dates(parts[1], parts[2]):
                category = 0 if len(parts) == 3 else int(parts[3])
                output_file = REPORTS_DIR / f"report_{parts[1]}-{parts[2]}.pdf"
                from_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
                to_date = datetime.strptime(parts[2], "%Y-%m-%d").date()
                generate_pdf(from_date, to_date, str(output_file), category)
                print(f"Report created: {output_file}\n")
                if not category: Path.unlink(BASE_DIR / "piechart.png")
            else:
                print("Usage: export_all <from-date> <to-date> <optional: category>\n")
        ## elif "visualize <from:date> <to:date>"
        elif parts[0] == "clear":
            welcome.clear_terminal()
            welcome.txt_animator(welcome.bloomberg_file_path, direction="instant", clear=True)
            print()
        else:
            print("Unknown command.\n")

if __name__ == "__main__":
    main()