# Security

Keep API keys, passwords, JWT/MFA keys and OAuth/SMTP credentials in ignored
environment files or a deployment secret store. Use the committed `*.env.example`
templates with your own values. Never put credentials in `VITE_*` variables:
Vite embeds them in the public browser bundle.

Do not commit databases, uploads, backups, agent transcripts or real user data.
The local Docker Compose stack binds host ports to loopback. Use
[the production guide](docs/production-deployment.md) for an Internet deployment;
making this source repository public does not make a deployment production-ready.

Before pushing, scan all Git history with Gitleaks (redacted output), run
`npm audit --prefix frontend`, and audit the locked backend environment with
`pip-audit`. CI repeats the history and dependency checks. Never suppress a real
credential finding: revoke/rotate it first and review every branch and pull
request that may retain it. See
[GitHub's sensitive-data removal guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

Report vulnerabilities using the repository's private vulnerability reporting
feature when available. Do not include live credentials, personal data or
private documents in public issues or pull requests.
