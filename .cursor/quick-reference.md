# Quick Reference - Content Fabric

## 🚀 Most Common Commands

### Voice Processing
```bash
# Basic voice change (auto mode)
python run_voice_changer.py input.mp3 output.mp3 --type male_to_female

# With background preservation
python run_voice_changer.py input.mp3 output.mp3 \
    --type male_to_female \
    --preserve-background

# Force parallel processing
python run_voice_changer.py input.mp3 output.mp3 \
    --type male_to_female \
    --parallel

# Custom voice model (Silero)
python run_voice_changer.py input.mp3 output.mp3 \
    --method silero \
    --voice kseniya

# Batch processing
python run_voice_changer.py \
    --batch input_folder/ output_folder/ \
    --type female_to_male
```

### Task Management
```bash
# Create task
python run_task_manager.py create \
    --account "Channel Name" \
    --video /path/to/video.mp4 \
    --title "Video Title" \
    --description "Video description" \
    --keywords "tag1,tag2,tag3" \
    --schedule "2025-12-25 18:00:00"

# List tasks
python run_task_manager.py list
python run_task_manager.py list --status pending
python run_task_manager.py list --account "Channel Name"

# Task statistics
python run_task_manager.py stats

# Delete task
python run_task_manager.py delete --task-id 123

# Start task worker
python run_task_worker.py
```

### YouTube Management
```bash
# List channels
python run_youtube_manager.py list

# Add new channel
python run_youtube_manager.py add "Channel Name"

# Upload video
python run_youtube_manager.py upload \
    --channel "Channel Name" \
    --video video.mp4 \
    --title "Title" \
    --description "Description" \
    --keywords "tag1,tag2,tag3"

# Check tokens
python run_youtube_manager.py check-tokens
```

### Database Operations
```bash
# Setup database
python run_setup_database.py

# Run migration (upload ID tracking)
python run_migration_upload_id.py
```

### Testing
```bash
# Voice processing tests
python test_simple_example.py
python test_quick_parallel.py
python test_with_background.py
python test_parallel_voice_processing.py --mode full

# Integration test
python run_test_integration.py
```

## 📝 Code Snippets

### Voice Processing in Python

#### Basic Usage
```python
from core.utils.voice_changer import VoiceChanger

# Initialize
changer = VoiceChanger()

# Process file
result = changer.process_file(
    input_file='input.mp3',
    output_file='output.mp3',
    method='silero',
    voice_model='kseniya'
)

# Always cleanup
changer.cleanup()

print(f"Success: {result['success']}")
print(f"Output: {result['file']}")
```

#### With Background Preservation
```python
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger(enable_parallel=True)

result = changer.process_file(
    input_file='audio_with_music.mp3',
    output_file='output.mp3',
    method='silero',
    voice_model='kseniya',
    preserve_background=True,
    vocals_gain=2.0,      # Boost vocals by 2dB
    background_gain=-3.0  # Lower background by 3dB
)

changer.cleanup()
```

#### Parallel Processing (Manual)
```python
from core.utils.parallel_voice_processor import ParallelVoiceProcessor
from core.utils.silero_voice_changer import SileroVoiceChanger

# Create processor
processor = ParallelVoiceProcessor(
    chunk_duration_minutes=3,
    max_workers=8
)

# Create voice changer
silero = SileroVoiceChanger()

# Process function
def process_chunk(chunk_path, output_path):
    return silero.change_voice(
        chunk_path,
        output_path,
        voice_model='kseniya'
    )

# Process with background
result_path = processor.process_with_background(
    input_file='long_audio.mp3',
    output_file='output.mp3',
    processor_func=process_chunk
)

print(f"Processed: {result_path}")
```

### Task Management

#### Create Task Programmatically
```python
from datetime import datetime, timedelta
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Schedule for tomorrow at 6 PM
schedule_time = datetime.now() + timedelta(days=1)
schedule_time = schedule_time.replace(hour=18, minute=0, second=0)

task_id = db.create_task(
    account_name='My Channel',
    video_path='/path/to/video.mp4',
    title='Amazing Video',
    description='Check out this video!',
    keywords='viral,trending,shorts',
    scheduled_time=schedule_time
)

print(f"Task created: {task_id}")
```

#### Get Pending Tasks
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Get all pending tasks
pending_tasks = db.get_tasks_by_status('pending')

for task in pending_tasks:
    print(f"Task {task.id}: {task.title}")
    print(f"  Scheduled: {task.scheduled_time}")
    print(f"  Account: {task.account_name}")
```

#### Update Task Status
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Update to completed
db.update_task_status(
    task_id=123,
    status='completed'
)

# Or with error message
db.update_task_status(
    task_id=124,
    status='failed',
    error_message='Quota exceeded'
)
```

### YouTube API Operations

#### Upload Video
```python
from core.api_clients.youtube_client import YouTubeClient

client = YouTubeClient(channel_name='My Channel')

result = client.upload_video(
    video_path='video.mp4',
    title='My Video Title',
    description='Video description with #shorts',
    keywords=['shorts', 'viral', 'trending'],
    privacy_status='public'
)

print(f"Video ID: {result['video_id']}")
print(f"URL: {result['url']}")
```

#### Auto-comment and Like
```python
from core.api_clients.youtube_client import YouTubeClient

client = YouTubeClient(channel_name='My Channel')

# Upload video
result = client.upload_video(...)
video_id = result['video_id']

# Add comment
client.add_comment(
    video_id=video_id,
    text='First! 🔥'
)

# Like video
client.like_video(video_id=video_id)
```

### Database Operations

#### YouTube Channels (SQLite)
```python
from core.database.sqlite_db import YouTubeDatabase

db = YouTubeDatabase()

# Add channel
db.add_channel(
    name='My Channel',
    channel_id='UC123456789',
    client_id='your_client_id',
    client_secret='your_client_secret'
)

# Get channel
channel = db.get_channel('My Channel')
print(f"Channel ID: {channel.channel_id}")

# Update tokens
db.update_tokens(
    channel_name='My Channel',
    access_token='new_access_token',
    refresh_token='new_refresh_token',
    expires_at=datetime.now() + timedelta(hours=1)
)

# List all channels
channels = db.get_all_channels()
for ch in channels:
    print(f"{ch.name}: {ch.channel_id}")
```

#### Tasks (MySQL)
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Create account
db.create_account(
    name='My Channel',
    channel_id='UC123456789',
    client_id='client_id',
    client_secret='client_secret'
)

# Create task
task_id = db.create_task(...)

# Get task
task = db.get_task(task_id)
print(f"Status: {task.status}")

# Track upload
db.create_upload_record(
    task_id=task_id,
    video_id='dQw4w9WgXcQ',
    upload_id='upload_123',
    platform='youtube',
    account_name='My Channel',
    video_url='https://youtube.com/watch?v=dQw4w9WgXcQ'
)
```

### OAuth & Token Management

#### Get Authorization URL
```python
from core.auth.oauth_manager import OAuthManager

oauth = OAuthManager()

auth_url = oauth.get_authorization_url(
    platform='youtube',
    account_name='My Channel'
)

print(f"Visit: {auth_url}")
```

#### Exchange Code for Token
```python
from core.auth.oauth_manager import OAuthManager

oauth = OAuthManager()

tokens = oauth.exchange_code_for_token(
    platform='youtube',
    code='authorization_code_from_redirect',
    account_name='My Channel'
)

print(f"Access Token: {tokens['access_token']}")
print(f"Expires in: {tokens['expires_in']} seconds")
```

#### Auto-refresh Token
```python
from core.auth.token_manager import TokenManager

token_mgr = TokenManager()

# Get token (auto-refreshes if expired)
token = token_mgr.get_valid_token(
    platform='youtube',
    account_name='My Channel'
)

print(f"Token: {token.access_token}")
print(f"Expires at: {token.expires_at}")
```

### Content Processing

#### Optimize Video
```python
from core.utils.content_processor import ContentProcessor

processor = ContentProcessor()

# Optimize for YouTube Shorts
result = processor.process_video(
    input_path='input.mp4',
    output_path='output.mp4',
    platform='youtube',
    target_duration=60,
    target_aspect_ratio='9:16'
)

print(f"Duration: {result['duration']}s")
print(f"Resolution: {result['resolution']}")
```

### Logging

#### Setup Logger
```python
from core.utils.logger import get_logger

logger = get_logger(__name__)

# Different levels
logger.debug("Detailed debug info")
logger.info("Operation started")
logger.warning("Low quota warning")
logger.error("Upload failed")
logger.critical("Database connection lost")

# With variables
logger.info(f"Processing file: {filename}")
logger.error(f"Failed with error: {str(e)}")
```

### Notifications

#### Send Telegram Notification
```python
from core.utils.notifications import send_telegram_notification

send_telegram_notification(
    title="Upload Successful",
    message="Video uploaded to YouTube",
    success=True
)
```

#### Send Email
```python
from core.utils.notifications import send_email_notification

send_email_notification(
    subject="Upload Failed",
    body="Failed to upload video: Quota exceeded",
    recipients=['admin@example.com']
)
```

## 🎯 Common Patterns

### Pattern 1: Voice Change with Error Handling
```python
from core.utils.voice_changer import VoiceChanger
from core.utils.logger import get_logger

logger = get_logger(__name__)

def safe_voice_change(input_file, output_file):
    changer = VoiceChanger(enable_parallel=True)
    
    try:
        logger.info(f"Processing: {input_file}")
        
        result = changer.process_file(
            input_file=input_file,
            output_file=output_file,
            method='silero',
            voice_model='kseniya',
            preserve_background=True
        )
        
        logger.info(f"Success: {output_file}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to process: {e}")
        raise
    
    finally:
        changer.cleanup()
```

### Pattern 2: Task Worker Loop
```python
import time
from datetime import datetime
from core.database.mysql_db import YouTubeMySQLDatabase
from core.api_clients.youtube_client import YouTubeClient
from core.utils.logger import get_logger

logger = get_logger(__name__)

def task_worker():
    db = YouTubeMySQLDatabase()
    
    while True:
        try:
            # Get pending tasks
            tasks = db.get_tasks_by_status('pending')
            
            for task in tasks:
                # Check if time to execute
                if task.scheduled_time <= datetime.now():
                    logger.info(f"Processing task {task.id}")
                    
                    # Update status
                    db.update_task_status(task.id, 'processing')
                    
                    try:
                        # Upload video
                        client = YouTubeClient(task.account_name)
                        result = client.upload_video(
                            video_path=task.video_path,
                            title=task.title,
                            description=task.description,
                            keywords=task.keywords.split(',')
                        )
                        
                        # Mark completed
                        db.update_task_status(task.id, 'completed')
                        logger.info(f"Task {task.id} completed")
                        
                    except Exception as e:
                        logger.error(f"Task {task.id} failed: {e}")
                        
                        # Retry logic
                        if task.retry_count < 3:
                            db.update_task_status(task.id, 'pending')
                            db.increment_retry_count(task.id)
                        else:
                            db.update_task_status(task.id, 'failed')
            
            # Wait before next iteration
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(60)
```

### Pattern 3: Batch Processing
```python
from pathlib import Path
from core.utils.voice_changer import VoiceChanger

def batch_process_directory(input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    changer = VoiceChanger(enable_parallel=True)
    
    try:
        # Get all audio files
        audio_files = list(input_path.glob('*.mp3')) + \
                     list(input_path.glob('*.wav'))
        
        for audio_file in audio_files:
            output_file = output_path / audio_file.name
            
            print(f"Processing: {audio_file.name}")
            
            result = changer.process_file(
                input_file=str(audio_file),
                output_file=str(output_file),
                method='silero'
            )
            
            if result['success']:
                print(f"✓ {audio_file.name}")
            else:
                print(f"✗ {audio_file.name}")
    
    finally:
        changer.cleanup()
```

## 📊 Configuration Examples

### config.yaml
```yaml
platforms:
  youtube:
    enabled: true
    max_duration: 60
    min_duration: 15
    aspect_ratio: '9:16'

accounts:
  youtube:
    - name: My Channel
      channel_id: UC123456789
      client_id: ${YOUTUBE_CLIENT_ID}
      client_secret: ${YOUTUBE_CLIENT_SECRET}
      enabled: true

schedule:
  specific_times:
    - "09:00"
    - "18:00"
  posting_days: [0, 1, 2, 3, 4, 5, 6]
  timezone: UTC

notifications:
  telegram:
    enabled: true
  email:
    enabled: true
```

### .env
```bash
# YouTube OAuth
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=content_fabric
MYSQL_PASSWORD=secure_password
MYSQL_DATABASE=content_fabric
```

## 🔍 Troubleshooting Quick Fixes

### Voice processing is slow
```python
# Enable parallel processing
changer = VoiceChanger(
    enable_parallel=True,
    chunk_duration_minutes=3,
    max_workers=8
)
```

### Out of memory
```python
# Use larger chunks, fewer workers
changer = VoiceChanger(
    enable_parallel=True,
    chunk_duration_minutes=10,
    max_workers=2
)
```

### YouTube quota exceeded
```python
# Check quota before upload
from core.api_clients.youtube_client import YouTubeClient

client = YouTubeClient('My Channel')
quota = client.get_quota_usage()

if quota < 1600:
    print("Not enough quota")
else:
    client.upload_video(...)
```

### Token expired
```python
# Manually refresh token
from core.auth.token_manager import TokenManager

token_mgr = TokenManager()
new_token = token_mgr.refresh_token(
    platform='youtube',
    account_name='My Channel'
)
```

### Database connection failed
```bash
# Check MySQL status
systemctl status mysql

# Restart MySQL
systemctl restart mysql

# Test connection
python run_setup_database.py
```

## 📚 Useful Links

### Internal Documentation
- Full Rules: `.cursor/rules`
- Architecture: `.cursor/architecture.md`
- Context: `.cursor/context.md`
- Docs Index: `DOCS_INDEX.md`

### Key Guides
- Voice Changer: `docs/VOICE_CHANGER.md`
- Parallel Processing: `docs/parallel/PARALLEL_VOICE_PROCESSING.md`
- Task Management: `docs/guides/TASK_MANAGEMENT.md`
- YouTube Setup: `docs/guides/YOUTUBE_SETUP.md`

### External Resources
- YouTube API: https://developers.google.com/youtube/v3
- Instagram API: https://developers.facebook.com/docs/instagram-api
- Silero TTS: https://github.com/snakers4/silero-models

---

**Version**: 1.0  
**Last Updated**: 2025-10-13

