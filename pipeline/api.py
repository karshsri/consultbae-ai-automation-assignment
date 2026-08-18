import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "consultbae.db"

app = FastAPI(title="ConsultBae Local Data API")


@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "ConsultBae Local Data API"
    }


@app.get("/people/untagged")
def untagged_people():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            person_id,
            full_name,
            skills
        FROM people
        WHERE skill_category IS NULL
        LIMIT 20
        """
    ).fetchall()

    conn.close()

    return [
        {
            "person_id": row["person_id"],
            "full_name": row["full_name"],
            "skills": json.loads(row["skills"] or "[]"),
        }
        for row in rows
    ]


@app.post("/people/{person_id}/skill-category")
def update_skill_category(
    person_id: int,
    category: str,
):
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        UPDATE people
        SET
            skill_category = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE person_id = ?
        """,
        (category, person_id),
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "person_id": person_id,
        "skill_category": category,
    }