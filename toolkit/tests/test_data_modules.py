import openpyxl
import pytest

from edikit.data.concordance import Concordance
from edikit.data.sam import read_labeled_matrix
from edikit.data.sut import check_supply_table, read_supply_table
from edikit.model.accounts import AccountKind, classify_by_prefix


# ---------- concordance ----------

def test_concordance_aggregate_and_validate():
    c = Concordance(name="t", mapping={"I1": "a1", "I2": "a1", "I3": "a2"})
    assert c.aggregate({"I1": 1.0, "I2": 2.0, "I3": 4.0}) == {"a1": 3.0, "a2": 4.0}
    assert c.validate(["I1", "I2", "I3"]) == []
    problems = c.validate(["I1", "I2", "I3", "I4"])
    assert len(problems) == 1 and "I4" in problems[0]


def test_concordance_csv_roundtrip(tmp_path):
    c = Concordance(name="t", mapping={"I1": "a1"}, target_labels={"a1": "Agri"})
    p = tmp_path / "c.csv"
    c.to_csv(str(p))
    c2 = Concordance.from_csv(str(p))
    assert c2.mapping == c.mapping and c2.target_labels == c.target_labels


# ---------- accounts ----------

def test_classify_by_prefix_longest_wins_and_raises():
    rules = {"a": AccountKind.ACTIVITY, "at": AccountKind.TAX}
    s = classify_by_prefix(["agri", "atax"], rules)
    kinds = {a.code: a.kind for a in s.accounts}
    assert kinds == {"agri": AccountKind.ACTIVITY, "atax": AccountKind.TAX}
    with pytest.raises(ValueError):
        classify_by_prefix(["zzz"], rules)


# ---------- synthetic workbook fixtures ----------

def _make_sut_workbook(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Supply Table 2019"
    ws.append(["", "", "", "Total supply at purchasers' prices",
               "Taxes less subsidies on products", "Trade and transport margins",
               "Total supply at basic prices", "I1", "I2"])
    ws.append(["Supply Table 2019"])
    ws.append(["R'million"])
    # basic = domestic output only in this toy (no imports)
    ws.append(["P1", "011", "Cereals", 130.0, 10.0, 20.0, 100.0, 60.0, 40.0])
    ws.append(["P2", "012", "Fruit", 62.0, 2.0, 10.0, 50.0, 50.0, 0.0])
    ws.append(["P1", "Total supply at basic prices", "", 192.0, 12.0, 30.0, 150.0, 110.0, 40.0])
    il = wb.create_sheet("Industry List")
    il.append(["Industry number in the SUT", "desc", "sic", "sic pub"])
    il.append(["I1", "Farming", "111", "11"])
    il.append(["I2", "Mining", "210", "21"])
    wb.save(path)


def test_read_and_check_supply_table(tmp_path):
    p = tmp_path / "sut.xlsx"
    _make_sut_workbook(str(p))
    t = read_supply_table(str(p), 2019)
    assert [pr.code for pr in t.products] == ["P1", "P2"]
    assert t.industries == ["I1", "I2"]
    assert t.output_by_industry() == {"I1": 110.0, "I2": 40.0}
    assert t.embedded_output_totals == {"I1": 110.0, "I2": 40.0}
    assert check_supply_table(t) == []


def test_check_supply_table_flags_broken_identity(tmp_path):
    p = tmp_path / "sut.xlsx"
    _make_sut_workbook(str(p))
    t = read_supply_table(str(p), 2019)
    t.total_supply_purchasers["P1"] = 999.0
    findings = check_supply_table(t)
    assert any(f.check == "row-identity" and f.subject == "P1" for f in findings)


def _make_sam_workbook(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SAM"
    ws.append(["Contents"])
    ws.append([None, "aagri", "cceri", "total"])
    ws.append(["aagri", 0, 100.0, 100.0])
    ws.append(["cceri", 100.0, 0, 100.0])
    ws.append(["total", 100.0, 100.0])
    wb.save(path)


def test_read_labeled_matrix(tmp_path):
    p = tmp_path / "sam.xlsx"
    _make_sam_workbook(str(p))
    m = read_labeled_matrix(str(p), "SAM")
    assert m.row_accounts == ["aagri", "cceri"]
    assert m.col_accounts == ["aagri", "cceri"]
    assert m.cells == {("aagri", "cceri"): 100.0, ("cceri", "aagri"): 100.0}
    assert m.embedded_col_totals == {"aagri": 100.0, "cceri": 100.0}
    assert m.embedded_row_totals == {"aagri": 100.0, "cceri": 100.0}
    assert m.col_sums() == {"aagri": 100.0, "cceri": 100.0}
    assert m.accounts_with_prefix("a") == ["aagri"]


def _make_use_workbook(path):
    from edikit.data.sut import read_use_table  # noqa: F401
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Use Table 2019"
    ws.append(["", "", "", "Total supply at purchasers' prices",
               "Taxes less subsidies on products", "I1", "I2", "", "", ""])
    ws.append(["", "", "", "", "", "11", "21", "Total industry", "Exports", "Households"])
    ws.append(["R'million"])
    # P1: supply 130 = intermediate (40+30) + exports 40 + hh 20
    ws.append(["P1", "011", "Cereals", 130.0, 10.0, 40.0, 30.0, 70.0, 40.0, 20.0])
    # P2x: supply 62 = intermediate (10+2) + exports 0 + hh 50
    ws.append(["P2", "012", "Fruit", 62.0, 2.0, 10.0, 2.0, 12.0, 0.0, 50.0])
    ws.append(["P2", " Total uses at purchasers' prices", "", None, None, 50.0, 32.0])
    ws.append(["B1", " Gross value added at basic prices", "", None, None, 60.0, 8.0])
    ws.append(["D1", "    Compensation of employees", "", None, None, 35.0, 5.0])
    ws.append(["D2/3", "    Taxes less subsidies", "", None, None, 5.0, 1.0])
    ws.append(["B2/3", "    Gross operation surplus/mixed income", "", None, None, 20.0, 2.0])
    ws.append(["P1", " Total output at basic prices", "", None, None, 110.0, 40.0])
    wb.save(path)


def test_read_and_check_use_table(tmp_path):
    from edikit.data.sut import check_use_table, read_use_table
    p = tmp_path / "use.xlsx"
    _make_use_workbook(str(p))
    t = read_use_table(str(p), 2019)
    assert [pr.code for pr in t.products] == ["P1", "P2"]
    assert t.industries == ["I1", "I2"]
    assert t.fd_categories == ["Exports", "Households"]
    assert t.intermediate_by_industry() == {"I1": 50.0, "I2": 32.0}
    assert t.value_added_by_industry("B1") == {"I1": 60.0, "I2": 8.0}
    assert t.embedded_output == {"I1": 110.0, "I2": 40.0}
    assert t.embedded_intermediate_by_product == {"P1": 70.0, "P2": 12.0}
    assert check_use_table(t) == []


def test_check_use_table_flags_broken_output_identity(tmp_path):
    from edikit.data.sut import check_use_table, read_use_table
    p = tmp_path / "use.xlsx"
    _make_use_workbook(str(p))
    t = read_use_table(str(p), 2019)
    t.embedded_output["I1"] = 999.0
    assert any(f.check == "output-identity" and f.subject == "I1"
               for f in check_use_table(t))


def test_cross_check_supply_use(tmp_path):
    from edikit.data.sut import cross_check_supply_use, read_supply_table, read_use_table
    ps, pu = tmp_path / "sut.xlsx", tmp_path / "use.xlsx"
    _make_sut_workbook(str(ps))
    _make_use_workbook(str(pu))
    sup = read_supply_table(str(ps), 2019)
    use = read_use_table(str(pu), 2019)
    assert cross_check_supply_use(sup, use) == []
    use.embedded_output["I2"] = 999.0
    assert any(f.check == "supply-use-output" for f in cross_check_supply_use(sup, use))


def _make_kbp_workbook(path):
    wb = openpyxl.Workbook()
    k = wb.active
    k.title = "K1"  # quarterly sheet, must be ignored by the annual reader
    k.append(["", "KBP9999K"])
    k.append(["20190100", 1.0])
    j = wb.create_sheet("J1")
    j.append(["", "KBP6000J", "KBP6001J"])
    j.append(["20180100", 2500000.0, 1000000.0])
    j.append(["20190100", 2732292.0, 1100000.0])
    wb.save(path)


def test_kbp_reader_and_formula(tmp_path):
    import zipfile
    from edikit.data.kbp import evaluate_formula, read_kbp_workbook, read_kbp_zips
    p = tmp_path / "kbp.xlsx"
    _make_kbp_workbook(str(p))
    d = read_kbp_workbook(str(p))
    assert d.get("KBP6000J", 2019) == 2732292.0
    assert d.get("KBP6000J", 2018) == 2500000.0
    assert "KBP9999K" not in d.values  # quarterly sheet ignored
    assert evaluate_formula("+KBP6000J+KBP6001J", d, 2019) == 3832292.0
    assert evaluate_formula("+KBP6000J-KBP6001J", d, 2019) == 1632292.0
    zp = tmp_path / "kbp.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.write(p, "inner/kbp.xlsx")
    d2 = read_kbp_zips([str(zp)])
    assert d2.get("KBP6001J", 2019) == 1100000.0
    with pytest.raises(KeyError):
        d2.get("KBP6001J", 1900)


# ---------- balancing ----------

def test_ras_converges_and_hits_targets():
    from edikit.model.balancing import ras
    seed = {("r1", "c1"): 1.0, ("r1", "c2"): 1.0, ("r2", "c1"): 1.0, ("r2", "c2"): 1.0}
    res = ras(seed, {"r1": 6.0, "r2": 4.0}, {"c1": 7.0, "c2": 3.0})
    assert res.converged
    assert abs(res.matrix[("r1", "c1")] + res.matrix[("r1", "c2")] - 6.0) < 1e-6
    assert abs(res.matrix[("r1", "c1")] + res.matrix[("r2", "c1")] - 7.0) < 1e-6
    assert res.max_factor_deviation() > 0


def test_ras_preserves_zero_structure():
    from edikit.model.balancing import ras
    seed = {("r1", "c1"): 2.0, ("r2", "c2"): 3.0}  # block-diagonal
    res = ras(seed, {"r1": 5.0, "r2": 7.0}, {"c1": 5.0, "c2": 7.0})
    assert res.converged
    assert ("r1", "c2") not in res.matrix and ("r2", "c1") not in res.matrix
    assert abs(res.matrix[("r1", "c1")] - 5.0) < 1e-6


def test_ras_rejects_bad_inputs():
    from edikit.model.balancing import ras
    with pytest.raises(ValueError):
        ras({("r", "c"): -1.0}, {"r": 1.0}, {"c": 1.0})
    with pytest.raises(ValueError):
        ras({("r", "c"): 1.0}, {"r": 2.0}, {"c": 1.0})  # inconsistent totals
    with pytest.raises(ValueError):
        ras({("r", "c"): 1.0}, {"r": 1.0, "r2": 1.0}, {"c": 2.0})  # empty seed row


def test_workbook_writer_live_formulas(tmp_path):
    from openpyxl import Workbook, load_workbook
    from edikit.report.workbook import add_matrix_sheet, add_readme_sheet, add_table_sheet
    wb = Workbook()
    add_readme_sheet(wb, "Test book", ["line one", "line two"])
    add_table_sheet(wb, "T", ["a", "b"], [[1, 2], [3, 4]])
    add_matrix_sheet(wb, "M", ["x", "y"], {("x", "y"): 5.0, ("y", "x"): 5.0})
    p = tmp_path / "t.xlsx"
    wb.save(p)
    rd = load_workbook(p)
    assert rd.sheetnames == ["README", "T", "M"]
    ws = rd["M"]
    assert ws["D2"].value == "=SUM(B2:C2)"      # row total formula, live
    assert ws["B4"].value == "=SUM(B2:B3)"      # column total formula, live
    assert ws["E2"].value == "=D2-B4"           # balance check formula, live
    assert ws["C2"].value == 5.0


def test_eurostat_jsonstat_reader(tmp_path):
    import json
    from edikit.data.eurostat import read_jsonstat
    doc = {
        "label": "Toy table", "id": ["geo", "item"], "size": [1, 3],
        "dimension": {
            "geo": {"category": {"index": {"NL": 0}, "label": {"NL": "Netherlands"}}},
            "item": {"category": {"index": {"A": 0, "B": 1, "C": 2},
                                  "label": {"A": "Alpha", "B": "Beta", "C": "Gamma"}}},
        },
        "value": {"0": 1.5, "2": 3.0},
    }
    p = tmp_path / "t.json"
    p.write_text(json.dumps(doc))
    t = read_jsonstat(str(p))
    assert t.values == {("NL", "A"): 1.5, ("NL", "C"): 3.0}
    assert t.value(geo="NL", item="A") == 1.5
    assert t.value(geo="NL", item="B") is None
    assert t.slice(geo="NL") == {("A",): 1.5, ("C",): 3.0}
    assert t.labels["item"]["B"] == "Beta"


def test_nace_coverage_parsing():
    from edikit.pipeline.eurostat_sam import coverage
    assert coverage("D") == ("D", None)
    assert coverage("CPA_C10-12") == ("C", {10, 11, 12})
    assert coverage("C31_32") == ("C", {31, 32})
    assert coverage("J59_60") == ("J", {59, 60})
    assert coverage("L68A") == ("L", {68})
    assert coverage("CPA_A01") == ("A", {1})


def test_partition_drops_contained_codes():
    from edikit.pipeline.eurostat_sam import partition
    # sub-details contained in a present aggregate are dropped
    assert partition(["C10-12", "C11", "C13-15", "C16"]) == \
        ["C10-12", "C13-15", "C16"]
    # a whole-section code absorbs its divisions
    assert partition(["E", "E36", "E37-39"]) == ["E"]
    # disjoint codes all survive, across sections
    assert partition(["A01", "A02", "B", "C10-12"]) == \
        ["A01", "A02", "B", "C10-12"]


def test_audit_balance_grain_and_aggregates(tmp_path):
    from edikit.pipeline.audit import audit, read_long_csv, write_report
    p = tmp_path / "sam.csv"
    # tiny 2-sector economy: act sells 100 to com; com sells 60 to hhd,
    # 40 back to act as intermediates; factors 60 -> hhd; hhd saves 0
    p.write_text("row,col,value\n"
                 "act,com,100\ncom,act,40\ncom,hhd,60\n"
                 "fac,act,60\nhhd,fac,60\n")
    cells = read_long_csv(p)
    kinds = {"act": "activity", "com": "commodity",
             "fac": "factor", "hhd": "household"}
    res = audit(cells, kinds=kinds)
    assert res.grain == 10.0
    assert res.gaps["act"] == 0 and res.gaps["com"] == 0
    assert res.aggregates["GVA (factor payments by activities)"] == 60
    assert res.aggregates["Private consumption"] == 60
    assert not res.coverage_gap
    write_report(res, tmp_path / "audit.md")
    text = (tmp_path / "audit.md").read_text()
    assert "Accounts: 4" in text and "GVA" in text


def test_audit_flags_unclassified_accounts():
    from edikit.pipeline.audit import audit
    res = audit({("a", "b"): 1.0, ("b", "a"): 1.0}, kinds={"a": "activity"})
    assert res.coverage_gap == ["b"]


def test_macro_balance_flips_negatives_and_converges():
    from edikit.pipeline.eurostat_sam import MacroSAMResult, balance
    res = MacroSAMResult(
        country="XX", year=2019, inds=[], prods=[], findings=[],
        cross_diffs=[], n3_check=0.0, n_closed=0, prod_resid={},
        sam={("a", "b"): 100.0, ("b", "a"): 90.0, ("a", "c"): -10.0,
             ("c", "b"): 12.0, ("b", "c"): 3.0})
    bal, flipped = balance(res)
    assert flipped == [("a", "c")]
    assert ("c", "a") in bal.matrix and all(v >= 0 for v in bal.matrix.values())
    assert bal.converged and max(bal.max_row_gap, bal.max_col_gap) < 1e-6
