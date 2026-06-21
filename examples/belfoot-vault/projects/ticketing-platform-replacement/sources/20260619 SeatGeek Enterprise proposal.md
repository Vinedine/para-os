# Vendor proposal - SeatGeek Enterprise

**Vendor:** SeatGeek Enterprise
**Submitted:** 2026-06-19 (one day before the deadline)
**In response to:** `20260515 BelFoot Ticketing RFP.md`

## Summary

SeatGeek Enterprise proposes its Open Platform with full API coverage, native dynamic pricing, and an integrated resale marketplace. EU data residency via their Frankfurt region. Salesforce integration through a supported managed connector.

## Fit against mandatory requirements

| Requirement | Response |
|-------------|----------|
| Open API | Met - REST + webhooks; GraphQL in beta |
| Dynamic pricing | Met - rule- and demand-based |
| Secondary market | Met - native, with configurable price caps |
| Salesforce integration | Met - managed connector, bidirectional |
| 24k account migration | Met - phased migration tooling, dedicated migration lead |
| Phased cutover | Met |
| EU data residency | Met - Frankfurt |
| SSO | Met - SAML / OIDC |

## Commercials (indicative)

- One-off implementation + migration: €420,000.
- Annual platform fee: €180,000 + 1.2% per-ticket fee on primary sales.
- 5-year TCO at current volumes: ~€2.1M.

## Open questions for evaluation

- GraphQL API still in beta - confirm GA timeline before the corporate-hospitality go-live (2027-02-01).
- The per-ticket fee on primary sales needs modelling against our volume; could exceed flat-fee competitors at our scale.
- Three reference clubs offered, two in the Bundesliga - arrange a reference call.

*Fictional example source backing the [ticketing replacement brief](../brief.md).*
