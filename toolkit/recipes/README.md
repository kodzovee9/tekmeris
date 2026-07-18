# Recipes

Three entry points over one library (`edikit`), one per use case. They
correspond to the replicability spectrum of the P001 working paper: what
you can do depends on what the public record gives you.

| Recipe | You have | You get | Worked example |
|---|---|---|---|
| [`replicate/`](replicate/) | this repository | every number in the P001 paper, regenerated | South Africa, Kenya, Netherlands |
| [`audit/`](audit/) | a published SAM (+ published national accounts) | structural audit; macro-controls comparison | Kenya (IFPRI 2019 Nexus SAM) |
| [`build/`](build/) | a country code — or your country's SUT files | a validated macro SAM, no benchmark needed | covered ESA country-years ([COVERAGE.md](build/COVERAGE.md)), one command |

All three share the same machinery — readers, identity checks, explicit
classification, logged balancing — so a fix anywhere benefits every
recipe. Logic lives in `../src/edikit/`; recipes hold only thin scripts,
configuration, and documentation.

The common rule: **every choice a reader cannot see is a choice they
cannot check.** Register sources, enforce identities, report residuals.
