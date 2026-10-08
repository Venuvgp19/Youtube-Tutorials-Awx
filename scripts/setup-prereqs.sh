#!/usr/bin/env bash
# ==============================================================================
# Helper Script: Install Prerequisites for Ansible AWX Operator
# ==============================================================================
set -e

echo "[+] Updating system package list..."
sudo apt-get update -y

echo "[+] Installing core tools..."
sudo apt-get install -y curl git jq python3-pip python3-venv

echo "[+] Installing kubectl..."
if ! command -v kubectl &> /dev/null; then
    KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt)
    curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm -f kubectl
fi

echo "[+] Verifying kubectl installation..."
kubectl version --client --output=yaml

echo "[+] All prerequisites installed successfully!"
