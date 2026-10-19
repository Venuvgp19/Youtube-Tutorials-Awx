# Episode 9: Workflows: approvals and failure paths

**After this episode you can:** Chain jobs with approvals and rollback.

**Lab / demo:** workflow `safe-deploy`: wf-health -> approval -> wf-deploy, on failure -> wf-rollback; survey `package_name`

**Files:**

- `health_check.yml`: fails if / is over 90% full
- `deploy.yml`: installs `package_name` (default tree)
- `rollback.yml`: removes `package_name`

Try `no-such-package-xyz` as the package to watch the failure path run.

**Status:** files ready; video coming soon.
