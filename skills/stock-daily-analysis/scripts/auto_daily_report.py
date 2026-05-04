#!/usr/local/bin/python3
"""
auto_daily_report.py - Institutional Intelligence Engine (V7: Absolute Reliability)
"""
import sys
import os
import subprocess
import re
import markdown
import argparse
from google import genai

# Setup paths
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")
from py_lib.sms import BBSms
from py_lib.bb_date_time import BBDateTime

DEFAULT_MODEL = "gemini-2.5-pro"
SCRIPTS_DIR = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts"

def run_script(script_name, *args):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = ["/usr/local/bin/python3", script_path] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def generate_report(ticker, date_str, model_name=DEFAULT_MODEL, send_email=False):
    ticker = ticker.upper()
    print(f"--- Synthesizing V7 Absolute-Reliability Report for {ticker} ---")
    
    # 1. Gather Data (Sync with Original DB Filters)
    options_raw = run_script("open_options_flow_analysis.py", ticker)
    orders_raw = run_script("open_order_flow_analysis.py", ticker)
    spikes_raw = run_script("open_spike_analysis.py", ticker)
    tech_raw = run_script("get_tech_data.py", ticker, date_str)
    
    # 2. AI Synthesis Call
    master_prompt = f"""
    你是一名顶级机构策略总监。请根据以下 30-40 天的机构行为数据为 {ticker} 生成深度研判。

    ### 原始数据:
    - 期权流 (40日): {options_raw if options_raw else "无显著异动"}
    - 现货流 (30日): {orders_raw if orders_raw else "无显著大单"}
    - 磁吸位 (30日): {spikes_raw if spikes_raw else "无显著未回补磁吸位"}
    - 技术指标: {tech_raw}

    ### 任务清单:
    
    ===ANALYSIS_START===
    5-10 天核心预测文字 (核心逻辑摘要，3-4句)。
    ===ANALYSIS_END===

    ===MASTER_START===
    生成一个【2列4行】的纵向表格。
    表头为：| 维度 | 核心研判内容 |
    行内容必须包含：
    1. 5-10天核心方向 (需包含逻辑摘要)
    2. 股价Spike (需包含具体点位及支撑阻力描述)
    3. 期权大单 (Options Flow) (需包含具体合约异动及方向暗示)
    4. 订单流大单 (Order Flow) (需包含成交量级及关键价位)
    ===MASTER_END===
    
    ===TECH_START===
    生成三列表格：指标、数值、情绪解读。
    ===TECH_END===

    要求：全中文，严格遵守定界符。
    """

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    ai_output = ""
    used_model = "N/A"
    
    # Use the specific models defined in your original PyTools scripts
    for m in ["gemini-2.5-pro", "gemini-2.5-flash-lite"]:
        try:
            print(f"Requesting BBT Analysis from {m}...")
            res = client.models.generate_content(model=m, contents=master_prompt)
            temp_output = res.text.strip()
            if "START" in temp_output.upper():
                ai_output = temp_output
                used_model = m
                print(f"Synthesis successful using {m}.")
                break
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue

    def extract(prefix):
        # Multi-stage extraction
        patterns = [
            rf"[=-]{{2,}}\s*{prefix}_START\s*[=-]{{2,}}(.*?)[=-]{{2,}}\s*{prefix}_END\s*[=-]{{2,}}",
            rf"{prefix}_START\s*(.*?){prefix}_END"
        ]
        for p in patterns:
            m = re.search(p, ai_output, re.DOTALL | re.IGNORECASE)
            if m: return m.group(1).strip()
        
        # Intelligent Fallback: If section specific tags are missing but AI output is present
        if ai_output and "|" in ai_output:
            if prefix == "MASTER" and "维度" in ai_output: return ai_output.strip()
            if prefix == "TECH" and "指标" in ai_output: return ai_output.strip()
            if prefix == "ANALYSIS" and len(ai_output) > 100: return ai_output.split("|")[0].strip()

        return "*(该环节数据正在同步计算中)*"

    # 3. Assemble Final Markdown (Core Forecast FIRST)
    # Important: Added extra newlines to ensure table rendering
    final_md = f"""
# 📈 BBT综合研判报告: {ticker} ({date_str})

***

## 1. BBT 5-10天核心预测
\n\n{extract('ANALYSIS')}\n\n

***

## 2. BBT综合研判 (Synthesis)
\n\n{extract('MASTER')}\n\n

***

## 3. 技术面情绪看板 (Technical Sentiment)
\n\n{extract('TECH')}\n\n

***

## 4. BBT分项数据 (Detailed Evidence)

### 4.1 期权大单分析 (40-Day Options Flow)
\n\n{options_raw if "|" in options_raw else "*(近 40 日无显著期权异动)*"}\n\n

***

### 4.2 订单流大单分析 (30-Day Order Flow)
\n\n{orders_raw if "|" in orders_raw else "*(近 30 日无显著现货大单)*"}\n\n

***

### 4.3 股价Spike分析 (30-Day Price Spikes)
\n\n{spikes_raw if "|" in spikes_raw else "*(近 30 日无显著未回补磁吸位)*"}\n\n
"""

    # 4. Render HTML
    html_body = markdown.markdown(final_md, extensions=['tables', 'extra'])
    
    # 5. Ultra-Stable Sentiment Coloring
    def apply_sentiment_colors(html):
        bull_p = r"(?:看多|看涨|多头|吸筹|Bullish|▲ BULL|▲|Buy|强势|超卖|Bullish Bias)"
        bear_p = r"(?:看空|看跌|空头|派发|Bearish|▼ BEAR|▼|Sell|弱势|超买|Bearish Bias)"
        html = re.sub(rf"(<td[^>]*>)([^<]*?{bull_p}[^<]*?)(</td>)", 
                      r'\1<span style="display:block; background-color:#e8f5e9; color:#2e7d32; font-weight:bold; padding:4px; border-radius:3px;">\2</span>\3', 
                      html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(rf"(<td[^>]*>)([^<]*?{bear_p}[^<]*?)(</td>)", 
                      r'\1<span style="display:block; background-color:#ffebee; color:#c62828; font-weight:bold; padding:4px; border-radius:3px;">\2</span>\3', 
                      html, flags=re.IGNORECASE | re.DOTALL)
        return html

    html_body = apply_sentiment_colors(html_body)
    
    final_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; max-width: 900px; margin: 0 auto; padding: 30px; line-height: 1.6; }}
        h1 {{ text-align: center; color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 10px; }}
        h2 {{ color: #1a5276; background: #f4f7f9; padding: 10px; border-left: 6px solid #1a5276; margin-top: 40px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; border: 1px solid #666; }}
        th {{ background-color: #1a5276; color: white; padding: 12px; text-align: left; }}
        td {{ border: 1px solid #ccc; padding: 10px; font-size: 0.9em; }}
        tr:nth-child(even) {{ background-color: #fcfcfc; }}
    </style>
    </head>
    <body>
        {html_body}
        <div style='text-align: center; margin-top: 80px; padding: 20px; border-top: 1px solid #eee; color: #7f8c8d; font-size: 0.8em;'>
            BBTrading Institutional Intelligence | Exact 40/30/30 Logic | Source: {used_model}
        </div>
    </body>
    </html>
    """

    if send_email:
        import time
        subject = "Stock Analysis Daily"
        # Unique fingerprint to prevent Gmail trimming
        final_html = final_html.replace("</body>", f"<p style='color:#fff; font-size:1px;'>ReportID: {time.time()}</p></body>")
        BBSms.send_to_gmail_html_from_ai(final_html, title=subject)
        print(f"Absolute-Reliability report dispatched.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="TSLA")
    parser.add_argument("date", nargs="?", default=None)
    parser.add_argument("--send-email", action="store_true")
    args = parser.parse_args()
    date_val = args.date if args.date else BBDateTime.get_last_trading_day()
    generate_report(args.ticker, date_val, send_email=args.send_email)
