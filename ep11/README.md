# Episode 11: AWX as code + the REST API from n8n

**After this episode you can:** Rebuild AWX from code and trigger jobs from n8n.

**Lab / demo:** awx.awx collection creates project `awx-as-code`, inventory `lab-as-code`, template `ping (as code)`; curl and n8n launch `ping-lab`

**Files:**

- `awx-config.yml`: project, inventory, host and job template managed with the awx.awx collection (run twice: no changes)
- `api.sh`: find, launch and poll a job template through the REST API (needs curl and jq)
- `n8n-launch-awx.json`: the same three calls as an n8n workflow (Bearer Auth credential "AWX token")

**Status:** files ready; video coming soon.
