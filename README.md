# Social Media Auto-Poster

A comprehensive Python tool for automatically posting content to Instagram, TikTok, and YouTube Shorts with support for scheduling, content optimization, and multi-account management.

## 🆕 Enhanced Multi-Account Features

- ✅ **Unlimited Accounts** - Support for unlimited accounts per platform
- ✅ **Automated OAuth** - Automatic token generation and refresh
- ✅ **Smart Validation** - Real-time account and token validation
- ✅ **CLI Management** - Powerful command-line tools for account management
- ✅ **Secure Storage** - Protected token storage with automatic encryption
- ✅ **YouTube Shorts Support** - Full automation for YouTube Shorts posting
- ✅ **Channel Management** - Easy addition and management of YouTube channels
- ✅ **Database Integration** - SQLite database for managing multiple YouTube channels
- ✅ **Single OAuth Setup** - One credentials.json file for all channels
- ✅ **Token Management** - Automatic token refresh and expiration handling

## 🎯 Task Management System (NEW!)

**Автоматична система обробки задач з бази даних MySQL**

- 📋 **Database-Driven Tasks** - Задачі зберігаються в MySQL і автоматично виконуються
- ⏰ **Scheduled Posting** - Публікація за розкладом (дата і час)
- 🔄 **Auto-Retry** - Автоматичні повтори при помилках
- 🛠️ **CLI Management** - Повний CLI для управління задачами
- 📊 **Status Tracking** - Відстеження статусу кожної задачі
- 🎬 **Video Publishing** - Публікація відео з назвою, описом, хештегами
- 💬 **Post Comments** - Автоматичне додавання коментарів після публікації
- 📈 **Statistics** - Детальна статистика виконання

### Quick Start

```bash
# Створити задачу
python3 run_task_manager.py create \
    --account "Channel Name" \
    --video "/path/to/video.mp4" \
    --title "Video Title" \
    --description "Description" \
    --keywords "tag1,tag2,tag3" \
    --schedule "2024-12-25 18:00:00"

# Переглянути задачі
python3 run_task_manager.py list --status pending

# Статистика
python3 run_task_manager.py stats
```

📖 **Документація**: [Task Management Guide](docs/guides/TASK_MANAGEMENT.md)  
⚡ **Quick Start**: [Task Quick Start](docs/guides/TASK_QUICK_START.md)

## 🎙️ Voice Changer (NEW!)

**Механізм зміни голосу у відео та аудіо файлах**

- 🎯 **Повна зміна голосу** - Чоловічий ↔ Жіночий, Дорослий → Дитячий
- 🎬 **Відео та аудіо** - Підтримка MP4, AVI, MOV, WAV, MP3 та інших
- 🔊 **Висока якість** - Використання Praat для професійної обробки
- 📦 **Пакетна обробка** - Обробка множини файлів одночасно
- ⚙️ **Гнучкі налаштування** - Власні параметри pitch і formant
- 🔌 **Інтеграція** - Працює standalone або через task system

### Quick Start

```bash
# Конвертувати чоловічий голос на жіночий
python3 run_voice_changer.py input.mp4 output.mp4 --type male_to_female

# Пакетна обробка
python3 run_voice_changer.py --batch videos/ output/ --type female_to_male

# Список пресетів
python3 run_voice_changer.py --list-presets
```

### Доступні пресети
- `male_to_female` - Чоловічий → Жіночий
- `female_to_male` - Жіночий → Чоловічий
- `male_to_child` - Чоловічий → Дитячий
- `female_to_child` - Жіночий → Дитячий

📖 **Документація**: [Voice Changer Guide](docs/VOICE_CHANGER.md)  
🧪 **Тестування**: `python3 tests/test_voice_changer.py`  
💡 **Приклади**: `python3 examples/voice_changer_example.py`

## Features

- **Multi-Platform Support**: Post to Instagram Reels, TikTok, and YouTube Shorts
- **Content Optimization**: Automatic video processing for each platform's requirements
- **Smart Scheduling**: Support for specific times and random posting schedules
- **Multi-Account Management**: Manage 10+ accounts per platform
- **Comprehensive Logging**: Detailed logging with colored console output
- **Notification System**: Telegram and email notifications for success/failure
- **CLI Interface**: Easy-to-use command-line interface
- **Retry Logic**: Automatic retry for failed posts
- **Rate Limiting**: Built-in rate limit handling

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd content-fabric
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg** (required for Voice Changer):
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

4. **Setup configuration**:
   ```bash
   python main.py setup
   ```

5. **Configure your accounts**:
   - Copy `config.env.example` to `.env` and fill in your API credentials
   - Edit `config.yaml` to configure your accounts and posting schedule

## Configuration

### API Credentials Setup

#### Instagram
1. Create a Facebook Developer account
2. Create a new app and get your App ID and App Secret
3. Set up Instagram Basic Display API
4. Generate access tokens for your accounts

#### TikTok
1. Apply for TikTok for Developers access
2. Create an app and get your Client Key and Client Secret
3. Generate access tokens for your accounts

#### YouTube
1. Create a Google Cloud Console project
2. Enable YouTube Data API v3
3. Set up OAuth consent screen with required scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
4. Create OAuth 2.0 Desktop application credentials
5. Download the credentials JSON file as `credentials.json`
6. Add your Google account to Test Users

### Configuration Files

#### config.yaml
Main configuration file with:
- Platform settings and requirements
- Account information
- Posting schedules (specific times and random ranges)
- Content processing settings
- Notification preferences

#### .env
Environment variables for API credentials:
- Instagram API keys
- TikTok API keys
- YouTube API keys
- Notification settings (Telegram, Email)

## Usage

### Basic Commands

#### Post Immediately
```bash
python main.py post --content video.mp4 --caption "Check this out!" --platforms "instagram,tiktok,youtube"
```

#### Schedule Posts
```bash
# Schedule with random timing
python main.py schedule --content video.mp4 --caption "Coming soon!" --platforms "instagram,tiktok"

# Schedule for specific time
python main.py schedule --content video.mp4 --caption "Live now!" --platforms "instagram,tiktok,youtube" --time "2024-01-15T18:00:00"
```

#### Start Scheduler Daemon
```bash
python main.py start-scheduler
```

#### List Scheduled Posts
```bash
python main.py list-scheduled
```

#### Cancel a Post
```bash
python main.py cancel --post-id "instagram_account1_1705123456"
```

### Management Commands

#### Validate Accounts
```bash
python main.py validate-accounts
```

#### Test Notifications
```bash
python main.py test-notifications
```

#### Check System Status
```bash
python main.py status
```

#### View Statistics
```bash
python main.py stats
```

## 🆕 Multi-Account Management

### Account Manager CLI

The new `account_manager.py` provides powerful tools for managing multiple accounts:

#### Check Account Status
```bash
# Check all accounts
python account_manager.py status

# Check specific platform
python account_manager.py status --platform instagram

# JSON output
python account_manager.py status --json
```

#### Authorize Accounts
```bash
# Authorize all accounts automatically
python account_manager.py authorize --all

# Authorize specific platform
python account_manager.py authorize --platform instagram --all

# Authorize specific account
python account_manager.py authorize --platform instagram --account main_account

# Manual authorization (no auto-browser)
python account_manager.py authorize --platform instagram --account main_account --no-browser
```

#### Token Management
```bash
# Refresh all tokens
python account_manager.py refresh

# Refresh specific platform
python account_manager.py refresh --platform youtube

# Get authorization URL for manual setup
python account_manager.py auth-url instagram main_account

# Add token manually
python account_manager.py add-token instagram main_account "your_access_token" --refresh-token "refresh_token" --expires-in 3600

# Remove token
python account_manager.py remove-token instagram main_account

# Get token info
python account_manager.py token-info instagram main_account
```

#### Account Validation
```bash
# Validate all accounts
python account_manager.py validate

# Validate specific platform
python account_manager.py validate --platform tiktok --json
```

### Interactive Management
```bash
# Launch interactive multi-account manager
python example_multiple_accounts.py
```

This provides a user-friendly interface for:
- 📊 Account status monitoring
- 🔐 Account authorization
- 📤 Content publishing
- ⏰ Post scheduling
- 🛠️ Token management

## 🆕 YouTube Database Integration

### 🗄️ Database-Powered Channel Management
The new YouTube Database Integration provides a powerful, scalable solution for managing multiple YouTube channels:

```bash
# Migrate existing channels to database
python migrate_to_db.py

# Manage channels through database
python youtube_db_manager.py list
python youtube_db_manager.py add "ChannelName" --channel-id "UC123456789" --client-id "ID" --client-secret "SECRET"

# Check token status
python youtube_db_manager.py check-tokens

# Publish to multiple channels simultaneously
python main.py post --platforms youtube --accounts "Teasera,Andrew Garle"
```

### 🎯 Key Benefits
- ✅ **Single OAuth Setup** - One `credentials.json` file for all channels
- ✅ **Database Storage** - Tokens stored securely in SQLite database
- ✅ **Automatic Token Refresh** - No manual token management needed
- ✅ **Scalable Architecture** - Easy to add unlimited channels
- ✅ **CLI Management** - Powerful command-line tools
- ✅ **Migration Support** - Easy migration from config.yaml

### 📋 Quick Setup
1. **Create OAuth Client** in Google Cloud Console (Desktop application)
2. **Download credentials.json** to project root
3. **Migrate channels**: `python migrate_to_db.py`
4. **Update .env** with client credentials
5. **Test**: `python youtube_db_manager.py list`

### YouTube Shorts Features
- ✅ **Automatic Shorts Detection** - Detects 9:16 aspect ratio videos
- ✅ **Optimized Metadata** - Auto-adds #Shorts hashtag and category
- ✅ **Resumable Upload** - Handles large video files with retry logic
- ✅ **Quota Management** - Tracks YouTube API quota usage
- ✅ **Multiple Channels** - Support for unlimited YouTube channels
- ✅ **Database Integration** - Centralized channel and token management

## Content Requirements

### Video Specifications
- **Format**: MP4, MOV
- **Aspect Ratio**: 9:16 (vertical)
- **Duration**: 
  - Instagram Reels: 15-90 seconds
  - TikTok: 15-180 seconds
  - YouTube Shorts: 15-60 seconds
- **Resolution**: 1080x1920 (recommended)

### Content Processing
The system automatically:
- Optimizes video duration for each platform
- Adjusts aspect ratio to 9:16
- Resizes to recommended resolution
- Adds captions (optional)
- Adds watermarks (optional)

## Scheduling

### Specific Times
Configure specific posting times in `config.yaml`:
```yaml
schedule:
  specific_times:
    - "09:00"
    - "12:00"
    - "15:00"
    - "18:00"
    - "21:00"
```

### Random Time Ranges
Configure random posting windows:
```yaml
schedule:
  random_ranges:
    - start: "08:00"
      end: "10:00"
    - start: "14:00"
      end: "16:00"
    - start: "19:00"
      end: "21:00"
```

### Posting Days
Specify which days to post:
```yaml
schedule:
  posting_days: [0, 1, 2, 3, 4, 5, 6]  # 0=Monday, 6=Sunday
```

## Notifications

### Telegram
1. Create a bot with @BotFather
2. Get your bot token
3. Get your chat ID
4. Configure in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```

### Email
Configure SMTP settings in `.env`:
```
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

## File Structure

```
content-fabric/
├── src/
│   ├── __init__.py
│   ├── auto_poster.py          # Main coordinator
│   ├── logger.py               # Logging system
│   ├── content_processor.py    # Content optimization
│   ├── scheduler.py            # Posting scheduler
│   ├── notifications.py        # Notification system
│   └── api_clients/
│       ├── __init__.py
│       ├── base_client.py      # Base API client
│       ├── instagram_client.py # Instagram API
│       ├── tiktok_client.py    # TikTok API
│       └── youtube_client.py   # YouTube API
├── content/
│   ├── videos/                 # Input videos
│   ├── descriptions/           # Caption files
│   ├── thumbnails/            # Thumbnail images
│   └── processed/             # Processed videos
├── logs/                      # Log files
├── config.yaml               # Main configuration
├── config.env.example        # Environment variables template
├── credentials.json          # YouTube OAuth credentials
├── youtube_token.json        # YouTube access tokens
├── requirements.txt          # Python dependencies
├── main.py                   # CLI interface
├── account_manager.py        # Multi-account management
├── add_youtube_channel.py    # YouTube channel management
└── README.md                 # This file
```

## API Rate Limits

### Instagram
- ~200 API calls per hour
- Built-in rate limit handling

### TikTok
- Varies by endpoint
- Automatic retry with exponential backoff

### YouTube
- 10,000 quota units per day (free tier)
- Video upload costs 1,600 units (~6 uploads per day)
- Automatic quota tracking and management
- Built-in retry logic for quota exceeded errors

## Error Handling

The system includes comprehensive error handling:
- Automatic retry for failed posts
- Rate limit detection and handling
- Detailed error logging
- Notification alerts for failures

## Security Considerations

- Store API credentials in environment variables
- Use app-specific passwords for email
- Regularly rotate access tokens
- Monitor API usage and quotas

## Troubleshooting

### Common Issues

1. **API Authentication Errors**
   - Verify API credentials in `.env`
   - Check token expiration
   - Ensure proper API permissions

2. **Content Processing Failures**
   - Verify video file format and size
   - Check available disk space
   - Ensure proper file permissions

3. **Scheduling Issues**
   - Verify timezone configuration
   - Check posting day settings
   - Ensure scheduler is running

4. **Notification Problems**
   - Test notification channels
   - Verify credentials
   - Check network connectivity

### Logs
Check log files in the `logs/` directory for detailed error information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Check the troubleshooting section
- Review log files for error details
- Create an issue on GitHub

## Disclaimer

This tool is for educational and legitimate business purposes only. Users are responsible for:
- Complying with platform terms of service
- Respecting API rate limits
- Following content guidelines
- Managing account security

Always review and comply with each platform's terms of service and API usage policies.

