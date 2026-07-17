# Tekmeris

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21419196.svg)](https://doi.org/10.5281/zenodo.21419196) [![tests](https://github.com/kodzovee9/tekmeris/actions/workflows/tests.yml/badge.svg)](https://github.com/kodzovee9/tekmeris/actions/workflows/tests.yml)

Reproducible construction and auditing of social accounting matrices
(SAMs) from official statistics: an open toolkit (**edikit**) and the
research papers built on it.

> *tekmērion* (Greek): decisive proof.

## What is here

- **[`toolkit/`](toolkit/)** — `edikit`, a small Python library
  (Apache-2.0, Python ≥3.11, one dependency) in which accounting
  identities are executable checks, classification is never by naming
  convention, and every balancing adjustment is logged at the cell where
  it acts. Three documented entry points in
  [`toolkit/recipes/`](toolkit/recipes/):

  | Recipe | You have | You get |
  |---|---|---|
  | `replicate/` | this repository | every number in the P001 paper |
  | `audit/` | a published SAM | structural audit + macro-controls comparison |
  | `build/` | a country code | a validated, balanced macro SAM (any ESA-transmitting country) |

  ```bash
  cd toolkit/recipes/build && python build_sam.py --country AT --year 2019
  ```

- **[`papers/P001-za-sam/`](papers/P001-za-sam/)** — the working paper
  *"From Supply and Use Tables to Reproducible Social Accounting
  Matrices: A Transparent Construction and Audit Framework"* (South
  Africa · Kenya · Netherlands) with its complete replication package:
  registered sources with SHA-256 hashes, fifteen pipeline scripts,
  validation reports, and the manuscript. Appendix E of the paper maps
  every claim to the script that produces it.

## Reviewer pathway (five minutes, no network needed)

```bash
git clone https://github.com/kodzovee9/tekmeris && cd tekmeris
pip install -e "./toolkit[dev]"
pytest toolkit/tests -q          # expected: 23 passed
cd papers/P001-za-sam/code
python 15_netherlands_generate.py
```

The Dutch generation runs entirely from data committed in this
repository (three registered Eurostat JSON responses). A successful run
prints:

```
industries 65/65; products 65; identity findings 0; cross-diffs 0; commodity closure 65/65
macro matrix: 18 accounts, GDP(bp) EUR 724,960m
...
balanced SAM: converged=True in 418 its; max residual EUR 0.009m; max |factor-1| 2.82%
```

and regenerates `outputs/netherlands_generation.md` and the two matrix
CSVs byte-for-byte. For a networked demonstration on a country of your
choice: `cd toolkit/recipes/build && python build_sam.py --country AT
--year 2019`.

## Data availability

Raw inputs whose licences permit redistribution are committed under
`papers/P001-za-sam/data/raw/` (Statistics South Africa, with
attribution; IFPRI, CC-BY-4.0; Eurostat, free reuse with attribution).
Inputs that cannot be redistributed — SARB Quarterly Bulletin bulk
files, KNBS Economic Surveys, the UNU-WIDER benchmark SAM, and
DataFirst survey microdata — are registered in
[`SOURCES.md`](papers/P001-za-sam/data/SOURCES.md) with source URL,
access date, and SHA-256 hash: fetch them from the publisher and verify
the hash before running the scripts that need them (each script's
docstring states its inputs). Statistics South Africa data are used and
redistributed with acknowledgement of Stats SA as the source and may
not be sold.

## Citing

If you use the toolkit or the results, please cite the working paper
(citation file: [`CITATION.cff`](CITATION.cff)); a software paper for
`edikit` is in preparation.

## License

Code: Apache-2.0 (see [`LICENSE`](LICENSE)). Third-party data files
retain their publishers' terms, as noted above and in `SOURCES.md`.
