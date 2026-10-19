# Episode 10: Schedules, notifications and GitHub webhooks

**After this episode you can:** Run on a timer, get the result on your phone, and start jobs on every push.

**Lab / demo:** template `report` with a daily schedule, a Webhook notification into n8n -> Telegram, and a GitHub webhook

**Files:**

- `report.yml`: prints how the job was launched (manual, scheduled, webhook)
- `github-push.sh`: sends AWX the same signed push event GitHub sends (for a home lab GitHub cannot reach)
- `n8n-awx-notify.json`: n8n workflow, Webhook `/webhook/awx-notify` -> Telegram (set your Telegram credential and chat ID, then activate)

AWX notification: type Webhook, target `http://<n8n host>:5678/webhook/awx-notify`, method POST.

**Status:** files ready; video coming soon.
