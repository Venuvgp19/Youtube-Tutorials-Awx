# Episode 3: The 8 building blocks of AWX

**After this episode you can:** Map any AWX screen to its object.

**Lab / demo:** Org, credential, project, inventory, template, workflow, schedule, EE

**Files:**

- `ping.yml`: the playbook the job template runs (can AWX reach every host, and does the `ansible` user get root through sudo)

Everything is clicked in the AWX UI (`http://192.168.100.102:30080`), built on the lab from [ep02](../ep02/). AWX runs on the first VM (**node1**, `192.168.100.102`), so we also make a second VM (**node2**, `192.168.100.103`) for AWX to manage.

## Before you start (on the VM)

```bash
k3s kubectl -n awx get pods                      # all Running or Completed
systemctl is-active sshd                         # active
grep -i '^PasswordAuthentication' /etc/ssh/sshd_config  # must not say no
```

Read the admin password if you need it:

```bash
k3s kubectl -n awx get secret awx-admin-password -o jsonpath='{.data.password}' | base64 -d; echo
```

## What to build, in order

| # | Object | Menu | Values |
|---|--------|------|--------|
| 1 | Organization | Access > Organizations | `Homelab` |
| 2a | Second node | VirtualBox + node2 console | clone the lab VM as `awx-node2`, IP `192.168.100.103` |
| 2b | Linux user | node1 and node2 consoles | `ansible` with sudo on both nodes |
| 2c | Credential | Resources > Credentials | `lab-ssh`, type Machine, user `ansible`, password, privilege escalation `sudo` |
| 3 | Project (connect the repo) | Resources > Projects | `series-repo`, Git, `https://github.com/Venuvgp19/Youtube-Tutorials-Awx.git`, branch `main`, tick Update revision on job launch |
| 4 | Inventory | Resources > Inventories | `lab`, hosts `192.168.100.102` and `192.168.100.103` |
| 5 | Execution environment | Administration > Execution Environments | look at the default `AWX EE (latest)` |
| 6 | Job template | Resources > Templates | `ping-lab`: project `series-repo`, inventory `lab`, credential `lab-ssh`, playbook `ep03/ping.yml` |
| 7 | Workflow template | Resources > Templates | `sync-then-ping`: Project Sync `series-repo` -> on success -> `ping-lab` |
| 8 | Schedule | on `ping-lab` > Schedules | `every-5-min`, frequency Minute, every 5, then switch it off |

The playbook is `ep03/ping.yml` in this folder. The project is the whole repo; the job template picks this one file.

## Make a second node (clone the VM)

AWX runs on node1, and a lab where AWX manages only itself teaches little. Clone the lab VM first, then create the `ansible` user on both nodes (next section).

1. Shut down the lab VM (`poweroff`)
2. VirtualBox: right-click the VM > **Clone**. Name `awx-node2`, MAC address policy **Generate new MAC addresses for all network adapters**, **Full clone**, **Current machine state**
3. Optional, saves RAM: node2 > Settings > System: 1 vCPU, 2048 MB (it does not run AWX)
4. Start both VMs. On the **node2** console, as root, make the copy unique:

```bash
hostnamectl set-hostname node2
rm -f /etc/machine-id && systemd-machine-id-setup         # new machine ID
rm -f /etc/ssh/ssh_host_* && ssh-keygen -A && systemctl restart sshd   # new SSH host keys
systemctl disable --now k3s; /usr/local/bin/k3s-killall.sh # node2 is only a target, no AWX
```

5. Give node2 its own IP on the host-only network. Find the connection that holds `192.168.100.x`:

```bash
ip -br a                       # the NIC with 192.168.100.x (it is the cloned 102)
nmcli con show --active        # note the connection name for that NIC
nmcli con mod "<connection name>" ipv4.method manual ipv4.addresses 192.168.100.103/24
nmcli con up "<connection name>"
ip -br a                       # must show 192.168.100.103/24
```

6. Check from node1: `ping -c 2 192.168.100.103` replies. If ssh later shows an old key warning for that IP, run `ssh-keygen -R 192.168.100.103`.

In AWX, add `192.168.100.103` as a second host of the `lab` inventory. The job template then runs on both: you see two hosts in the job output.

## Create the ansible user (on both nodes)

AWX logs in to your machines with a **machine credential** (added below). Do not use root for this: create a dedicated account with sudo rights.

On node1 **and then node2**, as root (same password on both):

```bash
useradd -m -s /bin/bash ansible
passwd ansible                                            # type a password
echo 'ansible ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/ansible
chmod 440 /etc/sudoers.d/ansible
visudo -cf /etc/sudoers.d/ansible                         # must say: parsed OK
su - ansible -c 'sudo whoami'                             # must print: root
```

`NOPASSWD:ALL` means full sudo with no prompt, which automation needs. Lab only: in production limit the commands.

## Add the credential in AWX

The `lab-ssh` credential works on both nodes because both have the same user and password. **Resources > Credentials > Add**

1. Name `lab-ssh`, organization `Homelab`
2. Credential type **Machine**
3. Username `ansible`, password
4. Privilege escalation method `sudo`, username `root`, leave the password empty
5. **Save**. The password now shows as **Encrypted**: AWX never shows it again

When you build the job template, tick **Privilege escalation**. The playbook's last task runs `whoami` with sudo and prints `root`.

SSH key instead of a password (optional, also covered in [ep05](../ep05/)):

```bash
su - ansible -c "ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519 && cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
cat /home/ansible/.ssh/id_ed25519      # paste into a credential of type Machine, field SSH Private Key
```

Never share the private key.

## Connect the repo to AWX

AWX does not store playbooks. It pulls them from Git through a **project**.

1. On GitHub open the repo, click **Code**, copy the HTTPS URL: `https://github.com/Venuvgp19/Youtube-Tutorials-Awx.git`
2. AWX: **Resources > Projects > Add**
3. Name `series-repo`, organization `Homelab`, source control type **Git**
4. Paste the URL, branch `main`. The repo is public, so no source control credential is needed (private repos: [ep05](../ep05/))
5. Tick **Update revision on job launch**, then **Save**
6. Wait for **Successful**. Open the project **Jobs** tab to see the sync (git clone) output
7. The playbook now shows up in the job template dropdown: `ep03/ping.yml`

To pull new commits later, click the sync icon on the project.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Project sync fails | No internet from the pod | Check NIC 2 (NAT) and `curl https://github.com` on the VM |
| Playbook not in the dropdown | Project not synced yet | Wait for the green Successful status, then reload |
| Job fails: unreachable, connection timed out | Pod cannot reach the host | Check `firewall-cmd --zone=trusted --list-sources` shows 10.42.0.0/16 and 10.43.0.0/16 |
| One host unreachable, the other fine | node2 IP or sshd not set | On node2 `ip -br a` shows `192.168.100.103`; `systemctl is-active sshd`; test `ssh ansible@192.168.100.103` from node1 |
| Both VMs answer on the same IP | Cloned with the same address | Finish step 5 of the clone section on node2 |
| Job fails: permission denied | Wrong password, or `PasswordAuthentication no` | Re-enter the password in the credential; set `PasswordAuthentication yes`, `systemctl restart sshd` |
| Last task fails: sudo asks for a password | Sudoers file missing | Recreate `/etc/sudoers.d/ansible` (see above) and tick Privilege escalation on the template |
| Job fails: host key verification failed | Host key checking on | Set extra variable `ansible_ssh_common_args: '-o StrictHostKeyChecking=no'` on the inventory (lab only) |

Teleprompter script for AWX Studio: `studio/scripts/ep03.json`.
