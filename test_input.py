from pynput import keyboard
import sys

print("Starting input test. Press Alt to see if it's detected. Press ESC to exit.")

def on_press(key):
    try:
        print(f"Key pressed: {key}")
        if key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
            print("ALT DETECTED!")
    except AttributeError:
        print(f"Special key pressed: {key}")

def on_release(key):
    if key == keyboard.Key.esc:
        return False

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
