# Voice Changer Guide

## Overview

Voice Changer is a powerful tool for transforming voice characteristics in audio and video files. It can convert male voices to female, female to male, and even create child-like voices while preserving audio quality.

## Features

- ✅ Support for both audio and video files
- ✅ Multiple voice conversion presets
- ✅ Custom pitch and formant shifting
- ✅ High-quality voice transformation
- ✅ Batch processing capability
- ✅ Integration with task management system
- ✅ CLI and programmatic interfaces

## Supported File Formats

### Video Formats
- MP4
- AVI
- MOV
- MKV
- WebM
- FLV

### Audio Formats
- WAV
- MP3
- M4A
- OGG
- FLAC

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `pydub` - Audio processing
- `praat-parselmouth` - Voice transformation
- `soundfile` - Audio I/O
- `numpy` - Numerical operations
- `librosa` - Audio analysis
- `moviepy` - Video processing

### 2. Install FFmpeg (Required)

#### macOS
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

#### Windows
Download from [FFmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Usage

### Command Line Interface (CLI)

#### Basic Usage

Convert a video file from male to female voice:
```bash
python run_voice_changer.py input.mp4 output.mp4 --type male_to_female
```

Convert an audio file from female to male voice:
```bash
python run_voice_changer.py input.wav output.wav --type female_to_male
```

#### Advanced Options

Custom pitch and formant shift:
```bash
python run_voice_changer.py input.mp4 output.mp4 --pitch 4.0 --formant 1.3
```

Faster processing (lower quality):
```bash
python run_voice_changer.py input.mp4 output.mp4 --type male_to_female --no-preserve-quality
```

#### Batch Processing

Process all MP4 files in a directory:
```bash
python run_voice_changer.py --batch videos/ output/ --type male_to_female
```

Process specific file types:
```bash
python run_voice_changer.py --batch videos/ output/ --pattern "*.mov" --type female_to_male
```

#### List Available Presets

```bash
python run_voice_changer.py --list-presets
```

### Programmatic Usage

#### Simple Voice Change

```python
from core.utils.voice_changer import change_voice

# Convert male to female voice
result = change_voice(
    input_file='input.mp4',
    output_file='output.mp4',
    conversion_type='male_to_female'
)

print(f"Success: {result['success']}")
print(f"Output: {result['output_file']}")
print(f"Duration: {result['duration']}s")
```

#### Advanced Usage with VoiceChanger Class

```python
from core.utils.voice_changer import VoiceChanger

# Initialize voice changer
changer = VoiceChanger(temp_dir='/tmp/voice_processing')

# Process with custom parameters
result = changer.process_file(
    input_file='input.mp4',
    output_file='output.mp4',
    conversion_type='male_to_female',
    pitch_shift=3.5,  # Custom pitch shift in semitones
    formant_shift=1.2,  # Custom formant shift multiplier
    preserve_quality=True
)

# Check result
if result['success']:
    print(f"✅ Voice conversion completed!")
    print(f"Output: {result['output_file']}")
    print(f"Pitch shift: {result['pitch_shift']} semitones")
    print(f"Formant shift: {result['formant_shift']}x")
else:
    print(f"❌ Conversion failed")
```

#### Batch Processing

```python
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger()

# Process multiple files
input_files = ['video1.mp4', 'video2.mp4', 'audio1.wav']
result = changer.batch_process(
    input_files=input_files,
    output_dir='output/',
    conversion_type='male_to_female'
)

print(f"Total: {result['total']}")
print(f"Successful: {result['successful']}")
print(f"Failed: {result['failed']}")

# Check individual results
for file_result in result['files']:
    if file_result['status'] == 'success':
        print(f"✅ {file_result['input']} -> {file_result['output']}")
    else:
        print(f"❌ {file_result['input']}: {file_result['error']}")
```

## Voice Conversion Presets

### male_to_female
- **Description**: Convert male voice to female
- **Pitch shift**: +3.5 semitones
- **Formant shift**: 1.2x
- **Use case**: Make male voice sound more feminine

### female_to_male
- **Description**: Convert female voice to male
- **Pitch shift**: -3.5 semitones
- **Formant shift**: 0.85x
- **Use case**: Make female voice sound more masculine

### male_to_child
- **Description**: Convert male voice to child
- **Pitch shift**: +6.0 semitones
- **Formant shift**: 1.3x
- **Use case**: Make male voice sound like a child

### female_to_child
- **Description**: Convert female voice to child
- **Pitch shift**: +4.0 semitones
- **Formant shift**: 1.25x
- **Use case**: Make female voice sound like a child

## Integration with Task System

You can use the voice changer through the task management system.

### Create a Voice Change Task

```python
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime
import json

# Connect to database
db = YouTubeMySQLDatabase()

# Create voice change task
task_id = db.add_task(
    account_id=0,  # No account needed for voice change
    media_type='voice_change',
    title='Convert Male to Female Voice',
    description='Voice transformation task',
    att_file_path='/path/to/input/video.mp4',
    scheduled_time=datetime.now(),
    add_info=json.dumps({
        'conversion_type': 'male_to_female',
        'pitch_shift': 3.5,  # Optional custom value
        'formant_shift': 1.2  # Optional custom value
    })
)

print(f"Voice change task created with ID: {task_id}")
```

### Run Task Worker

The task worker will automatically process voice change tasks:

```bash
python run_task_worker.py
```

The worker will:
1. Pick up pending voice change tasks
2. Process them using the VoiceChanger
3. Save output to `voice_converted/` directory
4. Mark tasks as completed
5. Retry failed tasks automatically

### Check Task Status

```python
# Get task status
task = db.get_task_by_id(task_id)
print(f"Status: {task.status}")
print(f"Progress: {task.progress}%")
```

## Understanding Parameters

### Pitch Shift
- **Range**: -12 to +12 semitones (typically)
- **Positive values**: Higher pitch (more feminine/child-like)
- **Negative values**: Lower pitch (more masculine)
- **Recommendation**: 
  - Male to Female: +3 to +4 semitones
  - Female to Male: -3 to -4 semitones

### Formant Shift
- **Range**: 0.7 to 1.4 (typically)
- **Values > 1.0**: Smaller vocal tract (more feminine/child-like)
- **Values < 1.0**: Larger vocal tract (more masculine)
- **Recommendation**:
  - Male to Female: 1.15 to 1.25
  - Female to Male: 0.80 to 0.90

### Quality Preservation
- **preserve_quality=True**: Higher quality output, slower processing
- **preserve_quality=False**: Faster processing, acceptable quality
- **Recommendation**: Use True for production, False for testing

## Troubleshooting

### FFmpeg Not Found
```
Error: FFmpeg not found
```
**Solution**: Install FFmpeg as described in Installation section.

### Poor Voice Quality
**Possible causes**:
- Pitch shift too extreme (> ±6 semitones)
- Formant shift too extreme (< 0.7 or > 1.4)
- Low quality input audio

**Solutions**:
- Use more conservative parameters
- Ensure input audio is high quality (48kHz, 16-bit or higher)
- Enable quality preservation: `preserve_quality=True`

### Processing Too Slow
**Solutions**:
- Disable quality preservation: `--no-preserve-quality`
- Use smaller formant shift adjustments
- Process shorter clips

### Out of Memory
**Solutions**:
- Process smaller files
- Close other applications
- Use batch processing with smaller batches

## Examples

### Example 1: Content Creation
Convert your male voice to female for a video:
```bash
python run_voice_changer.py my_video.mp4 female_voice.mp4 --type male_to_female
```

### Example 2: Podcast Processing
Batch convert all podcast episodes:
```bash
python run_voice_changer.py --batch podcasts/ output_podcasts/ --pattern "*.wav" --type female_to_male
```

### Example 3: Custom Voice Effect
Create a unique voice with custom parameters:
```bash
python run_voice_changer.py input.mp4 output.mp4 --pitch 5.0 --formant 1.35
```

### Example 4: Automated Workflow
Integrate with task system for automated processing:
```python
import json
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime

db = YouTubeMySQLDatabase()

# Queue multiple voice change tasks
videos = ['video1.mp4', 'video2.mp4', 'video3.mp4']

for video in videos:
    task_id = db.add_task(
        account_id=0,
        media_type='voice_change',
        title=f'Convert {video}',
        description='Auto voice conversion',
        att_file_path=f'/path/to/{video}',
        scheduled_time=datetime.now(),
        add_info=json.dumps({
            'conversion_type': 'male_to_female'
        })
    )
    print(f"Task {task_id} queued for {video}")

# Start worker to process all tasks
# python run_task_worker.py
```

## Performance Benchmarks

| File Type | Duration | Processing Time | Quality |
|-----------|----------|----------------|---------|
| Video (1080p) | 1 min | ~30-45 sec | High |
| Video (720p) | 1 min | ~20-30 sec | High |
| Audio (WAV) | 1 min | ~10-15 sec | High |
| Audio (MP3) | 1 min | ~15-20 sec | High |

*Note: Times measured on M1 MacBook Pro with preserve_quality=True*

## Best Practices

1. **Use high-quality source audio**: Better input = better output
2. **Test with presets first**: Before using custom parameters
3. **Start conservative**: Use default preset values, adjust if needed
4. **Batch process similar files**: More efficient than one-by-one
5. **Keep original files**: Don't overwrite original audio/video
6. **Monitor quality**: Listen to samples before batch processing

## API Reference

### VoiceChanger Class

#### `__init__(temp_dir: Optional[str] = None)`
Initialize voice changer with optional temporary directory.

#### `process_file(input_file, output_file, conversion_type, pitch_shift, formant_shift, preserve_quality)`
Process a single audio or video file.

**Parameters**:
- `input_file` (str): Path to input file
- `output_file` (str): Path to output file
- `conversion_type` (str): Preset type ('male_to_female', etc.)
- `pitch_shift` (float, optional): Custom pitch shift in semitones
- `formant_shift` (float, optional): Custom formant shift multiplier
- `preserve_quality` (bool): Whether to preserve maximum quality

**Returns**: Dictionary with processing results

#### `batch_process(input_files, output_dir, conversion_type, **kwargs)`
Process multiple files in batch.

**Parameters**:
- `input_files` (list): List of input file paths
- `output_dir` (str): Output directory
- `conversion_type` (str): Preset type
- `**kwargs`: Additional arguments for process_file

**Returns**: Dictionary with batch results

#### `get_available_presets()`
Get available voice conversion presets.

**Returns**: Dictionary of available presets with parameters

## Support

For issues or questions:
1. Check this guide first
2. Review error messages carefully
3. Check FFmpeg installation
4. Verify file paths and permissions
5. Test with provided examples

## License

This tool is part of the Content Fabric project and follows the project's license terms.
