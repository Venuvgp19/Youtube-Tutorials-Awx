# AWX Studio session format (`awx-recording-session/1`)

For humans and for AI editors (Claude, Nemotron). Read this, then `session.json`, then look at `frames/`.

## Folder produced by the studio

```
<slug>-<date>/
  recording.webm     screen capture (VP9). In Live mode it carries the voice (Opus). Browser WebM has no duration header: let ffmpeg regenerate timestamps (-fflags +genpts, plan_edit.py does it).
  mic.webm           clean mic-only track (Live mode only), same clock as recording.webm
  session.json       everything below
  script.json        the script that was on the prompter (steps, commands, say text)
  frames/            JPEG still at each step start and each mark/zoom/callout/retake, named NNN-<type>-<step>.jpg
```

All times are seconds from the start of `recording.webm` (t = 0 is the first video frame, give or take 0.1 s).

## session.json

| key | meaning |
| --- | --- |
| `episode` | `{number, slug, title}` |
| `mode` | `live` (voice recorded with the screen) or `silent` (screen only; narration is added later with the cloned voice) |
| `recording` | `file`, `mic_file`, `duration_s`, `width`, `height`, `fps`, `audio_in_recording` |
| `steps[]` | each script step: `id`, `title`, `chapter`, `start_s`, `end_s` (of the LAST visit), `visited` |
| `markers[]` | raw event log: `{t, type, step, note?, frame?}` |
| `ranges[]` | derived: `{type: cut or speed, start, end, note, step}` |
| `takes[]` | `{step, from, to, final?}`. A take with `to` set was abandoned by Retake and must be dropped |
| `frames[]` | `{file, t}` index of the stills |
| `script` | full script copy (steps with `cmd` lines and `say` text) |

### Marker types and what they mean for the edit

| type | presses | edit meaning |
| --- | --- | --- |
| `step` | Next / Back / step list | A new script step starts. Basis for chapters and for aligning narration |
| `retake` | Retake | The take of the current step since its last start is bad. Drop `[take.from, take.to]`; the new take starts now |
| `cut_start` / `cut_end` | Cut (toggle) | Remove this stretch (mistakes, dead air). An open cut is closed at stop |
| `speed_start` / `speed_end` | Speed (toggle) | Time-lapse this stretch (waits, image pulls). Default 8x; write `x16` in the note to change. Audio muted |
| `zoom` | Zoom | Zoom in about 1.6x for 4 s starting here. Look at the frame to choose the region (usually the last terminal lines or a highlighted line) |
| `callout` | Callout + text | Show `note` on screen for about 3.5 s |
| `note` | Note | Private instruction to the editor, never shown |
| `mark` | Mark | Something to look at (good moment, mistake, thumbnail candidate) |
| `chapter` | Chapter | Extra chapter start inside a step |

## How to edit

1. `python3 tools/plan_edit.py <session-folder> --run` produces in `<session>/edit/`:
   - `edl.json` kept segments with speed, step and chapter times in OUTPUT time, callouts, `editor_tasks`
   - `chapters.txt` YouTube chapters in output time
   - `narration_plan.json` one entry per step with the `say` text and its output start/end (Silent mode: generate one cloned-voice clip per entry)
   - `render.sh` / `edited.mp4` the ffmpeg render (cuts, retakes dropped, time-lapses, callouts, 1080p)
2. `editor_tasks` (zoom, note, mark) are not automated. For each, open the `frame` and apply the change, for example an ffmpeg `crop`+`scale` between `out_t` and `out_t + 4`.
3. Silent mode: add narration with the Voicebox pipeline (`pipeline/`), start each clip at `out_start`, check each with Whisper, then mix with music (`mix.sh`). Live mode: loudness-normalise the voice and duck music the same way.
4. Look at the result before delivering: frames at each chapter start, the end of each time-lapse, and each callout.

## Rules for editors

- Never edit `recording.webm` in place. Write to `edit/`.
- Do not show the AWX admin password: if a frame shows it, blur or cut it.
- A step that was not visited (`visited: false`) was skipped by the presenter: do not narrate it.
- If markers contradict each other, trust the later one and say so in the delivery note.
- Keep what the presenter actually did on screen. Do not invent terminal output.

## Script format (`awx-script/1`)

`scripts/epNN.json`: `{episode, slug, title, preflight[], steps[{id, title, chapter, show, cmd[], say, watch?, expect_wait?}]}`. Load any script with "Load script JSON…" in the studio.
