# AWX from Zero: episode playbook (lessons from Ep 02)

Fed to the narration LLM as house rules. Update after every episode.

## What a good episode looks like
- Target 8 to 14 minutes. Every minute of the final video must have either speech or something clearly happening on screen. No silent stretches over 4 seconds, except a deliberate pause on a result.
- Roughly one spoken sentence for every 6 to 10 seconds of footage; speech should cover about half the runtime or more.
- The recording is raw. Long waits (installs, pulls, "pods creating") are CUT or sped up; narration is written for the edited footage, not the raw one.

## Structure (use these step ids)
1. `open` (title card, 2 to 3 sentences): hook, what we do, what you get. Narrated over the title card; never leave it silent.
2. `intro`: first footage step, an overview of what is on screen.
3. One step per real action (`vm`, `check`, `fw`, `k3s`, `operator`, `awx`, ...). A step is 30 to 120 seconds of edited footage. Give each a chapter title and a short `sub` line (max 8 words) for the lower-third.
4. Troubleshooting is its own steps: say what failed, why, and the fix ("When the API goes down", "Apply again"). Narrate the failure; never skip it, viewers hit it too.
5. `wrapup`: recap, snapshot advice, what comes next.
6. `close` (end card, 3 sentences): repo pointer, next episode teaser, subscribe.
Never reuse `open`/`close` as footage step ids (this caused duplicate narration and a mis-timed intro).

## Narration style
- Beginner audience, warm, plain, short sentences (max 22 words), contractions fine.
- Match the picture: say what is on screen NOW. If the screen shows a command running, describe what it does and why, not the flags or paths.
- No digits. Spell numbers, ports, versions and letters as spoken; put on-screen spelling in `display`.
- Say "containers" instead of "pods" when ambiguous (speech-to-text mishears it).
- No filler, no repeated sentences across steps, no claims not in the script.
- 2.2 words per second of available time, plus about 10 words. Longer than that and the video freezes on the last frame.

## Editing rules the pipeline applies
- Idle footage is cut automatically (no screen activity for a few seconds); long waits are sped up.
- Voice starts 0.4 s after each step starts. Title-card voice at 0.7 s. Close voice sits on the end card.
- Lower-thirds (chapter plus `sub`) appear 1.2 s into each step for 6 s. Chapter pills and captions are burned in.
- Personal desktop areas (wallpaper, taskbar) must not be visible; crop or blur if they appear.

## Checks before approving the preview
- Duration under `max_minutes`; no WARNING overlap lines in the lab-build log.
- Voice coverage reasonable (see ratio above); title card is voiced; captions and chapters are unique.
- Whisper flags: spelling variants are fine (the checker is word and character tolerant); real mismatches get re-worded.
