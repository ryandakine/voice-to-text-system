import sys
from pathlib import Path

# Add project root to path so `src.utils.audio_utils` resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils.audio_utils import audio_manager

print("\n=== Available Audio Devices ===")
devices = audio_manager.get_audio_devices()
for dev in devices:
    marker = "*" if dev['is_default'] else " "
    print(f"{marker} [{dev['index']}] {dev['name']} (Channels: {dev['channels']}, Rate: {dev['sample_rate']})")
print("===============================\n")
