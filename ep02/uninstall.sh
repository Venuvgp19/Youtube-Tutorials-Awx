#!/usr/bin/env bash
# AWX from Zero, episode 2: remove everything install.sh set up (AWX, the Operator, k3s, firewall rules).
# Run as root on the VM from inside this folder:  sudo ./uninstall.sh   (add -y to skip the question)
# Add --selinux to also put SELinux back to enforcing (install.sh only changed it if it was enforcing).
# This DELETES the AWX database and all job data. Nothing is touched outside k3s, firewalld and /etc/selinux/config.
set -uo pipefail
cd "$(dirname "$0")"
YES=0; SEL=0
for a in "$@"; do case "$a" in -y|--yes) YES=1;; --selinux) SEL=1;; esac; done
[ "$(id -u)" = 0 ] || { echo "Run as root (sudo ./uninstall.sh)"; exit 1; }

if [ "$YES" != 1 ]; then
  read -r -p "Remove AWX, the AWX Operator and k3s from this machine? All AWX data is lost. Type yes: " r
  [ "$r" = yes ] || { echo "Cancelled."; exit 1; }
fi

K="k3s kubectl"
if command -v k3s >/dev/null 2>&1 && $K get nodes >/dev/null 2>&1; then
  echo "== 1. AWX and the Operator (graceful, so volumes are released)"
  $K -n awx delete awx --all --timeout=180s 2>/dev/null
  $K delete -k . --timeout=180s 2>/dev/null
  $K delete namespace awx --timeout=180s 2>/dev/null
else
  echo "== 1. k3s is not running, skipping the graceful AWX removal"
fi

echo "== 2. k3s (its own uninstall script stops services, removes containers, /etc/rancher, /var/lib/rancher)"
if [ -x /usr/local/bin/k3s-uninstall.sh ]; then
  /usr/local/bin/k3s-uninstall.sh
else
  echo "k3s-uninstall.sh not found, k3s already removed"
fi

echo "== 3. Leftovers"
rm -rf /etc/rancher /var/lib/rancher /var/lib/kubelet /var/log/pods /var/log/containers 2>/dev/null
rm -f /etc/systemd/system/k3s*.service /etc/systemd/system/k3s*.env 2>/dev/null
systemctl daemon-reload

echo "== 4. Firewall rules added by install.sh (only if firewalld is running)"
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --remove-port=6443/tcp
  firewall-cmd --permanent --remove-port=30080/tcp
  firewall-cmd --permanent --zone=trusted --remove-source=10.42.0.0/16
  firewall-cmd --permanent --zone=trusted --remove-source=10.43.0.0/16
  firewall-cmd --reload
fi

echo "== 5. SELinux"
if [ "$SEL" = 1 ]; then
  sed -i 's/^SELINUX=permissive/SELINUX=enforcing/' /etc/selinux/config
  echo "Set to enforcing in /etc/selinux/config. Reboot to apply (a relabel may take a while)."
else
  echo "Left as is (permissive). Re-run with --selinux to restore enforcing."
fi

echo "== Done. Check:"
ls -d /etc/rancher /var/lib/rancher 2>&1 | sed 's/^/  /'
command -v k3s >/dev/null && echo "  k3s still on PATH" || echo "  k3s gone"
echo "Tip: for a guaranteed clean slate, restore the VirtualBox snapshot instead."
