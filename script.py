
from datetime import datetime
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from init_db import Transaction
from colorama import Fore, Style, init
try:
    import readline  # Linux / macOS
except ImportError:
    import pyreadline3 as readline # windows
import subprocess

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
    "input_single": BANKS,
    "exit": [],
    "view_db": []
}

BASE_DIR = Path(__file__).parent
CSV_DIR = BASE_DIR / "auskunft_folder"
DB_PATH = (BASE_DIR / "auskunft.db")

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
    - Suggests args for input_single (and later input_bulk)
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

        # Arguments for input_single
        if cmd == "input_single":
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
    engine = create_engine(f"sqlite:///{DB_PATH.resolve()}")
    with Session(engine) as session:
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

# def piechart with mathplotlib
# def summarizing algorithm
# def pdf algorithm

def main():
    init(autoreset=True)
    readline.parse_and_bind("tab: complete")
    readline.set_completer(completer)
    while True:
        print(f"Available commands: {G}ping{S}, {G}input_single{S} {C}<bank> <input.csv>{S}, {G}exit{S}\n")
        cmd = input("-> ").strip().lower()
        print() 
        if cmd == "exit":
            print("Limiting cash flow...")
            break
        parts = cmd.split()
        if not parts:
            continue
        if parts[0] == "input_single":
            if len(parts) == 3:
                target_file = CSV_DIR / "new" / parts[1] / parts[2]
                df = read_csv(target_file)
                if insert_db(df): break
                relocate_path = CSV_DIR / "old" / parts[1] / parts[2]
                target_file.rename(relocate_path)
            else:
                print("Usage: input_single <bank> <input.csv>\n")
        elif parts[0] == "view_db":
            view_db()
        ## elif "export <from:date> <to:date> <output_file>"
        ## elif "visualize <from:date> <to:date>"
        else:
            print("Unknown command.\n")

if __name__ == "__main__":
    main()