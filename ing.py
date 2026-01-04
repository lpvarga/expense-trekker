import pandas as pd
from pathlib import Path

# Folder containing the CSV files
file_path = Path("auskunft_folder/new/ing/ing2025jan.csv")

# Iterate over all CSV files in the folder

print(f"Processing {file_path.name}...")

# Read CSV, skip first 12 rows
df = pd.read_csv(file_path, skiprows=12, encoding='latin-1', delimiter=';')

# Fix "Betrag" column: remove thousand separators and convert decimal comma to dot

# df["Betrag"] = df["Betrag"].astype(str).str.replace('.', '', regex=False)

df["Betrag"] = df["Betrag"].astype(str).str.replace(',', '.', regex=False)

# Read the first 12 lines to preserve them
with open(file_path, "r", encoding="latin-1") as f:
    first_12_lines = [next(f) for _ in range(12)]

# Write back: first 12 lines + modified DataFrame
with open(file_path, "w", encoding="latin-1", newline="") as f:
    f.writelines(first_12_lines)
    df.to_csv(f, index=False, sep=';')

print(f"{file_path.name} updated successfully.")
