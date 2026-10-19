# Episode 7: Custom Execution Environments

**After this episode you can:** Ship collections and Python deps reliably.

**Lab / demo:** check-ee fails on the default EE -> ansible-builder builds `localhost/awx-ee-mysql:1.0` -> imported into k3s -> EE in AWX -> check-ee passes

**Files:**

- `execution-environment.yml`: ansible-builder v3 definition on top of awx-ee 24.6.1 (community.mysql, PyMySQL, git)
- `check-ee.yml`: fails on the default EE, passes on the custom one

**Commands (AWX node, root):**

```bash
dnf install -y podman python3-pip && pip3 install ansible-builder
cd ep07 && ansible-builder build -t localhost/awx-ee-mysql:1.0 -v 1
podman save localhost/awx-ee-mysql:1.0 | k3s ctr images import -
```

In AWX: Execution Environments > Add, image `localhost/awx-ee-mysql:1.0`, pull "Only pull the image if not present". With more than one node, push the image to a registry (quay.io, a private registry) instead of importing it.

**Status:** files ready; video coming soon.
