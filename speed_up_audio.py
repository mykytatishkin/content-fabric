#!/usr/bin/env python3
"""Speed up audio file"""

import sys
import librosa
import soundfile as sf

if len(sys.argv) < 4:
    print("Usage: python3 speed_up_audio.py INPUT OUTPUT SPEED")
    print("Example: python3 speed_up_audio.py input.mp3 output.mp3 1.1")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]
speed = float(sys.argv[3])

print(f"⏩ Ускорение на {(speed - 1) * 100:.0f}%...")
print(f"   Вход: {input_file}")
print(f"   Выход: {output_file}")

# Load
audio, sr = librosa.load(input_file, sr=None)

# Speed up
audio_faster = librosa.effects.time_stretch(audio, rate=speed)

# Save
sf.write(output_file, audio_faster, sr)

print(f"✅ Готово! Файл сохранен: {output_file}")

