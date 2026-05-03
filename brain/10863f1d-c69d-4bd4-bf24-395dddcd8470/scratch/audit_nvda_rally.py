import pandas as pd
import json

def generate_rally_audit():
    res_path = "/Users/zhijiebian/.gemini/skills/spike-analysis/references/backtest_spike_results_nvda.csv"
    df = pd.read_csv(res_path)
    
    # Filter for signals since March 1, 2026
    start_date = "2026-03-01"
    df_rally = df[df['date'] >= start_date].copy()
    
    # Sort by date and time
    df_rally = df_rally.sort_values(by=['date', 'time'], ascending=True)
    
    output_rows = []
    for _, row in df_rally.iterrows():
        t_hit = "✅" if row['target_hit'] else "❌"
        d_hit = "✅" if row['delayed_hit'] else "❌"
        t_days = f"{int(row['days_to_target'])}" if row['target_hit'] else "-"
        
        # Determine Phase
        dt = row['date']
        if dt < "2026-03-20":
            phase = "Shadow Build"
        elif dt < "2026-03-31":
            phase = "Spring Load"
        else:
            phase = "Expansion"
            
        output_rows.append({
            'Date': row['date'],
            'Time': row['time'],
            'Phase': phase,
            'Side': row['direction'],
            'Target': f"${row['target']:.2f}",
            'Spot': f"${row['spot']:.2f}",
            'Vol': f"{int(row['vol']):,}",
            'Move': f"{row['target_move_pct']:.2f}%",
            'Hit': t_hit,
            'Days': t_days,
            'DD': f"{row['max_drawdown_pct']:.2f}%"
        })
    
    # Format into markdown table
    header = "| Date | Time | Phase | Side | Target | Vol | Move | Hit | Days | DD |"
    separator = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    
    table_lines = [header, separator]
    for r in output_rows:
        line = f"| {r['Date']} | {r['Time']} | {r['Phase']} | {r['Side']} | {r['Target']} | {r['Vol']} | {r['Move']} | {r['Hit']} | {r['Days']} | {r['DD']} |"
        table_lines.append(line)
    
    # Phase Statistics
    phases = ["Shadow Build", "Spring Load", "Expansion"]
    stats_lines = ["\n### Phase Efficiency Statistics\n"]
    stats_lines.append("| Phase | Total Signals | Hit Rate | Avg Days | Avg Drawdown |")
    stats_lines.append("| :--- | :--- | :--- | :--- | :--- |")
    
    for p in phases:
        subset = [r for r in output_rows if r['Phase'] == p]
        if not subset: continue
        total = len(subset)
        hits = len([s for s in subset if s['Hit'] == "✅"])
        hit_rate = (hits / total) * 100
        
        # Calculate averages from original DF to keep it numeric
        df_p = df_rally[(df_rally['date'] >= start_date)] # Re-derive phase masks as needed
        if p == "Shadow Build": mask = df_rally['date'] < "2026-03-20"
        elif p == "Spring Load": mask = (df_rally['date'] >= "2026-03-20") & (df_rally['date'] < "2026-03-31")
        else: mask = df_rally['date'] >= "2026-03-31"
        
        df_mask = df_rally[mask]
        avg_days = df_mask[df_mask['target_hit'] == True]['days_to_target'].mean()
        avg_dd = df_mask[df_mask['target_hit'] == True]['max_drawdown_pct'].mean()
        
        stats_lines.append(f"| {p} | {total} | {hit_rate:.1f}% | {avg_days:.1f} | {avg_dd:.2f}% |")

    with open("/Users/zhijiebian/.gemini/brain/10863f1d-c69d-4bd4-bf24-395dddcd8470/scratch/nvda_rally_audit_table.md", "w") as f:
        f.write("\n".join(table_lines))
        f.write("\n")
        f.write("\n".join(stats_lines))
    
    print("Audit table generated successfully.")

if __name__ == "__main__":
    generate_rally_audit()
