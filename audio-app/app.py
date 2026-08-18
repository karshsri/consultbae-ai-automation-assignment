import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
import streamlit as st


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "consultbae.db"
AUDIO_DIR = ROOT / "audio-app" / "uploads"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def db():
    return sqlite3.connect(DB_PATH)


def normalize_phone(value):
    import re

    digits = re.sub(r"\D", "", str(value))

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    return digits


def get_or_create_person(name, phone):
    phone = normalize_phone(phone)

    conn = db()

    person = conn.execute(
        """
        SELECT person_id
        FROM people
        WHERE phone = ?
        LIMIT 1
        """,
        (phone,),
    ).fetchone()

    if person:
        conn.close()
        return person[0]

    conn.execute(
        """
        INSERT INTO people (
            full_name,
            email,
            phone,
            city,
            skills,
            created_at,
            updated_at
        )
        VALUES (?, '', ?, '', '[]', ?, ?)
        """,
        (
            name.strip(),
            phone,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()

    person_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.close()

    return person_id


def analyze_audio(audio_bytes):
    data, sample_rate = sf.read(
        io.BytesIO(audio_bytes),
        always_2d=True,
    )

    duration = len(data) / sample_rate

    mono = data.mean(axis=1)

    rms = float(
        np.sqrt(
            np.mean(
                np.square(mono.astype(np.float64))
            )
        )
    )

    loudness = (
        20 * np.log10(rms)
        if rms > 0
        else -100.0
    )

    bitrate = (
        len(audio_bytes) * 8 / duration / 1000
        if duration > 0
        else 0
    )

    return {
        "duration": duration,
        "sample_rate_khz": sample_rate / 1000,
        "bitrate_kbps": bitrate,
        "loudness_db": loudness,
    }


def save_submission(
    person_id,
    name,
    phone,
    audio_bytes,
    extension,
    metadata,
):
    timestamp = datetime.utcnow().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    filename = f"{person_id}_{timestamp}.{extension}"

    file_path = AUDIO_DIR / filename

    file_path.write_bytes(audio_bytes)

    conn = db()

    conn.execute(
        """
        INSERT INTO audio_submissions (
            person_id,
            name,
            phone,
            file_path,
            duration_seconds,
            sample_rate_khz,
            bitrate_kbps,
            loudness_db,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person_id,
            name,
            normalize_phone(phone),
            str(file_path),
            metadata["duration"],
            metadata["sample_rate_khz"],
            metadata["bitrate_kbps"],
            metadata["loudness_db"],
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


st.set_page_config(
    page_title="ConsultBae Audio",
    page_icon="🎙️",
    layout="wide",
)

st.title("🎙️ ConsultBae Audio Collection")
st.caption(
    "Mini audio submission system for the assignment"
)


tab_submit, tab_list = st.tabs(
    ["Submit Audio", "Submissions"]
)


with tab_submit:

    st.subheader("New submission")

    name = st.text_input(
        "Name",
        placeholder="Enter your name",
    )

    phone = st.text_input(
        "Phone",
        placeholder="Enter phone number",
    )

    st.write("Record audio or upload an audio file.")

    recorded = st.audio_input(
        "Record audio"
    )

    uploaded = st.file_uploader(
        "Or upload audio",
        type=[
            "wav",
            "flac",
            "ogg",
        ],
    )

    audio_file = recorded or uploaded

    if st.button(
        "Submit",
        type="primary",
    ):

        if not name.strip():
            st.error("Name is required.")

        elif not phone.strip():
            st.error("Phone is required.")

        elif not audio_file:
            st.error("Please record or upload audio.")

        else:

            try:
                audio_bytes = audio_file.getvalue()

                metadata = analyze_audio(
                    audio_bytes
                )

                person_id = get_or_create_person(
                    name,
                    phone,
                )

                extension = (
                    "wav"
                    if recorded
                    else Path(
                        audio_file.name
                    ).suffix.lower().lstrip(".")
                )

                save_submission(
                    person_id,
                    name,
                    phone,
                    audio_bytes,
                    extension,
                    metadata,
                )

                st.success(
                    "Audio submitted successfully."
                )

                st.json(metadata)

            except Exception as e:
                st.error(
                    f"Could not process audio: {e}"
                )


with tab_list:

    st.subheader("All submissions")

    conn = db()

    rows = conn.execute(
        """
        SELECT
            submission_id,
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

    if not rows:
        st.info("No submissions yet.")

    for row in rows:

        (
            submission_id,
            name,
            phone,
            file_path,
            duration,
            sample_rate,
            bitrate,
            loudness,
            created_at,
        ) = row

        st.markdown(
            f"### {name} — Submission #{submission_id}"
        )

        st.audio(
            Path(file_path).read_bytes()
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Duration",
            f"{duration:.2f} sec",
        )

        col2.metric(
            "Sample Rate",
            f"{sample_rate:.2f} kHz",
        )

        col3.metric(
            "Bitrate",
            f"{bitrate:.2f} kbps",
        )

        col4.metric(
            "Loudness",
            f"{loudness:.2f} dB",
        )

        st.caption(
            f"Phone: {phone} | Submitted: {created_at}"
        )

        st.divider()