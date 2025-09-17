# Social Media Auto-Poster

A comprehensive Python tool for automatically posting content to Instagram, TikTok, and YouTube Shorts with support for scheduling, content optimization, and multi-account management.

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

3. **Setup configuration**:
   ```bash
   python main.py setup
   ```

4. **Configure your accounts**:
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
3. Create OAuth 2.0 credentials
4. Download the credentials JSON file

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
├── requirements.txt          # Python dependencies
├── main.py                   # CLI interface
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
- 10,000 quota units per day
- Video upload costs 1,600 units

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

