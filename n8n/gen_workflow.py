#!/usr/bin/env python3
"""Generates awx-episode-builder.json (n8n import file). Run: python gen_workflow.py"""
import json, os

nodes, conns = [], {}
_pos = {}


def add(name, typ, ver, params, x, y, creds=None, **extra):
    n = {"parameters": params, "id": f"n{len(nodes) + 1:02d}", "name": name, "type": typ, "typeVersion": ver, "position": [x, y]}
    if creds: n["credentials"] = creds
    n.update(extra)
    nodes.append(n)
    return name


def link(a, b, out=0, inp=0):
    conns.setdefault(a, {"main": []})
    m = conns[a]["main"]
    while len(m) <= out: m.append([])
    m[out].append({"node": b, "type": "main", "index": inp})


def S(name, assigns, x, y, keep=True):
    return add(name, "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [{"id": f"a{i}", "name": k, "value": v, "type": "string"} for i, (k, v) in enumerate(assigns)]}, "includeOtherFields": keep, "options": {}}, x, y)


def IF(name, left, right, x, y, op="equals"):
    return add(name, "n8n-nodes-base.if", 2.2, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
               "conditions": [{"id": "c1", "leftValue": left, "rightValue": right, "operator": {"type": "string", "operation": op}}], "combinator": "and"}, "options": {}}, x, y)


CFG = "$('Config').first().json"


def RUN(name, cmd, x, y, voicebox=False):
    body = "={{ JSON.stringify({project: %s.project, cmd: '%s'%s}) }}" % (CFG, cmd, ", voicebox: true" if voicebox else "")
    return add(name, "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "={{ %s.runner }}/run" % CFG, "sendHeaders": True,
               "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]}, "sendBody": True, "contentType": "raw", "rawContentType": "application/json",
               "body": body, "options": {"timeout": 7200000}}, x, y)


# ---------------------------------------------------------------- triggers + config
add("Notes", "n8n-nodes-base.stickyNote", 1, {"content": "## AWX episode builder\nSame stages as the manual pipeline: author script -> Voicebox narration (Whisper-verified) -> slides + timeline -> **you approve the preview** -> render -> mix -> package.\n\nNeeds `pipeline/server.py` running on the PC (see n8n/README.md). Edit the **Config** node first (runner URL, LLM model).\n\nTwo entry points: the form (new episode, AI authors the script) or the manual trigger (re-run an existing project folder).", "height": 260, "width": 460}, -80, -260)
add("New episode brief", "n8n-nodes-base.formTrigger", 2.2, {"path": "awx-episode", "formTitle": "AWX from Zero - new episode", "formDescription": "AI drafts narration + scenes from your outline, then the pipeline builds the video. You approve before the long render.",
    "formFields": {"values": [{"fieldLabel": "Project folder", "placeholder": "ep03", "requiredField": True}, {"fieldLabel": "Episode number", "fieldType": "number", "requiredField": True},
    {"fieldLabel": "Episode title", "requiredField": True}, {"fieldLabel": "Subtitle (optional)"}, {"fieldLabel": "Outline / talking points", "fieldType": "textarea", "requiredField": True},
    {"fieldLabel": "Next episode title"}, {"fieldLabel": "Next episode tagline"}, {"fieldLabel": "Target length in minutes (10-15, max 15)", "fieldType": "number", "placeholder": "10"}]}, "options": {}}, 0, 0)
add("Re-run existing project", "n8n-nodes-base.manualTrigger", 1, {}, 0, 200)
S("Existing project folder", [("Project folder", "ep02")], 220, 200, keep=False)
S("Config", [("runner", "http://127.0.0.1:8787"), ("runnerBrowser", "http://127.0.0.1:8787"), ("token", ""), ("llmModel", "nvidia/nemotron-3-super-120b-a12b"),
    ("project", "={{ $json['Project folder'] }}"), ("brief", "={{ $json['Outline / talking points'] || '' }}")], 440, 100)
link("New episode brief", "Config"); link("Re-run existing project", "Existing project folder"); link("Existing project folder", "Config")
IF("Has a brief?", "={{ $json.brief }}", "", 660, 100, op="notEmpty")
link("Config", "Has a brief?")

# ---------------------------------------------------------------- authoring
add("Project info", "n8n-nodes-base.httpRequest", 4.2, {"url": "={{ %s.runner }}/project?name={{ encodeURIComponent(%s.project) }}" % (CFG, CFG), "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]}, "options": {}}, 880, 0)
link("Has a brief?", "Project info", 0)

PROMPT_JS = r'''
const cfg = $('Config').first().json;
const form = $('New episode brief').first().json;
const info = $('Project info').first().json;
const prev = $json.errors ? $json : null;
const slideDoc = `Slide scene = {"id":"vm","label":"STEP 1","title":"The virtual machine","states":[{"i":1},{"i":2}],"elements":[...]}
 - id must equal a narration segment id. "states" are moments inside that segment: {"i": sentence index, "frac": 0..1 (optional), "off": seconds (optional)}. State 0 is the initial look; states[0] starts state 1, and so on.
 - Elements stack top to bottom. Each accepts "from" (first state it is visible, default 0) and "to" (first state hidden).
 - {"type":"tiles","items":[{"big":"4","small":"vCPU","from":0,"glow_at":[0]}],"cols":3,"h":190,"bs":64,"glow":[0]}   (3-4 tiles max; items can appear later via their own "from")
 - {"type":"term","title":"root@awx-lab","lines":["$ command","output line"],"hl":{"1":[0]},"size":30}   ("$ " = typed command; hl maps state -> highlighted line indexes; max ~9 lines, line length < 70)
 - {"type":"cards","items":[{"title":"..","sub":"..","mono":false,"from":1}],"numbered":true,"stacked":false,"h":125}   (max 4 cards; the card whose "from" equals the current state glows)
 - {"type":"note","title":"..","sub":"..","mono_sub":"..","red":false,"from":2}
 - {"type":"pill","text":"..","red":false,"from":2,"to":3}   (short call-out under the content)
 Keep total stacked height under ~650 px: roughly 1 term of 5 lines + 1 tiles row + 1 pill. Never put more than 4 elements on one slide.`;
const example = ${JSON.stringify(EXAMPLE)};
const sys = `You write scripts and on-screen scenes for the YouTube series "AWX from Zero" (channel Venu Automates), for a beginner audience. Output ONE JSON object and nothing else.
NARRATION RULES (spoken by a cloned voice, then checked by speech-to-text):
- Segments of 3-5 short spoken sentences, max 22 words each. One idea per sentence. Plain, warm, direct; contractions are fine.
- First segment id "open" (chapter "Intro"): hook + what we build + what they get. Last segment id "close" (chapter "Wrap up"): recap, next episode teaser, "All the commands are in the repo, in the epNN folder" (spell the number, e.g. ep zero three).
- NO digits anywhere in narration. Spell everything as spoken: ports ("thirty thousand eighty"), versions ("two point nineteen point one"), letters ("S E Linux", "K three S"). Put the on-screen spelling in "display" ([["spoken","shown"],...]) so captions read "SELinux", "k3s", "30080".
- Say commands by purpose, never read flags aloud. Avoid hard-to-hear words; prefer "containers" over "pods" when ambiguous.
- Every segment after the first has "chapter" (2-4 words, shown as a YouTube chapter).
SCENE RULES: one slide scene per middle segment (not for open/close). Each narrated moment gets a visual change: command appears when it is mentioned, the key lines highlight while they are explained, warnings use red pills. Only kind "slide" scenes - browser screenshots are not available for new episodes unless listed here: ${JSON.stringify(info.shots || [])}.
SLIDE SPEC:
${slideDoc}
OUTPUT SHAPE: {"narration":{"segments":[{"id":"open","chapter":"Intro","sentences":["..."]}]},"scenes":[ ...slide scenes... ],"display":[["spoken","shown"]]}
EXAMPLE (abridged, from episode 2):
${example}`;
const target = Math.min(15, Math.max(5, Number(form['Target length in minutes (10-15, max 15)']) || 10));
const budget = Math.round(target * 60 * 2.6);
let user = `LENGTH: the finished video must run about ${target} minutes (hard maximum 15). Voice speaks ~3 words per second, so write about ${budget} narration words in total across 8-14 segments of 4-6 sentences each. Spread them evenly; each segment is one idea with a visual state change per sentence.\nEpisode ${form['Episode number']}: ${form['Episode title']} ${form['Subtitle (optional)'] || ''}\nOutline / talking points:\n${cfg.brief}`;
if (prev) user += `\n\nYour previous answer failed validation. Fix these problems and return the full corrected JSON:\n- ` + prev.errors.join('\n- ');
return [{json:{model: cfg.llmModel, messages:[{role:'system',content:sys},{role:'user',content:user}], errors: undefined}}];
'''
EXAMPLE = {"narration": {"segments": [{"id": "open", "chapter": "Intro", "sentences": ["Today we install AWX the way the project recommends.", "By the end, you'll log in to your own AWX."]},
    {"id": "check", "chapter": "Check the machine", "sentences": ["Now log in as root and check the machine.", "The minimums are two CPUs, four gigabytes of free memory, and fifteen gigabytes of free disk.", "Read your own numbers out loud before you go on."]}]},
    "scenes": [{"id": "check", "label": "STEP 2", "title": "Check the machine", "states": [{"i": 1}, {"i": 2}], "elements": [
        {"type": "term", "lines": ["$ free -m; nproc; df -h /; getenforce"], "hl": {"0": [0]}},
        {"type": "tiles", "from": 1, "glow": [1], "h": 220, "items": [{"big": "2", "small": "CPUs minimum"}, {"big": "4 GB", "small": "free RAM"}, {"big": "15 GB", "small": "free disk on /"}]},
        {"type": "pill", "from": 2, "text": "Read your own numbers out loud"}]}],
    "display": [["thirty thousand eighty", "30080"], ["S E Linux", "SELinux"]]}
add("Build prompt", "n8n-nodes-base.code", 2, {"jsCode": PROMPT_JS.replace("${JSON.stringify(EXAMPLE)}", "${JSON.stringify(EXAMPLE)}").replace("const example = ${JSON.stringify(EXAMPLE)};", "const example = " + json.dumps(json.dumps(EXAMPLE)) + ";")}, 1100, 0)
link("Project info", "Build prompt")
add("Author (NVIDIA LLM)", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "https://integrate.api.nvidia.com/v1/chat/completions", "authentication": "predefinedCredentialType", "nodeCredentialType": "openAiApi",
    "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "={{ JSON.stringify({model: $json.model, messages: $json.messages, temperature: 0.3, top_p: 0.9, max_tokens: 12000}) }}", "options": {"timeout": 300000}},
    1320, 0, creds={"openAiApi": {"id": "", "name": "OpenAI account"}})
link("Build prompt", "Author (NVIDIA LLM)")

VALIDATE_JS = r'''
const cfg = $('Config').first().json;
const form = $('New episode brief').first().json;
const raw = ($json.choices?.[0]?.message?.content || '').trim();
const errors = [];
let data = null;
try {
  const m = raw.match(/\{[\s\S]*\}/);
  data = JSON.parse(m ? m[0] : raw);
} catch (e) { errors.push('Output is not valid JSON: ' + e.message); }
const KINDS = ['tiles','term','cards','note','pill'];
if (data) {
  const segs = data.narration?.segments;
  if (!Array.isArray(segs) || segs.length < 4) errors.push('narration.segments needs at least 4 segments (open, middle..., close)');
  else {
    const ids = new Set();
    segs.forEach((s, si) => {
      if (!/^[a-z0-9_]{1,20}$/.test(s.id || '')) errors.push(`segment ${si}: id must be lowercase letters/digits/underscore`);
      if (ids.has(s.id)) errors.push('duplicate segment id ' + s.id); ids.add(s.id);
      if (si > 0 && !s.chapter) errors.push(`segment ${s.id}: chapter missing`);
      if (!Array.isArray(s.sentences) || s.sentences.length < 2) errors.push(`segment ${s.id}: needs 2+ sentences`);
      (s.sentences || []).forEach((t, i) => {
        if (/\d/.test(t)) errors.push(`segment ${s.id} sentence ${i}: contains digits - spell them out ("${t.slice(0,50)}")`);
        if (t.split(/\s+/).length > 32) errors.push(`segment ${s.id} sentence ${i}: longer than 32 words - split it`);
      });
    });
    if (segs[0].id !== 'open') errors.push('first segment id must be "open"');
    if (segs[segs.length-1].id !== 'close') errors.push('last segment id must be "close"');
    if (segs[segs.length-1].sentences?.length < 3) errors.push('close needs 3+ sentences (end card starts on the second-to-last)');
    const bySeg = Object.fromEntries(segs.map(s => [s.id, s]));
    const scenes = data.scenes;
    if (!Array.isArray(scenes)) errors.push('scenes must be an array');
    else {
      const have = new Set(scenes.map(s => s.id));
      segs.slice(1, -1).forEach(s => { if (!have.has(s.id)) errors.push(`no scene for segment ${s.id}`); });
      scenes.forEach(sc => {
        const seg = bySeg[sc.id];
        if (!seg) { errors.push(`scene ${sc.id}: no narration segment with this id`); return; }
        if ((sc.kind || 'slide') !== 'slide') errors.push(`scene ${sc.id}: only kind "slide" is allowed`);
        if (!sc.label || !sc.title) errors.push(`scene ${sc.id}: label and title required`);
        const nst = (sc.states || []).length;
        (sc.states || []).forEach(st => { if (!(st.i >= 0 && st.i < seg.sentences.length)) errors.push(`scene ${sc.id}: state i=${st.i} is outside the segment's sentences`); });
        if (!Array.isArray(sc.elements) || !sc.elements.length) errors.push(`scene ${sc.id}: elements missing`);
        if ((sc.elements || []).length > 4) errors.push(`scene ${sc.id}: max 4 elements`);
        (sc.elements || []).forEach(e => {
          if (!KINDS.includes(e.type)) errors.push(`scene ${sc.id}: unknown element type ${e.type}`);
          if ((e.from || 0) > nst + (sc.extra_states || 0)) errors.push(`scene ${sc.id}: element "from" ${e.from} is beyond the last state (${nst})`);
          if (e.type === 'term' && (e.lines || []).length > 9) errors.push(`scene ${sc.id}: term has more than 9 lines`);
          if (e.type === 'term') (e.lines || []).forEach(l => { if (l.length > 75) errors.push(`scene ${sc.id}: term line too long: ${l.slice(0,40)}...`); });
          if (e.type === 'cards' && (e.items || []).length > 4) errors.push(`scene ${sc.id}: max 4 cards`);
          if (e.type === 'tiles' && (e.items || []).length > 4) errors.push(`scene ${sc.id}: max 4 tiles`);
        });
      });
    }
  }
}
const tgt = Math.min(15, Math.max(5, Number(form['Target length in minutes (10-15, max 15)']) || 10));
if (data && data.narration && Array.isArray(data.narration.segments)) {
  const ss = data.narration.segments;
  const w = ss.reduce((n, s) => n + (s.sentences || []).reduce((m, t) => m + t.split(/\s+/).filter(Boolean).length, 0), 0);
  const sn = ss.reduce((n, s) => n + (s.sentences || []).length, 0);
  const estMin = (w / 3.0 + sn * 0.32 + ss.length * 0.85 + 12) / 60;
  if (estMin > 15) errors.push(`narration is about ${estMin.toFixed(1)} min - over the 15 minute limit, cut to about ${Math.round(tgt * 60 * 2.6)} words`);
  else if (estMin < tgt * 0.75) errors.push(`narration is about ${estMin.toFixed(1)} min but the target is ${tgt} - add content (about ${Math.round(tgt * 60 * 2.6)} words total, ${w} now)`);
  else if (estMin > tgt * 1.25) errors.push(`narration is about ${estMin.toFixed(1)} min but the target is ${tgt} - trim to about ${Math.round(tgt * 60 * 2.6)} words (${w} now)`);
}
const attempt = $runIndex + 1;
if (errors.length) return [{json:{ok:false, errors:errors.slice(0,12), attempt}}];
const segs = data.narration.segments;
const folder = cfg.project;
const num = Number(form['Episode number']);
const episode = {
  series: 'AWX from Zero', number: num, title: form['Episode title'], subtitle: form['Subtitle (optional)'] || '', channel: 'Venu Automates', handle: '@VenAutomates',
  folder, repo: 'github.com/Venuvgp19/Youtube-Tutorials-Awx',
  next: { title: form['Next episode title'] || 'Next episode', sub: form['Next episode tagline'] || '' },
  end_at: { seg: 'close', i: segs[segs.length-1].sentences.length - 2, off: -0.1 },
  chapter_pills: segs.slice(1, -1).map(s => s.id), description: form['Outline / talking points'].split('\n')[0].slice(0, 200),
  output_name: `AWX from Zero - Ep ${String(num).padStart(2,'0')} - ${form['Episode title']}`.replace(/[\\/:*?"<>|]/g, '')
};
const scenes = { episode, gaps: { lead: 0.7, sentence: 0.32, segment: 0.85, tail: 5.0, after_seg: { open: 1.0 }, extra: [] }, display: data.display || [], scenes: data.scenes };
return [{json:{ok:true, attempt, files:{ 'narration.json': data.narration, 'scenes.json': scenes }}}];
'''
add("Validate script", "n8n-nodes-base.code", 2, {"jsCode": VALIDATE_JS}, 1540, 0)
link("Author (NVIDIA LLM)", "Validate script")
IF("Script valid?", "={{ $json.ok }}", "true", 1760, 0, op="true") if False else None
add("Script valid?", "n8n-nodes-base.if", 2.2, {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"}, "conditions": [{"id": "c1", "leftValue": "={{ $json.ok }}", "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 1760, 0)
link("Validate script", "Script valid?")
IF("Retries left?", "={{ $json.attempt }}", "3", 1760, 200)
nodes[-1]["parameters"]["conditions"]["conditions"][0]["operator"] = {"type": "number", "operation": "lt"}
link("Script valid?", "Retries left?", 1)
# retry: feed errors back into Build prompt
link("Retries left?", "Build prompt", 0)
add("Script failed", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'AI script failed validation 3 times: ' + $json.errors.join('; ') }}"}, 1980, 300)
link("Retries left?", "Script failed", 1)
add("Write project files", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "={{ %s.runner }}/write" % CFG, "sendHeaders": True, "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]},
    "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "={{ JSON.stringify({project: %s.project, files: $json.files}) }}" % CFG, "options": {}}, 1980, -100)
link("Script valid?", "Write project files", 0)

# ---------------------------------------------------------------- pipeline
add("Start Voicebox if down", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "={{ %s.runner }}/voicebox/ensure" % CFG, "sendHeaders": True,
    "headerParameters": {"parameters": [{"name": "X-Token", "value": "={{ %s.token }}" % CFG}]}, "sendBody": True, "contentType": "raw", "rawContentType": "application/json", "body": "{}", "options": {"timeout": 300000}}, 2100, -60)
RUN("Doctor", "doctor", 2200, 100, voicebox=True)
link("Has a brief?", "Start Voicebox if down", 1); link("Write project files", "Start Voicebox if down"); link("Start Voicebox if down", "Doctor")
IF("Environment OK?", "={{ $json.status }}", "ok", 2400, 100)
link("Doctor", "Environment OK?")
add("Stop: pipeline failed", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'Stage failed: ' + ($json.status || '') + '\\n' + ($json.log_tail || JSON.stringify($json)) }}"}, 2400, 700)
link("Environment OK?", "Stop: pipeline failed", 1)
RUN("Narrate (Voicebox + Whisper check)", "narrate", 2600, 100)
link("Environment OK?", "Narrate (Voicebox + Whisper check)", 0)
IF("Narration clean?", "={{ $json.status }}", "ok", 2820, 100)
link("Narrate (Voicebox + Whisper check)", "Narration clean?")
add("Review flagged lines", "n8n-nodes-base.wait", 1.1, {"resume": "form", "formTitle": "Narration needs a listen",
    "formDescription": "={{ 'These lines did not match what Whisper heard after 4 seeds. Listen in Voicebox (history) or re-word them in narration.json and re-run.<br><br>' + ($json.result.flagged || []).map(f => '<b>#' + f.k + '</b> expected: ' + f.text + '<br>&nbsp;&nbsp;heard: ' + f.heard).join('<br><br>') }}",
    "formFields": {"values": [{"fieldLabel": "Decision", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "accept as is"}, {"option": "abort"}]}, "requiredField": True}]}, "options": {}}, 3040, 300)
link("Narration clean?", "Review flagged lines", 1)
IF("Accepted?", "={{ $json.Decision }}", "accept as is", 3260, 300)
link("Review flagged lines", "Accepted?"); link("Accepted?", "Stop: pipeline failed", 1)
RUN("Build timeline + captions", "build", 3480, 100)
link("Narration clean?", "Build timeline + captions", 0); link("Accepted?", "Build timeline + captions", 0)
IF("Build OK?", "={{ $json.status }}", "ok", 3700, 100); link("Build timeline + captions", "Build OK?"); link("Build OK?", "Stop: pipeline failed", 1)
RUN("Render slides", "slides", 3920, 100); link("Build OK?", "Render slides", 0)
RUN("Preview frames", "preview", 4140, 100); link("Render slides", "Preview frames")
IF("Preview OK?", "={{ $json.status }}", "ok", 4360, 100); link("Preview frames", "Preview OK?"); link("Preview OK?", "Stop: pipeline failed", 1)
add("Approve preview", "n8n-nodes-base.wait", 1.1, {"resume": "form", "formTitle": "Approve the preview before the long render",
    "formDescription": "={{ 'Check text fits, nothing overlaps captions, highlights land on the right lines.<br><a href=\"' + %s.runnerBrowser + '/file?project=' + %s.project + '&path=previews/sheet.jpg\" target=\"_blank\">Open the contact sheet</a><br><img style=\"max-width:100%%\" src=\"' + %s.runnerBrowser + '/file?project=' + %s.project + '&path=previews/sheet.jpg\">' }}" % (CFG, CFG, CFG, CFG),
    "formFields": {"values": [{"fieldLabel": "Decision", "fieldType": "dropdown", "fieldOptions": {"values": [{"option": "approve"}, {"option": "reject"}]}, "requiredField": True}, {"fieldLabel": "Notes (if rejecting)", "fieldType": "textarea"}]}, "options": {}}, 4580, 100)
link("Preview OK?", "Approve preview", 0)
IF("Approved?", "={{ $json.Decision }}", "approve", 4800, 100); link("Approve preview", "Approved?")
add("Rejected", "n8n-nodes-base.stopAndError", 1, {"errorMessage": "={{ 'Preview rejected: ' + ($json['Notes (if rejecting)'] || 'no notes') + '. Edit scenes.json in the project folder and re-run (manual trigger).' }}"}, 4800, 400)
link("Approved?", "Rejected", 1)
RUN("Render video (long)", "render", 5020, 100); link("Approved?", "Render video (long)", 0)
IF("Render OK?", "={{ $json.status }}", "ok", 5240, 100); link("Render video (long)", "Render OK?"); link("Render OK?", "Stop: pipeline failed", 1)
RUN("Mix voice + music", "mix", 5460, 100); link("Render OK?", "Mix voice + music", 0)
IF("Mix OK?", "={{ $json.status }}", "ok", 5680, 100); link("Mix voice + music", "Mix OK?"); link("Mix OK?", "Stop: pipeline failed", 1)
RUN("Package (srt + description)", "package", 5900, 100); link("Mix OK?", "Package (srt + description)", 0)
S("Done", [("message", "={{ 'Episode ready: ' + %s.project }}" % CFG), ("files", "={{ ($json.result.files || []).join('\\n') }}"),
    ("download", "={{ %s.runnerBrowser + '/file?project=' + %s.project + '&path=' + encodeURIComponent((($json.result.files || [])[0] || '').split(/[\\\\/]/).pop()) }}" % (CFG, CFG))], 6120, 100, keep=False)
link("Package (srt + description)", "Done")

wf = {"name": "AWX episode builder", "nodes": nodes, "connections": conns, "active": False, "settings": {"executionOrder": "v1"}, "pinData": {}, "meta": {"templateCredsSetupCompleted": False}}
json.dump(wf, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "awx-episode-builder.json"), "w"), indent=2)
print(len(nodes), "nodes")
