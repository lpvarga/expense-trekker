"""
    fuck ING.
    Extracts transaction data from ING PDFs and writes them to a CSV file.
"""

import re
import csv
from pathlib import Path
from pypdf import PdfReader
import argparse

BUCHUNGSTEXT = ["Lastschrift", "Gutschrift", "Ueberweisung", "Entgelt", "Gehalt/Rente"]
BASE_DIR = Path(__file__).parent
CSV_DIR = BASE_DIR / "auskunft_folder" / "new" / "ing"
PDF_DIR = BASE_DIR / "auskunft_folder" / "ing_pdf"


regex_table = r"Valuta.*(\d{2}[A-Z]{4}\d{10}_T)$"
regex_transactions = (
    r"(^\d{2}\.\d{2}\.\d{4}) ([A-Z][a-z]+(?:/[A-Z][a-z]+)?) (.+?) ([\-\d,\.]+)$\n"
    r"(^\d{2}\.\d{2}\.\d{4}) (.*?)\n"
)


def parse_amount(amount_str: str) -> float:
    clean = amount_str.replace('.', '').replace(',', '.')
    try:
        return float(clean)
    except ValueError:
        return 0.0

def extract_transactions(input_pdf: Path, output_csv: Path):
    
    fieldnames = [
        "Wertstellungsdatum",
        "Auftraggeber/Empfänger",
        "Buchungstext",
        "Verwendungszweck",
        "Betrag",
        "Währung",
    ]

    reader = PdfReader(input_pdf)

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
        for _ in range(12):
            csvfile.write("\n")
        writer.writeheader()


        for page in reader.pages[:-1]:
            text = page.extract_text()
            match_table = re.search(regex_table, text, re.DOTALL | re.MULTILINE)
            if not match_table:
                print("warning")
                print(text)
                break

            table = match_table.group(0)[7:]  # cut off "VALUTA"
            matches = re.finditer(regex_transactions, table, re.MULTILINE)

            for match in matches:
                amount = parse_amount(match.group(4))
                writer.writerow({
                    "Wertstellungsdatum": match.group(1),
                    "Auftraggeber/Empfänger": match.group(3),
                    "Buchungstext": match.group(2),
                    "Verwendungszweck": match.group(6),
                    "Betrag": amount,
                    "Währung": "EUR",
                })

def main():
    parser = argparse.ArgumentParser(
        description="Extract transactions from ING bank PDFs into CSV."
    )
    parser.add_argument(
        "input_pdf", type=Path, help="Path to the input PDF file"
    )

    args = parser.parse_args()

    output_csv = args.input_pdf.with_suffix(".csv")

    extract_transactions(args.input_pdf, output_csv)

    print(f"Extracted data saved to: {output_csv}")

if __name__ == "__main__":
    main()
