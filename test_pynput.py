from pynput import keyboard
def on_press(key): print(f"pressed {key}"); return False
with keyboard.Listener(on_press=on_press) as l: l.join()
