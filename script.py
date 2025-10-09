
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
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import utils

import matplotlib.pyplot as plt
import textwrap

CATEGORIES = {
    1: "Groceries, food, household",
    2: "Entertainment, gym, bar, fun",
    3: "Utilities, health, transportation, rent, obligations",
    4: "Clothes",
    5: "Travel",
    6: "Wasted, lost, fined",
    7: "idk",
    8: "Income"
}

BANKS = ["revolut", "ing"]

COMMANDS = {
    "import_single": BANKS,
    "exit": [],
    "view_db": [],
    "export": []
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

def categorize(df: pd.DataFrame):
    new_categories = []
    new_notes = []
    for row in df.itertuples():
        print("Please enter a category (number) for each transaction\n")
        for k, v in CATEGORIES.items():
            print(k, v)
        print()
        if row.Bank == "ing": # ING
            print(f"{G}Index: {row.Index}, {M}Datum: {row.Wertstellungsdatum}, {C}Auftraggeber: {row.Auftraggeber_Empfänger}, {C}Betrag: {row.Betrag} {row.Währung}, {Y}Verwendungszweck: {row.Note}{S}")
        else: # Revolut
            print(f"{Fore.GREEN}Index: {row.Index}, Datum: {row.Started_Date}, {M}Auftraggeber: {row.Description}, {C}Betrag: {row.Amount} {row.Currency}{S}")
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
            df = pd.read_csv(file_path, delimiter=";", skiprows=13, encoding="latin-1")
            df.rename(columns={"Verwendungszweck": "Note"})
        else:
            df = pd.read_csv(file_path, delimiter=",", encoding="latin-1")
            df["Note"] = ""
        df["Category"] = None
        df["Bank"] = bank_code
        df.columns = df.columns.str.replace('/', '_').str.replace(' ', '_')
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return
    except Exception as e:
        print("Error during file handling:", e, "\n")
        return
    df_categorized = categorize(df)
    return df_categorized

def to_iso_date(value):
    for fmt in ("%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.date()
        except ValueError:
            continue
    return None

def insert_db(df: pd.DataFrame):
    
    with Session.begin() as session:
        for row in df.itertuples(index = True):
            try:
                if row.Bank == "ing":
                    transaction = Transaction(
                        transaction_date = to_iso_date(row.Wertstellungsdatum),
                        issuer = row.Auftraggeber_Empfänger,
                        amount = row.Betrag,
                        currency = row.Währung,
                        bank = row.Bank,
                        category = row.Category,
                        note = row.Note
                    )
                else:
                    transaction = Transaction(
                        transaction_date = to_iso_date(row.Started_Date),
                        issuer = row.Description,
                        amount = row.Amount,
                        currency = row.Currency,
                        bank = row.Bank,
                        category = row.Category,
                        note = row.Note
                    )
                session.add(transaction)
            except Exception as e:
                print(f"Error creating Transaction for row {row.Index}: {e}")
                return -1
        try:
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database commit failed: {e}")
            return -1
    return 0

def view_db():
    print(f"Opening Squall for SQLite database: {DB_PATH}...")
    command = [
        "squall",
        "-f",
        DB_PATH
    ]
    try:
        subprocess.run(command, check=True)
        print("\nChanges saved.")
    except FileNotFoundError:
        print("Error: 'squall' command not found. Is it installed? Does the .db exist?")
    except subprocess.CalledProcessError as e:
        print(f"Squall exited with an error: {e}")

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
    
def make_piechart(category_sums):
    labels = [CATEGORIES.get(k) for k in category_sums.keys()]
    values = [abs(v) for v in category_sums.values()]
    
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

def get_image(path, width):
    img = utils.ImageReader(path)
    iw, ih = img.getSize()
    aspect = ih / float(iw)
    return Image(path, width=width, height=(width * aspect))

def generate_pdf(from_date, to_date, output_file):
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
        7: []
    }
    with Session.begin() as session:
        query = select(Transaction) \
            .where(Transaction.transaction_date >= from_date, Transaction.transaction_date <= to_date) \
            .order_by(Transaction.transaction_date.desc())
        transactions = session.scalars(query).all()
        for t in transactions:
            categories[t.category].append(t.attr_list())
    category_sums = {cat: sum(r[3] for r in items) for cat, items in categories.items()}
    elements.append(Paragraph("Transaction Report", styles["Title"]))
    elements.append(Spacer(1, 4*cm))

    make_piechart(category_sums)
    elements.append(get_image(str(IMG_PATH), width = 15*cm))
    elements.append(PageBreak())

    # === Category Pages ===
    for cat, items in categories.items():
        if items:
            tables = make_category_tables(items, styles, category_sums.get(cat))
            for idx, table in enumerate(tables):
                # Category header at top of every page
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
            print(chunk)
            desc_text = f"Transaction #{transaction_id}, {transaction_date} - {issuer}<br/>&#10148; {note}"
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

def main():
    init(autoreset=True)
    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)
    while True:
        print(f"Available commands: {G}ping{S}, {G}import_single{S} {C}<bank> <input.csv>{S}, {G}view_db{S}, {G}export{S} {C}<from-date> <to-date>{S},  {G}exit{S}\n")
        cmd = input("-> ").strip().lower()
        print() 
        if cmd == "exit":
            print("Limiting cash flow...")
            break
        parts = cmd.split()
        if not parts:
            continue
        if parts[0] == "import_single":
            if len(parts) == 3:
                target_file = CSV_DIR / "new" / parts[1] / parts[2]
                df = read_csv(target_file)
                if insert_db(df): break
                relocate_path = CSV_DIR / "old" / parts[1] / parts[2]
                target_file.rename(relocate_path)
            else:
                print("Usage: import_single <bank> <input.csv>\n")
        elif parts[0] == "view_db":
            view_db()
        elif parts[0] == "export":
            if len(parts) == 3 and check_dates(parts[1], parts[2]):
                output_file = REPORTS_DIR / f"Report_{parts[1]}-{parts[2]}.pdf"
                from_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
                to_date = datetime.strptime(parts[2], "%Y-%m-%d").date()
                generate_pdf(from_date, to_date, str(output_file))
                print(f"Report created: {output_file}\n")
                Path.unlink(BASE_DIR / "piechart.png")
            else:
                print("Usage: export <from-date> <to-date>\n")
        ## elif "visualize <from:date> <to:date>"
        else:
            print("Unknown command.\n")

if __name__ == "__main__":
    main()