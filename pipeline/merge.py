import csv
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from rapidfuzz.fuzz import ratio


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = DATA / "consultbae.db"


FILES = {
    "naukri": DATA / "source1_naukri_applicants.csv",
    "gig_workers": DATA / "source2_gig_workers.csv",
    "cbnexus": DATA / "source3_cbnexus_contacts.csv",
}


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def norm_text(value):
    return re.sub(r"\s+", " ", clean(value).lower()).strip()


def norm_name(value):
    value = norm_text(value)
    value = re.sub(r"[^a-z0-9 ]", "", value)
    return value


def norm_email(value):
    return clean(value).lower()


def norm_phone(value):
    """
    Converts Indian phone representations to a canonical
    10-digit mobile number.
    """
    value = clean(value)

    digits = re.sub(r"\D", "", value)

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) == 10:
        return digits

    return digits


def norm_city(value):
    value = norm_text(value)

    aliases = {
        "bangalore": "bengaluru",
        "gurgaon": "gurugram",
        "gurugram": "gurugram",
        "pune": "pune",
        "noida": "noida",
        "new delhi": "new delhi",
        "delhi": "delhi",
        "delhi ncr": "delhi ncr",
    }

    return aliases.get(value, value)


def normalize_skills(value):
    if not value:
        return []

    parts = re.split(r",", value)

    skills = []

    for part in parts:
        skill = norm_text(part)

        if skill and skill not in skills:
            skills.append(skill)

    return sorted(skills)


# ---------------------------------------------------------
# DATABASE
# ---------------------------------------------------------

def create_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS people (
            person_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            city TEXT,
            experience_years REAL,
            current_ctc_raw TEXT,
            skills TEXT,
            status TEXT,
            verified INTEGER,
            projects_completed INTEGER,
            skill_category TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_records (
            source_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            source_row INTEGER,
            raw_data TEXT NOT NULL,
            match_method TEXT NOT NULL,
            match_confidence REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(person_id) REFERENCES people(person_id)
        );

        CREATE TABLE IF NOT EXISTS audio_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            file_path TEXT NOT NULL,
            duration_seconds REAL,
            sample_rate_khz REAL,
            bitrate_kbps REAL,
            loudness_db REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(person_id) REFERENCES people(person_id)
        );
        """
    )

    conn.commit()
    return conn


# ---------------------------------------------------------
# SOURCE LOADERS
# ---------------------------------------------------------

def load_naukri():
    records = []

    path = FILES["naukri"]

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):
            records.append(
                {
                    "source": "naukri",
                    "source_row": row_number,
                    "full_name": clean(row.get("Full Name")),
                    "email": norm_email(row.get("Email")),
                    "phone": norm_phone(row.get("Phone")),
                    "city": norm_city(row.get("City")),
                    "experience_years": clean(row.get("Experience (Years)")),
                    "current_ctc_raw": clean(row.get("Current CTC")),
                    "skills": normalize_skills(row.get("Skills")),
                    "status": "",
                    "verified": None,
                    "projects_completed": None,
                    "raw": dict(row),
                }
            )

    return records


def looks_like_email(value):
    return bool(
        re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            clean(value)
        )
    )


def load_gig_workers():
    records = []

    path = FILES["gig_workers"]

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header = rows[0]

    for row_number, row in enumerate(rows[1:], start=2):

        # Blank planted row
        if not any(clean(x) for x in row):
            continue

        row = row + [""] * (6 - len(row))

        email, name, rate, location, status, skills = row[:6]

        # -------------------------------------------------
        # Repair shifted Isha-style row
        # -------------------------------------------------

        if (
            not looks_like_email(email)
            and looks_like_email(name)
            and clean(location).endswith("/hr")
            and clean(skills).lower() in {
                "active",
                "inactive",
                "paused",
            }
        ):
            original = {
                "email_id": email,
                "worker_name": name,
                "rate": rate,
                "location": location,
                "status": status,
                "skill_tags": skills,
            }

            skills, email, name, rate, location, status = (
                email,
                name,
                rate,
                location,
                status,
                skills,
            )

            repaired = True
        else:
            original = dict(zip(header, row))
            repaired = False

        records.append(
            {
                "source": "gig_workers",
                "source_row": row_number,
                "full_name": clean(name),
                "email": norm_email(email),
                "phone": "",
                "city": norm_city(location),
                "experience_years": "",
                "current_ctc_raw": clean(rate),
                "skills": normalize_skills(skills),
                "status": norm_text(status),
                "verified": None,
                "projects_completed": None,
                "raw": original,
                "repaired": repaired,
            }
        )

    return records


def load_cbnexus():
    records = []

    path = FILES["cbnexus"]

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):

            name = clean(row.get("Name"))
            phone = clean(row.get("Phone Number"))

            # Remove repeated header planted inside data
            if (
                norm_text(name) == "name"
                and norm_text(phone) == "phone number"
            ):
                continue

            verified_raw = norm_text(row.get("Verified"))

            verified = None

            if verified_raw in {"y", "yes"}:
                verified = 1
            elif verified_raw in {"n", "no"}:
                verified = 0

            projects = clean(row.get("Projects Completed"))

            records.append(
                {
                    "source": "cbnexus",
                    "source_row": row_number,
                    "full_name": name,
                    "email": "",
                    "phone": norm_phone(phone),
                    "city": norm_city(row.get("City")),
                    "experience_years": "",
                    "current_ctc_raw": "",
                    "skills": [],
                    "status": "",
                    "verified": verified,
                    "projects_completed": (
                        int(float(projects))
                        if projects.replace(".", "", 1).isdigit()
                        else None
                    ),
                    "raw": dict(row),
                }
            )

    return records


# ---------------------------------------------------------
# MATCHING
# ---------------------------------------------------------

def get_person_indexes(conn):
    people = conn.execute(
        "SELECT * FROM people"
    ).fetchall()

    columns = [
        "person_id",
        "full_name",
        "email",
        "phone",
        "city",
        "experience_years",
        "current_ctc_raw",
        "skills",
        "status",
        "verified",
        "projects_completed",
        "skill_category",
        "created_at",
        "updated_at",
    ]

    return [
        dict(zip(columns, row))
        for row in people
    ]


def find_match(record, people):
    email = norm_email(record["email"])
    phone = norm_phone(record["phone"])
    name = norm_name(record["full_name"])
    city = norm_city(record["city"])

    # -----------------------------------------------------
    # Tier 1: exact phone
    # -----------------------------------------------------

    if phone:
        matches = [
            p for p in people
            if norm_phone(p["phone"]) == phone
        ]

        if len(matches) == 1:
            return matches[0], "exact_phone", 1.0

    # -----------------------------------------------------
    # Tier 2: exact email
    # -----------------------------------------------------

    if email:
        matches = [
            p for p in people
            if norm_email(p["email"]) == email
        ]

        if len(matches) == 1:
            return matches[0], "exact_email", 1.0

    # -----------------------------------------------------
    # Tier 3: email or phone + same name
    # -----------------------------------------------------

    for person in people:

        email_match = (
            email
            and norm_email(person["email"]) == email
        )

        phone_match = (
            phone
            and norm_phone(person["phone"]) == phone
        )

        name_match = (
            name
            and norm_name(person["full_name"]) == name
        )

        if (email_match or phone_match) and name_match:
            return person, "identity_plus_name", 0.99

    # -----------------------------------------------------
    # Tier 4: fuzzy name + city
    # -----------------------------------------------------

    if name:

        candidates = []

        for person in people:

            person_name = norm_name(person["full_name"])
            person_city = norm_city(person["city"])

            name_score = ratio(name, person_name)

            city_match = (
                city
                and person_city
                and city == person_city
            )

            if city_match and name_score >= 92:
                candidates.append(
                    (person, name_score)
                )

        if len(candidates) == 1:
            person, score = candidates[0]

            return (
                person,
                "fuzzy_name_city",
                round(score / 100, 3),
            )

    return None, "new_person", 0.0


# ---------------------------------------------------------
# PERSON INSERT / UPDATE
# ---------------------------------------------------------

def insert_person(conn, record):
    now = datetime.utcnow().isoformat()

    cursor = conn.execute(
        """
        INSERT INTO people (
            full_name,
            email,
            phone,
            city,
            experience_years,
            current_ctc_raw,
            skills,
            status,
            verified,
            projects_completed,
            skill_category,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["full_name"],
            record["email"],
            record["phone"],
            record["city"],
            float(record["experience_years"])
            if record["experience_years"]
            else None,
            record["current_ctc_raw"],
            json.dumps(record["skills"]),
            record["status"],
            record["verified"],
            record["projects_completed"],
            None,
            now,
            now,
        ),
    )

    conn.commit()

    return cursor.lastrowid


def update_person(conn, person_id, record):
    person = conn.execute(
        "SELECT * FROM people WHERE person_id = ?",
        (person_id,),
    ).fetchone()

    if not person:
        return

    columns = [
        "person_id",
        "full_name",
        "email",
        "phone",
        "city",
        "experience_years",
        "current_ctc_raw",
        "skills",
        "status",
        "verified",
        "projects_completed",
        "skill_category",
        "created_at",
        "updated_at",
    ]

    existing = dict(zip(columns, person))

    def choose(old, new):
        return new if clean(new) and not clean(old) else old

    name = choose(
        existing["full_name"],
        record["full_name"],
    )

    email = choose(
        existing["email"],
        record["email"],
    )

    phone = choose(
        existing["phone"],
        record["phone"],
    )

    city = choose(
        existing["city"],
        record["city"],
    )

    experience = (
        existing["experience_years"]
        if existing["experience_years"] is not None
        else (
            float(record["experience_years"])
            if record["experience_years"]
            else None
        )
    )

    ctc = choose(
        existing["current_ctc_raw"],
        record["current_ctc_raw"],
    )

    existing_skills = (
        json.loads(existing["skills"])
        if existing["skills"]
        else []
    )

    merged_skills = sorted(
        set(existing_skills + record["skills"])
    )

    status = choose(
        existing["status"],
        record["status"],
    )

    verified = (
        record["verified"]
        if record["verified"] is not None
        else existing["verified"]
    )

    projects = (
        record["projects_completed"]
        if record["projects_completed"] is not None
        else existing["projects_completed"]
    )

    conn.execute(
        """
        UPDATE people
        SET
            full_name = ?,
            email = ?,
            phone = ?,
            city = ?,
            experience_years = ?,
            current_ctc_raw = ?,
            skills = ?,
            status = ?,
            verified = ?,
            projects_completed = ?,
            updated_at = ?
        WHERE person_id = ?
        """,
        (
            name,
            email,
            phone,
            city,
            experience,
            ctc,
            json.dumps(merged_skills),
            status,
            verified,
            projects,
            datetime.utcnow().isoformat(),
            person_id,
        ),
    )

    conn.commit()


# ---------------------------------------------------------
# INGESTION
# ---------------------------------------------------------

def ingest_source(conn, records):
    created = 0
    matched = 0

    for record in records:

        people = get_person_indexes(conn)

        person, method, confidence = find_match(
            record,
            people,
        )

        if person:
            person_id = person["person_id"]
            matched += 1

            update_person(
                conn,
                person_id,
                record,
            )

        else:
            person_id = insert_person(
                conn,
                record,
            )

            created += 1

        conn.execute(
            """
            INSERT INTO source_records (
                person_id,
                source,
                source_row,
                raw_data,
                match_method,
                match_confidence,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                record["source"],
                record["source_row"],
                json.dumps(record["raw"]),
                method,
                confidence,
                datetime.utcnow().isoformat(),
            ),
        )

        conn.commit()

    return created, matched


def main():

    # Start clean every time so the pipeline is reproducible.
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = create_database()

    all_sources = [
        ("Naukri", load_naukri()),
        ("Gig Workers", load_gig_workers()),
        ("CBNexus", load_cbnexus()),
    ]

    total_created = 0
    total_matched = 0

    for source_name, records in all_sources:

        created, matched = ingest_source(
            conn,
            records,
        )

        total_created += created
        total_matched += matched

        print(
            f"{source_name}: "
            f"{len(records)} records | "
            f"{created} new | "
            f"{matched} matched"
        )

    people_count = conn.execute(
        "SELECT COUNT(*) FROM people"
    ).fetchone()[0]

    source_count = conn.execute(
        "SELECT COUNT(*) FROM source_records"
    ).fetchone()[0]

    print("\n" + "=" * 60)
    print("MERGE COMPLETE")
    print("=" * 60)
    print(f"People: {people_count}")
    print(f"Source records: {source_count}")
    print(f"New people: {total_created}")
    print(f"Matched records: {total_matched}")
    print(f"Database: {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()