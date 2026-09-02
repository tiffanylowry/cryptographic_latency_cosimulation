#!/usr/bin/env python3
"""
diff_csv.py

Column-aware CSV diff for comm_federate_log_300.csv-style output, where
manual "eyeball the CSV" comparison doesn't scale to hundreds/thousands of
columns (300 houses x several fields each). Two modes:

  Baseline mode (--mode=baseline): asserts every shared column is
  byte-identical (after float-tolerant numeric comparison) between two runs
  -- for regression checks where nothing should have changed (e.g. crypto
  disabled, same seed, before/after an unrelated code change).

  Sentinel mode (--mode=sentinels): asserts columns that are expected to be
  all-zero/disabled/not_delivered under a given condition actually are --
  e.g. crypto-disabled runs should show *_profile=disabled and *_dec_ms=0
  everywhere, not the not_delivered sentinel (which would indicate a
  delivery-pipeline bug, not merely "crypto is off").

Usage:
    python3 diff_csv.py --mode=baseline <run_a.csv> <run_b.csv> [--tol=1e-6]
    python3 diff_csv.py --mode=sentinels <run.csv> --expect-profile=disabled --expect-dec-ms=0
"""
import argparse
import csv
import sys


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def diff_baseline(path_a, path_b, tol):
    rows_a = load_csv(path_a)
    rows_b = load_csv(path_b)

    if len(rows_a) != len(rows_b):
        print(f"FAIL: row count differs ({len(rows_a)} vs {len(rows_b)})")
        return False

    cols_a = set(rows_a[0].keys()) if rows_a else set()
    cols_b = set(rows_b[0].keys()) if rows_b else set()
    shared = cols_a & cols_b
    only_a = cols_a - cols_b
    only_b = cols_b - cols_a
    if only_a:
        print(f"NOTE: {len(only_a)} column(s) only in {path_a}: {sorted(only_a)[:5]}{'...' if len(only_a) > 5 else ''}")
    if only_b:
        print(f"NOTE: {len(only_b)} column(s) only in {path_b}: {sorted(only_b)[:5]}{'...' if len(only_b) > 5 else ''}")

    mismatches = []
    for row_idx, (ra, rb) in enumerate(zip(rows_a, rows_b)):
        for col in shared:
            va, vb = ra[col], rb[col]
            if va == vb:
                continue
            try:
                fa, fb = float(va), float(vb)
                if abs(fa - fb) <= tol:
                    continue
            except ValueError:
                pass
            mismatches.append((row_idx, col, va, vb))

    if mismatches:
        print(f"FAIL: {len(mismatches)} mismatch(es) across {len(shared)} shared columns, {len(rows_a)} rows")
        for row_idx, col, va, vb in mismatches[:20]:
            print(f"  row {row_idx} col '{col}': {va!r} != {vb!r}")
        if len(mismatches) > 20:
            print(f"  ... and {len(mismatches) - 20} more")
        return False

    print(f"PASS: {len(shared)} shared columns, {len(rows_a)} rows, all identical (tol={tol})")
    return True


def diff_sentinels(path, expect_profile, expect_dec_ms):
    rows = load_csv(path)
    if not rows:
        print("FAIL: empty CSV")
        return False

    profile_cols = [c for c in rows[0].keys() if c.endswith("_profile")]
    dec_ms_cols = [c for c in rows[0].keys() if c.endswith("_dec_ms")]

    # Row 0 (the first control cycle) legitimately has no prior interval to
    # report delivery for -- ns3_cosim_300.cc documents this explicitly
    # (AggregatorControl's audit-buffer comment): every delivery column is
    # "not_delivered"/-1 there regardless of crypto state, by design. Skip
    # it here so this check reflects actual crypto-state sentinels, not the
    # unrelated first-row artifact.
    violations = []
    for row_idx, row in enumerate(rows[1:], start=1):
        for col in profile_cols:
            if row[col] != expect_profile:
                violations.append((row_idx, col, row[col], expect_profile))
        for col in dec_ms_cols:
            try:
                v = float(row[col])
            except ValueError:
                violations.append((row_idx, col, row[col], expect_dec_ms))
                continue
            if abs(v - expect_dec_ms) > 1e-9:
                violations.append((row_idx, col, row[col], expect_dec_ms))

    if violations:
        print(f"FAIL: {len(violations)} sentinel violation(s) across {len(profile_cols) + len(dec_ms_cols)} columns, {len(rows)} rows")
        for row_idx, col, got, expected in violations[:20]:
            print(f"  row {row_idx} col '{col}': got {got!r}, expected {expected!r}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        return False

    print(f"PASS: {len(profile_cols)} profile columns == '{expect_profile}', "
          f"{len(dec_ms_cols)} dec_ms columns == {expect_dec_ms}, {len(rows)} rows")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "sentinels"], required=True)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--expect-profile", default="disabled")
    ap.add_argument("--expect-dec-ms", type=float, default=0.0)
    args = ap.parse_args()

    if args.mode == "baseline":
        if len(args.paths) != 2:
            print("baseline mode requires exactly 2 CSV paths", file=sys.stderr)
            sys.exit(2)
        ok = diff_baseline(args.paths[0], args.paths[1], args.tol)
    else:
        if len(args.paths) != 1:
            print("sentinels mode requires exactly 1 CSV path", file=sys.stderr)
            sys.exit(2)
        ok = diff_sentinels(args.paths[0], args.expect_profile, args.expect_dec_ms)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
