#!/bin/bash
# Script to switch Whisper model

CONFIG_FILE="$HOME/.config/voice-to-text/config.ini"
MODEL=$1

if [ -z "$MODEL" ]; then
    echo "Usage: $0 <model_name>"
    echo "Available models: tiny, base, small, medium, large"
    echo "Current configuration:"
    grep "model =" "$CONFIG_FILE"
    exit 1
fi

if [[ ! "$MODEL" =~ ^(tiny|base|small|medium|large)$ ]]; then
    echo "Error: Invalid model name. Choose from: tiny, base, small, medium, large"
    exit 1
fi

# Update config file
sed -i "s/model = .*/model = $MODEL/" "$CONFIG_FILE"

echo "Switched to model: $MODEL"
echo "Restarting service..."
systemctl --user restart voice-to-text.service
echo "Done."
