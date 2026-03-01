from pynput import keyboard
import time

def on_press(key):
    try:
        print('Alphanumeric key pressed: {0}'.format(key.char))
    except AttributeError:
        print('Special key pressed: {0}'.format(key))

def on_release(key):
    print('{0} released'.format(key))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

print("Starting Listener... Press F8 to test. Press ESC to stop.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
