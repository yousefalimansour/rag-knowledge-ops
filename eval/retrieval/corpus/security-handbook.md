# Security Handbook

Authoritative security reference for the engineering org.

## Password storage

User passwords are hashed with **Argon2id**, default parameters from `argon2-cffi`. Bcrypt is acceptable only as a last resort and only at cost factor 12 or higher.

## Secrets

All secrets are stored in 1Password vaults. Production secrets live in the `engineering-prod` vault and are mirrored into Kubernetes secrets via External Secrets Operator. Never commit secrets to git; the pre-commit hook scans for known prefixes.

## SAML / SSO

SSO uses Okta as the identity provider. SAML signing certificates rotate every 6 months. The rotation runbook is owned by the platform team and lives at `runbooks/saml-cert-rotation.md`. The next rotation is due 2026-08-15.

## Incident response

Severity-1 incidents page the on-call engineer via PagerDuty. The on-call writes a public retro in the `#eng-retros` Slack channel within 5 business days.

## Vulnerability disclosure

External researchers report vulnerabilities to security@example.com. We acknowledge within 24 hours and aim to ship a fix within 30 days for critical issues.
