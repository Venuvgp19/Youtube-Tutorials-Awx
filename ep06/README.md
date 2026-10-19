# Episode 6: Inventories, properly

**After this episode you can:** Organise hosts with groups and variables, keep the inventory in Git, and filter it with a smart inventory.

**Lab / demo:** groups and variables in the UI, an inventory source from this repo, a smart inventory

**Files:**

- `show-vars.yml`: pings every host and prints its groups, `env`, `role_name` and `app_port`
- `inventory/hosts.yml`: the inventory in Git (groups `homelab`, `web`, `db`; hosts `web1`, `web2`, `db1`)
- `inventory/group_vars/`: `all.yml` (env), `web.yml` and `db.yml` (role and port)
- `inventory/host_vars/web2.yml`: overrides `app_port` for one host (host beats group)
- `aws_ec2-source-vars.yml`: bonus, source variables for an Amazon EC2 inventory source (same idea, hosts come from AWS)

**AWX objects created:** group `linux` in the Lab inventory, template `show-vars`, inventory `lab-git` with source `git-hosts`, smart inventory `web-only`.

**Status:** files ready; video coming soon.
