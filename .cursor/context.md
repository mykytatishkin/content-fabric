# Content Fabric - Project Context

## 🎯 What is this project?

Content Fabric is a comprehensive automation platform for social media content management with advanced voice processing capabilities.

### Core Capabilities:
1. **Social Media Automation** - Auto-post to Instagram, TikTok, YouTube Shorts
2. **Voice Processing** - Advanced voice changing with parallel processing
3. **Task Management** - MySQL-based scheduling and task execution
4. **Multi-Account** - Manage unlimited accounts per platform
5. **Content Processing** - Video optimization for each platform

## 🏗️ Architecture Overview

### Three-Layer Architecture

```
┌─────────────────────────────────────────┐
│         Application Layer (app/)         │
│  ├─ main.py          (entry point)      │
│  ├─ auto_poster.py   (coordinator)      │
│  ├─ scheduler.py     (scheduling)       │
│  └─ task_worker.py   (background tasks) │
└─────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────┐
│           Core Layer (core/)             │
│  ├─ api_clients/   (platform APIs)      │
│  ├─ auth/          (OAuth & tokens)     │
│  ├─ database/      (data persistence)   │
│  └─ utils/         (voice, processing)  │
└─────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────┐
│      Infrastructure Layer (scripts/)     │
│  ├─ task_manager.py    (CLI tasks)      │
│  ├─ youtube_manager.py (CLI YouTube)    │
│  └─ account_manager.py (CLI accounts)   │
└─────────────────────────────────────────┘
```

### Data Flow

#### Voice Processing Flow
```
Audio Input
    ↓
Duration Check → < 3min: Sequential
                 > 3min: Parallel (split into chunks)
    ↓
Background Music? → Yes: Separate vocals/instrumental
                    No: Direct processing
    ↓
Voice Conversion (RVC/Silero/SoVITS)
    ↓
Reassemble (if parallel)
    ↓
Mix with Background (if separated)
    ↓
Audio Output
```

#### Publishing Flow
```
Create Task (CLI/API)
    ↓
Save to MySQL Database
    ↓
Task Worker (background daemon)
    ↓
Scheduled Time? → Wait or Process
    ↓
Load Account Tokens
    ↓
Process Video (if needed)
    ↓
Upload to Platform (YouTube/Instagram/TikTok)
    ↓
Update Task Status
    ↓
Send Notification (Telegram/Email)
    ↓
[Optional] Auto-comment & Like
```

## 🔑 Key Components

### 1. Voice Changer System (`core/utils/voice_changer.py`)

**Purpose**: Transform voice in audio/video files

**Features**:
- Multiple methods: RVC (high quality), Silero (fast), SoVITS (balanced)
- Presets: male_to_female, female_to_male, child_voice, elderly, robot
- Parallel processing for 2-4x speed improvement
- Background music preservation
- Russian stress marking for proper pronunciation

**Usage**:
```python
changer = VoiceChanger(enable_parallel=True)
result = changer.process_file(
    'input.mp3', 'output.mp3',
    method='silero',
    voice_model='kseniya',
    preserve_background=True
)
changer.cleanup()
```

### 2. Parallel Voice Processor (`core/utils/parallel_voice_processor.py`)

**Purpose**: Speed up voice processing via parallelization

**How it works**:
1. Split audio into N-minute chunks (default: 5)
2. Process chunks in parallel using ThreadPoolExecutor
3. Reassemble with crossfade to eliminate clicks
4. Support for background music preservation

**Benefits**:
- 2-4x faster for long audio files
- Automatic mode selection based on duration
- Configurable chunk size and worker count

### 3. Task Management System (`core/database/mysql_db.py`)

**Purpose**: Database-driven scheduled publishing

**Features**:
- MySQL storage for tasks
- Cron-like scheduling
- Status tracking (pending/processing/completed/failed)
- Automatic retry logic
- CLI for task management

**Task Structure**:
```python
@dataclass
class Task:
    id: int
    account_name: str
    video_path: str
    title: str
    description: str
    keywords: str
    scheduled_time: datetime
    status: str
    retry_count: int
```

### 4. API Clients (`core/api_clients/`)

**Purpose**: Unified interface for platform APIs

**Base Client** (`base_client.py`):
- Rate limiting with exponential backoff
- Automatic retry logic
- Error handling and logging
- OAuth token management

**Platform Clients**:
- `youtube_client.py` - YouTube Data API v3
- `instagram_client.py` - Instagram Graph API  
- `tiktok_client.py` - TikTok Content Posting API
- `youtube_db_client.py` - YouTube with DB integration

**Common Pattern**:
```python
client = YouTubeClient(channel_name='MyChannel')
result = client.upload_video(
    video_path='video.mp4',
    title='Title',
    description='Description',
    keywords=['tag1', 'tag2']
)
```

### 5. OAuth & Token Management (`core/auth/`)

**Purpose**: Handle authentication for multiple accounts

**Components**:
- `oauth_manager.py` - OAuth 2.0 flow management
- `token_manager.py` - Token storage and refresh

**Flow**:
1. Generate auth URL
2. User authorizes in browser
3. Exchange code for tokens
4. Store in database
5. Auto-refresh before expiry

### 6. Database Layer (`core/database/`)

**SQLite** (`sqlite_db.py`):
- YouTube channels
- Channel metadata
- Legacy token storage

**MySQL** (`mysql_db.py`):
- Publishing tasks
- Task history
- Upload tracking
- Comments/likes tracking

**Migrations** (`migrations/`):
- Version-controlled schema changes
- Migration scripts with rollback support

## 📊 Current State & Recent Changes

### ✅ Recently Completed (Oct 2024)

1. **Parallel Voice Processing** 🚀
   - New `ParallelVoiceProcessor` class
   - 2-4x speed improvement
   - Automatic chunk splitting and reassembly
   - Crossfade between chunks

2. **Background Music Preservation** 🎵
   - Vocal/instrumental separation
   - Independent voice processing
   - Smart mixing with adjustable levels

3. **Task Management System** 📋
   - MySQL-based task storage
   - Background worker daemon
   - CLI for task management
   - Retry logic and error handling

4. **Upload ID Tracking** 📊
   - Track all uploads in DB
   - Video metadata storage
   - Upload history

### 🔄 Current Branch: `speed-up-voice-change`

**Untracked Files**:
- `core/utils/parallel_voice_processor.py` - NEW parallel processor
- `docs/parallel/` - NEW parallel processing docs
- `run_parallel_voice.py` - Test script for parallel processing
- `test_parallel_voice_processing.py` - Comprehensive tests
- `test_quick_parallel.py` - Quick test
- `test_simple_example.py` - Simple example
- `test_with_background.py` - Background preservation test

**Modified**:
- `core/utils/voice_changer.py` - Integrated parallel processing

### 🎯 Current Focus

**Voice Processing Optimization**:
- Parallel processing is implemented and tested
- Ready for production use
- Documentation complete

**Next Steps** (likely):
- Commit parallel processing changes
- Merge to main branch
- Clean up test files
- Production deployment

## 🗂️ File Organization

### Entry Points
```
run_*.py files - Direct script execution
├── run_voice_changer.py      # Voice changing CLI
├── run_parallel_voice.py     # Parallel processing test
├── run_task_manager.py       # Task management CLI
├── run_task_worker.py        # Start task worker
├── run_youtube_manager.py    # YouTube management CLI
└── run_setup_database.py     # Database setup
```

### Configuration
```
config/
├── config.yaml          # Main config (platforms, accounts, schedule)
├── mysql_config.yaml    # MySQL connection settings
├── mysql_schema.sql     # Database schema
└── env_template.txt     # Environment variables template
```

### Documentation Structure
```
docs/
├── guides/              # User guides
│   ├── TASK_MANAGEMENT.md
│   ├── YOUTUBE_SETUP.md
│   ├── RUSSIAN_STRESS_GUIDE.md
│   └── ...
├── parallel/            # Parallel processing docs
│   ├── PARALLEL_VOICE_PROCESSING.md
│   ├── IMPLEMENTATION_SUMMARY.md
│   └── PARALLEL_PROCESSING_README.md
├── setup/              # Setup guides
│   ├── QUICK_START.md
│   ├── MYSQL_SETUP_GUIDE.md
│   └── PLATFORM_SETUP_GUIDE.md
└── technical/          # Technical docs
    ├── TECHNICAL_DOCS.md
    └── MYSQL_MIGRATION.md
```

## 🔧 Development Workflow

### Testing Voice Processing
```bash
# Simple test
python test_simple_example.py

# Quick parallel test
python test_quick_parallel.py

# Full test with background
python test_with_background.py

# Comprehensive benchmark
python test_parallel_voice_processing.py --mode full
```

### Task Management
```bash
# Create task
python run_task_manager.py create \
    --account "Channel Name" \
    --video video.mp4 \
    --title "Title" \
    --schedule "2024-12-25 18:00:00"

# List tasks
python run_task_manager.py list --status pending

# Start worker
python run_task_worker.py
```

### YouTube Management
```bash
# List channels
python run_youtube_manager.py list

# Add channel
python run_youtube_manager.py add "Channel Name"

# Upload video
python run_youtube_manager.py upload \
    --channel "Channel Name" \
    --video video.mp4 \
    --title "Title"
```

## 🔍 Code Patterns

### Resource Management
```python
# ALWAYS use cleanup
changer = VoiceChanger()
try:
    result = changer.process_file(...)
finally:
    changer.cleanup()
```

### Error Handling
```python
# Catch specific exceptions
try:
    client.upload_video(...)
except QuotaExceededError:
    logger.error("Quota exceeded")
    # Reschedule for tomorrow
except RateLimitError as e:
    logger.warning(f"Rate limited: {e.retry_after}s")
    # Wait and retry
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Logging
```python
from core.utils.logger import get_logger

logger = get_logger(__name__)

logger.debug("Detailed info")      # Development
logger.info("Operation started")   # Normal flow
logger.warning("Low quota")        # Attention needed
logger.error("Failed to upload")   # Error occurred
logger.critical("DB connection lost")  # Critical failure
```

### Database Operations
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Always validate before DB ops
if not db.account_exists(account_name):
    raise ValueError(f"Account not found: {account_name}")

# Use transactions for multi-step
with db.transaction():
    task_id = db.create_task(...)
    db.create_upload_record(...)
```

## 🎓 Domain Knowledge

### Voice Processing
- **Pitch**: Frequency of voice (Hz) - higher = female/child
- **Formant**: Resonance characteristics - defines voice character
- **RVC**: Retrieval-based Voice Conversion - high quality, slower
- **Silero**: Neural TTS - fast, good quality, Russian support
- **SoVITS**: So-VITS-SVC - balanced quality/speed

### Social Media APIs
- **YouTube**: Quota-based (10k/day), upload costs 1,600 units
- **Instagram**: Rate limited ~200 calls/hour
- **TikTok**: Varies by endpoint, strict content policies
- **OAuth 2.0**: Authorization code flow with refresh tokens

### Audio Processing
- **Sample Rate**: 44.1kHz (standard), 48kHz (professional)
- **Bit Depth**: 16-bit (standard), 24-bit (professional)
- **Crossfade**: Smooth transition between audio segments
- **Vocal Separation**: MDX-Net models (UVR-MDX-NET-Inst_HQ_3)

## 📈 Performance Metrics

### Voice Processing Speed
- Sequential: ~30s per minute of audio
- Parallel (5min chunks): ~10-15s per minute of audio
- Speedup: 2-4x depending on file length and CPU cores

### API Quotas
- YouTube: 6 uploads/day (free tier)
- Instagram: ~200 posts/hour
- TikTok: ~100 posts/day

### Database Performance
- MySQL: 1000+ tasks/second insertion
- SQLite: 100+ channels without issues
- Task worker: Process 1 task every 5-10 seconds

## 🚨 Known Issues & Limitations

1. **Voice Processing**
   - Large files (>1 hour) may cause memory issues
   - Crossfade might be audible in very quiet sections
   - RVC quality depends on model (some artifacts possible)

2. **API Limitations**
   - YouTube quota restricts to ~6 uploads/day
   - Instagram requires Facebook app approval
   - TikTok API access is limited

3. **Database**
   - SQLite legacy system (migrating to MySQL)
   - No database encryption yet (planned)
   - Manual cleanup of old tasks needed

## 💡 Quick Tips

### For Voice Processing
- Use Silero for speed, RVC for quality
- Enable parallel for files > 3 minutes
- Always preserve background if music exists
- Clean up temp files to save disk space

### For API Clients
- Check quota before bulk operations
- Handle rate limits gracefully
- Use refresh tokens for long-running tasks
- Log all API calls for debugging

### For Task Management
- Validate all inputs before creating tasks
- Schedule tasks at least 5 minutes in future
- Monitor worker logs for errors
- Clean up completed tasks periodically

---

**Last Updated**: 2025-10-13  
**Current Phase**: Voice Processing Optimization  
**Next Milestone**: Production Deployment of Parallel Processing

