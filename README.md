# 🚀 Ansible AWX YouTube Tutorial Series

[![Ansible](https://img.shields.io/badge/Ansible-E00?style=for-the-badge&logo=ansible&logoColor=white)](https://www.ansible.com/)
[![AWX](https://img.shields.io/badge/AWX-000000?style=for-the-badge&logo=ansible&logoColor=white)](https://github.com/ansible/awx)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Welcome to the official companion repository for our **Ansible AWX YouTube Tutorial Series**! Here you will find all episode walkthrough notes, production-ready playbooks, inventory templates, setup scripts, and hands-on lab exercises demonstrated in the videos.

---

## 📺 Video Tutorial Index

| Episode | Title | Description | Code / Notes | Video Link |
| :---: | :--- | :--- | :---: | :---: |
| **01** | **AWX in 2026: what it is and is it worth learning?** | AWX vs Ansible CLI vs AAP, and where AWX stands today | [ep01](ep01/) | *Coming Soon* |
| **02** | **Install AWX on k3s with the AWX Operator** | k3s + Operator 2.19.1 via kustomize on CentOS Stream 10 | [ep02](ep02/) | *Coming Soon* |
| **03** | **The 8 building blocks of AWX** | Organizations, credentials, projects, inventories, templates, workflows, schedules, EEs | [ep03](ep03/) | *Coming Soon* |
| **04** | **Your first job: Git project to job template** | Link this repo, build an inventory and run a playbook | [ep04](ep04/) | *Coming Soon* |
| **05** | **Credentials and Ansible Vault** | Machine, source control, vault and custom credential types | [ep05](ep05/) | *Coming Soon* |
| **06** | **Dynamic inventory from AWS** | EC2 inventory source, groups by tag, smart inventories | [ep06](ep06/) | *Coming Soon* |
| **07** | **Custom Execution Environments** | ansible-builder, push to a registry, use it in AWX | [ep07](ep07/) | *Coming Soon* |
| **08** | **Surveys and RBAC: self-service automation** | Surveys, teams and execute-only roles | [ep08](ep08/) | *Coming Soon* |
| **09** | **Workflows: approvals and failure paths** | Workflow templates, approval nodes, on-failure branches | [ep09](ep09/) | *Coming Soon* |
| **10** | **Schedules, notifications and GitHub webhooks** | Run on a timer, notify on result, trigger on push | [ep10](ep10/) | *Coming Soon* |
| **11** | **AWX as code + the REST API from n8n** | awx.awx collection and launching jobs from n8n | [ep11](ep11/) | *Coming Soon* |
| **12** | **Backup, restore and troubleshooting** | AWXBackup / AWXRestore and the most common failures | [ep12](ep12/) | *Coming Soon* |

---

## 📂 Repository Structure

```plaintext
Youtube-Tutorials-Awx/
├── ep01/ … ep12/                # One folder per episode: notes, files and commands
│   └── ep02/install.sh          # Installs AWX 24.6.1 on k3s (the series lab)
├── playbooks/                   # Shared playbooks used across episodes
│   └── ping-test.yml            # Basic connectivity & credential verification
├── inventories/                 # Sample inventory files
│   └── hosts.example.ini        # Starter static inventory template
├── scripts/                     # Helper scripts (setup-prereqs.sh targets Ubuntu)
├── templates/                   # Jinja2 configuration templates
└── README.md                    # Series index & repository guide
```

---

## 🛠️ Prerequisites

The series lab, built and tested on Oct 7, 2026:
- A VirtualBox VM running **CentOS Stream 10**: 4 vCPU, 8 GB RAM, 60 GB disk; NIC 1 host-only, NIC 2 NAT
- **k3s** v1.36.5 (single node), **AWX Operator** 2.19.1, **AWX** 24.6.1
- Windows hosts: turn the Windows hypervisor off (`bcdedit /set hypervisorlaunchtype off`, then reboot), or VirtualBox falls back to Hyper-V mode and the guest can crash
- **Git**; `kubectl` comes with k3s (`k3s kubectl`)

AWX releases have been paused since 24.6.1 (Jul 2, 2024) while the project is refactored, so the series pins these versions. Start with [ep02](ep02/) to build the lab.

---

## 🚀 Quick Start: Running Your First AWX Job

1. **Link this repository into your AWX project configuration:**
   - In AWX UI, go to **Projects > Add**
   - **Source Control Type**: `Git`
   - **Source Control URL**: `https://github.com/Venuvgp19/Youtube-Tutorials-Awx.git`
   - **Branch**: `main`
2. Create an **Inventory** with your target managed hosts (or use localhost).
3. Add a **Machine Credential** with your SSH key or password.
4. Create a **Job Template** pointing to `playbooks/ping-test.yml` and click **Launch**!

---

## 🔒 Security Best Practices
- **Never commit plain-text passwords or SSH private keys.**
- Use **Ansible Vault** for sensitive variables (`ansible-vault encrypt`).
- All inventory files in this repo contain placeholder values (`example.com`, dummy IPs).

---

## 🤝 Connect & Subscribe
If you found these tutorials helpful, make sure to:
- 🔔 **Subscribe to the YouTube Channel**
- ⭐ **Star this repository** to bookmark it for future updates
- 💬 Drop questions or topic requests in the video comments or via GitHub Issues!

---
*Maintained with ❤️ by [Venuvgp19](https://github.com/Venuvgp19)*
