#!/usr/bin/env python3
"""Generates awx-lab-episode-builder.json: Studio silent recording -> AI spoken narration -> Voicebox -> edit -> render. Run: python gen_lab_workflow.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(HERE, "gen_workflow.py")).read().split("# ---------------------------------------------------------------- triggers + config")[0])

add("Notes", "n8n-nodes-base.stickyNote", 1, {"content": "## AWX LAB episode builder\nFor episodes you record yourself in **AWX Studio** (Silent mode).\n\n1. Record in Studio, save the session folder into your `_projects` folder.\n2. Run this workflow: it cuts the recording (cuts, retakes dropped, time-lapses, callouts), has the AI turn your script into **spoken** narration, records it in your Voicebox voice (Whisper-checked), holds the last frame of a step when the narration is longer than the footage, adds title/end card, captions, chapters and music.\n3. You approve a preview sheet before the long render.\n\nNeeds `pipeline/server.py` running (see n8n/README.md). Edit **Config** first.", "height": 300, "width": 520}, -80, -300)
add("Lab episode form", "n8n-nodes-base.formTrigger", 2.2, {"path": "awx-lab-episode", "formTitle": "AWX from Zero - lab episode (Studio recording)", "formDescription": "Save the Studio session folder (recording.webm, session.json, ...) into your _projects folder first, then give its folder name.",
    "formFields": {"values": [{"fieldLabel": "Session folder name", "placeholder": "ep02-awx-install-2026-10-09", "requiredField": True}, {"fieldLabel": "Episode number", "fieldType": "number", "requiredField": True},
    {"fieldLabel": "Episode title", "requiredField": True}, {"fieldLabel": "Subtitle (optional)"}, {"fieldLabel": "Next episode title"}, {"fieldLabel": "Next episode tagline"}]}, "options": {}}, 0, 0)
S("Config", [("runner", "http://127.0.0.1:8787"), ("runnerBrowser", "http://127.0.0.1:8787"), ("token", ""), ("llmModel", "nvidia/llama-3.3-nemotron-super-49b-v1"), ("project", "={{ $json['Session folder name'] }}")], 220, 0)
link("Lab episode form", "Config")
add("Project info", "n8n-nodes-base.httpRequest", 4.2, {"url": "={{ %s.runner }}/project?name={{ encodeURIComponent(%s.project) }}" % (CFG, CFG), "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]}, "options": {}}, 440, 0)
link("Config", "Project info")
add("Session present?", "n8n-nodes-base.if", 2.2, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"id": "c1", "leftValue": "={{ $json.has_session }}", "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 660, 0)
link("Project info", "Session present?")
add("Stop: no session", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'No session.json + recording.webm in ' + $('Config').first().json.project + '. In AWX Studio use Silent mode and save the session folder inside your _projects folder.' }}"}, 660, 300)
link("Session present?", "Stop: no session", 1)
add("Stop: pipeline failed", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'Stage failed: ' + ($json.status || '') + '\\n' + ($json.error || '') + '\\n' + ($json.result && $json.result.error ? $json.result.error : '') + '\\n' + ($json.log_tail || '') }}"}, 2400, 800)
RUN("Doctor", "doctor", 880, 0, voicebox=True); link("Session present?", "Doctor", 0)
IF("Environment OK?", "={{ $json.status }}", "ok", 1100, 0); link("Doctor", "Environment OK?"); link("Environment OK?", "Stop: pipeline failed", 1)
RUN("Cut the recording (lab-plan)", "lab-plan", 1320, 0); link("Environment OK?", "Cut the recording (lab-plan)", 0)
IF("Cut OK?", "={{ $json.status }}", "ok", 1540, 0); link("Cut the recording (lab-plan)", "Cut OK?"); link("Cut OK?", "Stop: pipeline failed", 1)
add("Lab steps", "n8n-nodes-base.httpRequest", 4.2, {"url": "={{ %s.runner }}/file?project={{ encodeURIComponent(%s.project) }}&path=lab_steps.json" % (CFG, CFG), "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]}, "options": {}}, 1760, 0)
link("Cut OK?", "Lab steps", 0)

PROMPT_JS = r'''
const cfg = $('Config').first().json;
const lab = $('Lab steps').first().json;
const prev = $json.errors ? $json : null;
const steps = lab.steps.filter(s => (s.say || '').trim()).map(s => ({id: s.id, chapter: s.chapter, available_s: Math.round((s.out_end - s.out_start) * 10) / 10, script: s.say}));
const sys = `You turn a presenter's screen-recording script into SPOKEN narration for the YouTube series "AWX from Zero" (channel Venu Automates), beginner audience. A cloned voice reads it, then speech-to-text checks it. Output ONE JSON object and nothing else.
RULES:
- Stay faithful to each step's script: same facts, same order. Do not invent facts, commands or numbers.
- NO digits anywhere. Spell everything as spoken: numbers ("four vCPUs", "sixty gigabyte disk"), ports ("thirty thousand eighty"), versions ("two point nineteen point one"), letters ("S E Linux", "K three S"). Put the on-screen spelling in "display" ([["spoken","shown"],...]) so captions read "SELinux", "k3s", "30080", "24.6.1".
- Short spoken sentences, max 22 words each, contractions fine, plain and warm. Never read flags or file paths aloud; describe what the command does.
- The video shows the command being typed and running while you speak. Length per step: aim for at most about 2.2 words per second of available_s plus 10 words; if the script is longer, tighten it (the video will freeze the last frame for any overrun, so do not pad).
- Prefer "containers" to "pods" when ambiguous (speech-to-text mishears it).
- Also write "open": 3 sentences (hook, what we do today, what the viewer gets) and "close": 3 sentences (recap, snapshot/next-step advice from the script if any, then "All the commands are in the repo, in the epNN folder" with the number spelled out).
OUTPUT SHAPE: {"open":["..."],"steps":{"<step id>":["..."]},"close":["..."],"display":[["spoken","shown"]]}`;
let user = `Episode ${$('Lab episode form').first().json['Episode number']}: ${$('Lab episode form').first().json['Episode title']}\nSteps (in order):\n` + JSON.stringify(steps, null, 1);
if (prev) user += `\n\nYour previous answer failed validation. Fix these problems and return the full corrected JSON:\n- ` + prev.errors.join('\n- ');
return [{json:{model: cfg.llmModel, messages:[{role:'system',content:sys},{role:'user',content:user}], errors: undefined}}];
'''
add("Build prompt", "n8n-nodes-base.code", 2, {"jsCode": PROMPT_JS}, 1980, 0); link("Lab steps", "Build prompt")
add("Spoken rewrite (NVIDIA LLM)", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "https://integrate.api.nvidia.com/v1/chat/completions", "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
    "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "={{ JSON.stringify({model: $json.model, messages: $json.messages, temperature: 0.2, top_p: 0.9, max_tokens: 6000}) }}", "options": {"timeout": 300000}},
    2200, 0, creds={"openAiApi": {"id": "", "name": "OpenAI account"}})
link("Build prompt", "Spoken rewrite (NVIDIA LLM)")

VALIDATE_JS = r'''
const cfg = $('Config').first().json;
const form = $('Lab episode form').first().json;
const lab = $('Lab steps').first().json;
const raw = ($json.choices?.[0]?.message?.content || '').trim();
const errors = [];
let data = null;
try { const m = raw.match(/\{[\s\S]*\}/); data = JSON.parse(m ? m[0] : raw); } catch (e) { errors.push('Output is not valid JSON: ' + e.message); }
const words = t => t.split(/\s+/).filter(Boolean).length;
const check = (label, arr, min) => {
  if (!Array.isArray(arr) || arr.length < min) { errors.push(`${label}: needs ${min}+ sentences`); return; }
  arr.forEach((t, i) => {
    if (typeof t !== 'string') { errors.push(`${label} ${i}: not a string`); return; }
    if (/\d/.test(t)) errors.push(`${label} sentence ${i}: contains digits - spell them out ("${t.slice(0,50)}")`);
    if (words(t) > 32) errors.push(`${label} sentence ${i}: longer than 32 words - split it`);
  });
};
if (data) {
  check('open', data.open, 2); check('close', data.close, 2);
  lab.steps.filter(s => (s.say || '').trim()).forEach(s => {
    const arr = data.steps?.[s.id];
    check('step ' + s.id, arr, 1);
    if (Array.isArray(arr)) {
      const avail = s.out_end - s.out_start, w = arr.reduce((n, t) => n + words(t), 0);
      if (w > 2.6 * avail + 35) errors.push(`step ${s.id}: ${w} words is too long for ${avail.toFixed(0)}s of footage - shorten to about ${Math.round(2.2 * avail + 10)} words`);
    }
  });
}
const attempt = $runIndex + 1;
if (errors.length) return [{json:{ok:false, errors:errors.slice(0,12), attempt}}];
const segs = [{id:'open', chapter:'Intro', sentences:data.open}];
lab.steps.filter(s => (s.say || '').trim()).forEach(s => segs.push({id:s.id, chapter:s.chapter, sentences:data.steps[s.id]}));
segs.push({id:'close', chapter:'Wrap up', sentences:data.close});
const num = Number(form['Episode number']);
const episode = {series:'AWX from Zero', number:num, title:form['Episode title'], subtitle:form['Subtitle (optional)'] || '', channel:'Venu Automates', handle:'@VenAutomates',
  folder:'ep' + String(num).padStart(2,'0'), repo:'github.com/Venuvgp19/Youtube-Tutorials-Awx', next:{title:form['Next episode title'] || 'Next episode', sub:form['Next episode tagline'] || ''},
  description: form['Episode title'], output_name:`AWX from Zero - Ep ${String(num).padStart(2,'0')} - ${form['Episode title']}`.replace(/[\\/:*?"<>|]/g,'')};
return [{json:{ok:true, attempt, files:{'narration.json':{segments:segs}, 'scenes.json':{episode, gaps:{sentence:0.32}, display:data.display || []}}}}];
'''
add("Validate narration", "n8n-nodes-base.code", 2, {"jsCode": VALIDATE_JS}, 2420, 0); link("Spoken rewrite (NVIDIA LLM)", "Validate narration")
add("Narration valid?", "n8n-nodes-base.if", 2.2, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"id": "c1", "leftValue": "={{ $json.ok }}", "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2640, 0)
link("Validate narration", "Narration valid?")
IF("Retries left?", "={{ $json.attempt }}", "3", 2640, 200); nodes[-1]["parameters"]["conditions"]["conditions"][0]["operator"] = {"type": "number", "operation": "lt"}
link("Narration valid?", "Retries left?", 1); link("Retries left?", "Build prompt", 0)
add("Narration failed", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'AI narration failed validation 3 times: ' + $json.errors.join('; ') }}"}, 2860, 300); link("Retries left?", "Narration failed", 1)
add("Write narration + meta", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "={{ %s.runner }}/write" % CFG, "sendHeaders": True, "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]},
    "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "={{ JSON.stringify({project: %s.project, files: $json.files}) }}" % CFG, "options": {}}, 2860, -100)
link("Narration valid?", "Write narration + meta", 0)

RUN("Narrate (Voicebox + Whisper check)", "narrate", 3080, -100); link("Write narration + meta", "Narrate (Voicebox + Whisper check)")
IF("Narration clean?", "={{ $json.status }}", "ok", 3300, -100); link("Narrate (Voicebox + Whisper check)", "Narration clean?")
add("Review flagged lines", "n8n-nodes-base.wait", 1.1, {"resume": "form", "formTitle": "Narration needs a listen",
    "formDescription": "={{ 'These lines did not match what Whisper heard after 4 seeds. Listen in Voicebox (history) or re-word them in narration.json and re-run.<br><br>' + ($json.result.flagged || []).map(f => '<b>#' + f.k + '</b> expected: ' + f.text + '<br>&nbsp;&nbsp;heard: ' + f.heard).join('<br><br>') }}",
    "formFields": {"values": [{"fieldLabel": "Decision", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "accept as is"}, {"option": "abort"}]}, "requiredField": True}]}, "options": {}}, 3520, 150)
link("Narration clean?", "Review flagged lines", 1)
IF("Accepted?", "={{ $json.Decision }}", "accept as is", 3740, 150); link("Review flagged lines", "Accepted?"); link("Accepted?", "Stop: pipeline failed", 1)
RUN("Compose: video + voice (lab-build)", "lab-build", 3960, -100); link("Narration clean?", "Compose: video + voice (lab-build)", 0); link("Accepted?", "Compose: video + voice (lab-build)", 0)
IF("Compose OK?", "={{ $json.status }}", "ok", 4180, -100); link("Compose: video + voice (lab-build)", "Compose OK?"); link("Compose OK?", "Stop: pipeline failed", 1)
RUN("Preview frames", "preview", 4400, -100); link("Compose OK?", "Preview frames", 0)
IF("Preview OK?", "={{ $json.status }}", "ok", 4620, -100); link("Preview frames", "Preview OK?"); link("Preview OK?", "Stop: pipeline failed", 1)
add("Approve preview", "n8n-nodes-base.wait", 1.1, {"resume": "form", "formTitle": "Approve the preview before the long render",
    "formDescription": "={{ 'Check chapters, captions, title/end cards and that freeze-holds feel right. Editor tasks you may still want to do by hand (zoom/note/mark markers) are listed in lab_steps.json.<br><a href=\"' + %s.runnerBrowser + '/file?project=' + %s.project + '&path=previews/sheet.jpg\" target=\"_blank\">Open the contact sheet</a><br><img style=\"max-width:100%%\" src=\"' + %s.runnerBrowser + '/file?project=' + %s.project + '&path=previews/sheet.jpg\">' }}" % (CFG, CFG, CFG, CFG),
    "formFields": {"values": [{"fieldLabel": "Decision", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "approve"}, {"option": "reject"}]}, "requiredField": True}, {"fieldLabel": "Notes (if rejecting)", "fieldType": "textarea"}]}, "options": {}}, 4840, -100)
link("Preview OK?", "Approve preview", 0)
IF("Approved?", "={{ $json.Decision }}", "approve", 5060, -100); link("Approve preview", "Approved?")
add("Rejected", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'Preview rejected: ' + ($json['Notes (if rejecting)'] || 'no notes') + '. Re-record or fix in Studio markers, or edit narration.json, then re-run.' }}"}, 5060, 300); link("Approved?", "Rejected", 1)
RUN("Render video (long)", "render", 5280, -100); link("Approved?", "Render video (long)", 0)
IF("Render OK?", "={{ $json.status }}", "ok", 5500, -100); link("Render video (long)", "Render OK?"); link("Render OK?", "Stop: pipeline failed", 1)
RUN("Mix voice + music", "mix", 5720, -100); link("Render OK?", "Mix voice + music", 0)
IF("Mix OK?", "={{ $json.status }}", "ok", 5940, -100); link("Mix voice + music", "Mix OK?"); link("Mix OK?", "Stop: pipeline failed", 1)
RUN("Package (srt + description)", "package", 6160, -100); link("Mix OK?", "Package (srt + description)", 0)
S("Done", [("message", "={{ 'Lab episode ready: ' + %s.project }}" % CFG), ("files", "={{ ($json.result.files || []).join('\\n') }}")], 6380, -100, keep=False)
link("Package (srt + description)", "Done")

wf = {"name": "AWX lab episode builder (Studio recording)", "nodes": nodes, "connections": conns, "active": False, "settings": {"executionOrder": "v1"}, "pinData": {}, "meta": {"templateCredsSetupCompleted": False}}
json.dump(wf, open(os.path.join(HERE, "awx-lab-episode-builder.json"), "w"), indent=2)
print(len(nodes), "nodes")
