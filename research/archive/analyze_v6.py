
import pandas as pd

def analyze_v6():
    try:
        df = pd.read_csv('engineering_results_v6.csv')
    except FileNotFoundError:
        print("Error: engineering_results_v6.csv not found.")
        return

    print("\n" + "="*80)
    print("  v6.0 ENGINEERING ANALYSIS REPORT")
    print("="*80)
    
    # 1. Did any pass the FULL validation?
    passed_full = df[df['full_trades'] > 0].copy()
    
    if passed_full.empty:
        print("\nWARNING: No candidates passed the sprint qualification (>60% WR).")
        print("Showing top 10 Sprint Performers (3-Week) instead:")
        print(df.sort_values('sprint_wr', ascending=False).head(10)[['asset', 'sprint_wr', 'sprint_trades', 'sprint_pnl']])
    else:
        print(f"\nSUCCESS: {len(passed_full)} candidates passed full validation!")
        
        # Sort by WR
        top_wr = passed_full.sort_values('full_wr', ascending=False)
        print("\n--- TOP CANDIDATES BY WIN RATE (3-Months) ---")
        cols = ['asset', 'full_wr', 'full_trades', 'full_pnl', 'use_macro', 'bb_expand', 'min_rvol', 'breakeven_r']
        print(top_wr.head(10)[cols].to_string())
        
        # Check for our 70% Target
        grails = passed_full[passed_full['full_wr'] >= 70]
        if not grails.empty:
            print("\n🏆 GRAIL FOUND (>= 70% WR)")
            print(grails[cols].to_string())
        else:
            print(f"\nNo 70% WR found. Best is {top_wr.iloc[0]['full_wr']:.2f}%")

if __name__ == "__main__":
    analyze_v6()
