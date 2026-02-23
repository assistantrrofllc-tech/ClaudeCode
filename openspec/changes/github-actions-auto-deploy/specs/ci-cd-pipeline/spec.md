## ADDED Requirements

### Requirement: Auto-deploy on push to main
The system SHALL automatically deploy the latest code to the production VPS when commits are pushed to the `main` branch on GitHub.

#### Scenario: Successful deploy
- **WHEN** a commit is pushed to `main`
- **THEN** GitHub Actions SSHs into the VPS as root
- **AND** fixes file ownership (`chown -R crewledger:crewledger /opt/crewledger/`)
- **AND** runs `deploy/update.sh` (git pull, pip install, systemctl restart)
- **AND** the health check at `/health` returns `{"status": "ok"}`
- **AND** the workflow completes with a green check

#### Scenario: Failed deploy
- **WHEN** a deploy fails (health check fails or script errors)
- **THEN** the GitHub Actions workflow fails with a red X
- **AND** the error is visible in the workflow logs

### Requirement: SSH secrets configuration
The GitHub repository SHALL have three secrets configured for VPS access.

#### Scenario: Required secrets
- **GIVEN** the repository settings at Settings > Secrets > Actions
- **THEN** `VPS_HOST` contains the VPS IP address (`76.13.109.32`)
- **AND** `VPS_USER` contains `root`
- **AND** `VPS_SSH_KEY` contains the ed25519 private key authorized on the VPS
