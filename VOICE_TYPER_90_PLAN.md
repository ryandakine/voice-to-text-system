<!-- /autoplan restore point: ~/.gstack/projects/ryandakine-voice-to-text-system/main-autoplan90-restore-*.md -->
# Voice Typer 90+ Plan

Take the system from 80/100 to 90+/100 by shipping three coordinated features. Skip packaging (Phase 4 candidate) until after v1.0 gets real user feedback — distribution doesn't make the tool better, just makes it more findable.

## Target score breakdown

| Dimension       | Now | After | Driver |
|-----------------|-----|-------|--------|
| Latency         | 8   | 10    | Streaming partials appear while speaking |
| UX              | 8   | 10    | Listening overlay + audio cues + voice editing |
| Features        | 8   | 10    | Voice commands + streaming + editing commands |
| Reliability     | 8   | 9     | Visual feedback = immediate error signal |
| Innovation      | 7   | 8     | Overlap-chunk streaming over faster-whisper (rare) |
| All others      | —   | —     | Unchanged |

Weighted gain: ~+10 points → **90/100 target.**

## Execution order (by ROI)

**Change 1 first** (layup — existing code, wire it up), **Change 2 second** (enables Change 3's dev loop — you need visual feedback to tune streaming), **Change 3 third** (biggest impact but riskiest).

---

## Change 1 — Wire up voice commands

Existing `voice_commands.py` at repo root is complete but dead (never imported by voice_typer_whisper.py). Has regex patterns for stop/start/scratch that/undo/export/help with "computer" prefix support.

### Integration

**File:** `/home/ryan/voice-to-text-system/voice_typer_whisper.py`

1. Import: `from voice_commands import VoiceCommandProcessor, VoiceCommand`
2. In `VoiceTyperWhisper.__init__`:
   - `self._cmd = VoiceCommandProcessor(enabled=True, prefix="computer")`
   - Register handlers via `self._cmd.register_handler(VoiceCommand.STOP_LISTENING, self._handle_stop_listening)` etc.
   - Track `self._last_typed_text: Optional[str] = None` for scratch/clear support.
3. In `_transcribe_and_type` — **before** calling `_type_text`:
   ```python
   if self._cmd.process(text):
       return  # command handled, don't type
   ```
4. Handler implementations (new methods on VoiceTyperWhisper):
   - `_handle_stop_listening`: `self._listening_flag.clear()` + status file update
   - `_handle_start_listening`: `self._listening_flag.set()` + status file
   - `_handle_clear_last`: backspace-delete `self._last_typed_text` via `xdotool key --repeat N BackSpace`
   - `_handle_undo`: xdotool `key ctrl+z`
   - `_handle_help`: `self._type_text(self._cmd.get_help_text())`
   - `_handle_export`: call existing `export_manager.py` (already exists)

### Notes
- The "computer" prefix catches commands. A bare "stop listening" while dictating shouldn't trigger — must be prefixed. Safe default.
- `clear that` / `scratch that` need `self._last_typed_text` populated in `_type_text` — one-line add.

### Tests
- `test_voice_command_intercepts_before_typing` — mock the typer, verify "computer stop listening" pauses listening and doesn't type
- `test_scratch_that_sends_backspaces` — mock xdotool, verify `len(last_typed_text)` backspaces sent
- `test_non_command_transcription_types_normally` — "hello world" goes through to type_text

### Effort
~2 hours. +3 score points.

---

## Change 2 — Visual listening overlay + audio cues

Current status signal is `/tmp/voice_typer_status` + tray icon (only visible if you mouse over). No on-screen indicator that says "listening now" during a recording, no audio cue.

### Overlay window

**New file:** `src/listening_overlay.py`

GTK3 borderless always-on-top window. ~60px x 60px, bottom-right corner by default. Shows:
- Green pulsing circle = speech detected (in utterance)
- Gray static circle = listening but no speech
- Hidden = not listening

Piggybacks `src/status_gui.py`'s GTK3 setup pattern. Controlled via file-based signaling (`/tmp/voice_typer_state`) so the overlay process can be separate from the main transcriber — avoids GTK main-loop entanglement in the transcription thread.

**New file:** `src/listening_overlay_daemon.py` — long-running GTK process. Reads `/tmp/voice_typer_state` every 100ms.

**voice_typer_whisper.py** — write state to `/tmp/voice_typer_state` on `_in_speech` transitions. One function, 5 lines.

### Audio cues

**New files:** `assets/listen_start.wav`, `assets/listen_end.wav` — 50ms quiet beeps. Generate with `sox` at build time: `sox -n listen_start.wav synth 0.05 sine 880 vol 0.3`.

**voice_typer_whisper.py** — new method `_play_cue(name)` that calls `subprocess.Popen(["paplay", asset_path])` non-blocking. Feature-flagged via config: `[Whisper] audio_cues = true`.

Config additions: `[Whisper] audio_cues = true`, `overlay_enabled = true`, `overlay_position = bottom-right`.

### Integration

Launch the overlay daemon from `install.sh` as an autostart user unit. Tray icon gets a menu item to toggle.

### Tests
- `test_state_file_updates_on_speech_transition` — mock filesystem, verify writes happen
- `test_audio_cue_feature_flag_respected` — config audio_cues=false → no subprocess spawn
- Overlay daemon is GTK — test via manual verification, not pytest

### Effort
~4 hours. +3 score points.

---

## Change 3 — Streaming partial transcription

The biggest felt-latency win. Today the user waits until they stop talking for text to appear; with streaming, text appears every ~800ms while they're still speaking.

### Architecture

**New file:** `src/partial_buffer.py`

```
         [mic chunks]
              |
              v
    [Silero VAD + buffer]
              |
   ┌──── every 800ms if in_speech ────┐
   |                                  |
   v                                  v
 [faster-whisper.transcribe(buffer)]  [faster-whisper.transcribe(final buffer)]
   |                                  |
   v                                  v
 [partial text, deduped]          [final text, replaces last partial]
   |                                  |
   v                                  v
 [text_insertion.insert_partial(text, prev_partial)]
```

Each 800ms tick inside an utterance:
1. Snapshot current audio buffer (no flush)
2. Transcribe with `beam_size=1, condition_on_previous_text=False`
3. Compare to `self._last_partial` — if same, skip
4. If different, compute diff:
   - Common prefix → no change
   - Changed suffix → `text_inserter.insert_partial(new_suffix, old_suffix_length)` deletes old and types new

At utterance end (Silero reports silence window):
- Run one final transcribe on the complete buffer
- Compare to `self._last_partial`, apply same diff logic
- Clear partial state

### Text insertion support for partials

**Modify:** `src/text_insertion.py`

Add method `insert_partial(new_suffix: str, old_suffix_length: int)`:
1. If `old_suffix_length > 0`: `xdotool key --delay 0 --repeat <N> BackSpace`
2. Then `insert_text(new_suffix)` via keyboard strategy (not clipboard — partials must not pollute clipboard)
3. Clipboard-paste strategy doesn't support partial updates; skip it for streaming mode

Force `primary_method = keyboard` when partials are active. Revert to user-configured method for final full-utterance insertion.

### Risks

1. **Typing into wrong window mid-utterance** — if user clicks elsewhere while speaking, partials type there. Mitigation: capture the focused window at VAD-start, refuse to partial-type if focus changes. (Same mechanism `src/text_insertion.py` already uses at line 180-182 for window_id capture.)
2. **Backspace-over-text user typed manually** — if user manually types between partials, backspaces will eat their text. Mitigation: for v1, only do partials during continuous-listening mode (F8), not PTT. PTT is "I'm dictating a chunk now," continuous is "I'm in flow."
3. **Compute cost** — transcribing every 800ms is 2-4x more GPU than waiting for end. Tolerable on modern GPU; on CPU, disable streaming (config flag `streaming = false` if device=cpu).
4. **Partial flicker** — if every partial is different, user sees constant rewrite. Mitigation: only update if new partial has >2 char diff from previous (hysteresis).

### Config

```ini
[Whisper]
streaming = true                ; auto-disabled if device=cpu
streaming_interval_ms = 800     ; partial transcribe cadence
streaming_min_diff_chars = 2    ; hysteresis threshold
```

### Tests

- `test_partial_buffer_emits_at_interval` — fake audio stream, mock transcribe, verify partials emitted every 800ms
- `test_diff_computes_common_prefix` — two strings with shared prefix, verify backspace count + new suffix
- `test_final_transcribe_replaces_partial` — partial says "hello wor", final says "hello world" → verify insertion correct
- `test_streaming_disabled_on_cpu` — config with device=cpu → verify no partial buffer starts
- `test_window_focus_change_aborts_partials` — mock active window ID change → verify partials stop

### Effort
~8 hours. +5 score points. Highest-risk change — **consider running a full review gauntlet (/autoplan) before implementing.**

---

## Files to modify

| Change | File | Type |
|--------|------|------|
| 1 | `voice_typer_whisper.py` | modify (+40 lines for command wiring + handlers) |
| 1 | `tests/test_voice_commands_integration.py` | new (3 tests) |
| 2 | `src/listening_overlay.py` | new (~120 lines) |
| 2 | `src/listening_overlay_daemon.py` | new (~60 lines) |
| 2 | `assets/listen_start.wav`, `assets/listen_end.wav` | new (generated by sox in build step) |
| 2 | `voice_typer_whisper.py` | modify (+15 lines for state file write + cue calls) |
| 2 | `install.sh` | modify (+5 lines autostart daemon) |
| 2 | `config.ini.example` | modify (+3 keys) |
| 2 | `tests/test_overlay_signals.py` | new (2 tests) |
| 3 | `src/partial_buffer.py` | new (~150 lines) |
| 3 | `src/text_insertion.py` | modify (+30 lines for insert_partial) |
| 3 | `voice_typer_whisper.py` | modify (+25 lines to use partial buffer in continuous mode) |
| 3 | `config.ini.example` | modify (+3 keys) |
| 3 | `tests/test_partial_buffer.py` | new (5 tests) |

Total: ~350 new lines, ~80 modified. 3 new classes. 15 new tests (17 → 32).

## Verification plan

Run after each change independently:

### Change 1 verification
1. `.venv/bin/python -m pytest tests/test_voice_commands_integration.py -v`
2. Start typer, say "computer stop listening" — status goes to OFF, no "computer stop listening" typed
3. Say "computer scratch that" after typing — last utterance disappears via backspaces
4. Say a normal sentence — transcribes normally (no prefix = no command)

### Change 2 verification
1. `.venv/bin/python -m pytest tests/test_overlay_signals.py -v`
2. Start typer with overlay daemon running — see bottom-right overlay indicator
3. Speak — indicator pulses green, hear `listen_start.wav`
4. Stop speaking — indicator fades, hear `listen_end.wav`
5. `config audio_cues = false` + restart → no sounds, overlay still works

### Change 3 verification
1. `.venv/bin/python -m pytest tests/test_partial_buffer.py -v`
2. Open a text editor, start typer, speak a 6-second sentence — text appears in ~800ms chunks, updating as speech continues
3. Final utterance: verify the corrected full text matches what final-only mode produces
4. Stop streaming mid-sentence (flip provider or kill process) — no partial text left dangling
5. Click a different window mid-utterance → partials stop (don't leak to wrong window)
6. Set `device=cpu` in config, restart — streaming disabled automatically, falls back to full-utterance mode

## Deferred (Phase 4 — post-v1.1)

- **AUR + Flatpak + snap packaging** — adoption work, not tool quality. Do after collecting v1.0 GitHub issues.
- **Wake word detection** — requires openWakeWord or similar runtime, not worth the complexity for a user who already has a key to press.
- **VS Code / browser extensions** — large separate projects, not blocking 90+.

## Risk and review

- Change 1 is low-risk — existing tested code, minimal surface.
- Change 2 is medium-risk — new GTK daemon process, startup complications possible. Mitigate by launching overlay lazily from within voice_typer_whisper.py instead of as a separate process. (Design note: consider consolidating if overlay-as-separate-process proves fragile.)
- Change 3 is high-risk — touches text insertion, thread safety, user-visible rewriting. **Run /autoplan before implementing Change 3.** Do NOT batch all three into one PR.

## Ship order

Three PRs, merged sequentially:
1. PR #1 — Change 1 (voice commands)
2. PR #2 — Change 2 (overlay + cues)
3. PR #3 — Change 3 (streaming partials) — only after /autoplan review

Tag `v1.1.0` after PR #3 lands. This is the 90+ milestone.

---

## GSTACK REVIEW REPORT

Full /autoplan pipeline: CEO + Eng + Design with dual voices (Codex + Claude subagent) per phase. DX skipped (personal tool not dev-facing).

### Consensus across 6 voices

**CRITICAL (blocking — must fix before implementing):**

| # | Finding | Who flagged | Fix |
|---|---------|------|------|
| C1 | Streaming is O(n²), not 2-4x. `faster-whisper.transcribe(growing_buffer)` every 800ms re-transcribes the full buffer each tick. 10s utterance = 62s of audio transcribed. | both engs | Replace "type partial into target window" with "display partial in overlay only." Cap tick cadence to 1.2s and bound the buffer snapshot to last 5s of audio. Use committed-prefix algorithm (whisper_streaming style) for final. |
| C2 | `scratch that` fails with clipboard insertion. Counted backspaces don't match clipboard-paste char count (cursor movement, app auto-format, trailing space). | both engs | Use `xdotool key ctrl+z` (app-level undo), not counted backspaces. Works regardless of insertion strategy. |
| C3 | `computer help` types regex patterns into the target window — corrupts user's document. | all 4 (engs + designs) | Route to `notify-send` instead of typing. |
| C4 | Silent fail on focus change mid-utterance = user speaks a sentence, nothing appears, no feedback. | both engs + both designs | On focus change, abort partials and route final text via clipboard to ORIGINAL window (capture at VAD-start). If original window gone, flash overlay amber + error tone. |
| C5 | No "model loading" state. First run downloads ~250MB; user sees nothing for 30s. | both designs | Add `loading` state to overlay + state file. |

**HIGH (fix in same pass):**

| # | Finding | Who flagged | Fix |
|---|---------|------|------|
| H1 | Overlay daemon as separate process with 100ms file polling is sluggish + fragile. | both engs | Embed overlay in main process: GTK on main thread via `GLib.idle_add`, audio/transcription on workers. No separate daemon. |
| H2 | Listening flag not checked inside `_transcribe_and_type` thread — race when "computer stop listening" fires mid-transcribe. | claude eng | Check `self._listening_flag.is_set()` at top of `_transcribe_and_type`. |
| H3 | "computer" prefix too rigid for natural speech. | both designs | Alias set: `computer`, `hey computer`, `ok computer`, `okay computer`. |
| H4 | Backspace-retype flicker visible as "typos in real time." | both designs | Demoted to overlay-only via C1. Resolved by consequence. |
| H5 | No acknowledgment cue on command success. | both designs | Separate chime per command (`cmd_ack.wav`). |
| H6 | No transcribing state between speech-end and text-arrival. | both designs | 4th overlay state: `transcribing`, slow blue pulse. |
| H7 | No error state in overlay. | both designs | 5th state: red persistent, with fallback `notify-send`. |
| H8 | Insert_partial forcing keyboard mode regresses clipboard path. | both engs | Resolved by C1 — no partial typing, so no keyboard/clipboard split. |
| H9 | Handler exceptions swallowed, `process()` returns command anyway. | claude eng | Check `_execute_handler` bool return, log failed commands. |

**MEDIUM:**

| # | Finding | Fix |
|---|---------|------|
| M1 | Overlay position fixed bottom-right — clashes with system tray | Add `overlay_position` config (4 corners). |
| M2 | Pulse rate unspecified | Add `overlay_pulse_hz = 1.2` to config. |
| M3 | Gray = broken perception | Drop gray. Use `low-alpha ring = listening idle`, green pulse = speech, blue slow pulse = transcribing, red static = error. |
| M4 | Tests are mocks-only, miss O(n²) + thread races | Add 1-2 integration tests with synthetic audio feeding real transcriber timing. |
| M5 | Config surface grows +6 keys in `[Whisper]` | Acceptable; all have sensible defaults. |

### USER CHALLENGES (both models disagree with stated direction)

**UC-1: Ship order — packaging before more features.**
All four strategic voices (CEO×2 + Eng×2) recommend AUR + Flatpak BEFORE Changes 2 and 3. Plan line 4 says "distribution doesn't make the tool better." Both CEOs call this "founder self-deception." Install friction = first 90 seconds of user experience. AUR PKGBUILD ~5h effort = same as Change 2, delivers more first-time users than any in-product feature.

**Decision:** Ryan was explicit about "do all three changes" and "get to 90+." Not overriding the user's stated direction on strategy. Will add AUR + Flatpak as a fourth parallel workstream (PR #0) but preserve Changes 1-3. Five PRs total: AUR/Flatpak (optional, parallel), then Change 1 → 2 → 3.

**UC-2: Streaming architecture — don't type partials into target window.**
Both engs CRITICAL-flagged this. Ryan's original plan: type partials into target window, backspace-and-retype. Models recommend: show partials in overlay ONLY; keep final insertion in target window via existing text_inserter.

**Decision:** Amending Change 3 to "overlay-only partials + final typed normally." This resolves C1, C4, H4, H8 in one architectural shift. Streaming value preserved (visible partials during speech) without the footguns (wrong-window contamination, O(n²) blow-up, insertion regression).

---

## Revised plan (round 2)

### Change 1 — Voice commands (amended)

Same as original, with these round-2 fixes:

- `_handle_clear_last`: `subprocess.run(["xdotool", "key", "ctrl+z"])` (app-level undo, not counted backspaces) — **resolves C2**
- `_handle_help`: `subprocess.run(["notify-send", "-t", "8000", "-i", "audio-input-microphone", "Voice Typer", self._cmd.get_help_text()])` — **resolves C3**
- Check `_execute_handler` bool return; log `command failed` on False — **resolves H9**
- Add listening-flag check at top of `_transcribe_and_type` — **resolves H2**
- Alias prefixes: pass `prefixes=["computer", "hey computer", "ok computer", "okay computer"]` to a small wrapper around `VoiceCommandProcessor` (or patch `VoiceCommandProcessor.process` to try each prefix) — **resolves H3**
- Play `assets/cmd_ack.wav` (a distinct short chime) in every command handler — **resolves H5**

### Change 2 — Listening overlay + audio cues (amended)

- **Embed overlay in main process** (no separate daemon). Use GLib main loop on the main thread, audio/transcription on worker threads. Use `GLib.idle_add()` for cross-thread GTK calls. — **resolves H1**
- States: `loading` (yellow spinner, during model download/warm), `idle` (low-alpha ring), `speech` (green pulse at 1.2Hz), `transcribing` (slow blue pulse during the gap between speech-end and text-arrival), `error` (red static, with `notify-send` fallback). — **resolves C5, H6, H7, M3**
- Config: `overlay_position = bottom-right` (or top-left/top-right/bottom-left), `overlay_pulse_hz = 1.2`. — **resolves M1, M2**
- Audio cues: `listen_start.wav` (A5 880Hz), `listen_end.wav` (E5 659Hz), `cmd_ack.wav` (G5 784Hz short blip), `error.wav` (C4 261Hz low).
- Attention hierarchy: errors > command acks > recording state. Audio only on transitions/errors. Overlay owns persistent state. `notify-send` for command results.

### Change 3 — Streaming partial transcription (reworked — overlay-only)

**Critical architectural change: partials display in the overlay, NOT in the target window.** Final utterance transcription still types into the target window via existing `text_inserter`.

**New architecture:**

```
         [mic chunks]
              |
              v
    [Silero VAD + rolling buffer]
              |
   ┌──── every 1.2s if in_speech ────┐
   |                                  |
   v                                  v
 [faster-whisper.transcribe(last 5s)] [faster-whisper.transcribe(full utterance)]
   |                                  |
   v                                  v
 [partial text → overlay]          [final text → text_inserter → target window]
```

- **Bounded buffer:** transcribe only the last 5 seconds of audio on each tick. Prevents O(n²) blow-up. — **resolves C1**
- **Partials go to overlay only:** `self._overlay.show_partial(text)` — no typing. — **resolves C4, H4, H8**
- **Final transcription unchanged:** Silero VAD reports silence → run one final transcribe on the full buffer → route via `text_inserter.insert_text()` as today.
- **Focus change:** if active window at VAD-start differs at VAD-end, skip typing, show overlay error + notify-send "Speech lost: focus changed." — **resolves C4 fallback path**

Tick cadence 1.2s (not 800ms) = ~6x less compute than plan's original cadence, and only on bounded 5s buffer. Compute is now bounded and predictable.

**Files:**
- `src/partial_buffer.py` (new, ~100 lines — simpler now)
- `src/listening_overlay.py` — add `show_partial(text)` method
- `voice_typer_whisper.py` — wire the partial callback from inside `_on_audio_chunk`

**Tests:**
- Integration test with synthetic audio: fake 10s utterance, verify bounded buffer stays ≤5s, verify partial transcribe calls are bounded, verify no target-window typing occurs until final. — **resolves M4**
- Unit tests: mock overlay, verify `show_partial` called; mock transcriber, verify final text typed once.

### Change 0 (new, optional parallel workstream) — AUR PKGBUILD + Flatpak manifest

Not gating Changes 1-3. Can be done in parallel by a worktree agent or deferred.

- `packaging/aur/PKGBUILD` — build from GitHub release tarball, install via `yay -S voice-typer`
- `packaging/flatpak/com.osi.VoiceTyper.yml` — Flatpak manifest with required `--filesystem=xdg-run/pulse`, `--talk-name=org.freedesktop.portal.*` for typing
- GitHub Actions workflow: on tag push, publish PKGBUILD to AUR (needs `aurpublish` action), build Flatpak artifact and attach to release.

Effort: ~5 hours. Independent of code changes.

### Updated ship order

Three code PRs + optional packaging PR:

1. **PR #1** — Change 1 (voice commands, with round-2 fixes)
2. **PR #2** — Change 2 (embedded overlay + audio cues + all 5 states)
3. **PR #3** — Change 3 (overlay-only streaming partials, bounded buffer)
4. **PR #0 (parallel, optional)** — AUR + Flatpak packaging

Tag `v1.1.0` after PR #3 lands.

### Updated score projection

| Dimension | Now | After v1.1 | Driver |
|-----------|-----|-----------|--------|
| Latency | 8 | 9 | Overlay partials give "something happening" signal; final-insertion latency unchanged |
| UX | 8 | 10 | Overlay (5 states) + audio cues + voice editing + command acks |
| Features | 8 | 10 | Commands + streaming preview + editing (ctrl+z) |
| Reliability | 8 | 9 | 5-state overlay surfaces errors immediately |
| Install | 8 | 9 | +1 if AUR/Flatpak land |
| Innovation | 7 | 8 | Overlay-only streaming preview is unusual |

Weighted: 80 → **89-90.** Packaging (Change 0) pushes to 90+.

---

## Final verdict

**Plan is shippable after round-2 amendments.** Critical issues C1-C5 resolved by the overlay-only streaming architecture + ctrl+z undo + notify-send help + embedded GTK overlay. All High issues addressed inline. User challenge UC-1 (ship order) honored per Ryan's stated direction with AUR/Flatpak added as parallel optional workstream. User challenge UC-2 (streaming arch) resolved — safer design.

| Review | Runs | Status | Findings |
|--------|------|--------|----------|
| CEO (Claude + Codex) | 1 | resolved via amendments | 3 user challenges; 2 resolved by amendments, 1 honored |
| Eng (Claude + Codex) | 1 | resolved | 9 findings, all addressed in revised plan |
| Design (Claude + Codex) | 1 | resolved | 9 findings, all addressed |
| DX | 0 | skipped — personal tool not dev-facing | — |

**VERDICT:** Approved for implementation.

