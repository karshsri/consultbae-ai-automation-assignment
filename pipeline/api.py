from pathlib import Path
import json
import sqlite3
import uuid
from typing import Optional

import soundfile as sf
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "consultbae.db"

AUDIO_DIR = PROJECT_ROOT / "audio" / "uploads"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

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
    version="1.1.0",
)

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
    if not DB_PATH.exists():
        raise RuntimeError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_audio_table():
    """
    Create the audio submissions table if it does not exist.
    """

    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audio_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            duration_seconds REAL,
            sample_rate INTEGER,
            channels INTEGER,
            file_size_bytes INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


# ============================================================
# HELPERS
# ============================================================

def parse_skills(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    value = str(value).strip()

    if not value:
        return []

    try:
        parsed = json.loads(value)

        if isinstance(parsed, list):
            return [
                str(skill).strip()
                for skill in parsed
                if str(skill).strip()
            ]

    except (json.JSONDecodeError, TypeError):
        pass

    return [
        skill.strip()
        for skill in value.split(",")
        if skill.strip()
    ]


def row_to_person(row):
    result = {
        "person_id": row["person_id"],
        "full_name": row["full_name"],
        "skills": parse_skills(row["skills"]),
    }

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
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    ensure_audio_table()


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "ConsultBae Local Data API",
    }


@app.get("/health")
def health():

    try:
        conn = get_connection()

        count = conn.execute(
            "SELECT COUNT(*) AS count FROM people"
        ).fetchone()["count"]

        audio_count = conn.execute(
            "SELECT COUNT(*) AS count FROM audio_submissions"
        ).fetchone()["count"]

        conn.close()

        return {
            "status": "ok",
            "database": "connected",
            "people_count": count,
            "audio_submissions": audio_count,
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
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):

    conn = get_connection()

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
# BULK-FRIENDLY CATEGORY UPDATE
# ============================================================

@app.post("/people/category")
def update_category(payload: dict):

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


# ============================================================
# AUDIO SUBMISSIONS
# ============================================================

@app.post("/audio/submit")
async def submit_audio(
    name: str = Form(...),
    phone: str = Form(...),
    audio: UploadFile = File(...),
):

    if not name.strip():
        raise HTTPException(
            status_code=400,
            detail="Name is required",
        )

    if not phone.strip():
        raise HTTPException(
            status_code=400,
            detail="Phone is required",
        )

    if not audio.filename:
        raise HTTPException(
            status_code=400,
            detail="Audio file is required",
        )

    extension = Path(audio.filename).suffix.lower()

    allowed_extensions = {
        ".wav",
        ".mp3",
        ".ogg",
        ".flac",
        ".m4a",
    }

    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {extension}",
        )

    stored_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    destination = AUDIO_DIR / stored_filename

    try:

        contents = await audio.read()

        destination.write_bytes(contents)

        file_size = destination.stat().st_size

        duration = None
        sample_rate = None
        channels = None

        # soundfile supports WAV/FLAC/OGG and other
        # formats supported by libsndfile.
        try:
            info = sf.info(str(destination))

            duration = round(
                float(info.duration),
                3,
            )

            sample_rate = int(info.samplerate)
            channels = int(info.channels)

        except Exception:
            # Some formats such as certain MP4/M4A files
            # may not be supported by soundfile.
            pass

        conn = get_connection()

        cursor = conn.execute(
            """
            INSERT INTO audio_submissions (
                name,
                phone,
                filename,
                stored_filename,
                duration_seconds,
                sample_rate,
                channels,
                file_size_bytes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                phone.strip(),
                audio.filename,
                stored_filename,
                duration,
                sample_rate,
                channels,
                file_size,
            ),
        )

        conn.commit()

        submission_id = cursor.lastrowid

        conn.close()

        return {
            "status": "submitted",
            "submission_id": submission_id,
            "name": name.strip(),
            "phone": phone.strip(),
            "filename": audio.filename,
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "file_size_bytes": file_size,
        }

    except Exception as e:

        if destination.exists():
            destination.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)}",
        )


# ============================================================
# LIST AUDIO SUBMISSIONS
# ============================================================

@app.get("/audio/submissions")
def get_audio_submissions():

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            submission_id,
            person_id,
            name,
            phone,
            file_path,
            duration_seconds,
            sample_rate_khz,
            bitrate_kbps,
            loudness_db,
            created_at
        FROM audio_submissions
        ORDER BY submission_id DESC
        """
    ).fetchall()

    conn.close()

    return [
        {
            "submission_id": row["submission_id"],
            "person_id": row["person_id"],
            "name": row["name"],
            "phone": row["phone"],
            "file_path": row["file_path"],
            "duration_seconds": row["duration_seconds"],
            "sample_rate_khz": row["sample_rate_khz"],
            "bitrate_kbps": row["bitrate_kbps"],
            "loudness_db": row["loudness_db"],
            "created_at": row["created_at"],
            "audio_url": f"/audio/file/{Path(row['file_path']).name}",
        }
        for row in rows
    ]

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM audio_submissions
        ORDER BY submission_id DESC
        """
    ).fetchall()

    conn.close()

    return [
        {
            "submission_id": row["submission_id"],
            "name": row["name"],
            "phone": row["phone"],
            "filename": row["filename"],
            "duration_seconds": row["duration_seconds"],
            "sample_rate": row["sample_rate"],
            "channels": row["channels"],
            "file_size_bytes": row["file_size_bytes"],
            "created_at": row["created_at"],
            "audio_url": f"/audio/file/{row['stored_filename']}",
        }
        for row in rows
    ]


# ============================================================
# AUDIO FILE
# ============================================================

@app.get("/audio/file/{filename}")
def get_audio_file(filename: str):

    safe_filename = Path(filename).name
    audio_path = AUDIO_DIR / safe_filename

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found",
        )

    return FileResponse(
        audio_path,
        filename=safe_filename,
    )