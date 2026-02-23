## Tasks

### Task 1: Create GitHub Actions workflow file
- **File:** `.github/workflows/deploy.yml`
- **Trigger:** push to `main` branch
- **Steps:** SSH into VPS, fix permissions, run `deploy/update.sh`
- **Uses:** `appleboy/ssh-action` for SSH execution

### Task 2: Fix `deploy/update.sh` to run without sudo
- The current script uses `sudo -u crewledger` which fails when the crewledger user isn't in sudoers
- Update to use `su -s /bin/bash crewledger -c` for git operations, run pip and systemctl as root directly
- Keep the health check at the end

### Task 3: Configure GitHub repository secrets
- Add `VPS_HOST` = `76.13.109.32`
- Add `VPS_USER` = `root`
- Add `VPS_SSH_KEY` = contents of the ed25519 private key
- This is a manual step done via GitHub web UI or `gh secret set`

### Task 4: Test the pipeline
- Push a commit to `main` and verify the workflow runs
- Confirm the VPS is updated and healthy
