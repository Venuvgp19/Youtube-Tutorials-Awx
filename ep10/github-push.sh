#!/usr/bin/env bash
# Sends AWX exactly what GitHub sends on a push, signed with the webhook key.
# GitHub cannot reach a home lab on 192.168.100.x; with a public URL (tunnel) you
# would paste the same URL and key into GitHub > Settings > Webhooks instead.
# Usage: ./github-push.sh <webhook URL from AWX> <webhook key from AWX>
set -euo pipefail
URL="${1:?webhook URL}"; KEY="${2:?webhook key}"
BODY=$(cat <<JSON
{"ref":"refs/heads/main","before":"0000000000000000000000000000000000000000",
 "after":"$(date +%s | sha1sum | cut -c1-40)",
 "repository":{"full_name":"Venuvgp19/Youtube-Tutorials-Awx","html_url":"https://github.com/Venuvgp19/Youtube-Tutorials-Awx"},
 "head_commit":{"message":"demo push from the lab"},"pusher":{"name":"venu"}}
JSON
)
SIG1=$(printf '%s' "$BODY" | openssl dgst -sha1 -hmac "$KEY" | awk '{print $NF}')
SIG256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$KEY" | awk '{print $NF}')
curl -s -o /dev/stderr -w "HTTP %{http_code}\n" -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: $(cat /proc/sys/kernel/random/uuid)" \
  -H "X-Hub-Signature: sha1=$SIG1" \
  -H "X-Hub-Signature-256: sha256=$SIG256" \
  --data-binary "$BODY"
