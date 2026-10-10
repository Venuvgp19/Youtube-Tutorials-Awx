# AWX Studio

Recording studio for the AWX from Zero series. Teleprompter with commands to type, screen + mic recording, and edit markers (retake, cut, speed up, zoom, callout) that an editor, Claude or Nemotron, turns into a finished cut.

## Use

1. Double-click `serve.bat` (needs Python). Chrome opens `http://localhost:8765/index.html`.
2. Pick the episode, tick the pre-flight list, choose **Live voice** or **Silent (narrate later)**.
3. Press **Pop out prompter**, then **Record**. In Chrome's picker choose the VM/terminal **window** only.
4. Work through the steps. Click **Next** in the pop-out (it stays on top). Use the markers as you go:
   - **Pause** (⏸ button in the pop-out and main panel, or press `P`): stops recording during downloads, installs and reboots; the paused time is not in the video and markers stay in sync. Press again to resume.
   - **Retake**: you fumbled, redo the step. The bad take is dropped automatically.
   - **Cut**: press at the start and again at the end of a mistake or dead stretch.
   - **Speed**: press at the start and end of a wait (image downloads). Time-lapsed, audio muted.
   - **Zoom / Callout / Note / Mark**: type text first for Callout and Note.
5. **Stop**, then **Save session folder…** and pick `Desktop\YTVideo\sessions`.
6. Tell Claude "session ready". It reads `session.json` and `frames/`, runs `tools/plan_edit.py`, adds narration and music, and delivers the video.

Format and editing rules: `SESSION_FORMAT.md`. Add episodes: drop `scripts/epNN.json` in and run `python build.py`, or use "Load script JSON…".
