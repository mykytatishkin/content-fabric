#!/bin/bash
# Quick installer for weights.com model

echo "🎙️  Installing Voice Model from Weights.com"
echo "============================================================"

# Check if model file provided
if [ -z "$1" ]; then
    echo "❌ Error: Model file not provided"
    echo ""
    echo "Usage:"
    echo "  1. Download .pth file from weights.com"
    echo "  2. Run: bash INSTALL_WEIGHTS_MODEL.sh ~/Downloads/model.pth female my_voice"
    echo ""
    echo "Arguments:"
    echo "  \$1 - Path to .pth file"
    echo "  \$2 - Voice type (male/female/neutral)"
    echo "  \$3 - Model ID (e.g., my_voice)"
    exit 1
fi

MODEL_FILE="$1"
VOICE_TYPE="${2:-female}"
MODEL_ID="${3:-custom_voice}"

# Check if file exists
if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ Error: File not found: $MODEL_FILE"
    exit 1
fi

echo "📦 Installing model:"
echo "  File: $MODEL_FILE"
echo "  Type: $VOICE_TYPE"
echo "  ID: $MODEL_ID"
echo ""

# Run Python installer
python3 scripts/add_custom_model.py \
  --file "$MODEL_FILE" \
  --id "$MODEL_ID" \
  --name "Voice from Weights.com" \
  --desc "Downloaded from weights.com" \
  --type "$VOICE_TYPE"

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "✅ Model installed successfully!"
    echo "============================================================"
    echo ""
    echo "🎙️  Use it now:"
    echo "  python3 run_voice_changer.py \\"
    echo "    --voice-model $MODEL_ID \\"
    echo "    input.mp3 output.mp3"
    echo ""
fi

