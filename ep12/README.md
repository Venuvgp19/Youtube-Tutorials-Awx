# Episode 12: Backup, restore and troubleshooting

**After this episode you can:** Recover AWX and debug failed jobs.

**Lab / demo:** AWXBackup, delete a template and the AWX instance, AWXRestore, read a failed job, first-look cluster commands

**Files:**

- `backup.yml`: AWXBackup of the `awx` deployment
- `restore.yml`: AWXRestore from that backup
- `troubleshoot.sh`: pods, operator/task/web logs, events, disk and memory

```bash
k3s kubectl apply -f ep12/backup.yml
k3s kubectl -n awx wait awxbackup/awx-backup-1 --for=condition=Successful --timeout=900s
k3s kubectl apply -f ep12/restore.yml
k3s kubectl -n awx wait awxrestore/awx-restore-1 --for=condition=Successful --timeout=1800s
```

Take a VM snapshot before practising the restore.

**Status:** files ready; video coming soon.
