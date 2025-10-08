# Voice Changer - Quick Start Guide 🎙️

Transform voices in your audio and video files with ease!

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install FFmpeg (choose your platform)
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

## Quick Usage

### 1. Convert Male to Female Voice

```bash
python run_voice_changer.py input_video.mp4 output_video.mp4 --type male_to_female
```

### 2. Convert Female to Male Voice

```bash
python run_voice_changer.py input_audio.wav output_audio.wav --type female_to_male
```

### 3. Batch Process Multiple Files

```bash
python run_voice_changer.py --batch input_folder/ output_folder/ --type male_to_female
```

### 4. List Available Presets

```bash
python run_voice_changer.py --list-presets
```

## Available Presets

| Preset | Description | Use Case |
|--------|-------------|----------|
| `male_to_female` | Male → Female voice | Content creation, anonymization |
| `female_to_male` | Female → Male voice | Voice disguise, character voices |
| `male_to_child` | Male → Child voice | Animation, storytelling |
| `female_to_child` | Female → Child voice | Animation, storytelling |

## Programmatic Usage

```python
from core.utils.voice_changer import change_voice

# Simple conversion
result = change_voice(
    input_file='my_video.mp4',
    output_file='converted_video.mp4',
    conversion_type='male_to_female'
)

print(f"✅ Conversion complete: {result['output_file']}")
```

## Integration with Task System

```python
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime
import json

db = YouTubeMySQLDatabase()

# Create voice change task
task_id = db.add_task(
    account_id=0,
    media_type='voice_change',
    title='Convert Voice',
    description='Voice transformation',
    att_file_path='/path/to/video.mp4',
    scheduled_time=datetime.now(),
    add_info=json.dumps({
        'conversion_type': 'male_to_female'
    })
)

# Run task worker to process
# python run_task_worker.py
```

## Advanced Options

```bash
# Custom pitch and formant shift
python run_voice_changer.py input.mp4 output.mp4 --pitch 4.0 --formant 1.3

# Faster processing (lower quality)
python run_voice_changer.py input.mp4 output.mp4 --type male_to_female --no-preserve-quality

# Specify temporary directory
python run_voice_changer.py input.mp4 output.mp4 --temp-dir /tmp/voice_processing

# Verbose logging
python run_voice_changer.py input.mp4 output.mp4 --type male_to_female -v
```

## Supported Formats

**Video**: MP4, AVI, MOV, MKV, WebM, FLV  
**Audio**: WAV, MP3, M4A, OGG, FLAC

## Tips for Best Results

1. ✅ Use high-quality source audio (48kHz, 16-bit+)
2. ✅ Start with presets before customizing
3. ✅ Keep pitch shift between -6 and +6 semitones
4. ✅ Keep formant shift between 0.8 and 1.3
5. ✅ Test on short clips before batch processing

## Common Issues

### FFmpeg not found
```bash
# Install FFmpeg first
brew install ffmpeg  # macOS
sudo apt-get install ffmpeg  # Linux
```

### Poor quality output
- Use `preserve_quality=True` (default)
- Use less extreme pitch/formant values
- Ensure high-quality input audio

### Processing too slow
- Use `--no-preserve-quality` flag
- Process shorter clips
- Close other applications

## Full Documentation

For detailed documentation, see: [Voice Changer Guide](docs/guides/VOICE_CHANGER_GUIDE.md)

## Examples

### Example 1: YouTube Video Preparation
```bash
# Convert your voice for a video
python run_voice_changer.py my_tutorial.mp4 tutorial_female_voice.mp4 --type male_to_female
```

### Example 2: Podcast Processing
```bash
# Batch convert podcast episodes
python run_voice_changer.py --batch podcast_episodes/ converted_episodes/ --pattern "*.wav" --type female_to_male
```

### Example 3: Custom Voice Effect
```python
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger()
result = changer.process_file(
    input_file='video.mp4',
    output_file='output.mp4',
    pitch_shift=5.0,  # Custom pitch
    formant_shift=1.35,  # Custom formant
    preserve_quality=True
)
```

## Help

```bash
python run_voice_changer.py --help
```

---

**Ready to transform voices?** Try it now! 🚀
