<!-- /autoplan restore point: /home/ryan/.gstack/projects/ryandakine-voice-to-text-system/main-autoplan-restore-20260416-173410.md -->
# Voice Typer Speed Plan

Make local Whisper dictation feel instant (≤500ms perceived latency per utterance) without giving up accuracy or going cloud-only.

## Goal

Target: a full utterance is transcribed and typed within ~500ms of the user finishing speaking. Hallucinations on silence eliminated. Accuracy ≥ current `small` on openai-whisper.

## Why the current setup is slow

`voice_typer_whisper.py` currently:

1. Uses **openai-whisper** reference PyTorch runtime. `small.en` on RTX 5060 runs at ~0.5–1.0× RTF. CTranslate2 runs the same model 2–4× faster for the same accuracy.
2. Uses **RMS-based VAD** (SPEECH_THRESHOLD=500, SILENCE_THRESHOLD=300 at lines 42–43). Lets microphone noise through → Whisper hallucinates `"Thank you"`, `"you"`, `"That's alright babe..."` (visible in `voice_typer.log`).
3. Uses `condition_on_previous_text=True` (Whisper default) → hallucination loops propagate across utterances.
4. Uses **`xdotool type`** (line 446) which types one keypress at a time. Long utterances visibly trail behind.
5. `beam_size`/`best_of` defaults are 5/5 (Whisper default) → ~30% slower than greedy decode for negligible accuracy gain on short dictation utterances.

## Recommended approach

Three coordinated changes in `voice_typer_whisper.py`, staged so each is shippable standalone. No changes to `src/speech_processor.py` (legacy, not on active path), `src/interfaces.py`, or the tray/launcher — scope limited to the Whisper path.

### Change 1 — Swap runtime to `faster-whisper` (CTranslate2)

Single biggest win. Same model files (auto-downloaded/converted), same accuracy, 2–4× faster, lower VRAM.

**File:** `/home/ryan/voice-to-text-system/voice_typer_whisper.py`

**Edits:**
- Replace `import whisper` with `from faster_whisper import WhisperModel` (line 25).
- In `WhisperTranscriber.__init__` / `_load` (lines 49–108), construct `WhisperModel(model_name, device=device, compute_type="float16")` instead of `whisper.load_model(...)`. Use `compute_type="int8_float16"` as a fallback for smaller VRAM footprint if float16 OOMs.
- In `transcribe()` (lines 124–160), call `segments, info = self._model.transcribe(audio_np, language=lang, beam_size=1, vad_filter=False, condition_on_previous_text=False, no_speech_threshold=0.6)` and join `segments` text. Note: faster-whisper returns a generator — materialize with `" ".join(s.text for s in segments).strip()`.
- Update `DOWNGRADE_CHAIN` (line 25) to faster-whisper model IDs (same strings work: `small.en`, `base.en`, `tiny.en`).
- Remove the numpy→tempfile soundfile fallback (lines 142–156) — faster-whisper handles numpy natively and is more reliable.

**Decoding flags** (in the `transcribe()` call):
- `beam_size=1` — greedy decode, ~30% faster, negligible quality loss for dictation
- `condition_on_previous_text=False` — prevents cross-utterance hallucination drift
- `no_speech_threshold=0.6` — skip decode when model is confident there's no speech
- `vad_filter=False` — we do our own VAD (Change 2)

**Requirements update:** Add `faster-whisper>=1.0.0` to `requirements.txt`. Keep `openai-whisper` for now (harmless, allows rollback). Both coexist without conflict (verified: torch 2.10.0+cu128 already present).

### Change 2 — Replace RMS VAD with Silero VAD

Silero is a 2MB neural VAD that massively outperforms RMS thresholds on real-world audio. Eliminates the `"Thank you"` / `"you"` hallucinations seen in the log and gives cleaner utterance boundaries.

**File:** `/home/ryan/voice-to-text-system/voice_typer_whisper.py`

**Edits:**
- Add `import torch` and load Silero via `torch.hub.load('snakers4/silero-vad', 'silero_vad')` (cache after first run).
- Replace the RMS block in `_on_audio_chunk()` (lines 339–381). New logic: accumulate 512-sample frames (32ms at 16kHz), run Silero on each, treat `prob > 0.5` as speech. Start utterance on first speech frame; end on 7 consecutive non-speech frames (same SILENCE_CHUNKS semantics, different signal source).
- Keep the existing `MAX_BUFFER_CHUNKS` 30-second cap, the PTT branch (lines 247–251), and the listening flag gate — only the detection heuristic changes.
- Delete `SPEECH_THRESHOLD`, `SILENCE_THRESHOLD`, `_rms()` (they become dead code).

**Config additions** (`~/.config/voice-to-text/config.ini` `[Whisper]` section):
- `vad_threshold = 0.5` — Silero speech probability cutoff
- `vad_silence_frames = 7` — frames of silence to end utterance (already matches SILENCE_CHUNKS)

**Requirements update:** Silero is torch-hub, no pip package needed. Add `onnxruntime` only if we opt for ONNX variant (skip for now — torch path is fine given we already depend on torch).

### Change 3 — Clipboard-paste for long text (optional polish)

`xdotool type` at line 446 types one key at a time (~5–10ms per char). A 200-char utterance burns 1–2 seconds just on typing.

**File:** `/home/ryan/voice-to-text-system/voice_typer_whisper.py` (line 441–451, `_type_text`)

**Edits:**
- For outputs > 50 chars: copy to clipboard via `xclip -selection clipboard`, then `xdotool key ctrl+v`. Fallback to `xdotool type` if clipboard fails.
- For outputs ≤ 50 chars: keep `xdotool type` (lower overhead than clipboard round-trip).
- Reason to keep it narrow: `src/text_insertion.py` has a fuller three-strategy fallback, but importing it into `voice_typer_whisper.py` couples this entry point to the `src/` module tree, which it currently avoids. A local clipboard path keeps the file self-contained.

### Deferred (not in this plan)

- **Streaming partial transcription** (show text while speaking) — biggest latency win but requires overlapping chunk windows and partial→final reconciliation. Worth a separate plan if the three changes above don't go far enough.
- **Parakeet-TDT / NeMo** — SOTA real-time local STT but different runtime, different ops model. Revisit only if faster-whisper still feels slow.
- **Deepgram flip** — already wired (`~/.voice_typer/provider.txt = deepgram`). Not a code change; treat as a runtime toggle the user makes when minimum latency matters more than local-only.
- Touching `src/speech_processor.py` — it's not on the active voice-typer path; any refactor there is separate.

## Files to modify

| File | Purpose |
|------|---------|
| `/home/ryan/voice-to-text-system/voice_typer_whisper.py` | Runtime swap + VAD swap + typing path. The only hot file. |
| `/home/ryan/voice-to-text-system/requirements.txt` | Add `faster-whisper>=1.0.0`. |
| `/home/ryan/.config/voice-to-text/config.ini` | Add `[Whisper] vad_threshold`, `vad_silence_frames`. |

## Verification plan

1. **Syntax check:** `.venv/bin/python -m py_compile voice_typer_whisper.py`.
2. **Cold-start test:** kill running process, restart, confirm `Whisper model loaded` log line appears within 5s (faster-whisper ctranslate2 load is faster than openai-whisper).
3. **Latency measurement:** with the existing `_record_latency` instrumentation, speak 10 utterances of varying length. Expected: median RTF drops from current (~0.3–0.5) to ≤0.15 on `small.en` with faster-whisper. Wall-clock for a 3-second utterance should be ≤450ms.
4. **Hallucination check:** sit silent for 60 seconds with typer active. Expected: zero transcribed text (was producing `"Thank you"`, `"you"` every ~30s under RMS VAD).
5. **Accuracy spot-check:** dictate three known paragraphs (a code comment, a README blurb, a Slack message). Compare WER qualitatively against current `base.en`. Expected: matches or beats current because we can run `small.en` at the latency budget that currently only `base.en` hits.
6. **Auto-downgrade still works:** artificially set `downgrade_rtf=0.05` in config, dictate 5 utterances, confirm downgrade log line fires (`Whisper auto-downgrade: small.en → base.en`).
7. **Clipboard-paste path:** dictate a long sentence (>50 chars) into a text editor; verify it appears as one paste (undo is single-step) not character-by-character.
8. **Rollback test:** flip `~/.voice_typer/provider.txt` to `deepgram`, confirm Deepgram path still works unchanged.

## Risk / rollback

- Risk: faster-whisper model download on first run is ~500MB — one-time, delays first boot. Mitigation: pre-download before swap by running `faster-whisper-cli` once or scripting a warm-up.
- Risk: Silero VAD may be too aggressive/lax for the user's mic profile. Mitigation: threshold is in config, tunable without code changes.
- Rollback: `git checkout voice_typer_whisper.py requirements.txt` reverts instantly. `openai-whisper` stays installed so the old code path works without reinstall.

## Scope summary

One hot file, ~100 lines changed. ~30min work. No touch to tray, launchers, systemd, or other provider paths. Config-tunable. Reversible in one `git checkout`.

---

## GSTACK REVIEW REPORT

Full /autoplan pipeline run. CEO + Eng reviews with dual voices (Codex + independent Claude subagent). Design and DX phases skipped (no UI scope, personal tool not dev-facing).

### CEO Dual Voices — Consensus Table

| # | Dimension | Claude subagent | Codex | Consensus |
|---|-----------|-----------------|-------|-----------|
| 1 | Premises valid? | DISAGREE — 2–4× speedup unproven on RTX 5060 | DISAGREE — "instant" defined as post-speech, not partials | **DISAGREE** |
| 2 | Right problem? | DISAGREE — Deepgram already solves this | DISAGREE — streaming partials is the 10x | **DISAGREE** |
| 3 | Scope correct? | CONFIRMED if offline is a hard constraint | DISAGREE — scope minimization, not strategy | DISAGREE |
| 4 | Alternatives explored? | DISAGREE — Parakeet dismissed too quickly | DISAGREE — streaming + Deepgram reframe dismissed | **CONFIRMED DISAGREE** |
| 5 | Competitive/market risk | Medium: commodity plumbing | Flagged: not defensible vs OS-native + browser APIs | CONFIRMED |
| 6 | 6-month trajectory | Risk: plan ships, still slow, redo | Risk: local-vs-cloud contradiction never resolved | **CONFIRMED** |

**Three user challenges surfaced** (both models agree the user's stated direction should change):
- **UC-1:** Streaming partials should be Change 1, not deferred. Both voices: it's the real perceived-latency win.
- **UC-2:** Evaluate Parakeet-TDT (1 hour spike) before locking in faster-whisper as the runtime.
- **UC-3:** Benchmark current openai-whisper RTF on RTX 5060 before assuming faster-whisper is the bottleneck.

### Eng Dual Voices — Consensus Table

| # | Dimension | Claude subagent | Codex | Consensus |
|---|-----------|-----------------|-------|-----------|
| 1 | Architecture sound? | DISAGREE — `_try_downgrade` line 208 still calls `whisper.load_model` | DISAGREE — same finding, line 193 | **CONFIRMED CRITICAL** |
| 2 | Test coverage | DISAGREE — manual only | DISAGREE — no automated regression | **CONFIRMED** |
| 3 | Performance risks | Flagged — downgrade threshold dead after swap | Flagged — load-under-lock stalls all transcription | CONFIRMED |
| 4 | Security / leakage | Flagged — clipboard persists dictated text | Flagged — plan reimplements worse subset of text_insertion.py | **CONFIRMED** |
| 5 | Error paths handled? | DISAGREE — _loaded never set on failure, 180s silent hang | DISAGREE — same finding | **CONFIRMED** |
| 6 | Deployment risk | Low — rollback is clean | Low — single-file edit | CONFIRMED |

### Critical Findings (must fix before implementation)

| # | Severity | Issue | Source |
|---|----------|-------|--------|
| E1 | CRITICAL | `_try_downgrade` at line 208 still calls `whisper.load_model` — runtime crash on first downgrade | both eng voices |
| E2 | HIGH | Silero 512-sample frames vs current 1024-chunk VAD — timing silently halves (448ms → 224ms silence) unless thresholds re-derived in ms, not frames | Codex eng |
| E3 | HIGH | `_load` never calls `self._loaded.set()` on failure → 180s silent hang on no-internet or GPU OOM | both eng voices |
| E4 | HIGH | `compute_type="float16"` breaks existing `device=cpu` config — needs device-aware selection | Codex eng |
| E5 | HIGH | Clipboard change reinvents a worse subset of `src/text_insertion.py` which already has app-aware paste, window capture, clipboard restore | both eng voices |
| E6 | HIGH | Silero VAD not thread-safe, needs lock + `reset_states()` between utterances + warm-up call | Claude eng |
| E7 | MEDIUM | `_try_downgrade` loads new model while holding transcribe lock → stalls all transcription during download | Codex eng |
| E8 | MEDIUM | `downgrade_rtf=0.7` default is dead after faster-whisper (actual RTF ~0.1) — auto-downgrade never fires | Claude eng |
| E9 | MEDIUM | No automated regression tests for frame splitter, segment consumption, downgrade, clipboard fallback | both eng voices |
| E10 | LOW | `xclip` not verified installed; no `shutil.which()` guard; clipboard leakage after dictation | both eng voices |

### Revised Plan — Changes to original approach

The strategic reframe (user challenges UC-1/2/3) is deferred to the approval gate for Ryan's call. The tactical eng issues (E1–E10) are addressed here by amending the changes.

**Amendments to Change 1 (faster-whisper):**
- Add: extract model construction into a `_build_model(model_name)` helper used by both `_load()` and `_try_downgrade()`. _try_downgrade rewrite is in scope (E1).
- Add: device-aware compute_type — `cuda` → `float16` with fallback to `int8_float16`; `cpu` → `int8`. Not hardcoded (E4).
- Add: in `_try_downgrade`, build new model OUTSIDE the transcribe lock, swap pointer under lock. Guard against concurrent downgrades with a second lock (E7).
- Add: `_load` sets `self._load_error` and still triggers `self._loaded.set()` (with `self._model = None`) on failure so the 180s wait fails fast with a specific error string (E3).
- Add: after first successful load, log `effective compute_type` and `device` from the loaded model for operator visibility.
- Update: revise `downgrade_rtf` default to `0.3` and `downgrade_abs_s` to `1.2` for the faster-whisper baseline (E8).

**Amendments to Change 2 (Silero VAD):**
- Add: define silence window in **milliseconds** (`vad_silence_ms = 448`) and convert to 512-sample-frame count at runtime (E2). Same for `min_speech_ms` and `max_buffer_ms`. Replace the integer chunk constants with time-based equivalents.
- Add: `self._silero_lock = threading.Lock()` around all `vad_model(...)` calls (E6).
- Add: `vad_model.reset_states()` at utterance end (where `_in_speech` resets to False in `_on_audio_chunk`, line 381) (E6).
- Add: explicit warm-up call `vad_model(torch.zeros(512), 16000)` immediately after load to JIT-compile before first utterance (E6).
- Add: split each incoming 1024-sample chunk into two consecutive 512-sample frames passed to Silero independently (explicit code in plan, not "obvious to developer").
- Add: `torch.hub` cache pre-download step at first install; catch network errors on first run and log actionable message.

**Amendments to Change 3 (clipboard-paste):**
- **Replace local reimplementation with reuse of `src/text_insertion.py`** (E5). Accept the import coupling — it's the same repo and this code path already exists battle-tested.
  - From `voice_typer_whisper.py`, import `from src.text_insertion import text_inserter` (follow the existing module pattern).
  - Delete the local clipboard implementation idea; delegate to `text_inserter.insert_text(text)`.
  - Rationale: the existing module handles app-aware paste hotkeys (Ctrl+Shift+V in terminals), window capture, `--clearmodifiers`, and clipboard restore — all of which the local reimpl would silently omit.
- If the import creates a circular or heavy-load issue, fallback: local clipboard with `shutil.which("xclip")` check + clipboard clear after paste (E10). But reuse first.

**New Change 4 — Regression tests** (added in response to E9)

Add to `tests/` (or create a new `tests/test_voice_typer_whisper.py`):
- `test_frame_splitter` — feeds a known 1024-sample chunk, verifies two 512-sample frames are emitted in order.
- `test_downgrade_swap` — mocks `WhisperModel`, verifies `_try_downgrade` builds the new model outside the lock and atomically swaps `self._model`.
- `test_load_failure_surfaces` — mocks `WhisperModel` to raise `OSError("HTTP error")`, verifies `_loaded` event is set within 5s (not 180s) and `run()` exits with the specific network error string.
- `test_clipboard_fallback` — mocks `text_inserter.insert_text`, verifies it's called for text > 50 chars.
- `test_silero_reset_between_utterances` — mocks Silero, verifies `reset_states()` is called when utterance ends.

These tests run against mocks; no live audio or GPU needed. All must pass before committing.

### Revised Verification Plan

1. Syntax check: `.venv/bin/python -m py_compile voice_typer_whisper.py`
2. Unit tests: `.venv/bin/pytest tests/test_voice_typer_whisper.py -v` — all 5 new tests pass.
3. Cold-start: restart, confirm `Whisper model loaded` within 5s. Confirm a second log line shows effective `compute_type` and `device`.
4. **New baseline measurement (UC-3 response):** before the swap, run 10 utterances on current openai-whisper and record median/p90 RTF. This is the required premise check — if RTF is already ≤0.15 on GPU, Change 1 is the wrong bottleneck fix and the review recommends redirecting effort to streaming partials.
5. Latency measurement after swap: 10 utterances, expected median RTF ≤ 0.15 on `small.en`, wall-clock ≤ 450ms for a 3-second utterance.
6. Hallucination check: 60s silent, zero transcribed text.
7. Accuracy spot-check: 3 known paragraphs, qualitative WER.
8. Auto-downgrade test with corrected thresholds: `downgrade_rtf=0.01`, `downgrade_trigger=1` (E8 — old thresholds too loose).
9. Clipboard-paste path via `text_inserter`: dictate long sentence, verify single-paste undo, verify clipboard is restored/cleared after.
10. Error-path test: disconnect network, start cold. Expected: fast-fail within 10s with specific network error; NOT a 180s hang.
11. Rollback: flip provider to `deepgram`, confirm unchanged.

### Scope Delta

| | Original | Revised |
|---|---|---|
| Files modified | 3 | 3 + `tests/test_voice_typer_whisper.py` |
| Lines changed | ~100 | ~180 (incl. tests) |
| Estimated time | 30 min | 60–90 min |
| Risk | Medium (silent failure modes) | Low (tests + fast-fail error paths) |

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | **DISAGREE-PREMISES** | 3 user challenges (UC-1/2/3) |
| Codex Review | `/codex review` | Independent 2nd opinion | 2 | issues_open | Agrees with Claude subagent on all critical eng + CEO findings |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 | **issues_open → resolved in revised plan** | 10 findings; E1–E6 blocking, all addressed |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No UI scope |
| DX Review | `/plan-devex-review` | Developer experience | 0 | skipped | Personal tool, not dev-facing |

**VERDICT:** Plan technically sound after amendments (E1–E10 resolved in revised plan above). Three strategic user challenges (UC-1/2/3) require Ryan's call at the approval gate — both models agree the stated direction should change, but the user's context (offline requirement? taste for local-first? willingness to invest in streaming?) is needed.

---

## Round 2 Review — Findings on the Amendments

User rejected UC-1/2/3 (local-only, $5/mo Deepgram cost not worth it). Re-ran CEO + Eng dual voices against the amended plan. All three voices (Claude CEO, Claude Eng, Codex) converged on 5 new issues the amendments introduced or failed to fully resolve.

| # | Severity | Issue | Source |
|---|----------|-------|--------|
| R1 | HIGH | **E3 incomplete.** `_load` setting `_loaded.set()` with `_model=None` fixes the 180s hang but creates a "false ready" state. `wait_until_ready()` and `run()` must ALSO check `self._load_error` and exit with that error message. `transcribe()` must guard `if self._model is None: return None` after the `is_set()` check. | all three voices |
| R2 | MEDIUM | **Change 3 is internally inconsistent.** Amendment text says "delegate to `text_inserter.insert_text(text)`" unconditionally, but retained verification step 9 still references ">50 chars" threshold. Behavior for short text is undefined. Decision needed: use `text_inserter` for ALL text, or keep the threshold. | Codex |
| R3 | MEDIUM | **Silero `reset_states()` must hold `_silero_lock`, not `_buffer_lock`.** Plan put the reset inside the buffer lock (line 381 in `_on_audio_chunk`). GRU state corruption possible if a 512-frame inference is in flight when reset runs. | Claude Eng |
| R4 | MEDIUM | **`pyperclip` is an undeclared dependency.** `src/text_insertion.py:11` imports `pyperclip`, but `requirements.txt` does not list it. Pulling `text_inserter` into the Whisper hot path imports `pyperclip` on startup — if not installed, silent ImportError on first model load. | Codex |
| R5 | LOW | **Test mocks must return iterable, not dict.** `WhisperModel.transcribe()` returns a generator of `Segment` objects, not a dict. `test_downgrade_swap` and related mocks must return `iter([Mock(text="...")])` or similar, else `" ".join(s.text for s in segments)` raises `TypeError`. | Claude Eng |
| R6 | INFO | **UC-3 benchmark still smuggled into verification step 4.** User rejected UC-3 ("run 10 utterances on current openai-whisper before swap"). Step 4 still enforces it as a go/no-go gate. Remove or demote to optional. | both CEO voices |
| R7 | INFO | **Import-time side effects of `src.text_insertion`.** Importing the module fires `TextInserter()` constructor (line 396), which reads config, creates log dirs, opens pyperclip handle. Not a crash — but new startup coupling that operators should know about. Document in plan. | Codex |

### Round 2 Amendments

**R1 resolution (E3 correction):**
- In `_load()`: on any exception, set `self._load_error = str(exc)` AND `self._model = None` AND `self._loaded.set()` (so waiters unblock).
- In `wait_until_ready(timeout)`: after `self._loaded.wait(...)`, return `self._model is not None` so a caller sees "not ready" on failure.
- In `run()` (line 479): after `wait_until_ready`, if `self._transcriber._load_error` is non-None, log `"Whisper failed to load: {error}"` and exit(1) — don't proceed into mic loop.
- In `transcribe()` (line 133): after `if not self._loaded.is_set()` check, add `if self._model is None: logging.warning("Whisper model failed to load, dropping."); return None`.

**R2 resolution (Change 3 consistency):**
- **Decision: use `text_inserter.insert_text(text)` UNCONDITIONALLY for all typed text**, short or long. Remove the ">50 chars" heuristic. Rationale: `text_inserter` already optimizes internally (keystroke for short, clipboard for long based on its own config), and splitting logic across two places reintroduces the E5 failure mode.
- Update verification step 9: "dictate a long sentence; confirm single-paste undo (not character-by-character). Dictate a short word; confirm it appears via keystroke."

**R3 resolution (Silero lock scope):**
- Explicit nesting: at utterance end in `_on_audio_chunk`, do `with self._silero_lock: vad_model.reset_states()`. Do NOT hold `_buffer_lock` around `_silero_lock` (avoid lock-order issues). Release `_buffer_lock` first, then acquire `_silero_lock` for the reset.

**R4 resolution (pyperclip dep):**
- Add `pyperclip>=1.8.2` to `requirements.txt` alongside `faster-whisper>=1.0.0`.
- Add `shutil.which("xclip")` check at startup (xclip is pyperclip's Linux backend). Log a one-line warning if missing: `"xclip not found — clipboard paste will fall back to keystroke typing. Install: sudo apt install xclip"`.

**R5 resolution (test mocks):**
- For `test_downgrade_swap` and related tests: mock `WhisperModel.transcribe` to return `(iter([Mock(text="hello")]), Mock())` — a tuple of (generator, info) matching faster-whisper's real signature.
- Add explicit docstring on each test explaining the mock shape.

**R6 resolution (UC-3 benchmark):**
- Demote verification step 4 from blocking gate to optional diagnostic: "Optional: before the swap, record baseline RTF on current openai-whisper for curiosity/reference. Not a go/no-go — user has rejected this as a gate."

**R7 resolution (import side effects):**
- Add a one-line note to Change 3 amendment: "Note: `src.text_insertion` instantiates a `TextInserter()` singleton at import time (text_insertion.py:396). This reads config and creates log directories on first import. Acceptable trade-off for battle-tested behavior."

### Files to modify — updated

| File | Purpose |
|------|---------|
| `/home/ryan/voice-to-text-system/voice_typer_whisper.py` | Runtime + VAD + typing reuse + error path fixes (R1, R3). |
| `/home/ryan/voice-to-text-system/requirements.txt` | Add `faster-whisper>=1.0.0` **and** `pyperclip>=1.8.2` (R4). |
| `/home/ryan/.config/voice-to-text/config.ini` | Add Silero VAD config keys. |
| `/home/ryan/voice-to-text-system/tests/test_voice_typer_whisper.py` | 5 new mocked tests (R5 mock shape clarified). |

### Round 2 Consensus

| # | Dimension | Claude CEO | Claude Eng | Codex | Consensus |
|---|-----------|-----------|-----------|-------|-----------|
| 1 | R1 needed? | — | YES | YES | **CONFIRMED** |
| 2 | R2 needed? | — | — | YES | single-voice |
| 3 | R3 needed? | — | YES | — | single-voice |
| 4 | R4 needed? | — | — | YES | single-voice |
| 5 | R5 needed? | — | YES | — | single-voice |
| 6 | R6 needed? | YES | — | YES | **CONFIRMED** |
| 7 | Is amended plan shippable after R1–R7? | YES | YES | YES | **CONFIRMED** |

**VERDICT (Round 2):** Plan is ready to implement after R1–R7 amendments applied. All three voices agree the plan is "tactically shippable" now. No new strategic concerns. Scope creep is bounded (~30 lines added for R1 + R3 error/lock handling, 1 line for R4 dep, tests already in scope).


