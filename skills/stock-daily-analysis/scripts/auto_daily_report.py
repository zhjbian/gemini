#!/usr/local/bin/python3
"""
auto_daily_report.py - Automated Stock Analysis Report Generator

Usage:
  python auto_daily_report.py <ticker> <date> [--model MODEL_NAME] [--send-email]

Examples:
  python auto_daily_report.py TSLA 2026-03-13
  python auto_daily_report.py TSLA 2026-03-13 --model gemini-2.5-pro
  python auto_daily_report.py TSLA 2026-03-13 --model gemini-2.0-flash --send-email

Environment Variables:
  GEMINI_API_KEY  - Required. Your Google AI API key.
"""
import sys
import os
import subprocess
import re
import markdown
import datetime
import argparse

from google import genai

# Make sure we can import your BBSms script
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")
from py_lib.sms import BBSms
from py_lib.bb_date_time import BBDateTime

# Default model - can be overridden via --model flag
# DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_MODEL = "gemini-2.5-pro"
# DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"

def run_script(script_path, *args):
    result = subprocess.run(
        ["/usr/local/bin/python3", script_path] + list(args),
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error running {script_path}:\nRC: {result.returncode}\nSTDERR: {result.stderr}\nSTDOUT: {result.stdout}")
        return ""
    return result.stdout.strip()


def generate_report(ticker, date_str, model_name=DEFAULT_MODEL, send_email=False):
    print(f"Generating automatic report for {ticker} on {date_str}...")
    print(f"Using model: {model_name}")
    
    # 1. Gather Data
    tech_script = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_tech_data.py"
    bbt_script = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_bbt_data.py"
    
    # Target Stock Data
    tech_data = run_script(tech_script, ticker, date_str)
    bbt_data = run_script(bbt_script, ticker, date_str)
    
    if not tech_data and not bbt_data:
        print("Failed to gather target stock data.")
        return
        
    # General Market Data
    print("Gathering General Market Data...")
    spy_tech = run_script(tech_script, "SPY", date_str)
    spx_tech = run_script(tech_script, "^GSPC", date_str)
    es_bbt = run_script(bbt_script, "ES", date_str)
    nq_bbt = run_script(bbt_script, "NQ", date_str)
    vix_bbt = run_script(bbt_script, "VIX", date_str)
    
    # investing_cal_script = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_investing_cal.py"
    # catalyst_script = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_catalyst_data.py"
    
    # market_catalysts = run_script(investing_cal_script, date_str)
    # stock_catalysts = run_script(catalyst_script, "stock", ticker, date_str)
        
    # Institutional Flow Scripts
    fetch_options_script = "/Users/zhijiebian/.gemini/skills/options-flow-analysis/scripts/fetch_options_flow.py"
    fetch_spikes_script = "/Users/zhijiebian/.gemini/skills/spike-analysis/scripts/fetch_spikes.py"
    
    options_flow_data = run_script(fetch_options_script, ticker, date_str)
    spikes_data = run_script(fetch_spikes_script, ticker, date_str)
    
    spy_spikes = run_script(fetch_spikes_script, "SPY", date_str)
    qqq_spikes = run_script(fetch_spikes_script, "QQQ", date_str)


    # Read the latest skill instructions directly to ensure the AI uses the exact formatting
    skill_path = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/SKILL.md"
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            skill_content = f.read()
    except Exception as e:
        print(f"Could not read stock-daily-analysis SKILL.md: {e}")
        skill_content = "Please format as a professional trading report."
        
    # Read sub-skill instructions (Options Flow & Spikes)
    try:
        with open("/Users/zhijiebian/.gemini/skills/options-flow-analysis/SKILL.md", "r", encoding="utf-8") as f:
            opts_skill_content = f.read()
    except:
        opts_skill_content = "Analyze options flows."
        
    try:
        with open("/Users/zhijiebian/.gemini/skills/spike-analysis/SKILL.md", "r", encoding="utf-8") as f:
            spikes_skill_content = f.read()
    except:
        spikes_skill_content = "Analyze spikes."

        
    # 2. Build Prompt
    prompt = f"""
You are an expert stock market analyst. Generate a highly professional trading report for {ticker} based on the raw data provided below.

### 1. REPORT LAYOUT & FORMATTING RULES
You MUST follow the exact markdown structures (headings, tables, and bullet points) defined in the Master Skill instructions below. 
- **NO MASHING**: Every metric (Direction, Rating, etc.) MUST be on a new line with its own bullet point.
- **HEADERS**: Use `#### Trade: [Time] ...` or `#### [Time] (Magnet) ...` headers for each individual trade or spike found.
- **SPACING**: Insert an empty line between every individual trade group or spike target.


=== MASTER REPORT TEMPLATE (LAYOUT ONLY) ===
{skill_content}

---

### 2. ANALYTICAL LOGIC RULES
The master template requires you to identify "High Priority Trades" and "Magnets". Use the following specific sub-skill rules ONLY for the logic of classifying and identifying these signals.

=== OPTIONS ANALYSIS LOGIC (SIGNAL IDENTIFICATION ONLY) ===
{opts_skill_content}

=== SPIKE ANALYSIS LOGIC (SIGNAL IDENTIFICATION ONLY) ===
{spikes_skill_content}


---

### 3. RAW DATA
Date: {date_str}

=== PART A: S&P 500 MARKET RAW DATA ===
SPY Technicals:
{spy_tech}

SPX Technicals:
{spx_tech}

ES Flow Data (Use Orders Only):
{es_bbt}

NQ Flow Data (Use Orders Only):
{nq_bbt}

VIX Flow Data (Use Options Only):
{vix_bbt}

SPY RAW SPIKES:
{spy_spikes}

QQQ RAW SPIKES:
{qqq_spikes}



=== PART B: INDIVIDUAL STOCK RAW DATA ({ticker}) ===
RAW TECHNICAL DATA:
{tech_data}

RAW BBT FLOW DATA:
{bbt_data}


RAW OPTIONS FLOW DATA:
{options_flow_data}

RAW SPIKES MAGNET DATA:
{spikes_data}
"""

    print(f"Calling Gemini API ({model_name}) to analyze the data...")
    
    # 3. Call Gemini API via SDK
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY environment variable is not set.")
            return
        
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        
        md_content = response.text.strip()
        
        # Strip potential markdown code block wrappers if the model included them
        md_content = re.sub(r'^```markdown\s*', '', md_content)
        md_content = re.sub(r'\s*```$', '', md_content)
        
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return
    
    # 4. Save markdown report locally
    output_dir = "/Users/zhijiebian/.gemini/cli-workspace/stock-daily-analysis"
    os.makedirs(output_dir, exist_ok=True)
    md_path = f"{output_dir}/Stock_Analysis-{ticker}-{date_str}.md"
    html_path = f"{output_dir}/Stock_Analysis-{ticker}-{date_str}.html"
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Markdown report generated: {md_path}")
        
    # 5. Convert to HTML
    html_content = markdown.markdown(md_content, extensions=['tables'])

    # Inject basic CSS borders directly into HTML tags for Gmail compatibility
    html_content = html_content.replace('<table>', '<table style="border-collapse: collapse; width: 100%; margin-bottom: 20px; font-family: sans-serif;">')
    html_content = html_content.replace('<th>', '<th style="border: 1px solid #cccccc; padding: 8px; text-align: left; background-color: #f2f2f2;">')
    html_content = html_content.replace('<td>', '<td style="border: 1px solid #cccccc; padding: 8px; text-align: left;">')

    # Regex to safely find all <tr> elements and colorize based on content
    def colorize_row(match):
        row_html = match.group(0)
        # Check for sentiment keywords (including Chinese)
        if re.search(r'\b(Bull|Bullish|Buy|UP)\b|看多', row_html, re.IGNORECASE):
            return row_html.replace('<tr>', '<tr style="background-color: #e8f5e9;">')
        elif re.search(r'\b(Bear|Bearish|Sell|DN)\b|看空', row_html, re.IGNORECASE):
            return row_html.replace('<tr>', '<tr style="background-color: #ffebee;">')
        return row_html

    # Apply coloring to each table row
    html_content = re.sub(r'(?si)<tr>.*?</tr>', colorize_row, html_content)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML report generated: {html_path}")
    
    # 6. Send Email (optional)
    if send_email:
        print("Dispatching email...")
        BBSms.send_to_gmail_html_from_ai(html_content, title=f"Stock Analysis Daily: {ticker}")
        print("Email sent!")
    else:
        print("Skipping email dispatch (use --send-email to enable).")
    
    print("Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate automated stock analysis reports using Gemini AI.")
    parser.add_argument("ticker", nargs="?", default="TSLA", help="Stock ticker symbol (default: TSLA)")
    parser.add_argument("date", nargs="?", default=None, help="Date in YYYY-MM-DD format (default: last trading day)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--send-email", action="store_true", help="Send the report via email")
    
    args = parser.parse_args()
    
    if args.date is None:
        args.date = BBDateTime.get_last_trading_day()
    
    generate_report(args.ticker, args.date, model_name=args.model, send_email=args.send_email)
