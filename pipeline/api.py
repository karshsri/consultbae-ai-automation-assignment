from pathlib import Path
import json
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "consultbae.db"

ALLOWED_CATEGORIES = {
    "automation-heavy",
    "web-dev",
    "data",
    "backend",
    "general-tech",
}


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="ConsultBae Local Data API",
    description="API for the ConsultBae AI Automation assignment",
    version="1.0.0",
)


# Allow the local audio app / browser to communicate with API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """
    Create a fresh SQLite connection for each request.
    """
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# HELPERS
# ============================================================

def parse_skills(value):
    """
    Convert the skills field stored in SQLite into a Python list.

    Supports:
    - JSON arrays
    - comma-separated strings
    - Python-like lists
    - empty/null values
    """

    if value is None:
        return []

    if isinstance(value, list):
        return value

    value = str(value).strip()

    if not value:
        return []

    # Try JSON first
    try:
        parsed = json.loads(value)

        if isinstance(parsed, list):
            return [str(skill).strip() for skill in parsed if str(skill).strip()]

    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to comma-separated values
    return [
        skill.strip()
        for skill in value.split(",")
        if skill.strip()
    ]


def row_to_person(row):
    """
    Convert SQLite row into API response.
    """

    result = {
        "person_id": row["person_id"],
        "full_name": row["full_name"],
        "skills": parse_skills(row["skills"]),
    }

    # Include category when available
    if "skill_category" in row.keys():
        result["skill_category"] = row["skill_category"]

    return result


# ============================================================
# REQUEST MODELS
# ============================================================

class CategoryUpdate(BaseModel):
    skill_category: str = Field(
        ...,
        description="One of the allowed candidate categories",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "ConsultBae Local Data API",
    }


@app.get("/health")
def health():
    """
    Health check including database status.
    """

    try:
        conn = get_connection()

        count = conn.execute(
            "SELECT COUNT(*) AS count FROM people"
        ).fetchone()["count"]

        conn.close()

        return {
            "status": "ok",
            "database": "connected",
            "people_count": count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )


# ============================================================
# PEOPLE
# ============================================================

@app.get("/people")
def get_people(
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=1000,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    """
    Return people from the canonical people table.

    Examples:
        /people
        /people?limit=10
        /people?limit=10&offset=10
    """

    conn = get_connection()

    query = """
        SELECT *
        FROM people
        ORDER BY person_id
    """

    params = []

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    if offset:
        query += " OFFSET ?"
        params.append(offset)

    rows = conn.execute(query, params).fetchall()

    conn.close()

    return [row_to_person(row) for row in rows]


# ============================================================
# UNTAGGED PEOPLE
# ============================================================

@app.get("/people/untagged")
def get_untagged_people(
    limit: Optional[int] = Query(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of untagged people to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip",
    ),
):
    """
    Return people whose AI skill category has not been assigned.

    Examples:

        /people/untagged

        /people/untagged?limit=1

        /people/untagged?limit=5

        /people/untagged?limit=5&offset=5
    """

    conn = get_connection()

    # Make sure the expected category column exists.
    columns = conn.execute(
        "PRAGMA table_info(people)"
    ).fetchall()

    column_names = {column["name"] for column in columns}

    if "skill_category" not in column_names:
        conn.close()

        raise HTTPException(
            status_code=500,
            detail=(
                "The people table does not contain the "
                "'skill_category' column."
            ),
        )

    query = """
        SELECT *
        FROM people
        WHERE skill_category IS NULL
           OR TRIM(skill_category) = ''
        ORDER BY person_id
    """

    params = []

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    if offset:
        query += " OFFSET ?"
        params.append(offset)

    rows = conn.execute(query, params).fetchall()

    conn.close()

    return [row_to_person(row) for row in rows]


# ============================================================
# GET ONE PERSON
# ============================================================

@app.get("/people/{person_id}")
def get_person(person_id: int):
    """
    Return one person by canonical person_id.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM people
        WHERE person_id = ?
        """,
        (person_id,),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Person {person_id} not found",
        )

    return row_to_person(row)


# ============================================================
# UPDATE CATEGORY
# ============================================================

@app.post("/people/{person_id}/category")
def update_person_category(
    person_id: int,
    payload: CategoryUpdate,
):
    """
    Update AI-generated skill category for one person.

    This is the endpoint that n8n will call after Gemini
    classifies a candidate.
    """

    category = payload.skill_category.strip().lower()

    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid skill category",
                "allowed_categories": sorted(ALLOWED_CATEGORIES),
            },
        )

    conn = get_connection()

    # Check person exists
    person = conn.execute(
        """
        SELECT person_id, full_name
        FROM people
        WHERE person_id = ?
        """,
        (person_id,),
    ).fetchone()

    if person is None:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail=f"Person {person_id} not found",
        )

    # Update category
    cursor = conn.execute(
        """
        UPDATE people
        SET skill_category = ?
        WHERE person_id = ?
        """,
        (category, person_id),
    )

    conn.commit()

    updated = cursor.rowcount

    conn.close()

    return {
        "status": "updated",
        "person_id": person_id,
        "full_name": person["full_name"],
        "skill_category": category,
        "rows_updated": updated,
    }


# ============================================================
# ALTERNATIVE BULK-FRIENDLY UPDATE ENDPOINT
# ============================================================

@app.post("/people/category")
def update_category(payload: dict):
    """
    Alternative endpoint for n8n.

    Expected JSON:

    {
        "person_id": 1,
        "skill_category": "automation-heavy"
    }
    """

    if "person_id" not in payload:
        raise HTTPException(
            status_code=400,
            detail="person_id is required",
        )

    if "skill_category" not in payload:
        raise HTTPException(
            status_code=400,
            detail="skill_category is required",
        )

    try:
        person_id = int(payload["person_id"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="person_id must be an integer",
        )

    category = str(
        payload["skill_category"]
    ).strip().lower()

    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid skill category",
                "allowed_categories": sorted(ALLOWED_CATEGORIES),
            },
        )

    conn = get_connection()

    person = conn.execute(
        """
        SELECT person_id, full_name
        FROM people
        WHERE person_id = ?
        """,
        (person_id,),
    ).fetchone()

    if person is None:
        conn.close()

        raise HTTPException(
            status_code=404,
            detail=f"Person {person_id} not found",
        )

    conn.execute(
        """
        UPDATE people
        SET skill_category = ?
        WHERE person_id = ?
        """,
        (category, person_id),
    )

    conn.commit()
    conn.close()

    return {
        "status": "updated",
        "person_id": person_id,
        "full_name": person["full_name"],
        "skill_category": category,
    }


# ============================================================
# CATEGORY SUMMARY
# ============================================================

@app.get("/people/categories/summary")
def category_summary():
    """
    Return count of people in each AI category.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            COALESCE(
                NULLIF(TRIM(skill_category), ''),
                'untagged'
            ) AS category,
            COUNT(*) AS count
        FROM people
        GROUP BY category
        ORDER BY category
        """
    ).fetchall()

    conn.close()

    return {
        row["category"]: row["count"]
        for row in rows
    }