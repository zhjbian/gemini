#!/usr/local/bin/python3
import sys
import os
import subprocess
import re
import markdown
import json
import argparse
from google import genai

# Setup paths
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")
from py_lib.sms import BBSms
from py_lib.bb_date_time import BBDateTime

DEFAULT_MODEL = "gemini-2.5-pro"
SCRIPTS_DIR = "/Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts"

def run_script_json(script_name, *args):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    env = os.environ.copy()
    py_tools = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools"
    bbt_data = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web"
    env["PYTHONPATH"] = f"{py_tools}:{bbt_data}:{env.get('PYTHONPATH', '')}"
    cmd = ["/usr/local/bin/python3", script_path] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0: return []
    try: return json.loads(result.stdout.strip())
    except: return []

def format_options_html(data):
    if not data: return "*(近 40 日无显著期权异动)*"
    html = "<table><thead><tr><th>日期/时间</th><th>合约</th><th>价格</th><th>数量</th><th>权利金</th><th>DTE</th><th>Spot</th><th>情绪</th><th>类型</th></tr></thead><tbody>"
    group_counter = 0
    last_id = None
    
    for i, row in enumerate(data):
        curr_id = row.get('sprd_id') or f"{row['date']} {row['time']}"
        is_spread = bool(row.get('sprd_id'))
        
        # Increment group counter whenever a NEW group starts
        if curr_id != last_id:
            group_counter += 1
            last_id = curr_id
        
        # Determine if this row is part of a cluster (for the vertical bar)
        has_top_neighbor = (i > 0 and (data[i-1].get('sprd_id') == curr_id if curr_id and data[i-1].get('sprd_id') else f"{data[i-1]['date']} {data[i-1]['time']}" == curr_id))
        has_bottom_neighbor = (i + 1 < len(data) and (data[i+1].get('sprd_id') == curr_id if curr_id and data[i+1].get('sprd_id') else f"{data[i+1]['date']} {data[i+1]['time']}" == curr_id))
        
        # Only show the vertical bar if it's a multi-leg trade (spread) AND actually clustered
        in_group = is_spread and (has_top_neighbor or has_bottom_neighbor)
        
        # Alternating Styles
        if not in_group:
            row_bg = "#ffffff"
            group_border = "border-left: 1px solid transparent;"
        else:
            if group_counter % 2 == 1:
                row_bg = "#f0f7ff" # Light Blue
                group_border = "border-left: 6px solid #1a5276;" # Deep Blue Bar
            else:
                row_bg = "#f3e5f5" # Light Purple
                group_border = "border-left: 6px solid #6a1b9a;" # Deep Purple Bar
        
        # Remove year (YYYY-)
        date_short = row['date'][5:] if len(row['date']) > 5 else row['date']
        
        html += f"<tr style='background-color: {row_bg};'>"
        html += f"<td style='{group_border} text-align: center; padding-left: 12px;'>{date_short} {row['time']}</td>"
        html += f"<td>{row['contract']}</td>"
        html += f"<td style='text-align: right;'>${row['price']:.2f}</td>"
        html += f"<td style='text-align: right;'>{row['qty']}</td>"
        html += f"<td style='text-align: right;'>${row['premium']:.2f}M</td>"
        html += f"<td style='text-align: right;'>{row['dte']}d</td>"
        html += f"<td style='text-align: right;'>${row['spot']:.2f}</td>"
        html += f"<td style='text-align: center; font-weight: bold;'>{row['sentiment']}</td>"
        html += f"<td>{row['type']}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

def format_orders_html(data):
    if not data: return "*(近 30 日无显著订单流大单)*"
    html = "<table><thead><tr><th>日期/时间</th><th>成交价</th><th>方向</th><th>真实意图</th><th>成交量</th><th>关联</th></tr></thead><tbody>"
    for row in data:
        ts_color = "#28a745" if row['true_side'] == 'Buy' else "#dc3545"
        tied_char = "✓" if row['tied'] else ""
        date_short = row['date'][5:] if len(row['date']) > 5 else row['date']
        html += f"<tr><td style='text-align: center;'>{date_short} {row['time']}</td><td style='text-align: right;'>${row['price']:.2f}</td><td style='text-align: center;'>{row['side']}</td><td style='text-align: center; color: {ts_color}; font-weight: bold;'>{row['true_side']}</td><td style='text-align: right;'>{row['size']/1e6:.1f}M</td><td style='text-align: center;'>{tied_char}</td></tr>"
    html += "</tbody></table>"
    return html

def format_spikes_html(data):
    if not data: return "*(近 30 日无未回补 Spike)*"
    html = "<table><thead><tr><th>日期</th><th>时段</th><th>目标价</th><th>现价</th><th>方向</th><th>涨跌幅</th><th>成交量</th></tr></thead><tbody>"
    for row in data:
        is_bull = row['target'] > row['spot']
        dir_char = "▲" if is_bull else "▼"
        dir_color = "#28a745" if is_bull else "#dc3545"
        change_pct = f"{row['change']:.2%}"
        date_short = row['date'][5:] if len(row['date']) > 5 else row['date']
        html += f"<tr><td style='text-align: center;'>{date_short}</td><td style='text-align: center;'>{row['hour']}</td><td style='text-align: right;'>${row['target']:.2f}</td><td style='text-align: right;'>${row['spot']:.2f}</td><td style='text-align: center; color: {dir_color}; font-weight: bold;'>{dir_char}</td><td style='text-align: right;'>{change_pct}</td><td style='text-align: right;'>{row['vol']}</td></tr>"
    html += "</tbody></table>"
    return html

def generate_report(ticker, date_str, send_email=False):
    ticker = ticker.upper()
    print(f"--- Synthesizing V8 Architecture for {ticker} ---")
    options_data = run_script_json("open_options_flow_analysis.py", ticker)
    orders_data = run_script_json("open_order_flow_analysis.py", ticker)
    spikes_data = run_script_json("open_spike_analysis.py", ticker)
    try: tech_raw = run_script_json("get_tech_data.py", ticker, date_str)
    except: tech_raw = {}
    
    ai_options = "\n".join([f"{o['time']} {o['contract']} P:{o['premium']}M S:{o['sentiment']}" for o in options_data[:20]])
    ai_orders = "\n".join([f"{d['date']} ${d['price']} Vol:{d['size']}M S:{d['true_side']}" for d in orders_data[:10]])
    ai_spikes = "\n".join([f"Target:{s['target']} Spot:{s['spot']} Vol:{s['vol']}" for s in spikes_data[:10]])

    master_prompt = f"""
    顶级机构研报合成任务: {ticker}
    期权异动: {ai_options if ai_options else "无"}
    大单订单: {ai_orders if ai_orders else "无"}
    价格Spike: {ai_spikes if ai_spikes else "无"}
    技术指标: {tech_raw}
    ===ANALYSIS_START===
    BBT 5-10天核心预测摘要。
    ===ANALYSIS_END===
    ===MASTER_START===
    2列4行纵向表：5-10天核心方向、股价Spike、期权大单、订单流大单。
    表头：维度 | 核心研判内容
    ===MASTER_END===
    ===TECH_START===
    三列表格：指标、数值、情绪解读。
    ===TECH_END===
    """
    # AI Synthesis
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    ai_output, used_model = "", "N/A"
    
    # 1. Tiered Fallback: Pro -> Flash-Lite -> 1.5-Flash
    for m in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
        try:
            print(f"Requesting BBT Analysis from {m}...")
            res = client.models.generate_content(model=m, contents=master_prompt)
            if res.text:
                ai_output, used_model = res.text.strip(), m
                print(f"Synthesis successful using {m}.")
                break
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue

    # 2. Static Heuristic Engine (If AI Fails Completely)
    if not ai_output:
        used_model = "Static-Heuristic-V1"
        net_bias = "震荡 (Neutral)"
        if orders_data:
            buys = sum(1 for d in orders_data if d['true_side'] == 'Buy')
            sells = sum(1 for d in orders_data if d['true_side'] == 'Sell')
            if buys > sells: net_bias = "积累 (Accumulation)"
            elif sells > buys: net_bias = "派发 (Distribution)"
        
        spike_target = spikes_data[0]['target'] if spikes_data else "无"
        
        ai_output = f"""
        ===ANALYSIS_START===
        *(由于 API 频率限制，当前由 BBT 静态引擎生成基础研判)*
        检测到近期机构偏向: {net_bias}。建议关注分项数据中的异动点位。
        ===ANALYSIS_END===
        ===MASTER_START===
        | 维度 | 核心研判内容 |
        | :--- | :--- |
        | 5-10天核心方向 | {net_bias} |
        | 股价Spike | 关注目标价 ${spike_target} |
        | 期权大单 | 请参考 4.1 详细列表 |
        | 订单流大单 | 请参考 4.2 详细列表 |
        ===MASTER_END===
        """

    def extract(prefix):
        # 1. Try strict tag match
        tag_pattern = rf"[=-]{{2,}}\s*{prefix}_START\s*[=-]{{2,}}(.*?)[=-]{{2,}}\s*{prefix}_END\s*[=-]{{2,}}"
        m = re.search(tag_pattern, ai_output, re.DOTALL | re.IGNORECASE)
        if m: return m.group(1).strip()
        
        # 2. Semantic Fallback
        lines = ai_output.split('\n')
        if prefix == 'ANALYSIS':
            paragraphs = [l for l in lines if l.strip() and '|' not in l and '=' not in l]
            if paragraphs: return "\n".join(paragraphs[:5])
        
        if prefix == 'MASTER' or prefix == 'TECH':
            m_table = re.search(r'(\|.*\|.*?\n(?:\|.*?\n)+)', ai_output, re.MULTILINE)
            if m_table: return m_table.group(1).strip()
            
        return ai_output[:800] if prefix == 'ANALYSIS' else "*(未能解析)*"

    html_sections = {
        "analysis": markdown.markdown(extract('ANALYSIS')),
        "master": markdown.markdown(f"\n\n{extract('MASTER')}\n\n", extensions=['tables', 'extra']),
        "tech": markdown.markdown(f"\n\n{extract('TECH')}\n\n", extensions=['tables', 'extra']),
        "options": format_options_html(options_data),
        "orders": format_orders_html(orders_data),
        "spikes": format_spikes_html(spikes_data)
    }

    final_html = f"""
    <html>
    <head>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 950px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
        h2 {{ color: #1a5276; background: #f4f7f9; padding: 10px; border-left: 6px solid #1a5276; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 0.85em; }}
        th {{ background-color: #1a5276; color: white; padding: 10px; text-align: left; }}
        td {{ border: 1px solid #eee; padding: 8px; }}
        .bullish {{ background-color: #e8f5e9; color: #2e7d32; font-weight: bold; padding: 2px 6px; border-radius: 3px; }}
        .bearish {{ background-color: #ffebee; color: #c62828; font-weight: bold; padding: 2px 6px; border-radius: 3px; }}
    </style>
    </head>
    <body>
        <h1>📈 BBT机构研报: {ticker} ({date_str})</h1>
        <h2>1. BBT 5-10天核心预测</h2> {html_sections['analysis']}
        <h2>2. BBT综合研判 (Synthesis)</h2> {html_sections['master']}
        <h2>3. 技术面情绪看板</h2> {html_sections['tech']}
        <h2>4. BBT分项数据 (Detailed Evidence)</h2>
        <h3>4.1 期权大单分析 (40-Day Options Flow)</h3> {html_sections['options']}
        <h3>4.2 订单流大单分析 (30-Day Order Flow)</h3> {html_sections['orders']}
        <h3>4.3 股价Spike分析 (30-Day Price Spikes)</h3> {html_sections['spikes']}
        <div style='text-align: center; margin-top: 50px; color: #999; font-size: 0.8em; border-top: 1px solid #eee; padding-top: 20px;'>
            Institutional Intelligence | Source: {used_model}
        </div>
    </body>
    </html>
    """

    def colorize(html):
        # Use non-capturing groups (?:...) to prevent regex numbering issues
        bull_p = r"(?:看多|看涨|多头|Bullish|BULL|Buy|强势|▲)"
        bear_p = r"(?:看空|看跌|空头|Bearish|BEAR|Sell|弱势|▼)"
        
        # Replace only the content inside <td> that matches the pattern
        html = re.sub(rf"(<td[^>]*>)([^<]*?{bull_p}[^<]*?)(</td>)", r'\1<span class="bullish">\2</span>\3', html)
        html = re.sub(rf"(<td[^>]*>)([^<]*?{bear_p}[^<]*?)(</td>)", r'\1<span class="bearish">\2</span>\3', html)
        return html

    if send_email:
        BBSms.send_to_gmail_html_from_ai(colorize(final_html), title="Stock Analysis Daily")
        print(f"V8 Architecture report dispatched.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="TSLA")
    parser.add_argument("--send-email", action="store_true")
    args = parser.parse_args()
    generate_report(args.ticker, BBDateTime.get_last_trading_day(), send_email=args.send_email)
