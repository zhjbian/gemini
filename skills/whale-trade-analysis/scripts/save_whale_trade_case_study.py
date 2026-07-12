import sys
import os
import argparse
import shutil
import json
from datetime import datetime

# Append the bbt_data_web directory to path
web_dir = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web"
if web_dir not in sys.path:
    sys.path.insert(0, web_dir)

from flask import Flask
from db_connection_legacy import db
from models import WhaleTradeCaseStudy

def main():
    parser = argparse.ArgumentParser(description="Save or update a Whale Trade case study record in the database.")
    parser.add_argument("--date", required=True, help="Date of the case (YYYY-MM-DD)")
    parser.add_argument("--ticker", required=True, help="Ticker (e.g. TSLA)")
    parser.add_argument("--type", required=True, choices=["OrderFlow", "OptionsFlow", "OptionsFlowOrderFlow", "Spike", "OrderFlow+Adam"], help="Case type")
    parser.add_argument("--direction", required=True, choices=["Bullish", "Bearish", "Neutral"], help="Direction assessment")
    parser.add_argument("--summary", required=True, help="One-line summary description in Chinese")
    parser.add_argument("--detail-file", required=True, help="Path to file containing full markdown details")
    parser.add_argument("--images", nargs="*", default=[], help="List of absolute paths to screenshot images")
    parser.add_argument("--ai-model", default="gemini-1.5-pro", help="AI model used")
    parser.add_argument("--verify", choices=["Pending", "Correct", "Incorrect"], default="Pending", help="Verification actual result")
    parser.add_argument("--options-flow-file", help="Path to file containing raw Options Flow markdown table")
    parser.add_argument("--order-flow-file", help="Path to file containing raw Order Flow markdown table")
    parser.add_argument("--strength-score", type=int, help="Institutional intent strength score (0-100)")
    parser.add_argument("--strength-level", choices=["High", "Medium", "Low"], help="Institutional intent strength level (High/Medium/Low)")
    args = parser.parse_args()

    # Verify input date format
    try:
        case_date_val = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Error: Invalid date format '{args.date}'. Must be YYYY-MM-DD.")

    detail_file_path = args.detail_file
    if not os.path.exists(detail_file_path):
        sys.exit(f"Error: Detail file '{detail_file_path}' does not exist.")

    with open(detail_file_path, "r", encoding="utf-8") as f:
        detail_text = f.read().strip()

    # Construct strength_analysis dict if arguments provided
    strength_analysis = None
    if args.strength_score is not None and args.strength_level is not None:
        strength_analysis = {}
        if args.direction in ["Bullish", "Neutral"]:
            strength_analysis["accumulation"] = {
                "level": args.strength_level,
                "score": args.strength_score,
                "metrics": {},
                "breakdown": {}
            }
        if args.direction in ["Bearish", "Neutral"]:
            strength_analysis["distribution"] = {
                "level": args.strength_level,
                "score": args.strength_score,
                "metrics": {},
                "breakdown": {}
            }

    # Image files copying & URL resolution
    target_img_dir = os.path.join(web_dir, "static", "images", "whale_trade_case_studies")
    os.makedirs(target_img_dir, exist_ok=True)
    
    # Skill directory archive path
    skill_img_dir = "/Users/zhijiebian/.gemini/skills/whale-trade-analysis/images"
    os.makedirs(skill_img_dir, exist_ok=True)

    relative_img_urls = []
    analyze_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    for idx, img_path in enumerate(args.images):
        if not os.path.exists(img_path):
            print(f"Warning: Screenshot file '{img_path}' not found. Skipping.")
            continue
        
        _, ext = os.path.splitext(img_path)
        if not ext:
            ext = ".png" # default fallback
            
        # Create unique filename using whale_trade_<date>_<ticker>_<analyize date and time>_<idx>
        filename = f"whale_trade_{args.date}_{args.ticker}_{analyze_time_str}_{idx}{ext}"
        target_web_path = os.path.join(target_img_dir, filename)
        target_skill_path = os.path.join(skill_img_dir, filename)
        
        try:
            # Copy to Web Static Assets (for page rendering)
            shutil.copy2(img_path, target_web_path)
            print(f"Successfully copied image to web assets: {target_web_path}")
            
            # Copy to Skill Archive
            shutil.copy2(img_path, target_skill_path)
            print(f"Successfully archived image in skill folder: {target_skill_path}")
            
            # Resolve relative URL for database
            rel_url = f"/static/images/whale_trade_case_studies/{filename}"
            relative_img_urls.append(rel_url)
        except Exception as e:
            print(f"Error copying image '{img_path}': {e}")

    # Set up Flask app context
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        # Check if record already exists
        existing = WhaleTradeCaseStudy.query.filter_by(
            case_date=case_date_val,
            ticker=args.ticker,
            case_type=args.type
        ).first()

        new_analysis_block = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "content": detail_text
        }

        if existing:
            print(f"Record found for {args.ticker} on {args.date} ({args.type}). Performing follow-up update.")
            
            # Resolve JSON detail
            current_detail = existing.detail
            if not current_detail:
                current_detail = {"inputs": {"images": [], "time_range": "N/A"}, "analyses": []}
            elif isinstance(current_detail, str):
                try:
                    current_detail = json.loads(current_detail)
                except Exception:
                    current_detail = {"inputs": {"images": [], "time_range": "N/A"}, "analyses": []}

            # Update inputs.images if new images provided
            if relative_img_urls:
                existing_imgs = current_detail.get("inputs", {}).get("images", [])
                for img in relative_img_urls:
                    if img not in existing_imgs:
                        existing_imgs.append(img)
                if "inputs" not in current_detail:
                    current_detail["inputs"] = {}
                current_detail["inputs"]["images"] = existing_imgs

            if "inputs" not in current_detail:
                current_detail["inputs"] = {}
            if args.options_flow_file and os.path.exists(args.options_flow_file):
                with open(args.options_flow_file, "r", encoding="utf-8") as f:
                    current_detail["inputs"]["options_flow_md"] = f.read().strip()
            if args.order_flow_file and os.path.exists(args.order_flow_file):
                with open(args.order_flow_file, "r", encoding="utf-8") as f:
                    current_detail["inputs"]["order_flow_md"] = f.read().strip()

            # Append the new analysis to the list
            analyses_list = current_detail.get("analyses", [])
            # Place the newest analysis at the beginning of the list (ordered descending)
            analyses_list.insert(0, new_analysis_block)
            current_detail["analyses"] = analyses_list

            if strength_analysis:
                current_detail["strength_analysis"] = strength_analysis

            existing.detail = current_detail
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(existing, "detail")
            existing.summary = args.summary
            existing.direction = args.direction
            existing.ai_model = args.ai_model
            # Force update on last_modified_date_time since JSON modification may not trigger SQL onupdate automatically
            existing.last_modified_date_time = datetime.now()
            
            if args.verify != "Pending":
                existing.actual_result = args.verify

            db.session.commit()
            print("Successfully updated case study record in database.")
        else:
            print(f"No existing record. Creating new Whale Trade case study for {args.ticker} on {args.date}.")
            
            new_detail = {
                "inputs": {
                    "images": relative_img_urls,
                    "time_range": "N/A",
                    "options_flow_md": "",
                    "order_flow_md": ""
                },
                "analyses": [new_analysis_block]
            }

            if strength_analysis:
                new_detail["strength_analysis"] = strength_analysis

            if args.options_flow_file and os.path.exists(args.options_flow_file):
                with open(args.options_flow_file, "r", encoding="utf-8") as f:
                    new_detail["inputs"]["options_flow_md"] = f.read().strip()
            if args.order_flow_file and os.path.exists(args.order_flow_file):
                with open(args.order_flow_file, "r", encoding="utf-8") as f:
                    new_detail["inputs"]["order_flow_md"] = f.read().strip()

            study = WhaleTradeCaseStudy(
                case_date=case_date_val,
                ticker=args.ticker,
                case_type=args.type,
                direction=args.direction,
                summary=args.summary,
                detail=new_detail,
                actual_result=args.verify,
                ai_model=args.ai_model
            )

            db.session.add(study)
            db.session.commit()
            print("Successfully inserted new case study record in database.")

if __name__ == "__main__":
    main()
