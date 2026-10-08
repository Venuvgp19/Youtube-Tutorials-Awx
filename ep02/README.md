# Episode 2: Install AWX on k3s with the AWX Operator

**After this episode you can:** run AWX in a homelab VM.

Installs AWX 24.6.1 with AWX Operator 2.19.1 on single-node k3s (v1.36.5) on CentOS Stream 10. About 25 minutes, mostly image downloads.

## Quick start

```bash
git clone https://github.com/Venuvgp19/Youtube-Tutorials-Awx.git
cd Youtube-Tutorials-Awx/ep02
sudo ./install.sh
```

The script prints the URL and the admin password at the end. Change the password after the first login.

## Before you start

- VirtualBox VM: CentOS Stream 10, 4 vCPU, 8 GB RAM, 60 GB disk; NIC 1 host-only, NIC 2 NAT.
- Windows host: turn the Windows hypervisor off in an admin PowerShell, then reboot. Otherwise VirtualBox runs in Hyper-V mode (green turtle icon) and the guest can crash.

```powershell
bcdedit /set hypervisorlaunchtype off
```

- Reusing an old kubeadm node? Run `systemctl disable --now kubelet` first.

## Step by step (what the script does)

1. **Check the VM:** at least 2 CPU, 4 GB free RAM, 15 GB free on `/`.
2. **Firewall:** opens 6443 and 30080 and trusts the pod (10.42.0.0/16) and service (10.43.0.0/16) ranges, only if firewalld runs.
3. **SELinux:** sets permissive mode as a lab shortcut, only if enforcing.
4. **k3s:**
   ```bash
   curl -sfL https://get.k3s.io | INSTALL_K3S_SELINUX_WARN=true INSTALL_K3S_SKIP_SELINUX_RPM=true sh -s - --write-kubeconfig-mode 644
   k3s kubectl get nodes
   ```
5. **AWX Operator:** `k3s kubectl apply -k .` with [kustomization.yaml](kustomization.yaml).
6. **AWX instance:** `k3s kubectl apply -n awx -f awx.yaml` with [awx.yaml](awx.yaml) (NodePort 30080).
7. **Wait:** pods come up in this order: `awx-postgres-15-0`, `awx-web`, `awx-migration-24.6.1`, `awx-task`.
   ```bash
   k3s kubectl -n awx get pods -w
   ```
8. **Log in:**
   ```bash
   k3s kubectl -n awx get secret awx-admin-password -o jsonpath='{.data.password}' | base64 -d; echo
   ```

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Guest crashes, "stack guard page" in dmesg | VirtualBox running on Hyper-V | Turn the Windows hypervisor off, reboot Windows |
| Operator pod `ErrImagePull` on kube-rbac-proxy | gcr.io/kubebuilder images were removed | The `images` override in kustomization.yaml, or `k3s kubectl -n awx set image deploy/awx-operator-controller-manager kube-rbac-proxy=quay.io/brancz/kube-rbac-proxy:v0.15.0` |
| Exit code 139 or "exec format error" | Image layers corrupted by a crash | Scale the deployment to 0, `k3s crictl rmi <image>`, scale back to 1 |
| `kubectl` says localhost:8080 refused | An old kubeadm `kubectl` shadows k3s | Use `k3s kubectl` |
| `/` over 90% full | Disk too small | Add a disk, then `pvcreate /dev/sdb && vgextend cs /dev/sdb && lvextend -r -l +100%FREE cs/root` |
