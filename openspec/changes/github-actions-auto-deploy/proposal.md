## Why

Deploying code changes to the VPS is currently a manual process — someone has to SSH in and run `bash /opt/crewledger/deploy/update.sh` every time code is pushed. This delays updates and creates a gap between what's on GitHub and what's live. A GitHub Actions workflow will auto-deploy on every push to `main`, eliminating the manual step entirely.

## What Changes

- Add a GitHub Actions workflow file (`.github/workflows/deploy.yml`) that triggers on push to `main`
- The workflow SSHs into the VPS and runs the existing `deploy/update.sh` script
- Requires three GitHub repository secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
- No changes to the application code, database, or existing deploy scripts

## Capabilities

### New Capabilities
- `ci-cd-pipeline`: GitHub Actions workflow for automated deployment to VPS on push to main

### Modified Capabilities
<!-- No existing spec requirements are changing. The deploy scripts remain identical. -->

## Impact

- **New file:** `.github/workflows/deploy.yml`
- **GitHub repo settings:** Three secrets must be configured (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`)
- **VPS:** No changes — reuses existing `deploy/update.sh`
- **Dependencies:** None — GitHub Actions is free for public repos
- **Risk:** Low — workflow only runs the same update script that's already proven in manual deploys
