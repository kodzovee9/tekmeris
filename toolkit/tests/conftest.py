"""Shared fixtures: a synthetic two-industry Eurostat economy whose
identities close exactly, with hooks for the malformed variants the tests
in test_checks.py need."""

import json


def _jsonstat(dims: dict, values: dict) -> dict:
    """Build a minimal JSON-stat 2.0 document from {(coords...): value}."""
    ids = list(dims)
    sizes = [len(dims[d]) for d in ids]
    doc = {"label": "synthetic", "id": ids, "size": sizes,
           "dimension": {d: {"category": {"index": {c: i for i, c in
                                                    enumerate(dims[d])}}}
                         for d in ids},
           "value": {}}
    for key, v in values.items():
        lin = 0
        for d, c in zip(ids, key):
            lin = lin * len(dims[d]) + dims[d].index(c)
        doc["value"][str(lin)] = v
    return doc


def synthetic_economy_paths(tmp_path, supply_edits=None,
                            drop_use_industry=None, use_edits=None):
    """Write supply, use and sector-account JSON-stat files; return paths.

    supply_edits and use_edits override cells {(industry, product): value}
    in the supply and use tables; drop_use_industry removes one industry
    from the use table.
    """
    fixed = {"freq": ["A"], "unit": ["MIO_EUR"], "stk_flow": ["TOTAL"]}
    geo_time = {"geo": ["XX"], "time": ["2019"]}
    F = ("A", "MIO_EUR", "TOTAL")
    GT = ("XX", "2019")

    sup_vals = {}
    for ind, prd, v in [
            ("A01", "CPA_A01", 100), ("B", "CPA_B", 200),
            ("TOTAL", "CPA_A01", 100), ("TOTAL", "CPA_B", 200),
            ("TOTAL", "CPA_TOTAL", 300),
            ("P7", "CPA_A01", 10), ("P7", "CPA_B", 20),
            ("P7", "CPA_TOTAL", 30),
            ("D21X31", "CPA_A01", 5), ("D21X31", "CPA_B", 10),
            ("D21X31", "CPA_TOTAL", 15),
            ("TS_BP", "CPA_A01", 110), ("TS_BP", "CPA_B", 220),
            ("TS_BP", "CPA_TOTAL", 330),
            ("TS_PP", "CPA_A01", 115), ("TS_PP", "CPA_B", 230),
            ("TS_PP", "CPA_TOTAL", 345)]:
        sup_vals[F + (ind, prd) + GT] = v
    for (ind, prd), v in (supply_edits or {}).items():
        sup_vals[F + (ind, prd) + GT] = v
    sup = _jsonstat({**fixed, "ind_impv": ["TOTAL", "TS_BP", "TS_PP",
                                           "P7", "D21X31", "A01", "B"],
                     "prd_amo": ["CPA_TOTAL", "CPA_A01", "CPA_B"],
                     **geo_time}, sup_vals)

    use_vals = {}
    for ind, prd, v in [
            # intermediates and their published TOTAL column
            ("A01", "CPA_B", 30), ("B", "CPA_A01", 40),
            ("TOTAL", "CPA_A01", 40), ("TOTAL", "CPA_B", 30),
            ("TOTAL", "CPA_TOTAL", 70),
            # value added: B1G = D1 + D29X39 + B2A3G; P1 = inter + B1G
            ("A01", "D1", 50), ("A01", "D29X39", 5), ("A01", "B2A3G", 15),
            ("A01", "B1G", 70), ("A01", "P1", 100),
            ("B", "D1", 100), ("B", "D29X39", 10), ("B", "B2A3G", 50),
            ("B", "B1G", 160), ("B", "P1", 200),
            ("TOTAL", "D1", 150), ("TOTAL", "D29X39", 15),
            ("TOTAL", "B2A3G", 65), ("TOTAL", "B1G", 230),
            ("TOTAL", "P1", 300),
            # final demand: TS_PP = intermediates + final demand
            ("P3_S14", "CPA_A01", 50), ("P3_S14", "CPA_B", 120),
            ("P3_S13", "CPA_A01", 10), ("P3_S13", "CPA_B", 20),
            ("P51G", "CPA_A01", 10), ("P51G", "CPA_B", 30),
            ("P6", "CPA_A01", 5), ("P6", "CPA_B", 30),
            ("P3_S14", "CPA_TOTAL", 170), ("P3_S13", "CPA_TOTAL", 30),
            ("P51G", "CPA_TOTAL", 40), ("P6", "CPA_TOTAL", 35)]:
        use_vals[F + (ind, prd) + GT] = v
    for (ind, prd), v in (use_edits or {}).items():
        use_vals[F + (ind, prd) + GT] = v
    if drop_use_industry:
        use_vals = {k: v for k, v in use_vals.items()
                    if k[3] != drop_use_industry}
    use_inds = [c for c in ["TOTAL", "P3_S13", "P3_S14", "P3_S15", "P51G",
                            "P52", "P53", "P6", "A01", "B"]
                if c != drop_use_industry]
    use = _jsonstat({**fixed, "ind_use": use_inds,
                     "prd_use": ["CPA_TOTAL", "CPA_A01", "CPA_B", "D1",
                                 "D29X39", "B2A3G", "B1G", "P1"],
                     **geo_time}, use_vals)

    nasa_vals = {}
    for item, sector, direct, v in [
            ("D1", "S14_S15", "RECV", 152), ("D1", "S2", "PAID", 2),
            ("B2A3G", "S11", "RECV", 40), ("B2A3G", "S12", "RECV", 5),
            ("B2A3G", "S13", "RECV", 5), ("B2A3G", "S14_S15", "RECV", 15),
            ("D4", "S11", "PAID", 10), ("D4", "S14_S15", "RECV", 8),
            ("D4", "S2", "RECV", 2),
            ("B8G", "S11", "RECV", 30), ("B8G", "S12", "RECV", 5),
            ("B8G", "S13", "RECV", 5), ("B8G", "S14_S15", "RECV", 5),
            ("B9", "S1", "PAID", 5)]:
        nasa_vals[("A", "CP_MEUR", direct, item, sector) + GT] = v
    nasa = _jsonstat({"freq": ["A"], "unit": ["CP_MEUR"],
                      "direct": ["PAID", "RECV"],
                      "na_item": ["D1", "B2A3G", "D4", "B8G", "B9"],
                      "sector": ["S1", "S11", "S12", "S13", "S14_S15", "S2"],
                      **geo_time}, nasa_vals)

    paths = {}
    for name, doc in [("supply", sup), ("use", use), ("sectors", nasa)]:
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(doc))
        paths[name] = p
    return paths
