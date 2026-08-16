#!/usr/bin/env python3
"""
Send styled, mobile-optimized HTML email using BBSms.send_to_gmail_html from PyTools/py_lib/sms.py.

Usage:
    python3 send_email.py --to recipient@example.com --subject "Subject Title" --content-file /path/to/content.txt
    python3 send_email.py --to recipient@example.com --subject "Subject Title" --content "Raw text content"
"""

import os
import sys
import argparse
import re

# Add BBTrading project root to sys.path to access PyTools
project_root = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
pytools_dir = os.path.join(project_root, "PyTools")
if pytools_dir not in sys.path:
    sys.path.insert(0, pytools_dir)

from py_lib.sms import BBSms


def convert_text_to_mobile_html(title, content):
    """
    Format raw text/markdown itinerary or notification content into a beautiful, 
    card-based, mobile-optimized HTML layout matching iOS native aesthetics.
    """
    # Clean up title
    clean_title = title.strip()
    
    # Split content into blocks by double newlines or sections
    lines = [line.strip() for line in content.strip().split("\n")]
    
    html_cards = []
    current_card_lines = []
    nav_link = None
    
    def render_card(card_lines):
        if not card_lines:
            return ""
        
        card_text = "\n".join(card_lines)
        
        # Check if this card contains confirmation/tickets info
        is_highlight = any(k in card_text for k in ["确认号", "Confirmation", "已预订", "订单号", "Order Number", "e-Ticket", "门票"])
        bg_style = "background-color: #f0fdf4; border: 1px solid #dcfce7;" if is_highlight else "background-color: #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.08);"
        
        rendered_lines = []
        for line in card_lines:
            if not line:
                continue
            
            # Check for header-like line with time badge (e.g. 08:00 – 08:40)
            time_match = re.match(r"^([\d\:\s–\-]+)\s+(.+)", line)
            if time_match and (":" in time_match.group(1) or "：" in time_match.group(1)):
                time_str = time_match.group(1).strip()
                rest_str = time_match.group(2).strip()
                
                badge_html = f'<span style="background: #1e3a8a; color: #ffffff; padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 13px;">{time_str}</span>'
                if is_highlight:
                    badge_html += ' <span style="background: #059669; color: #ffffff; padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 13px; margin-left: 4px;">已预订出票</span>'
                
                rendered_lines.append(f'<div style="margin-bottom: 8px;">{badge_html} <strong style="font-size: 16px; margin-left: 6px; color: #1d1d1f;">{rest_str}</strong></div>')
            elif line.startswith("http://") or line.startswith("https://"):
                rendered_lines.append(f'<a href="{line}" style="display: block; background: #0284c7; color: #ffffff !important; text-align: center; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px; margin-top: 10px;">📍 打开 Google Maps 导航</a>')
            elif "💡" in line or "⚠️" in line or "📋" in line or "📅" in line:
                rendered_lines.append(f'<div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 10px 12px; font-size: 13px; color: #92400e; line-height: 1.6; margin-top: 8px;">{line}</div>')
            else:
                # Format sub-items and bold text
                formatted_line = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
                rendered_lines.append(f'<div style="margin-top: 6px; font-size: 14px; line-height: 1.6; color: #374151;">{formatted_line}</div>')
        
        return f'<div style="{bg_style} border-radius: 14px; padding: 16px; margin-top: 14px;">{"".join(rendered_lines)}</div>'

    # Process lines
    for line in lines:
        if line.startswith("http://") or line.startswith("https://"):
            if not nav_link and ("maps" in line or "google" in line):
                nav_link = line
                continue
        
        # New section indicator
        if re.match(r"^(\d{1,2}:\d{2}|Day\s+\d+|[\u4e00-\u9fa5]{2,4}\s*[:：])", line) and current_card_lines:
            html_cards.append(render_card(current_card_lines))
            current_card_lines = [line]
        else:
            current_card_lines.append(line)
            
    if current_card_lines:
        html_cards.append(render_card(current_card_lines))

    nav_btn_html = ""
    if nav_link:
        nav_btn_html = f'''
  <a href="{nav_link}" style="display: block; background: #2563eb; color: #ffffff !important; text-align: center; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 15px; margin-bottom: 16px;">
    🗺️ 点击打开 Google Maps 全程导航路线
  </a>'''

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; color: #1d1d1f; margin: 0; padding: 16px; }}
  .header {{ font-size: 22px; font-weight: 700; color: #1d1d1f; margin-bottom: 4px; }}
  .subtitle {{ font-size: 13px; color: #86868b; margin-bottom: 16px; }}
</style>
</head>
<body>

<div class="header">{clean_title}</div>
<div class="subtitle">起点：Tower Suites by Blue Orchid · 紧凑手机便携版</div>
{nav_btn_html}
{"".join(html_cards)}

</body>
</html>
"""
    return full_html


def main():
    parser = argparse.ArgumentParser(description="Send mobile-optimized HTML email using BBSms.send_to_gmail_html")
    parser.add_argument("--to", default="zhjbian@gmail.com", help="Recipient email address (default: zhjbian@gmail.com)")
    parser.add_argument("--subject", required=True, help="Email subject title")
    parser.add_argument("--content", help="Raw email text content")
    parser.add_argument("--content-file", help="Path to file containing raw email text or HTML content")

    args = parser.parse_args()

    content = ""
    if args.content_file and os.path.exists(args.content_file):
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.content:
        content = args.content
    else:
        print("Error: Either --content or --content-file must be provided.")
        sys.exit(1)

    # Check if content is already HTML
    if content.strip().startswith("<!DOCTYPE html") or content.strip().startswith("<html"):
        html_body = content
    else:
        html_body = convert_text_to_mobile_html(args.subject, content)

    print(f"Sending email to {args.to} with subject: '{args.subject}'...")
    BBSms.send_to_gmail_html(html_body, subject=args.subject)
    print("Email successfully dispatched via BBSms!")


if __name__ == "__main__":
    main()
