# 🎤 Text-to-Speech Guide

## Overview

This guide explains how to use the text-to-speech functionality to synthesize text directly into audio using Silero TTS, without requiring source audio files.

## ✨ Features

- **Direct text synthesis** - Convert text to audio without audio input
- **Multiple Russian voices** - 6 different voices (3 female, 3 male)
- **Automatic stress marks** - Normative Russian stress placement for natural pronunciation
- **Long text support** - Automatically splits long texts into chunks
- **High quality** - 48kHz sample rate output

## 🚀 Quick Start

### Method 1: Using CLI

```bash
# Basic synthesis
python run_voice_changer.py --text "Привет, это тест" output.wav --voice-model kseniya

# Without stress marks (faster)
python run_voice_changer.py --text "Длинный текст..." output.wav --voice-model eugene --no-stress
```

### Method 2: Using Python API

```python
from core.utils.voice_changer import VoiceChanger

# Initialize
changer = VoiceChanger()

# Synthesize text
result = changer.process_text(
    text="Привет! Это пример синтеза речи.",
    output_file="output.wav",
    voice="kseniya",
    add_stress=True
)

print(f"Saved to: {result['output_file']}")
print(f"Duration: {result['duration']:.2f}s")
```

### Method 3: Direct Silero API

```python
from core.utils.silero_voice_changer import SileroVoiceChanger

changer = SileroVoiceChanger()

result = changer.synthesize_text_to_audio(
    text="Использование прямого API.",
    output_file="output.wav",
    target_voice="baya",
    sample_rate=48000,
    add_stress=True
)
```

## 🎤 Available Voices

```bash
python run_voice_changer.py --list-silero-voices
```

| Voice ID | Gender | Description | Best For |
|----------|--------|-------------|----------|
| `kseniya` | Female | Ксения - женский голос | ⭐ General purpose |
| `baya` | Female | Бая - женский голос | Narrations |
| `aidar` | Male | Айдар - мужской голос | General purpose |
| `eugene` | Male | Евгений - мужской голос | ⭐ Professional |
| `xenia` | Female | Ксения (variant) | Alternative |

## ⭐ Best Practices for Quality

### Recommended: Disable Stress Marks (Default)

**Silero TTS handles Russian pronunciation excellently on its own.**

```bash
# Best quality - no stress marks (default)
python run_voice_changer.py output.wav \
  --text "Ваш текст" \
  --voice-model kseniya

# Optional: Slower speech for better comprehension
python run_voice_changer.py output.wav \
  --text "Ваш текст" \
  --voice-model kseniya \
  --speed 0.9  # 10% slower
```

**Why disable stress marks?**
- ✅ Silero TTS has excellent built-in Russian pronunciation
- ✅ No artificial stress marks interfering with natural speech
- ✅ Better prosody and intonation
- ✅ Faster processing
- ✅ More natural sounding output

**Default speech rate:** 1.0 (normal speed)
- Use `--speed 0.9` for 10% slower (better for audiobooks)
- Use `--speed 1.1` for 10% faster (news-style delivery)

### Natural Pauses Between Sentences

The system automatically adds pauses:
- **500ms** after sentences ending with `.`, `!`, `?`
- **300ms** after commas

This creates natural speech rhythm without manual timing control.

## 📝 Parameters

### CLI Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--text TEXT` | Text to synthesize | Required |
| `--voice-model NAME` | Voice to use | Required |
| `--speed RATE` | Speech rate (0.9 = 10% slower) | 1.0 |
| `output` | Output file path | Required |

**Note:** Stress marks are disabled by default for best quality. Silero TTS handles Russian pronunciation excellently.

### Python API Parameters

```python
process_text(
    text: str,              # Text to synthesize
    output_file: str,       # Output audio file path
    voice: str = 'kseniya', # Target voice
    sample_rate: int = 48000, # Output sample rate
    add_stress: bool = False, # Disabled by default - Silero handles Russian well
    speaking_rate: float = 1.0  # Speech rate (0.9 = 10% slower)
)
```

## 🎯 Russian Stress Marks (Optional)

### ⚠️ NOT Recommended for Best Quality

Stress marks are **disabled by default** because Silero TTS handles Russian pronunciation excellently without them.

**Problems with automatic stress marks:**
- ❌ Small dictionary (only ~145 words covered)
- ❌ Many words left without correct stress
- ❌ Can interfere with Silero's natural prosody
- ❌ Slower processing

**Library options attempted:**
- `russtress` - Requires TensorFlow, version conflicts
- `pymorphy3` - Installed but doesn't add stress marks
- `russian-accentuate` - Not available

### When to Enable Stress Marks

Only enable if you have specific words that Silero mispronounces:

```bash
# Not recommended (stress marks disabled by default)
python run_voice_changer.py output.wav \
  --text "текст" \
  --voice-model kseniya

# If needed, try with Silero's built-in pronunciation - it's usually correct!
```

## 📚 Examples

### Example 1: Basic Synthesis

```python
from core.utils.voice_changer import VoiceChanger

changer = VoiceChanger()

result = changer.process_text(
    text="Привет! Это пример синтеза речи.",
    output_file="output.wav",
    voice="kseniya"
)

print(f"Saved: {result['output_file']}")
print(f"Duration: {result['duration']:.2f}s")
```

### Example 2: Different Voices

```python
text = "Это один и тот же текст."

for voice in ['kseniya', 'eugene', 'aidar', 'baya']:
    result = changer.process_text(
        text=text,
        output_file=f"output_{voice}.wav",
        voice=voice
    )
    print(f"Created: {result['output_file']}")
```

### Example 3: Long Text

Long texts are automatically split into chunks:

```python
long_text = """
Искусственный интеллект продолжает развиваться.
Системы синтеза речи становятся все более естественными.
Этот текст будет автоматически разбит на части для синтеза.
"""

result = changer.process_text(
    text=long_text.strip(),
    output_file="long_output.wav",
    voice="eugene"
)
```

### Example 4: From File

```python
# Read text from file
with open("text.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Synthesize
result = changer.process_text(
    text=text,
    output_file="from_file.wav",
    voice="kseniya"
)
```

## 🆚 Comparison with Audio Input

### Audio Input (Existing Feature)

```
Audio File → Whisper Transcription → Text → Silero TTS → Audio
                                ↓
                        Prosody Transfer
                        (intonation from original)
```

**Use when:** You have source audio and want to change voice while preserving prosody

### Text Input (New Feature)

```
Text → Silero TTS → Audio
       ↓
   Stress Marks
   (normative Russian)
```

**Use when:** You have text and want to create voiceover/narration

## ⚡ Performance

- **With stress marks**: ~2-3 seconds per 100 characters
- **Without stress marks**: ~1-2 seconds per 100 characters
- **Sample rate**: 48kHz (high quality)
- **Format**: WAV (uncompressed)

## 🔧 Troubleshooting

### Error: "Whisper model not loaded"

This is normal for text-to-speech mode. Whisper is only used for audio transcription.

### Error: "Failed to add stress marks"

The system will fall back to text without stress marks. Audio will still be synthesized.

### Long text takes a long time

This is expected. The system splits long texts automatically and synthesizes each chunk. Consider using `--no-stress` for faster processing.

## 📖 See Also

- [Voice Changer Guide](VOICE_CHANGER.md) - Audio voice conversion
- [Russian Stress README](../docs/RUSSIAN_STRESS_README.md) - Stress marks explanation
- [Examples](../examples/text_to_speech_example.py) - Complete examples

## 🎉 Summary

Text-to-speech functionality allows you to:

✅ Synthesize text directly to audio  
✅ Use multiple Russian voices  
✅ Add normative stress marks automatically  
✅ Process long texts automatically  
✅ Create high-quality voiceovers  

Perfect for creating narrations, voiceovers, or converting text to speech!

