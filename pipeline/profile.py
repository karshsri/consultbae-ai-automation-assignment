import csv
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


FILES = {
    "Naukri Applicants": DATA_DIR / "source1_naukri_applicants.csv",
    "Gig Workers": DATA_DIR / "source2_gig_workers.csv",
    "CBNexus Contacts": DATA_DIR / "source3_cbnexus_contacts.csv",
}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def print_section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def profile_file(source_name: str, file_path: Path) -> None:
    print_section(f"SOURCE: {source_name}")

    print(f"File: {file_path.name}")

    # -----------------------------------------------------
    # Raw CSV structure check
    # -----------------------------------------------------

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        raw_rows = list(reader)

    if not raw_rows:
        print("ERROR: File is empty.")
        return

    header = raw_rows[0]
    expected_columns = len(header)

    print(f"Raw header columns: {expected_columns}")
    print(f"Raw data rows: {len(raw_rows) - 1}")

    malformed_rows = []

    for row_number, row in enumerate(raw_rows[1:], start=2):
        if len(row) != expected_columns:
            malformed_rows.append(
                {
                    "row": row_number,
                    "expected_columns": expected_columns,
                    "actual_columns": len(row),
                    "data": row,
                }
            )

    print(f"Rows with unexpected column count: {len(malformed_rows)}")

    for item in malformed_rows:
        print(
            f"  Row {item['row']}: "
            f"expected {item['expected_columns']} columns, "
            f"found {item['actual_columns']}"
        )

    # -----------------------------------------------------
    # Load with pandas
    # -----------------------------------------------------

    df = pd.read_csv(
    file_path,
    dtype=str,
    keep_default_na=False
)

    print(f"\nPandas rows: {len(df)}")
    print(f"Pandas columns: {len(df.columns)}")

    print("\nColumns:")
    for column in df.columns:
        print(f"  - {column}")

    # -----------------------------------------------------
    # Missing values
    # -----------------------------------------------------

    print("\nMissing values:")

    missing = df.isna().sum()
    missing = missing[missing > 0]

    if missing.empty:
        print("  None")
    else:
        for column, count in missing.items():
            print(f"  {column}: {count}")

    # -----------------------------------------------------
    # Completely blank rows
    # -----------------------------------------------------

    blank_rows = df.isna().all(axis=1)

    print(f"\nCompletely blank rows: {blank_rows.sum()}")

    if blank_rows.any():
        print("  Row numbers:")
        for index in df.index[blank_rows]:
            print(f"    CSV row {index + 2}")

    # -----------------------------------------------------
    # Exact duplicate rows
    # -----------------------------------------------------

    duplicate_rows = df.duplicated(keep=False)

    print(f"\nRows involved in exact duplicates: {duplicate_rows.sum()}")

    if duplicate_rows.any():
        duplicate_indices = df.index[duplicate_rows]

        for index in duplicate_indices:
            print(f"  CSV row {index + 2}")

    # -----------------------------------------------------
    # Repeated values for likely identity columns
    # -----------------------------------------------------

    identity_columns = [
        column
        for column in df.columns
        if any(
            keyword in column.lower()
            for keyword in ["email", "phone", "mobile", "name"]
        )
    ]

    print("\nPotential identity columns:")
    for column in identity_columns:
        print(f"  - {column}")

    for column in identity_columns:
        values = (
            df[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        duplicated_values = values[
            values.duplicated(keep=False)
        ]

        if duplicated_values.empty:
            print(f"\nRepeated values in {column}: None")
        else:
            print(f"\nRepeated values in {column}:")

            for value in sorted(duplicated_values.unique()):
                count = (values == value).sum()
                print(f"  {value} -> {count} occurrences")

    # -----------------------------------------------------
    # Unique values for categorical-looking columns
    # -----------------------------------------------------

    categorical_keywords = [
        "city",
        "location",
        "status",
        "verified",
        "skill",
        "tags",
    ]

    categorical_columns = [
        column
        for column in df.columns
        if any(
            keyword in column.lower()
            for keyword in categorical_keywords
        )
    ]

    print("\nCategorical / consistency checks:")

    for column in categorical_columns:
        values = (
            df[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        print(f"\n{column}:")
        print(f"  Unique values: {values.nunique()}")

        unique_values = sorted(values.unique(), key=str.lower)

        for value in unique_values:
            print(f"    {value}")

    # -----------------------------------------------------
    # Basic numeric information
    # -----------------------------------------------------

    numeric_columns = df.select_dtypes(
        include=["number"]
    ).columns.tolist()

    if numeric_columns:
        print("\nNumeric columns:")

        for column in numeric_columns:
            print(f"\n{column}:")
            print(f"  Min: {df[column].min()}")
            print(f"  Max: {df[column].max()}")
            print(f"  Mean: {df[column].mean():.2f}")

    print()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:
    print_section("CONSULTBAE DATA PROFILING")

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Data directory: {DATA_DIR}")

    for source_name, file_path in FILES.items():

        if not file_path.exists():
            print(
                f"\nERROR: {source_name} file not found:"
                f"\n{file_path}"
            )
            continue

        profile_file(source_name, file_path)

    print_section("PROFILING COMPLETE")


if __name__ == "__main__":
    main()