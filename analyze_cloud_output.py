
import pandas as pd
import numpy as np

def analyze_results():
    try:
        df = pd.read_csv("cloud_optimization_final.csv")
    except FileNotFoundError:
        print("Error: cloud_optimization_final.csv not found.")
        return

    with open("analysis_report_utf8.txt", "w", encoding="utf-8") as f:
        def log(msg):
            # print(msg) # Disabled to prevent charmap errors on Windows console
            f.write(str(msg) + "\n")

        print("Writing results to analysis_report_utf8.txt...")
        log(f"Loaded {len(df)} results.")
        
        # 1. Clean and Filter
        df = df[df['trades'] > 30] 
        
        log("\n🏆 TOP 10 STRATEGIES (Global) 🏆")
        log(df.sort_values("wr", ascending=False).head(10)[['config', 'asset', 'direction', 'wr', 'trades', 'pnl']])
        
        log("\n💎 BEST PER ASSET & TIMEFRAME 💎")
        for asset in ["ES", "NQ"]:
            asset_df = df[df['asset'] == asset]
            for tf in sorted(df['config'].apply(lambda x: eval(x)['timeframe_minutes']).unique()):
                tf_df = asset_df[asset_df['config'].apply(lambda x: eval(x)['timeframe_minutes']) == tf]
                if tf_df.empty:
                    continue
                    
                best = tf_df.sort_values("wr", ascending=False).iloc[0]
                log(f"\n{asset} - {tf}m:")
                log(f"  WR: {best['wr']:.2f}% | Trades: {best['trades']} | PnL: ${best['pnl']:.2f}")
                log(f"  Dir: {best['direction']}")
                log(f"  Config: {best['config']}")
                
                if best['wr'] > 70.0:
                     log("  🚨 GRAIL ALERT (>70%) 🚨")

        log("\n📜 ORIGINAL PROTOCOL (Deep Stop) CHECKS 📜")
        def is_original(cfg_str):
            cfg = eval(cfg_str)
            return float(cfg.get('fib_stop', 1.0)) < 0.9
            
        orig_df = df[df['config'].apply(is_original)]
        if not orig_df.empty:
            best_orig = orig_df.sort_values("wr", ascending=False).head(5)
            log(best_orig[['asset', 'direction', 'wr', 'trades', 'config']])
        else:
            print("No results found matching Original Protocol Deep Stop logic.")

if __name__ == "__main__":
    analyze_results()
