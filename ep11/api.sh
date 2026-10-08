#!/usr/bin/env bash
# Launch a job template through the AWX REST API and wait for it to finish.
# Usage: CONTROLLER_HOST=http://<AWX VM IP>:30080 CONTROLLER_OAUTH_TOKEN=... ./api.sh "Ping homelab"
set -euo pipefail

AWX="${CONTROLLER_HOST:?set CONTROLLER_HOST}"
TOKEN="${CONTROLLER_OAUTH_TOKEN:?set CONTROLLER_OAUTH_TOKEN}"
NAME="${1:-Ping homelab}"
auth=(-H "Authorization: Bearer $TOKEN")

# 1. find the template id
id=$(curl -sf "${auth[@]}" -G "$AWX/api/v2/job_templates/" --data-urlencode "name=$NAME" | jq -r '.results[0].id')
[ "$id" != "null" ] || { echo "No job template named '$NAME'"; exit 1; }
echo "Template '$NAME' has id $id"

# 2. launch it
job=$(curl -sf "${auth[@]}" -X POST -H "Content-Type: application/json" -d '{}' \
  "$AWX/api/v2/job_templates/$id/launch/" | jq -r '.job')
echo "Launched job $job"

# 3. poll until it finishes
while :; do
  status=$(curl -sf "${auth[@]}" "$AWX/api/v2/jobs/$job/" | jq -r '.status')
  echo "Job $job: $status"
  case "$status" in
    successful) exit 0 ;;
    failed|error|canceled) exit 1 ;;
  esac
  sleep 5
done
