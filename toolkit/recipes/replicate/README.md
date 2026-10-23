# Replicate recipe

Reproduce the numbers in the companion paper (P001) from the registered
sources. Several inputs cannot be redistributed, and each user obtains them
from the publisher and verifies them against the manifest. The replication
package is `papers/P001-sut-to-sam/`:

- `data/SOURCES.md` is the source registry: publisher, vintage, URL and
  license. `data/SOURCES.sha256` gives the SHA-256 of every input, checkable
  with `shasum -a 256 -c` or `edikit.data.provenance.verify_sources`. Public raw files are committed under
  `data/raw/`; access-restricted microdata (DataFirst) and
  redistribution-unclear files are registered by URL + hash and live in
  git-ignored `data/external/` — fetch them per the registry before
  running the scripts that need them.
- `code/01–13` — South Africa: SUT validation, concordances, the
  institutional block from SARB formulas, the capital/occupation/household
  share systems, assembly under rules R1–R7, RAS balancing, workbook
  generation, and the paper's tables and figure.
- `code/14` — Kenya: structural audit and KNBS macro-controls comparison.
- `code/15` — Netherlands: benchmark-free macro-SAM generation.
- `paper/` — the LaTeX manuscript; exhibits regenerate from `code/13`.

## Install

```bash
pip install -e "./toolkit[dev,replicate]"
```

`edikit` itself needs only `openpyxl`. The `replicate` extra adds two
packages that the P001 scripts use but the library does not: `xlrd`
(script 07 reads the Stats SA Annual Financial Statistics, which are
legacy `.xls`) and `matplotlib` (script 13 draws the paper's figure).
Without it those two scripts stop with `ModuleNotFoundError`; the other
thirteen are unaffected.

Run scripts in numeric order from `code/` (each states its inputs in its
docstring). Every script writes a validation report to `outputs/` — the
reports, not the console, are the record.

Most scripts need inputs that cannot be redistributed here. From a clean
clone with no fetched data, three scripts run to completion: 12, 14 and 15.
The rest stop on a registered source:
- eight on the UNU-WIDER benchmark SAM (01 to 06, 09 and 11);
- script 08 on the text of that benchmark's technical note;
- script 10 on the Living Conditions Survey microdata.

Scripts 07 and 13 also need the `replicate` extra. This is expected, not
breakage: `papers/P001-sut-to-sam/data/raw/NOT-REDISTRIBUTED.md` in the
public repository states where each fetched file belongs. Scripts 07, 08
and 13 read the technical note's text, `external/tn2023-1.txt`, which you
extract from the registered PDF (`external/tn2023-1.pdf`); the PDF has a
digest in `SOURCES.sha256`, the extracted text does not.
