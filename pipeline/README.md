# AWX video pipeline

The exact stages used to make Ep 1 and Ep 2, packaged so n8n (or you) can run them on any episode.

```
narration.json + scenes.json  ->  narrate  ->  build  ->  slides  ->  preview  ->  render  ->  mix  ->  package
                                  (Voicebox   (voiceover,  (3840x2160   (contact   (30 fps,   (loudnorm,  (.srt +
                                   + Whisper   timeline,    PNGs)        sheet)     resumable) ducked     YouTube
                                   verify,     captions,                                       music)      description)
                                   seed retry) chapters)
```

## Setup (Windows PC that runs Voicebox)
1. Python 3.10+ and ffmpeg on PATH (`winget install Gyan.FFmpeg`), then `pip install -r requirements.txt`.
2. Start Voicebox (profile **Venu**) as usual. Fonts are bundled in `fonts/` - nothing else to install.
3. `python awxvideo.py doctor examples/ep02 --voicebox` must say `"status": "ok"`.

## Project folder
`project.json` (Voicebox url/profile/seeds/threshold), `narration.json` (segments of sentences), `scenes.json` (episode meta, slide scenes keyed to narration segments, caption `display` fixes), `music.mp3`, `shots/` (browser screenshots, optional).
`examples/ep02` is the real Ep 2 expressed in this format. Slide element types are documented at the top of `slidelib.py`.

## Commands
`python awxvideo.py <doctor|narrate|build|slides|preview|render|mix|package|all> <project>` - each prints one JSON status line.
- **narrate** re-uses clips whose text did not change, so editing one sentence regenerates one clip. Lines that never match Whisper after all seeds are listed as `flagged` in `verify_report.json`.
- **render** writes ~73 s parts and concatenates (the 3-part approach used for Ep 2); re-run to resume.

## Runner for n8n
`python server.py --projects C:\path\to\_projects` exposes the commands over HTTP on 127.0.0.1:8787 (see docstring). Use `--host 0.0.0.0` if n8n runs in Docker (then Config.runner = `http://host.docker.internal:8787`).

## Lab episodes (recorded in AWX Studio, Silent mode)
Save the Studio session folder (`recording.webm`, `session.json`, ...) inside your projects folder, then:
`lab-plan` (cuts, dropped retakes, time-lapses, callouts -> `edit/edited.mp4`, writes `lab_steps.json`) -> write `narration.json` (spoken form, one segment per step, plus `open` and `close`) and `scenes.json` (episode meta + `display`) -> `narrate` -> `lab-build` -> `preview` -> `render` -> `mix` -> `package`.
`lab-build` starts each step's narration when the step starts. If the narration is longer than the footage, the last frame of that step is held (freeze) so voice and picture never drift. Title and end cards, chapters, captions and ducked music are the same as slide episodes.
Zoom / note / mark markers are not automated; they are listed in `lab_steps.json` (`editor_tasks`). Live-mode recordings (voice already in the video) are rejected by `lab-plan`.

## Lab episodes, Ep 4/5 finishing (`awxpro.py`)
The look of Ep 4 and Ep 5: footage cut to the voice, chapter lower-thirds, keyword callouts, ducked music, thumbnail, YouTube text, and a size-capped export.
One-time: `pip install -r requirements.txt` then `python -m playwright install chromium` (draws the graphics layer).
After `lab-plan` and `narrate` (use `"profile": "Venu Short"` in `project.json`):

`pro-compose` -> `pro-events` -> `pro-extras` -> `pro-overlay` (about 15 min) -> `pro-final` (about 15 min)

- **pro-compose**: sentences are grouped into chunks; each chunk gets its own slice of the step's footage. Footage much longer than the voice is jump-cut (1.15x); a bit longer is sped up; shorter than 0.8x is slowed to 0.8x and the last frame is held. Writes `voiceover_raw.wav` and `pro/timeline.json`.
- **pro-events**: chapter lower-thirds (one per step except first and last) and callouts from `pro.json`. A callout `kw` is a phrase from the spoken narration; the graphic appears when it is spoken. Reports `missing_keywords`.
- **pro-extras**: `epNN_thumbnail.png`, `youtube_epNN.txt` (title, description, chapters, hashtags, tags), `review_notes.txt` (frames to blur, per-chunk timing).
- **pro-overlay**: renders `pro/overlay.mov` (transparent graphics layer).
- **pro-final**: title and end card, music (volume 0.28, ducked under the voice), then `AWX EpNN - Motion Graphics.mp4` (set `"variants": ["text","clean"]` in pro.json to also get `AWX EpNN - Clean.mp4`), each under `size_cap_mb` (default 27) with 2-pass x264.
`pro.json` is optional, every key too: see `examples/ep05/pro.json` for the full Ep 5 file. To pin a chunk to exact footage use `"ranges": {"<step id>:<chunk number>": [from_s, to_s]}` (seconds in `edit/edited.mp4`).
Limits: the footage for a step is shared out by chunk length, so a callout can appear a second or two early or late; fix with `offset` on the callout or a `ranges` entry. If narration is much longer than a step's footage you get long freezes: record that step slower or shorten the narration.
