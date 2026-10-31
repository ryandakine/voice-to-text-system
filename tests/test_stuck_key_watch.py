"""The stuck-key watcher must notice a modifier left down and say so.

Intent: Ryan cannot tell when a fake (xdotool/voice-typer) key is stuck down,
so the watcher has to release it and tell him; a real key held for a long time
only gets a warning, and Alt push-to-talk holds never trigger anything.
"""
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stuck_key_watch as skw  # noqa: E402

XINPUT_LIST = """\
⎡ Virtual core pointer                    	id=2	[master pointer  (3)]
⎜   ↳ Virtual core XTEST pointer              	id=4	[slave  pointer  (2)]
⎣ Virtual core keyboard                   	id=3	[master keyboard (2)]
    ↳ Virtual core XTEST keyboard             	id=5	[slave  keyboard (3)]
    ↳ Power Button                            	id=6	[slave  keyboard (3)]
    ↳ Logitech USB Receiver                   	id=9	[slave  keyboard (3)]
    ↳ LogiOps Virtual Input                   	id=19	[slave  keyboard (3)]
"""


def test_parse_keyboards_finds_xtest_and_real_keyboards() -> None:
    devices: dict = skw.parse_keyboards(XINPUT_LIST)
    assert devices[5] == "Virtual core XTEST keyboard"
    assert devices[9] == "Logitech USB Receiver"
    assert 2 not in devices and 4 not in devices  # pointers are not keyboards


def test_parse_down_keys_reads_only_pressed_keys() -> None:
    state = "2 classes :\nKeyClass\n\tkey[37]=up\n\tkey[133]=down\n\tkey[54]=down\n"
    assert skw.parse_down_keys(state) == {133, 54}


def test_fake_super_held_two_seconds_is_released_once() -> None:
    t = skw.Tracker()
    t.update(5, {133}, now=100.0)
    limit = skw.XTEST_RELEASE_AFTER_S
    assert skw.decide(t, {5: skw.XTEST_NAME}, 5, now=100.0 + limit - 0.5) == []  # too soon
    assert skw.decide(t, {5: skw.XTEST_NAME}, 5, now=100.0 + limit + 0.5) == [("release", 5, 133)]
    t.acted.add((5, 133))
    assert skw.decide(t, {5: skw.XTEST_NAME}, 5, now=100.0 + limit + 30) == []  # never repeated


def test_real_super_held_long_warns_but_real_alt_push_to_talk_never_does() -> None:
    t = skw.Tracker()
    t.update(9, {133, 64}, now=0.0)  # Super and Alt down on the real keyboard
    actions = skw.decide(t, {9: "Logitech USB Receiver"}, 5, now=120.0)
    assert actions == [("warn", 9, 133)]  # Alt (64) is push-to-talk: no warning


def test_key_released_then_pressed_again_restarts_the_clock() -> None:
    t = skw.Tracker()
    t.update(5, {133}, now=0.0)
    t.update(5, set(), now=1.0)      # let go
    t.update(5, {133}, now=1.5)      # pressed again — the clock restarts here
    limit = skw.XTEST_RELEASE_AFTER_S
    assert skw.decide(t, {5: skw.XTEST_NAME}, 5, now=1.5 + limit - 0.5) == []
    assert skw.decide(t, {5: skw.XTEST_NAME}, 5, now=1.5 + limit + 0.1) == [("release", 5, 133)]


@pytest.mark.skipif(not (shutil.which("Xvfb") and shutil.which("xinput")),
                    reason="needs Xvfb and xinput")
def test_watcher_releases_a_real_stuck_fake_super_key_on_an_x_server(tmp_path, monkeypatch) -> None:
    display = ":96"
    # -noreset: a real desktop always has clients connected, so it never resets and a
    # fake key pressed by a since-exited client stays down. Xvfb would otherwise reset
    # (dropping all held keys) the moment its last client disconnects.
    xvfb = subprocess.Popen(["Xvfb", display, "-noreset", "-screen", "0", "640x480x24"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.0)
        monkeypatch.setenv("DISPLAY", display)
        monkeypatch.setattr(skw, "LOG_PATH", tmp_path / "stuck-keys.log")
        monkeypatch.setattr(skw, "POLL_S", 0.2)
        monkeypatch.setattr(skw, "XTEST_RELEASE_AFTER_S", 0.6)
        # This machine may have a real x11vnc session on :5900; the skip is tested separately.
        monkeypatch.setattr(skw, "remote_session_active", lambda: False)
        notes = []
        monkeypatch.setattr(skw, "notify", lambda title, body: notes.append(title))

        # Leave Super_L down on the XTEST device from a client that then exits, exactly what a
        # short-lived xdotool --clearmodifiers re-press can do.
        from Xlib import X, display as xdisplay
        from Xlib.ext import xtest
        presser = xdisplay.Display(display)
        xtest.fake_input(presser, X.KeyPress, 133)
        presser.sync()
        presser.close()

        def xtest_down() -> set:
            out = subprocess.run(["xinput", "list"], capture_output=True, text=True).stdout
            xid = next(i for i, n in skw.parse_keyboards(out).items() if n == skw.XTEST_NAME)
            state = subprocess.run(["xinput", "query-state", str(xid)],
                                   capture_output=True, text=True).stdout
            return skw.parse_down_keys(state)

        assert 133 in xtest_down()  # the stuck state really exists before the watcher runs

        stop = threading.Event()
        worker = threading.Thread(target=skw.run, kwargs={"stop_event": stop}, daemon=True)
        worker.start()
        try:
            deadline = time.time() + 5
            while time.time() < deadline and 133 in xtest_down():
                time.sleep(0.2)

            assert 133 not in xtest_down(), "watcher did not release the stuck fake Super key"
            assert notes == ["Keyboard was stuck - fixed"], "user was not told"
            assert "RELEASED fake Super_L" in (tmp_path / "stuck-keys.log").read_text()
        finally:
            stop.set()
            worker.join(timeout=5)
            assert not worker.is_alive(), "watcher thread kept polling after the test"
    finally:
        xvfb.terminate()
        xvfb.wait(timeout=5)


def test_xtest_release_is_skipped_while_a_remote_session_is_active(tmp_path, monkeypatch) -> None:
    """x11vnc/RustDesk deliver the remote user's real Shift/Ctrl through the XTEST device."""
    monkeypatch.setattr(skw, "LOG_PATH", tmp_path / "stuck-keys.log")
    monkeypatch.setattr(skw, "XTEST_RELEASE_AFTER_S", 0.0)
    monkeypatch.setattr(skw, "remote_session_active", lambda: True)
    released = []
    monkeypatch.setattr(skw, "release_xtest_key", lambda code: released.append(code))
    monkeypatch.setattr(skw, "notify", lambda title, body: None)

    def fake_run(argv, **kwargs):
        if argv[:2] == ["xinput", "list"]:
            return SimpleNamespace(stdout=XINPUT_LIST, returncode=0)
        return SimpleNamespace(stdout="\tkey[50]=down\n", returncode=0)

    monkeypatch.setattr(skw.subprocess, "run", fake_run)
    skw.run(once=True)

    assert released == []
    assert "skipped: remote session active" in (tmp_path / "stuck-keys.log").read_text()
