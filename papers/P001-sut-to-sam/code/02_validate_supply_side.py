"""Supply-side validation: official SUT vs the benchmark SAM.

Pipeline: read the StatsSA 2019 supply table (S-001), run its internal
consistency checks, aggregate industry output through the extracted 124->61
concordance, and compare per activity account with the benchmark SAM's
embedded column totals (S-003). Also checks that the benchmark SAM is
balanced (row sums equal column sums). Writes a markdown report and CSV.

Account classification is explicit: the SAM's `atx` account carries an
activity-style prefix but is taxes on production (its whole column pays gvt),
so prefix rules declare it TAX, not ACTIVITY. Unclassified codes raise.

Run from this directory, after 01_extract_concordance.py:
    python 02_validate_supply_side.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "toolkit" / "src"))
from edikit.data.concordance import Concordance  # noqa: E402
from edikit.data.sam import read_labeled_matrix  # noqa: E402
from edikit.data.sut import check_supply_table, read_supply_table  # noqa: E402
from edikit.model.accounts import AccountKind, classify_by_prefix  # noqa: E402

DATA = Path(__file__).parents[1] / "data"
OUT = Path(__file__).parents[1] / "outputs"
SUT_XLSX = DATA / "raw" / "statssa" / "Supply and use tables 2018 - 2019.xlsx"
SAM_XLSX = DATA / "external" / "tn2023-1-2019-SASAM-for-distribution.xlsx"
SAM_SHEET = "SASAM 2019 61Ind 10Occ"

# Rules for the 'a*' account block only; the full account map for all 209
# accounts is paper work against the technical note (see P001 README plan).
A_PREFIX_RULES = {"atx": AccountKind.TAX, "a": AccountKind.ACTIVITY}


def main() -> None:
    # 1. Official supply table + internal checks
    sut = read_supply_table(str(SUT_XLSX), 2019)
    findings = check_supply_table(sut, tolerance=0.5)

    # 2. Aggregate industry output through the concordance
    conc = Concordance.from_csv(str(DATA / "derived" / "concordance_industries.csv"),
                                name="sut124-to-sam61-industries")
    problems = conc.validate(sut.industries)
    sut_output_61 = conc.aggregate(sut.output_by_industry())

    # 3. Benchmark SAM: activity totals (explicitly classified) + balance check
    sam = read_labeled_matrix(str(SAM_XLSX), SAM_SHEET)
    a_block = sam.accounts_with_prefix("a")
    kinds = classify_by_prefix(a_block, A_PREFIX_RULES, source="S-003")
    activities = kinds.codes(AccountKind.ACTIVITY)
    non_activity = [a.code for a in kinds.accounts if a.kind != AccountKind.ACTIVITY]
    sam_activity = {c: sam.embedded_col_totals[c] for c in activities}

    col_sums, row_sums = sam.col_sums(), sam.row_sums()
    balance_gaps = {c: col_sums.get(c, 0.0) - row_sums.get(c, 0.0)
                    for c in sam.col_accounts}
    max_balance_gap = max(abs(g) for g in balance_gaps.values())

    # 4. Compare matched accounts; report unmatched separately
    matched, unmatched = [], []
    for code in sorted(set(sut_output_61) | set(sam_activity)):
        s, b = sut_output_61.get(code), sam_activity.get(code)
        if s is None or b is None:
            unmatched.append((code, s, b))
        else:
            matched.append((code, conc.target_labels.get(code, ""), s, b,
                            (b - s) / s * 100 if s else 0.0))

    OUT.mkdir(exist_ok=True)
    with open(OUT / "supply_validation.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sam_account", "label", "sut_output_aggregated_Rm",
                    "sam_activity_total_Rm", "deviation_pct"])
        for code, lab, s, b, d in matched:
            w.writerow([code, lab, f"{s:.1f}", f"{b:.1f}", f"{d:.4f}"])

    devs = [abs(d) for *_, d in matched]
    within1 = sum(1 for d in devs if d <= 1.0)
    tot_s = sum(s for _, _, s, _, _ in matched)
    tot_b = sum(b for _, _, _, b, _ in matched)
    worst = sorted(matched, key=lambda r: -abs(r[4]))[:10]

    with open(OUT / "supply_validation.md", "w") as f:
        f.write(f"# Supply-side validation report\n\nGenerated "
                f"by code/02_validate_supply_side.py.\n\n")
        f.write("## Internal consistency of the official supply table (S-001)\n\n")
        f.write(f"- Products: {len(sut.products)}; industries: {len(sut.industries)}\n")
        f.write(f"- Row identity (purchasers' = basic + taxes + margins) and column-total "
                f"checks: **{len(findings)} findings** at R0.5m tolerance\n")
        for x in findings[:20]:
            f.write(f"  - {x.check} / {x.subject}: {x.detail}\n")
        f.write("\n## Benchmark SAM integrity (S-003)\n\n")
        f.write(f"- Accounts: {len(sam.col_accounts)}; balance check (|column sum - row sum|): "
                f"max R{max_balance_gap:,.3f}m -> "
                f"{'balanced' if max_balance_gap < 0.5 else 'NOT balanced'}\n")
        f.write(f"- 'a*' block classified by explicit rules: {len(activities)} activities; "
                f"excluded as non-activity: {', '.join(non_activity)}\n")
        f.write("\n## Concordance (S-003 Industry_List)\n\n")
        f.write(f"- {len(conc.mapping)} SUT industries -> {len(conc.targets)} SAM activity accounts; "
                f"validation problems: {len(problems)}\n")
        for p in problems:
            f.write(f"  - {p}\n")
        f.write("\n## SUT output vs benchmark SAM activity totals\n\n")
        f.write(f"- Matched accounts: {len(matched)}; unmatched: "
                f"{', '.join(c for c, _, _ in unmatched) if unmatched else 'none'}\n")
        f.write(f"- Aggregate over matched: SUT R{tot_s:,.0f}m vs SAM R{tot_b:,.0f}m "
                f"({(tot_b - tot_s) / tot_s * 100:+.4f}%)\n")
        f.write(f"- Within 1%: {within1}/{len(matched)}; "
                f"median |dev| {sorted(devs)[len(devs)//2]:.4f}%; max |dev| {max(devs):.4f}%\n\n")
        f.write("### Largest deviations\n\n")
        f.write("| Account | Label | SUT (Rm) | SAM (Rm) | Dev % |\n|---|---|---|---|---|\n")
        for code, lab, s, b, d in worst:
            f.write(f"| {code} | {lab[:36]} | {s:,.0f} | {b:,.0f} | {d:+.4f} |\n")
        f.write("\nFull table: supply_validation.csv.\n")

    print(f"internal findings: {len(findings)}; concordance problems: {len(problems)}")
    print(f"SAM balance: max |colsum-rowsum| = R{max_balance_gap:,.3f}m; "
          f"non-activity in a* block: {non_activity}")
    print(f"matched: {len(matched)}; within 1%: {within1}; max |dev| {max(devs):.4f}%; "
          f"aggregate gap {(tot_b - tot_s) / tot_s * 100:+.4f}%")


if __name__ == "__main__":
    main()
