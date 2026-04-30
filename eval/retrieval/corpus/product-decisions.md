# Product Decisions Log — 2025

Authoritative product decisions log. One bullet per decision; reasons and date are mandatory.

## Q1 2025

- **D-014 — Drop the in-product wiki feature.** Decided 2025-02-12. Reason: low engagement (3% MAU touched it in the prior quarter), and it duplicates functionality customers already get via the Notion integration.
- **D-017 — Adopt Postgres `tsvector` for keyword search instead of Elasticsearch.** Decided 2025-03-04. Reason: ops cost of running Elasticsearch outweighed the marginal recall improvement on our corpus size.

## Q2 2025

- **D-022 — Default new workspaces to the Team plan.** Decided 2025-04-30. Reason: Starter conversion was 9% lower vs Team-trial cohorts; aligning default with the higher-converting plan.
- **D-024 — Sunset the on-premise installer for new customers.** Decided 2025-05-19. Reason: maintenance burden, only 1.4% of new ARR came from on-prem in 2024, all existing on-prem customers grandfathered.

## Q3 2025

- **D-031 — Stop investing in the Slack-only beta.** Decided 2025-08-06. Reason: insights from the Slack-only cohort showed 47% lower retention vs full-product users; we are concentrating on the unified Copilot experience.

## Q4 2025

- **D-039 — Move embeddings to Google `gemini-embedding-001`, truncated to 768 dims.** Decided 2025-11-04. Reason: previous embedding endpoint deprecated; 768-dim Matryoshka truncation keeps the existing Chroma collection compatible.
