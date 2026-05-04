#!/usr/local/bin/python3
"""
MASTER INSTITUTIONAL DAILY ANALYSIS
-----------------------------------
This is the master synthesis script that integrates Spikes, Options Flow, and Order Flow.
It runs the specialized sub-analysis scripts, aggregates their conclusions, and uses 
Gemini to produce a high-conviction 5-10 day directional judgment.

Usage:
    /usr/local/bin/python3 master_daily_analysis.py [TICKER]
"""

import os
import sys
import subprocess
import argparse
from google import genai
from rich.console import Console
from rich.panel import Panel

# Setup paths
SCRIPTS_DIR = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts"

def call_gemini(prompt, model_name="gemini-2.5-flash"):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "[Error: GEMINI_API_KEY environment variable not set]", "Error"
    
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text.strip(), model_name
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            fallback_model = "gemini-2.5-flash"
            try:
                response = client.models.generate_content(model=fallback_model, contents=prompt)
                return response.text.strip(), fallback_model
            except Exception as fe:
                return f"[Error: {fe}]", "Error"
        return f"[Error: {e}]", "Error"

def run_sub_script(script_name, ticker):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = ["/usr/local/bin/python3", script_path, ticker]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running {script_name}: {e.stderr}"

def main():
    parser = argparse.ArgumentParser(description="Master Institutional Analysis")
    parser.add_argument("ticker", help="Ticker symbol")
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    console = Console()
    
    console.print(Panel(f"[bold magenta]Starting Master Institutional Synthesis for {ticker}[/bold magenta]"))
    
    # 1. Run specialized analyses
    with console.status(f"[bold green]Running sub-analyses for {ticker}...[/bold green]"):
        spike_output = run_sub_script("open_spike_analysis.py", ticker)
        options_output = run_sub_script("open_options_flow_analysis.py", ticker)
        order_output = run_sub_script("open_order_flow_analysis.py", ticker)
    
    # 2. Extract AI summaries from outputs (assuming they are at the end of output)
    # We will pass the full outputs to Gemini for the most context
    
    # 3. Final Synthesis Prompt
    prompt = f"""
    You are a Master Institutional Strategist. Below are three specialized analyses for {ticker}.
    
    ### 1. SPIKE ANALYSIS (Price Magnets)
    {spike_output}
    
    ### 2. OPTIONS FLOW ANALYSIS (Institutional Bets)
    {options_output}
    
    ### 3. ORDER FLOW ANALYSIS (Big Trade Accumulation)
    {order_output}
    
    ### FINAL TASK:
    1. Synthesize these three pillars of institutional data into a single, high-conviction directional bias for {ticker} over the next 5-10 trading days.
    2. Identify the "Resonance Zones": Where do Spikes, Options strikes, and Big Trade levels overlap?
    3. Weigh conflicting signals: If Options are bullish but Order Flow is bearish, which one has higher volume/conviction?
    4. Provide the "Trade Logic": Why should a trader trust this direction?
    5. FORMAT: Provide a professional, concise summary in Chinese (简体中文).
       - Start with a clear [CORE DIRECTION]: (Bullish/Bearish/Neutral)
       - Follow with 3-4 bullet points of supporting evidence.
       - End with a "Confidence Rating" (0-100%).
    """
    
    with console.status("[bold blue]Performing Final Synthesis...[/bold blue]"):
        final_judgment, model = call_gemini(prompt)
    
    console.print("\n" + "="*60)
    console.print("[bold yellow]FINAL INSTITUTIONAL MASTER JUDGMENT[/bold yellow]")
    console.print("="*60)
    console.print(f"\n{final_judgment}")
    console.print(f"\n[dim]Model: {model}[/dim]")
    console.print("="*60 + "\n")

if __name__ == "__main__":
    main()
