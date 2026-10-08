#!/usr/bin/env bash
# AWX from Zero, episode 2: install AWX 24.6.1 on single-node k3s.
# Run as root on CentOS Stream 10 from inside this folder (needs kustomization.yaml and awx.yaml).
# Tested on Oct 7, 2026. The firewalld and SELinux blocks were not exercised on the
# test VM (firewalld was off, SELinux permissive); they only run when needed.
set -euo pipefail
cd "$(dirname "$0")"
K="k3s kubectl"

echo "== 1. Checks"
free -m | head -2; nproc; df -h / | tail -1

echo "== 2. Firewall (only if firewalld is running)"
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port=6443/tcp
  firewall-cmd --permanent --add-port=30080/tcp
  firewall-cmd --permanent --zone=trusted --add-source=10.42.0.0/16
  firewall-cmd --permanent --zone=trusted --add-source=10.43.0.0/16
  firewall-cmd --reload
fi

echo "== 3. SELinux to permissive (lab shortcut, only if enforcing)"
if [ "$(getenforce)" = "Enforcing" ]; then
  setenforce 0
  sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
fi

echo "== 4. k3s"
curl -sfL https://get.k3s.io | INSTALL_K3S_SELINUX_WARN=true INSTALL_K3S_SKIP_SELINUX_RPM=true \
  sh -s - --write-kubeconfig-mode 644
until $K get nodes 2>/dev/null | grep -q " Ready"; do sleep 5; done
$K get nodes

echo "== 5. AWX Operator 2.19.1"
command -v git >/dev/null || dnf -y install git
$K apply -k .
$K wait --for condition=established --timeout=180s crd/awxs.awx.ansible.com
$K -n awx rollout status deploy/awx-operator-controller-manager --timeout=600s

echo "== 6. AWX instance"
$K apply -n awx -f awx.yaml

echo "== 7. Waiting for AWX (about 10 minutes)"
until $K -n awx get deploy awx-task >/dev/null 2>&1; do sleep 10; done
$K -n awx rollout status deploy/awx-web --timeout=1800s
$K -n awx rollout status deploy/awx-task --timeout=1800s

echo "== 8. Login"
until curl -sf http://localhost:30080/api/v2/ping/ >/dev/null; do sleep 10; done
echo "URL:      http://$(hostname -I | awk '{print $1}'):30080"
echo "User:     admin"
echo -n "Password: "; $K -n awx get secret awx-admin-password -o jsonpath='{.data.password}' | base64 -d; echo
