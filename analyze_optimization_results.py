
import pandas as pd
import ast

def analyze_results():
    try:
        df = pd.read_csv('optimization_v51_einstein.csv')
    except FileNotFoundError:
        print("Error: optimization_v51_einstein.csv not found.")
        return

    output = []
    output.append("="*80)
    output.append("  EINSTEIN OPTIMIZATION DETAILED ANALYSIS")
    output.append("="*80)
    
    # helper to parse config string
    def parse_cfg(s):
        if pd.isna(s) or s == 'None': return None
        # It's a string representation of dataclass, e.g. "AssetConfig(asset='NQ', ...)"
        # We can regex it or just trust the string.
        return s

    # 1. BEST NQ CONFIGS
    output.append("\n--- BEST NQ CONFIGS (Sorted by WR, min 30 trades) ---")
    nq_results = []
    
    for idx, row in df.iterrows():
        # Parsing combined CSV is hard because we flattened it.
        # But we stored 'nq_config' as string.
        # Actually, the CSV rows come from "CombinedConfig".
        # If we want pure NQ, we look for rows where ES is None?
        # The optimizer loop: `for es in [None] + top_es: for nq in [None] + top_nq:`
        # So yes, there are rows with ES=None.
        
        es_cfg = str(row['es_config'])
        nq_cfg = str(row['nq_config'])
        
        if es_cfg != 'None': continue # Skip combined for now
        if nq_cfg == 'None': continue
        
        nq_results.append({
            'wr': row['combined_wr'],
            'pnl': row['combined_pnl'],
            'trades': row['combined_trades'],
            'cfg': nq_cfg
        })
        
    nq_df = pd.DataFrame(nq_results)
    if not nq_df.empty:
        best_nq = nq_df[nq_df['trades'] >= 30].sort_values('wr', ascending=False).head(10)
        output.append(best_nq.to_string())
    else:
        output.append("No NQ-only runs found in top results.")

    # 2. BEST ES CONFIGS
    output.append("\n\n--- BEST ES CONFIGS (Sorted by WR, min 30 trades) ---")
    es_results = []
    for idx, row in df.iterrows():
        es_cfg = str(row['es_config'])
        nq_cfg = str(row['nq_config'])
        
        if nq_cfg != 'None': continue 
        if es_cfg == 'None': continue
        
        es_results.append({
            'wr': row['combined_wr'],
            'pnl': row['combined_pnl'],
            'trades': row['combined_trades'],
            'cfg': es_cfg
        })
        
    es_df = pd.DataFrame(es_results)
    if not es_df.empty:
        best_es = es_df[es_df['trades'] >= 30].sort_values('wr', ascending=False).head(10)
        output.append(best_es.to_string())
    else:
        output.append("No ES-only runs found in top results.")
        
    # 3. BEST COMBINED BY PNL
    output.append("\n\n--- BEST COMBINED (Sorted by PnL) ---")
    best_combined = df.sort_values('combined_pnl', ascending=False).head(10)
    # Select cols
    cols = ['combined_wr', 'combined_pnl', 'combined_trades', 'es_config', 'nq_config']
    output.append(best_combined[cols].to_string())

    # Write to file
    with open('analysis_report.txt', 'w') as f:
        f.write("\n".join(output))
        
    print("Analysis saved to analysis_report.txt")
    
    # Print NQ best to stdout for quick check
    if not nq_df.empty:
        print("\nTOP NQ Candidate:")
        print(nq_df.sort_values('wr', ascending=False).iloc[0])

if __name__ == "__main__":
    analyze_results()
