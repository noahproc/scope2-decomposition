import lseg.data as ld
import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")
df = pd.read_csv(os.path.join(SCRIPT_DIR, "lseg_with_compustat.csv"))
instruments = df["Instrument"].dropna().tolist()
gvkey_map = dict(zip(df["Instrument"], df["GVKEY"]))

ld.open_session()

# ── TEST: 3 instruments ───────────────────────────────────────────────────────
TEST = False
universe = instruments[:3] if TEST else instruments
batch_size = 100
# ─────────────────────────────────────────────────────────────────────────────

CHECKPOINT = os.path.join(DATA_DIR, "financials_checkpoint.csv")
total = len(universe)

# Resume from checkpoint if it exists
if os.path.exists(CHECKPOINT):
    done_df = pd.read_csv(CHECKPOINT)
    done_instruments = set(done_df["Instrument"].unique())
    results = [done_df]
    print(f"Resuming from checkpoint: {len(done_instruments)}/{total} already done")
else:
    done_instruments = set()
    results = []

for idx, instrument in enumerate(universe):
    if instrument in done_instruments:
        continue
    try:
        data = ld.get_history(
            universe=instrument,
            fields=["TR.F.TotAssets", "TR.CompanyMarketCap"],
            interval="1Y",
            start="2010-01-01",
            end="2023-12-31"
        )
        if data is None or data.empty:
            continue
        data = data.reset_index()
        data.columns = [str(c) for c in data.columns]
        date_col = data.columns[0]
        data["Instrument"] = instrument
        data["year"] = pd.to_datetime(data[date_col]).dt.year
        results.append(data)
    except Exception as e:
        print(f"  [{idx+1}/{total}] {instrument} failed: {e}")
        continue

    # Save checkpoint every 500 instruments
    if (idx + 1) % 500 == 0:
        pd.concat(results, ignore_index=True).to_csv(CHECKPOINT, index=False)
        print(f"  [{idx+1}/{total}] Checkpoint saved")
    elif (idx + 1) % 100 == 0:
        print(f"  [{idx+1}/{total}] progress...")

ld.close_session()

combined = pd.concat(results, ignore_index=True)
print("Combined columns:", combined.columns.tolist())
print(combined.head(3))

# Rename whatever the two data columns are to standard names
data_cols = [c for c in combined.columns if c not in ["Instrument", "year"] and not c.lower().startswith("date")]
print("Data columns detected:", data_cols)
combined = combined.rename(columns={data_cols[0]: "total_assets", data_cols[1]: "market_cap"})

combined["gvkey"] = combined["Instrument"].map(gvkey_map)
financial_data = combined[["gvkey", "year", "total_assets", "market_cap"]].dropna(subset=["gvkey"])

print(financial_data.head(10))
out_file = "financial_data_test.csv" if TEST else "financial_data.csv"
financial_data.to_csv(os.path.join(DATA_DIR, out_file), index=False)
print(f"Saved {out_file} ({len(financial_data):,} rows)")
