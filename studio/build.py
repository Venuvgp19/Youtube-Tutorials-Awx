#!/usr/bin/env python3
"""Inline scripts/*.json into app.template.html -> index.html (single self-contained file)."""
import glob, json
scripts = [json.load(open(p)) for p in sorted(glob.glob("scripts/*.json"))]
html = open("app.template.html").read().replace("/*BUILTIN_SCRIPTS*/[]", json.dumps(scripts, ensure_ascii=False))
open("index.html", "w").write(html)
print("index.html built with", len(scripts), "script(s)")
