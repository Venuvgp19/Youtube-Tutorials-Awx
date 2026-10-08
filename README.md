# 🚀 Ansible AWX YouTube Tutorial Series

[![Ansible](https://img.shields.io/badge/Ansible-E00?style=for-the-badge&logo=ansible&logoColor=white)](https://www.ansible.com/)
[![AWX](https://img.shields.io/badge/AWX-000000?style=for-the-badge&logo=ansible&logoColor=white)](https://github.com/ansible/awx)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Welcome to the official companion repository for our **Ansible AWX YouTube Tutorial Series**! Here you will find all episode walkthrough notes, production-ready playbooks, inventory templates, setup scripts, and hands-on lab exercises demonstrated in the videos.

---

## 📺 Video Tutorial Index

| Episode | Title | Description | Code / Notes | Video Link |
| :---: | :--- | :--- | :---: | :---: |
| **01** | **Introduction to Ansible AWX** | What is AWX, architecture overview, and lab requirements | [Notes](01-introduction-and-setup/README.md) | *Coming Soon* |
| **02** | **Deploying AWX with AWX Operator** | Step-by-step installation on Kubernetes / K3s / Minikube | [Scripts](scripts/) | *Coming Soon* |
| **03** | **Inventories & Credentials Setup** | Managing machine credentials, SSH keys, and dynamic inventories | [Inventories](inventories/) | *Coming Soon* |
| **04** | **Creating Job Templates & Projects** | Linking GitHub repos, creating job templates, and running playbooks | [Playbooks](playbooks/) | *Coming Soon* |
| **05** | **Workflow Job Templates & Approvals** | Multi-step pipelines, approval gates, and error handlers | [Playbooks](playbooks/) | *Coming Soon* |
| **06** | **RBAC, Teams & Organizations** | Role-based access control and self-service execution | [Templates](templates/) | *Coming Soon* |

---

## 📂 Repository Structure

```plaintext
Youtube-Tutorials-Awx/
├── 01-introduction-and-setup/   # Episode 1 notes, architecture diagrams, and concepts
├── playbooks/                   # Ansible playbooks used in demonstrations
│   └── ping-test.yml            # Basic connectivity & credential verification
├── inventories/                 # Sample inventory files and dynamic inventory configs
│   └── hosts.example.ini        # Starter static inventory template
├── scripts/                     # Automation scripts for installing prerequisites
│   └── setup-prereqs.sh         # Shell script for microk8s/k3s/docker setup
├── templates/                   # Jinja2 configuration templates
└── README.md                    # Series index & repository guide
```

---

## 🛠️ Prerequisites

To follow along with the hands-on labs, ensure you have:
- A Linux environment (Ubuntu 22.04/24.04 recommended) or VM (VirtualBox / Proxmox / cloud instance)
- **Kubernetes cluster**: K3s, Minikube, MicroK8s, or a managed cluster (EKS/GKE/AKS)
- **Ansible Core**: `>= 2.15`
- **Git** & **kubectl** installed

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
