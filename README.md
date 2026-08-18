# ConsultBae AI Automation Assignment

An end-to-end implementation of the ConsultBae AI Automation assignment covering **data ingestion, data cleaning, entity matching, AI-based skill categorization, REST APIs, n8n automation, and audio submission with metadata extraction**.

The project is designed as a reproducible local workflow that can be tested, demonstrated, and extended toward a production-ready architecture.

---

## 1. Project Overview

The implementation covers four major areas:

1. **Data ingestion, profiling, cleaning, and entity matching**
2. **AI-powered candidate skill categorization using n8n and Gemini**
3. **FastAPI REST API for candidate and database operations**
4. **Audio submission application with automatic metadata extraction**

### Technology Stack

* **Python**
* **SQLite**
* **FastAPI**
* **n8n**
* **Google Gemini**
* **Pandas**
* **Cloudflare Tunnel**
* **Git / GitHub**

---

## 2. Repository Structure

```text
consultbae-assignment/
│
├── data/
│   ├── source1_naukri.csv
│   ├── source2_gig.csv
│   ├── source3_cbnetwork.csv
│   ├── consultbae.db
│   └── .gitkeep
│
├── pipeline/
│   ├── __init__.py
│   ├── profile.py
│   ├── merge.py
│   ├── api.py
│   └── .gitkeep
│
├── n8n/
│   ├── skill_categorization_workflow.json
│   └── .gitkeep
│
├── audio-app/
│   ├── app.py
│   ├── .gitkeep
│   └── uploads/
│
├── reports/
│   └── data_quality_report.md
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# 3. Task 1 — Data Ingestion, Cleaning & Entity Matching

The three source datasets contain overlapping worker/person information. The objective was to combine them into one canonical database while preventing duplicate people.

The matching strategy uses progressively weaker identifiers:

```text
Phone Number
     ↓
Email
     ↓
Fuzzy Name + City
```

This approach helps handle incomplete or inconsistent records across different sources.

### Data Profiling

Before merging, the source files were profiled for:

* Missing values
* Duplicate records
* Inconsistent names
* Inconsistent cities
* Missing contact information
* Different skill formats
* Potential identity collisions

The profiling implementation is located at:

```text
pipeline/profile.py
```

### Data Merge

The main entity-matching implementation is located at:

```text
pipeline/merge.py
```

The pipeline:

1. Reads the source datasets.
2. Normalizes important fields.
3. Matches records using phone numbers.
4. Falls back to email matching.
5. Uses fuzzy name/city matching when required.
6. Combines information belonging to the same person.
7. Preserves source information for traceability.
8. Stores the canonical records in SQLite.

The resulting database is:

```text
data/consultbae.db
```

---

# 4. Data Quality

Data-quality decisions are documented separately in:

```text
reports/data_quality_report.md
```

The report covers issues such as:

* Missing information
* Duplicate people across sources
* Different name formats
* Different skill representations
* Partial records
* Conflicting information
* Ambiguous identity matches

Instead of simply deleting problematic records, the implementation attempts to preserve useful source information and use the strongest available identifiers during matching.

---

# 5. Task 2 — AI Skill Categorization

The second major component uses **n8n** to automate candidate skill categorization.

The exported workflow is available at:

```text
n8n/skill_categorization_workflow.json
```

The workflow connects the FastAPI API with an LLM and writes the resulting category back to the database.

### Categories

Each candidate receives exactly one category:

```text
automation-heavy
web-dev
data
backend
general-tech
```

Examples of classification signals:

### automation-heavy

```text
n8n
Zapier
Selenium
web scraping
workflow automation
```

### web-dev

```text
React
JavaScript
frontend
web development
```

### data

```text
Python
Pandas
SQL
data analysis
analytics
```

### backend

```text
FastAPI
REST APIs
Docker
backend/server development
```

### general-tech

Used when none of the above categories clearly dominates.

---

# 6. n8n Workflow

The automation follows this flow:

```text
FastAPI
   ↓
GET /people/untagged
   ↓
n8n
   ↓
Candidate Skills
   ↓
Gemini AI
   ↓
One Skill Category
   ↓
PATCH Candidate
   ↓
FastAPI
   ↓
SQLite
```

During development, the local FastAPI application was exposed to n8n Cloud using a Cloudflare Quick Tunnel.

```text
Local FastAPI
     ↓
Cloudflare Tunnel
     ↓
Temporary HTTPS URL
     ↓
n8n Cloud
```

This allowed the cloud-hosted n8n workflow to communicate with the local development API.

---

# 7. Example Classification

Example candidate:

```text
Tanvi Gupta

Skills:
- langchain
- mongodb
- n8n
- rest apis
- sql
```

Classification:

```text
automation-heavy
```

The workflow is designed to return only the required category rather than a long explanation. This keeps the output predictable and easy for downstream automation to process.

---

# 8. Gemini Rate Limit Handling

During development, the Gemini free-tier API reached its request limit and returned:

```text
429 Too Many Requests
```

To avoid unnecessary requests during testing, the workflow was tested using a small number of candidates at a time.

For example:

```text
GET /people/untagged?limit=1
```

This allowed individual candidates to be processed and verified before increasing the workload.

For a production deployment, retry policies, exponential backoff, queueing, throttling, and monitoring would be added.

---

# 9. Task 3 — Audio Submission Application

The project also includes a small audio-submission application located at:

```text
audio-app/app.py
```

The application accepts candidate information and an audio file.

Uploaded files are stored under:

```text
audio-app/uploads/
```

The upload directory is excluded from Git because generated/test audio files should not be committed to the repository.

The general flow is:

```text
Candidate
   ↓
Audio Upload
   ↓
Metadata Extraction
   ↓
SQLite
   ↓
FastAPI
```

---

# 10. Audio Metadata Extraction

The application extracts useful audio metadata including:

* Duration
* Sample rate
* Bitrate
* Loudness

Example database record:

```json
{
  "submission_id": 1,
  "person_id": 55,
  "name": "Utkarsh Test",
  "phone": "9000000000",
  "duration_seconds": 9.6,
  "sample_rate_khz": 16.0,
  "bitrate_kbps": 256.04,
  "loudness_db": -26.97
}
```

This allows the system to retain both the submitted file and its technical characteristics.

---

# 11. FastAPI

The API is implemented in:

```text
pipeline/api.py
```

It acts as the interface between the database, n8n, and the audio application.

Important endpoints include:

```text
GET  /health
GET  /people/untagged
GET  /audio/submissions
GET  /audio/file/{filename}
```

The API also provides the endpoint required to update a candidate's skill category.

---

## Health Check

```text
GET /health
```

Example:

```json
{
  "status": "ok",
  "database": "connected",
  "people_count": 55,
  "audio_submissions": 1
}
```

---

## Untagged Candidates

```text
GET /people/untagged
```

For controlled testing:

```text
GET /people/untagged?limit=1
```

Example:

```json
[
  {
    "person_id": 1,
    "full_name": "Tanvi Gupta",
    "skills": [
      "langchain",
      "mongodb",
      "n8n",
      "rest apis",
      "sql"
    ],
    "skill_category": null
  }
]
```

After classification, the category is written back to the database.

---

# 12. Running the Project

## Requirements

Recommended environment:

```text
Python 3.11+
uv
SQLite
n8n
Google Gemini API key
```

Dependencies are listed in:

```text
requirements.txt
```

### Create Environment

From the repository root:

```powershell
cd D:\consultbae-assignment
uv venv
```

Install dependencies:

```powershell
uv pip install -r requirements.txt
```

---

# 13. Start FastAPI

Run the API from the repository root:

```powershell
uv run uvicorn pipeline.api:app --reload --port 8000
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Test it with:

```powershell
curl.exe http://127.0.0.1:8000/health
```

---

# 14. Test Candidate Retrieval

Run:

```powershell
curl.exe "http://127.0.0.1:8000/people/untagged?limit=1"
```

This is useful when testing the n8n workflow because it limits the number of LLM requests.

---

# 15. Cloudflare Tunnel

To allow n8n Cloud to access the locally running API:

```powershell
cloudflared tunnel --url http://localhost:8000
```

This generates a temporary URL similar to:

```text
https://<random-name>.trycloudflare.com
```

The n8n HTTP Request nodes can then use:

```text
https://<random-name>.trycloudflare.com/people/untagged?limit=1
```

The Quick Tunnel is intended for development/testing. Production would use a permanent deployment or named tunnel.

---

# 16. Importing the n8n Workflow

The workflow is located at:

```text
n8n/skill_categorization_workflow.json
```

To use it:

1. Open n8n.
2. Import the workflow JSON.
3. Configure the Gemini credentials.
4. Update the API/tunnel URL.
5. Start with a small candidate limit.
6. Execute the workflow.
7. Verify the returned category.
8. Verify the database/API was updated.

---

# 17. Scaling to 5,000 Workers

The current implementation is intentionally lightweight and suitable for an assignment-scale workload.

For approximately 5,000 workers, the main improvements would be:

### Database

Replace SQLite with:

```text
PostgreSQL
```

### Background Processing

Instead of processing candidates synchronously:

```text
API
 ↓
Queue
 ↓
Workers
 ↓
LLM
 ↓
Database
```

Possible queue technologies include:

```text
Redis
Celery
RQ
AWS SQS
Google Pub/Sub
```

### API Scaling

Deploy multiple FastAPI workers behind a load balancer:

```text
Load Balancer
      ↓
 ┌────┼────┐
 API  API  API
      ↓
 PostgreSQL
```

### LLM Reliability

Production processing should include:

* Rate limiting
* Retries
* Exponential backoff
* Failed-job handling
* Idempotency
* Cost monitoring
* Model/version tracking

---

# 18. Proposed Production Architecture

```text
                    ┌───────────────┐
                    │   Frontend    │
                    └───────┬───────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    FastAPI    │
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      ┌───────────────┐           ┌──────────────┐
      │  PostgreSQL   │           │  Job Queue   │
      └───────────────┘           └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │   Workers    │
                                  └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │     LLM      │
                                  └──────────────┘
```

Audio files should also move from local storage to object storage such as S3, Google Cloud Storage, or Azure Blob Storage.

---

# 19. Security Considerations

The current implementation is primarily a local assignment/prototype.

For production, the following should be added:

* Authentication and authorization
* HTTPS
* API validation
* File-type validation
* File-size limits
* Safe filename handling
* Protection against arbitrary file access
* Environment-based secret management
* Rate limiting
* Audit logging
* Database backups
* Audio security scanning

Sensitive credentials should never be committed to Git.

Local environment files such as:

```text
.env
```

are therefore ignored.

---

# 20. Git Development History

The implementation was developed incrementally.

Important commits include:

```text
f22ccc6  Initial project scaffold
b2198c1  Add data profiling and quality checks
939b3f1  Build SQLite merge pipeline with identity matching
a306c1f  Document source data quality issues
c2bb035  Build audio collection app with metadata extraction
2ecbae6  Add local API for n8n automation
c926067  Add n8n AI skill categorization workflow
217f018  Fix audio submission metadata API
a5cb46d  Add exported n8n workflow
e00414e  Ignore local audio test files
```

The development progression was:

```text
Project Scaffold
      ↓
Data Profiling
      ↓
Entity Matching
      ↓
Audio Application
      ↓
FastAPI
      ↓
n8n Automation
      ↓
API Fixes
      ↓
Workflow Export
      ↓
Repository Cleanup
```

---

# 21. Major Debugging Challenges

## FastAPI Import Issue

Running the API from inside the `pipeline` directory caused:

```text
ModuleNotFoundError: No module named 'pipeline'
```

The issue was resolved by running the API from the repository root:

```powershell
cd D:\consultbae-assignment
uv run uvicorn pipeline.api:app --reload --port 8000
```

---

## n8n Could Not Access Localhost

n8n Cloud could not directly access:

```text
http://127.0.0.1:8000
```

because `localhost` refers to the remote n8n environment rather than the developer machine.

Cloudflare Tunnel was therefore used:

```powershell
cloudflared tunnel --url http://localhost:8000
```

---

## Gemini Rate Limit

Repeated LLM executions resulted in:

```text
429 Too Many Requests
```

Testing was changed to process candidates incrementally using:

```text
/people/untagged?limit=1
```

---

## Audio API Schema Mismatch

The audio API initially expected fields that did not match the actual database schema, resulting in an internal server error.

The endpoint was corrected to use the actual stored fields:

```text
submission_id
person_id
name
phone
file_path
duration_seconds
sample_rate_khz
bitrate_kbps
loudness_db
created_at
```

The endpoint then returned the expected audio submission metadata successfully.

---

# 22. Testing Performed

The following components were tested:

### API Health

```powershell
curl.exe http://127.0.0.1:8000/health
```

Confirmed:

```text
status: ok
database: connected
people_count: 55
audio_submissions: 1
```

### Candidate Retrieval

```powershell
curl.exe "http://127.0.0.1:8000/people/untagged?limit=1"
```

Confirmed that untagged candidates could be retrieved.

### AI Classification

Confirmed that a candidate could be classified and updated with:

```text
automation-heavy
```

### Audio Submissions

```powershell
curl.exe http://127.0.0.1:8000/audio/submissions
```

Confirmed successful retrieval of audio metadata.

### Audio File Endpoint

```text
/audio/file/{filename}
```

Confirmed that uploaded audio files could be accessed through the API using sanitized filenames.

---

# 23. Current Implementation Status

| Component                           | Status     |
| ----------------------------------- | ---------- |
| Source data profiling               | Complete   |
| Data quality analysis               | Complete   |
| Entity matching                     | Complete   |
| SQLite database                     | Complete   |
| FastAPI API                         | Complete   |
| Candidate retrieval API             | Complete   |
| Candidate categorization update API | Complete   |
| n8n workflow                        | Complete   |
| Gemini classification               | Tested     |
| Cloudflare Tunnel                   | Tested     |
| Audio submission application        | Complete   |
| Audio metadata extraction           | Complete   |
| Audio submission API                | Complete   |
| Audio file serving                  | Complete   |
| Data quality report                 | Complete   |
| Git history                         | Complete   |
| n8n workflow export                 | Complete   |
| Documentation                       | Complete   |
| Production scaling design           | Documented |

---

# 24. Limitations

The main limitations of the current prototype are:

1. SQLite is used instead of PostgreSQL.
2. Audio files are stored locally.
3. Cloudflare Quick Tunnel is temporary.
4. Gemini is subject to provider rate limits.
5. Authentication is not implemented.
6. The n8n workflow is designed for assignment-scale processing.
7. Production-grade queueing and monitoring are not included.

These limitations are intentional for the scope of the assignment and are addressed in the proposed production architecture.

---

# 25. Future Improvements

### Data Pipeline

* Automated validation tests
* Matching confidence scores
* Manual review for ambiguous matches
* Field-level source provenance

### AI Classification

* Confidence scoring
* Model/version tracking
* Retry and backoff handling
* Classification evaluation metrics
* Cost and latency monitoring

### API

* Authentication
* Pagination
* API versioning
* Automated tests
* Rate limiting

### Audio

* Stronger validation
* Object storage
* Background processing
* Audio quality analysis
* Optional transcription

### Infrastructure

* PostgreSQL
* Redis/job queue
* Docker
* CI/CD
* Cloud deployment
* Monitoring and centralized logging

---

# 26. Demo Flow

A concise demonstration can follow this order:

```text
1. Show repository structure
        ↓
2. Show source datasets
        ↓
3. Explain entity matching
        ↓
4. Show SQLite database
        ↓
5. Start FastAPI
        ↓
6. Test /health
        ↓
7. Retrieve an untagged candidate
        ↓
8. Show n8n workflow
        ↓
9. Run AI classification
        ↓
10. Show category
        ↓
11. Verify database update
        ↓
12. Demonstrate audio submission
        ↓
13. Show extracted metadata
        ↓
14. Show Git history
        ↓
15. Explain 5,000-worker scaling approach
```

---

# 27. Conclusion

This project implements the ConsultBae assignment as a connected end-to-end system rather than as separate scripts.

The primary pipeline is:

```text
Source Data
    ↓
Profiling & Cleaning
    ↓
Entity Matching
    ↓
SQLite Database
    ↓
FastAPI
    ↓
n8n
    ↓
Gemini AI
    ↓
Skill Category
    ↓
Database Update
```

The audio pipeline works alongside it:

```text
Candidate
    ↓
Audio Submission
    ↓
Metadata Extraction
    ↓
SQLite
    ↓
FastAPI
```

The repository includes the source datasets, processing scripts, database, API, n8n workflow, audio application, data-quality report, Git history, testing information, debugging notes, and production-scaling design.

Overall, the implementation demonstrates the complete workflow from **messy source data to a canonical database, API-driven automation, AI classification, and audio processing**, while also documenting how the prototype could be evolved into a scalable production system.

---