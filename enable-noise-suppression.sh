#!/bin/bash
# Enable PulseAudio/PipeWire Noise Suppression (Echo Cancel)

echo "Enabling Noise Suppression..."

# Unload if already exists to avoid duplicates
pactl unload-module module-echo-cancel 2>/dev/null

# Load the module
# This creates a new source ending in .echo-cancel
if pactl load-module module-echo-cancel use_master_format=1 aec_method=webrtc aec_args="analog_gain_control=0 digital_gain_control=1"; then
    echo "✅ Noise suppression module loaded."
    echo "New Input Source created. You may need to select it in your sound settings or set it as default."
    
    # Get the name of the new source
    NEW_SOURCE=$(pactl list sources short | grep echo-cancel | awk '{print $2}')
    if [ ! -z "$NEW_SOURCE" ]; then
        echo "Source Name: $NEW_SOURCE"
        # Optional: Set as default
        # pactl set-default-source "$NEW_SOURCE"
        # echo "Set as default input."
    fi
else
    echo "❌ Failed to load module-echo-cancel."
fi
