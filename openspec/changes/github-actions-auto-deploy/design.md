## Context

CrewLedger is deployed on a Hostinger KVM 2 VPS (`76.13.109.32`) as a systemd service. Code lives on GitHub (`assistantrrofllc-tech/ClaudeCode`). Currently, after pushing to `main`, someone must SSH into the VPS and run `bash /opt/crewledger/deploy/update.sh` manually. That script does: `git pull`, `pip install -r requirements.txt`, `systemctl restart crewledger`, and a health check.

The VPS SSH key is at `~/.ssh/id_ed25519` on the developer's Mac. The VPS accepts key-based auth only (no passwords). The app runs as user `crewledger` but deploy operations need `root` (for `systemctl restart` and ownership fixes).

## Goals / Non-Goals

**Goals:**
- Auto-deploy to VPS on every push to `main`
- Reuse the existing `deploy/update.sh` script (no reinventing the wheel)
- Health check confirms the deploy succeeded
- Fail visibly in GitHub Actions if deploy breaks

**Non-Goals:**
- Staging environment or multi-environment deploy
- Docker or container-based deployment
- Running tests in CI (can be added later as a separate workflow)
- Branch deploy previews
- Rollback automation (manual SSH rollback is acceptable for now)

## Decisions

### 1. SSH action: `appleboy/ssh-action`
**Why:** Most popular GitHub Action for SSH commands (10k+ stars). Simple — takes host, user, key, and a script. No agent forwarding or complex setup needed.
**Alternative considered:** Raw `ssh` command in a `run:` step — works but requires manual key file handling, known_hosts management, and is more error-prone.

### 2. Deploy as `root`, run git as `crewledger`
**Why:** The existing `update.sh` script uses `sudo -u crewledger git pull` and `systemctl restart` which requires root. SSH'ing as root and running the script as-is keeps things consistent with manual deploys.
**Alternative considered:** SSH as `crewledger` user — would require sudoers config for systemctl, adding complexity.

### 3. Fix permissions before pull
**Why:** We've already hit issues where `deploy/` files owned by root block `git pull` as `crewledger`. The workflow should `chown -R crewledger:crewledger /opt/crewledger/` before running the update script.

### 4. Three secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
**Why:** Standard pattern. Host and user as separate secrets allows easy VPS migration. The SSH private key is the ed25519 key already authorized on the VPS.

## Risks / Trade-offs

- **[SSH key in GitHub secrets]** → Acceptable risk. GitHub encrypts secrets and never exposes them in logs. The key only has access to this one VPS.
- **[Deploy on every push to main]** → Could deploy broken code. Mitigated by health check at end of update script. Future improvement: add a test step before deploy.
- **[No rollback]** → If a deploy breaks the site, manual SSH is needed. Acceptable given the team size and deploy frequency.
- **[Root SSH access]** → The VPS only accepts key-based auth, and the key is in GitHub secrets only. Low risk for a single-app VPS.
