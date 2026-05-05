# GEMINI.md - Content Fabric (CFF)

This file provides instructional context for AI agents interacting with the **Content Fabric (CFF)** codebase.

---

## 🚀 Project Overview

**Content Fabric (CFF)** is a production-grade automated platform for full-cycle video content management. It handles everything from content ingestion and AI-driven processing (voice conversion, transcription, highlighting) to scheduled publishing on platforms like YouTube, TikTok, and Instagram.

### Core Tech Stack
- **Backend:** Python 3.10+, FastAPI
- **Database:** MySQL (InnoDB) with SQLAlchemy Core/ORM
- **Queuing:** Redis with RQ (Redis Queue)
- **AI/ML:** OpenAI (GPT-4, Whisper), RVC (Voice Conversion), Silero TTS
- **Video/Audio:** FFmpeg, FFprobe
- **Frontend:** Server-Side Rendering (SSR) with Jinja2, Vanilla CSS/JS
- **Infrastructure:** Ubuntu 22.04, systemd, Nginx

---

## 📁 Directory Structure

- `prod/`: Main application source code.
  - `app/`: FastAPI application (API endpoints, SSR views, Jinja2 templates).
  - `scheduler/`: Task scheduling logic (polls DB and enqueues to Redis).
  - `workers/`: Background worker entry points (publishing, voice, ingestion, etc.).
  - `shared/`: Core shared libraries, repositories, and business logic.
    - `db/`: Models and repositories.
    - `ingestion/`: DLE, Sora, and other content source scrapers.
    - `voice/`: Audio processing, RVC, and TTS logic.
    - `youtube/`: YouTube API clients and re-authentication logic.
    - `queue/`: Redis/RQ configuration and payload definitions.
- `database/`: SQL DDL, migrations, and schema indexes.
- `docs/`: Comprehensive architecture guides and migration reports.
- `scripts/`: Utility scripts for database comparisons and management.
- `yii-audit/`: Artifacts and logs from the legacy PHP application audit.

---

## 🛠 Building and Running

### Prerequisites
- Python 3.10+
- MySQL Server
- Redis Server
- FFmpeg

### Installation
1.  Navigate to the `prod/` directory.
2.  Create a virtual environment: `python -m venv venv`
3.  Install dependencies: `pip install -r requirements.txt`
4.  Configure environment variables in `prod/.env/` (see `.env.prod.example`).

### Running the System
- **API Server:** `python main.py`
- **Scheduler:** `python -m scheduler.run`
- **Workers:** `python -m workers.<worker_name>` (e.g., `voice_worker`, `publishing_worker`, `dle_ingestion_worker`)
- **Testing:** `pytest tests/`

---

## 🧪 Testing and Quality Assurance

- **Testing Framework:** `pytest`
- **Coverage:** Unit, integration, and Web UI tests (via `FastAPI TestClient`).
- **Production Verification:** Always run `pytest tests/` within the server's virtual environment before finalizing significant changes.
- **Data Integrity:** Use `scripts/compare_yii_cff_data.py` to verify data consistency during and after migrations.

---

## 📜 Development Conventions

1.  **Observability:** Implement structured logging with explicit module prefixes (e.g., `[DLE PIPELINE]`, `[SCHEDULER]`). Every significant state change must be logged.
2.  **Configuration:** Use `pydantic-settings` for managing configuration. All secrets must reside in `.env` files and never be hardcoded.
3.  **Database Access:** Use the Repository pattern located in `prod/shared/db/repositories/` to centralize DB operations.
4.  **UI Principles:** Prefer Jinja2 SSR for administrative tools. Keep JS/CSS simple and performant.
5.  **Security:** Protect credentials for external DLE databases and YouTube OAuth tokens. Use the `ensure_fresh_credentials` utility for YouTube API calls.

---

## 🔄 Legacy Migration (Yii2 Decommission)

The project is currently finalizing a "Big Bang" migration to replace a legacy Yii2 (PHP) application.
- **Migration Script:** `database/DDL/migrations/004_yii_decommission.sql`
- **Integration Branch:** `feat/yii-integration`
- **Migration Report:** `docs/MIGRATION_REPORT.md` (Refer here for the cutover plan).
