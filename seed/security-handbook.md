# Security Handbook

## Password requirements
Passwords must be at least 12 characters and include one symbol. We use
Argon2id for hashing — never store plaintext.

## Incident response
Suspected security incidents must be reported to security@example.com
within 30 minutes of detection. The on-call security engineer takes the
incident from there.

## Data classification
- **Public** — marketing pages, blog posts.
- **Internal** — engineering docs, ADRs.
- **Confidential** — customer data, source code.
- **Restricted** — credentials, signing keys.
