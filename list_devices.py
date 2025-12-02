import sys
from pathlib import Path

# Add project root to path
sys.path.append('/home/ryan/voice-to-text-system')

from src.utils.audio_utils import audio_manager

print("\n=== Available Audio Devices ===")
devices = audio_manager.get_audio_devices()
for dev in devices:
    marker = "*" if dev['is_default'] else " "
    print(f"{marker} [{dev['index']}] {dev['name']} (Channels: {dev['channels']}, Rate: {dev['sample_rate']})")
print("===============================\n")
