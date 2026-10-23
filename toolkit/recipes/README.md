# Recipes

Three entry points over one library (`edikit`), one per use case. They
correspond to the replicability spectrum of the P001 working paper: what
you can do depends on what the public record gives you.

| Recipe | You have | You get | Worked example |
|---|---|---|---|
| [`replicate/`](replicate/) | this repository, plus restricted inputs you obtain | the companion paper's numbers | South Africa, Kenya, Netherlands |
| [`audit/`](audit/) | a published SAM (+ published national accounts) | structural audit; macro-controls comparison | Ghana and Kenya (2019 Nexus SAMs) |
| [`build/`](build/) | a country code (Eurostat-covered country-years) | a balanced macro SAM, no benchmark needed | five shipped runs (`build/examples/`); other covered ESA country-years ([COVERAGE.md](build/COVERAGE.md)), one command |

All three share the same machinery — readers, identity checks, explicit
classification, logged balancing — so a fix anywhere benefits every
recipe. Logic lives in `../src/edikit/`; recipes hold only thin scripts,
configuration, and documentation.

The common rule: **every choice a reader cannot see is a choice they
cannot check.** Register sources, check identities and report what they find, report residuals.
