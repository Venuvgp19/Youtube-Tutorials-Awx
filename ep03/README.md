# Episode 3: The 8 building blocks of AWX

**After this episode you can:** Map any AWX screen to its object.

**Lab / demo:** Org, credential, project, inventory, template, workflow, schedule, EE

Everything is clicked in the AWX UI (`http://192.168.100.102:30080`), built on the lab from [ep02](../ep02/).

## Before you record (on the VM)

```bash
k3s kubectl -n awx get pods                      # all Running or Completed
systemctl is-active sshd                         # active
grep -i '^PermitRootLogin' /etc/ssh/sshd_config  # PermitRootLogin yes (lab only)
```

Read the admin password if you need it (do not show it on screen):

```bash
k3s kubectl -n awx get secret awx-admin-password -o jsonpath='{.data.password}' | base64 -d; echo
```

## What to build, in order

| # | Object | Menu | Values |
|---|--------|------|--------|
| 1 | Organization | Access > Organizations | `Homelab` |
| 2 | Credential | Resources > Credentials | `lab-ssh`, type Machine, user `root`, password |
| 3 | Project | Resources > Projects | `series-repo`, Git, `https://github.com/Venuvgp19/Youtube-Tutorials-Awx.git`, branch `main` |
| 4 | Inventory | Resources > Inventories | `lab`, host `192.168.100.102` |
| 5 | Execution environment | Administration > Execution Environments | look at the default `AWX EE (latest)` |
| 6 | Job template | Resources > Templates | `ping-lab`: project `series-repo`, inventory `lab`, credential `lab-ssh`, playbook `playbooks/ping-test.yml` |
| 7 | Workflow template | Resources > Templates | `sync-then-ping`: Project Sync `series-repo` -> on success -> `ping-lab` |
| 8 | Schedule | on `ping-lab` > Schedules | `every-5-min`, frequency Minute, every 5, then switch it off |

The playbook is `playbooks/ping-test.yml` in the repo root.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Project sync fails | No internet from the pod | Check NIC 2 (NAT) and `curl https://github.com` on the VM |
| Playbook not in the dropdown | Project not synced yet | Wait for the green Successful status, then reload |
| Job fails: unreachable, connection timed out | Pod cannot reach the host | Check `firewall-cmd --zone=trusted --list-sources` shows 10.42.0.0/16 and 10.43.0.0/16 |
| Job fails: permission denied | Wrong password or root login off | Set `PermitRootLogin yes`, `systemctl restart sshd`, fix the credential |
| Job fails: host key verification failed | Host key checking on | Set extra variable `ansible_ssh_common_args: '-o StrictHostKeyChecking=no'` on the inventory (lab only) |

Teleprompter script for AWX Studio: `studio/scripts/ep03.json`.
