# 📺 YouTube Shorts Automation - Complete Setup Guide

## 🎯 Overview

This guide will walk you through setting up complete YouTube Shorts automation for your Content Fabric project. You'll be able to automatically post videos to multiple YouTube channels with scheduling, metadata optimization, and quota management.

## ✅ What You'll Get

- ✅ **Multiple YouTube Channels** - Support for unlimited channels
- ✅ **Automatic Shorts Detection** - Smart 9:16 aspect ratio handling
- ✅ **Optimized Metadata** - Auto #Shorts hashtags and categories
- ✅ **Resumable Uploads** - Handles large video files
- ✅ **Quota Management** - Tracks API usage and limits
- ✅ **Scheduling Support** - Post at specific times or random intervals
- ✅ **Error Handling** - Automatic retry and failure notifications

## 📋 Prerequisites

- Google account with YouTube channel
- Python 3.8+ installed
- Content Fabric project set up

## 🔧 Step 1: Google Cloud Console Setup

### 1.1 Create Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name: "Content Fabric YouTube Auto Poster"
4. Click "Create"

### 1.2 Enable YouTube Data API v3
1. Go to **APIs & Services** → **Library**
2. Search for "YouTube Data API v3"
3. Click "Enable"

### 1.3 Configure OAuth Consent Screen
1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type
3. Fill in required fields:
   - **App name**: "Content Fabric Auto Poster"
   - **User support email**: your email
   - **Developer contact**: your email
4. Click "Save and Continue"

### 1.4 Add Required Scopes
1. In OAuth consent screen, click **"Add or Remove Scopes"**
2. Add these scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
3. Click "Update"

### 1.5 Add Test Users
1. In OAuth consent screen, click **"Add Users"**
2. Add your Google email address
3. Add any other Google accounts you want to use
4. Click "Save"

### 1.6 Create OAuth 2.0 Credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. Choose **"Desktop application"**
4. Name: "YouTube Desktop Client"
5. Click "Create"
6. **Download the JSON file** and save as `credentials.json`

## 📁 Step 2: Project Configuration

### 2.1 Place Credentials File
```bash
# Copy credentials.json to your project root
cp ~/Downloads/credentials.json /path/to/content-fabric/
```

### 2.2 Update .env File
Add to your `.env` file:
```bash
YOUTUBE_MAIN_CLIENT_ID=your_client_id_from_credentials.json
YOUTUBE_MAIN_CLIENT_SECRET=your_client_secret_from_credentials.json
```

### 2.3 Enable YouTube in Config
Your `config.yaml` should have:
```yaml
platforms:
  youtube:
    enabled: true
    max_duration: 60
    min_duration: 15
    aspect_ratio: "9:16"
    file_formats: ["mp4", "mov"]

accounts:
  youtube:
    - name: "main_channel"
      channel_id: "your_channel_id"
      client_id: "${YOUTUBE_MAIN_CLIENT_ID}"
      client_secret: "${YOUTUBE_MAIN_CLIENT_SECRET}"
      credentials_file: "credentials.json"
      enabled: true
```

## 🚀 Step 3: First Authorization

### 3.1 Test Connection
```bash
python3 main.py status
```

### 3.2 Authorize Account
When prompted, visit the OAuth URL in your browser:
1. Sign in with your Google account
2. Grant permissions to the app
3. You'll be redirected back to localhost

### 3.3 Verify Success
```bash
python3 main.py status
```
You should see:
```
🔌 API Clients:
  ✅ Youtube
```

## 📺 Step 4: Adding Multiple Channels

### 4.1 Using the Channel Manager
```bash
# Add a new channel
python add_youtube_channel.py add "MyChannel" --channel-id "UC123456789"

# List all channels
python add_youtube_channel.py list

# Add a disabled channel
python add_youtube_channel.py add "TestChannel" --disabled
```

### 4.2 Manual Configuration
Add to `config.yaml`:
```yaml
accounts:
  youtube:
    - name: "main_channel"
      # ... existing config
    - name: "backup_channel"
      channel_id: "UC987654321"
      client_id: "${YOUTUBE_MAIN_CLIENT_ID}"
      client_secret: "${YOUTUBE_MAIN_CLIENT_SECRET}"
      credentials_file: "credentials.json"
      enabled: true
```

## 🎬 Step 5: Testing Video Upload

### 5.1 Prepare Test Video
- Format: MP4 or MOV
- Aspect ratio: 9:16 (vertical)
- Duration: 15-60 seconds
- Resolution: 1080x1920 (recommended)

### 5.2 Test Immediate Post
```bash
python3 main.py post \
  --content content/videos/test_video.mp4 \
  --caption "Test YouTube Shorts upload! #shorts #test #youtube" \
  --platforms youtube
```

### 5.3 Test Scheduled Post
```bash
python3 main.py schedule \
  --content content/videos/test_video.mp4 \
  --caption "Scheduled YouTube Shorts! #shorts #scheduled" \
  --platforms youtube \
  --time "2024-01-15T18:00:00"
```

## ⚙️ Step 6: Advanced Configuration

### 6.1 YouTube Shorts Optimization
The system automatically:
- Detects 9:16 aspect ratio videos
- Adds #Shorts hashtag
- Sets appropriate category (People & Blogs)
- Optimizes title length (100 characters max)
- Extracts hashtags from description

### 6.2 Custom Metadata
```bash
python3 main.py post \
  --content video.mp4 \
  --caption "My awesome video! #shorts" \
  --platforms youtube \
  --metadata '{"title": "Custom Title", "privacy_status": "unlisted"}'
```

### 6.3 Quota Management
- System tracks daily quota usage
- Shows remaining uploads available
- Automatic retry for quota exceeded
- Logs quota consumption

## 🔍 Step 7: Monitoring and Management

### 7.1 Check System Status
```bash
python3 main.py status
```

### 7.2 Validate Accounts
```bash
python3 main.py validate-accounts
```

### 7.3 View Statistics
```bash
python3 main.py stats
```

### 7.4 List Scheduled Posts
```bash
python3 main.py list-scheduled
```

## 🚨 Troubleshooting

### Common Issues

#### "Access blocked" Error
**Solution**: Add your Google account to Test Users in OAuth consent screen

#### "Insufficient authentication scopes"
**Solution**: Add required scopes in OAuth consent screen:
- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube`

#### "Quota exceeded" Error
**Solution**: 
- Wait for daily quota reset (24 hours)
- Check quota usage in logs
- Consider upgrading to paid Google Cloud plan

#### "No credentials file found"
**Solution**: 
- Ensure `credentials.json` is in project root
- Check file permissions
- Verify file is not corrupted

### Debug Commands
```bash
# Check logs
tail -f logs/auto_posting.log

# Test specific account
python3 -c "
from src.api_clients.youtube_client import YouTubeClient
client = YouTubeClient('test', 'test', 'credentials.json')
print('Connection test:', client.test_connection())
"

# Validate configuration
python3 main.py status
```

## 📊 Best Practices

### Content Optimization
- Use 9:16 aspect ratio for Shorts
- Keep videos under 60 seconds
- Use engaging thumbnails
- Add relevant hashtags

### Scheduling
- Post during peak hours (6-9 PM)
- Space posts 2-4 hours apart
- Use random timing to avoid patterns
- Test different posting schedules

### Account Management
- Monitor quota usage daily
- Keep tokens refreshed
- Use multiple channels for different content types
- Regular account validation

## 🔒 Security

### Token Management
- Tokens are stored in `youtube_token.json`
- Automatic refresh when expired
- Secure storage with proper permissions
- Never commit tokens to version control

### API Security
- Use environment variables for credentials
- Regularly rotate access tokens
- Monitor API usage for anomalies
- Follow Google's security best practices

## 📈 Scaling

### Multiple Channels
- Each channel can have different settings
- Share OAuth credentials across channels
- Individual quota tracking per channel
- Bulk operations support

### Content Pipeline
- Batch upload multiple videos
- Automated content processing
- Smart scheduling across channels
- Performance analytics

## 🎯 Next Steps

1. **Test with multiple videos** to ensure stability
2. **Set up monitoring** for quota and errors
3. **Configure notifications** for success/failure
4. **Optimize posting schedule** based on analytics
5. **Scale to more channels** as needed

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section
2. Review log files in `logs/`
3. Verify all credentials are correct
4. Test with a simple video first
5. Check Google Cloud Console for API errors

---

**Congratulations!** 🎉 You now have a fully automated YouTube Shorts posting system!
