# n8n: AWX episode builders

Two workflows (n8n -> Workflows -> Import from file):
- `awx-episode-builder.json` - slide-style episodes (like Ep 1/2): AI writes script + slides.
- `awx-lab-episode-builder.json` - **lab episodes: you record the screen silently in AWX Studio**, the workflow edits it and adds your cloned voice (see "Lab workflow" below).

## One-time setup
1. On the PC: `python pipeline/server.py --projects "C:\Users\praka\Desktop\YTVideo\_projects"` (keep it running next to Voicebox).
2. In n8n open **Config** and set `runner` (and `runnerBrowser`, the same URL as your browser sees it). n8n in Docker: start the server with `--host 0.0.0.0` and use `http://host.docker.internal:8787`.
3. Create a credential **Header Auth** named `NVIDIA API`: header `Authorization`, value `Bearer nvapi-...`; select it on the node **Author (NVIDIA LLM)**. Check the model name in **Config -> llmModel** against the NVIDIA catalogue.
4. No Execute Command node is used, so nothing needs to be unblocked in n8n.

## Flow
Form (title, outline) -> LLM drafts `narration.json` + `scenes.json` -> **Validate script** (no digits, sentence length, scene/segment/state consistency, <=4 elements per slide; retries the LLM 3x with the errors) -> write project -> doctor -> **narrate** (Voicebox clip -> Whisper check -> seed retries) -> if any line is flagged you get a review form -> build -> slides -> **preview contact sheet: you approve** -> render -> mix -> package.
Manual trigger = re-run an existing project folder (e.g. after editing `scenes.json`); it skips authoring.

## Lab workflow (Studio recording -> finished video)
1. Record in AWX Studio in **Silent** mode. When saving, choose your `_projects` folder; Studio creates a `<slug>-<date>` folder there.
2. Run the form of **AWX lab episode builder**: session folder name, episode number/title, next episode.
3. It cuts the recording (Cut/Retake/Speed/Callout markers applied), the AI rewrites each step's `say` text as spoken narration (digits spelled out, length matched to the footage), Voicebox + Whisper produce and verify the clips, then it composes title card + edited recording + end card. If a step's narration is longer than its footage, the last frame is held. You approve the preview sheet, then render, mix music, package.
Not automated: Zoom / Note / Mark markers (listed in `lab_steps.json`).

## Honest limits
- Narration, captions, timing, render and mix are the same code as Ep 2. **Slide layouts authored by the LLM will be plainer than the hand-built ones** - that is what the preview gate is for. Edit `scenes.json` and re-run if it is not right.
- Voicebox must be running and its queue free; a hung job makes a narrate step time out (4 min per attempt).
- Long steps (narrate, render) hold one HTTP request open (timeout set to 2 h).
- Lab workflow: the cut is only as good as your Studio markers; the AI only rewrites wording, it never sees the video.
`gen_workflow.py` regenerates the JSON.
