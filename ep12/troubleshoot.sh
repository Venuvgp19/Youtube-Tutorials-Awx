#!/usr/bin/env bash
# First-look commands when AWX misbehaves (run as root on the AWX node).
K="k3s kubectl -n awx"
$K get awx,pods,pvc                      # is everything Running / Bound?
$K logs deploy/awx-operator-controller-manager -c awx-manager --tail=30   # operator errors
$K logs deploy/awx-task -c awx-task --tail=50                             # job dispatch errors
$K logs deploy/awx-web -c awx-web --tail=30                               # UI / API errors
$K get events --sort-by=.lastTimestamp | tail -15                         # pulls, OOM, scheduling
df -h / ; free -m                                                         # disk and memory
