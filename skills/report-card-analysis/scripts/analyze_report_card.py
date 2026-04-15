#!/usr/bin/env python3
"""
analyze_report_card.py - Overlake School Report Card Analyzer

Reads a report card HTML (or PDF), extracts course data, then generates
a bilingual analysis report using Gemini.

Usage:
  python analyze_report_card.py <html_or_pdf_path> [--output-dir <dir>]
"""
import sys
import os
import argparse
import json
import re
import datetime

from google import genai


DEFAULT_MODEL = "gemini-2.5-flash"


def extract_courses_from_html(html_path):
    """Parse the Veracross report card HTML deterministically using BeautifulSoup.
    Returns structured data dict with 100% accurate ratings."""
    from bs4 import BeautifulSoup

    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Extract student info from header
    student_info_div = soup.select_one(".student-info")
    student_name = ""
    grade_level = ""
    if student_info_div:
        # get_text() gives: "Name: Tingyu Tingyu BianGrade: 7Advisor: ..."
        info_text = student_info_div.get_text(separator="\n")
        name_match = re.search(r"Name:\s*(.+)", info_text)
        if name_match:
            student_name = name_match.group(1).strip()
        grade_match = re.search(r"Grade:\s*(\w+)", info_text)
        if grade_match:
            grade_level = grade_match.group(1).strip()

    time_info_div = soup.select_one(".time-info")
    school_year = ""
    quarter = ""
    if time_info_div:
        info_text = time_info_div.get_text()
        year_match = re.search(r"Year:\s*([\d-]+)", info_text)
        if year_match:
            school_year = year_match.group(1).strip()
        term_match = re.search(r"Term:\s*(.+?)$", info_text, re.MULTILINE)
        if term_match:
            quarter = term_match.group(1).strip()

    # Extract each course
    courses = []
    class_divs = soup.select(".body .class")

    for class_div in class_divs:
        course = {}

        # Course header: name, teacher, grade, absences
        header = class_div.select_one(".class-header")
        if header:
            grid_items = header.select("[class*='sf-grid-item']")
            for item in grid_items:
                text = item.get_text(strip=True)
                if text.startswith("Teacher:"):
                    course["teacher"] = text.replace("Teacher:", "").strip()
                elif text.startswith("Grade:"):
                    grade_str = text.replace("Grade:", "").strip()
                    course["grade"] = grade_str
                    # Parse numeric grade
                    num_match = re.match(r"(\d+)%", grade_str)
                    course["grade_numeric"] = int(num_match.group(1)) if num_match else None
                elif text.startswith("Absences:"):
                    course["absences"] = text.replace("Absences:", "").strip()
                elif not any(text.startswith(p) for p in ("Teacher:", "Grade:", "Absences:")):
                    course["course_name"] = text

        # Comments
        comment_div = class_div.select_one(".comment")
        curriculum_comment = ""
        teacher_comment = ""
        if comment_div:
            # Find all title divs within comment
            title_divs = comment_div.select(".title")
            for i, title_div in enumerate(title_divs):
                title_text = title_div.get_text(strip=True)
                # Get the text between this title and the next title (or end)
                # Use next siblings approach
                comment_text = ""
                sibling = title_div.next_sibling
                while sibling:
                    if hasattr(sibling, 'name') and sibling.name is not None:
                        # It's a Tag element
                        if 'title' in (sibling.get('class') or []):
                            break  # next title section
                        comment_text += sibling.get_text()
                    else:
                        # It's a NavigableString (plain text)
                        comment_text += str(sibling)
                    sibling = sibling.next_sibling

                comment_text = comment_text.strip()
                if "CURRICULUM COMMENT" in title_text:
                    curriculum_comment = comment_text
                elif "TEACHER COMMENT" in title_text:
                    teacher_comment = comment_text

        course["curriculum_comment"] = curriculum_comment
        course["teacher_comment"] = teacher_comment

        # Parse rubric tables
        behaviors = []
        skills = []
        tables_divs = class_div.select(".tables")

        for tables_div in tables_divs:
            table = tables_div.select_one("table.rubric-table")
            if not table:
                continue

            # Get column headers (rating levels)
            headers = []
            for th in table.select("thead th"):
                th_text = th.get_text(strip=True)
                headers.append(th_text)

            # Determine if this is behaviors or skills table
            table_type = headers[0] if headers else ""
            is_behaviors = "Behaviors" in table_type
            is_skills = "Skills" in table_type

            # Parse each row
            for tr in table.select("tbody tr"):
                tds = tr.select("td")
                if not tds:
                    continue

                item_text = tds[0].get_text(strip=True)
                rating = ""

                # Find which column has the "X" mark
                for col_idx in range(1, len(tds)):
                    cell_text = tds[col_idx].get_text(strip=True)
                    if cell_text == "X":
                        # Map column index to header
                        if col_idx < len(headers):
                            rating = headers[col_idx]
                        break

                entry = {"item": item_text, "rating": rating}
                if is_behaviors:
                    behaviors.append(entry)
                elif is_skills:
                    skills.append(entry)

        course["behaviors"] = behaviors
        course["skills"] = skills
        courses.append(course)

    data = {
        "student_name": student_name,
        "quarter": quarter,
        "school_year": school_year,
        "courses": courses,
    }

    # Print extraction summary for verification
    print(f"  Student: {data.get('student_name', 'Unknown')}")
    print(f"  Quarter: {data.get('quarter', 'Unknown')}")
    print(f"  Courses: {len(data.get('courses', []))}")
    for c in data.get("courses", []):
        name = c.get("course_name", "?")
        grade = c.get("grade", "?")
        n_behaviors = len(c.get("behaviors", []))
        n_skills = len(c.get("skills", []))
        # Show non-top ratings for quick verification
        non_top_b = [b for b in c.get("behaviors", []) if b.get("rating") not in ("Consistently",)]
        non_top_s = [s for s in c.get("skills", []) if s.get("rating") not in ("Accomplished", "Exemplary")]
        flag = ""
        if non_top_b or non_top_s:
            flag = " ⚠️ non-top ratings: " + ", ".join(
                [f"{b['item'][:30]}={b['rating']}" for b in non_top_b] +
                [f"{s['item'][:30]}={s['rating']}" for s in non_top_s]
            )
        print(f"    {name}: {grade} | {n_behaviors} behaviors, {n_skills} skills{flag}")

    return data


def generate_analysis_report(client, model_name, report_data):
    """Generate the bilingual analysis report from extracted data."""

    courses_json = json.dumps(report_data, ensure_ascii=False, indent=2)
    today = datetime.datetime.now().strftime('%Y-%m-%d')

    student = report_data.get('student_name', 'Unknown')
    quarter = report_data.get('quarter', 'Unknown')
    school_year = report_data.get('school_year', 'Unknown')

    prompt = f"""You are an educational consultant analyzing a student's report card from Overlake School.

Below is the EXACT structured data extracted from the report card PDF. The ratings in the "behaviors" and "skills" fields are PRECISE — use them EXACTLY as provided, do NOT change any rating values.

{courses_json}

Generate a comprehensive analysis report in Markdown format.

IMPORTANT RULES:
1. Translate ALL comments completely — do NOT summarize or shorten any teacher or curriculum comment
2. Keep person names, school names, and place names in English within Chinese translations
3. Analysis sections must be in Chinese with key English terms preserved
4. For grades below 95%, the improvement suggestions must be SPECIFIC and ACTIONABLE, referencing the teacher's actual words
5. Include a blank line before every markdown table
6. For CR (credit/no-credit) courses, focus on behavior and skill ratings
7. The Behaviors and Skills ratings in the tables below MUST match EXACTLY what is in the data above — do NOT modify any rating value

Use this exact structure:

# 📋 Overlake School 成绩单分析报告
**学生**: {student}
**学期**: {quarter} | **学年**: {school_year}
**分析日期**: {today}

---

## 📊 成绩总览

| 课程 | 成绩 | 状态 |
|------|------|------|

(Use ✅ for >=95%, ⚠️ for <95%, 📝 for CR)

---

Then for EACH course, create:

## [status emoji] [Course Name] — [Grade]

### 📝 课程描述 (Curriculum Comment)

**原文**: (Full original English curriculum_comment from the data, word for word)

**中文翻译**: (Complete Chinese translation)

### 💬 老师评语 (Teacher Comment)

**原文**: (Full original English teacher_comment from the data, word for word)

**中文翻译**: (Complete Chinese translation)

### 📊 评分详情

**Behaviors and Learning Dispositions (学习习惯与态度)**:

| 评估项目 | 评分 |
|----------|------|
(Copy EXACTLY from the behaviors list in the data — do NOT change any rating)

**Skills and Content (技能与内容)**:

| 评估项目 | 评分 |
|----------|------|
(Copy EXACTLY from the skills list in the data — do NOT change any rating)

### 🔍 综合分析

Based on teacher comment, behaviors, and skills ratings, generate the analysis below.

CRITICAL FORMATTING RULES for this section:
- DO NOT use nested sub-bullets. Use ONLY top-level bullets (single `-` with no indentation).
- Chinese and English MUST be in SEPARATE paragraphs/sections, NOT mixed on adjacent lines.
- Always add a blank line between each bullet point so markdown renders them as separate list items, not a single paragraph.
- Keep each bullet point concise — 1-2 sentences max.

If grade < 95% or any behavior not "Consistently" or any skill not "Accomplished"/"Exemplary":

#### ⚠️ 需要关注的领域 (Areas Needing Attention)

**中文：**

- [Item name in Chinese] — 评级: [rating]. [Brief explanation in Chinese, quoting teacher]

- [Next item] — 评级: [rating]. [Brief explanation]

(one bullet per area, with a blank line between each)

**English:**

- [Item name in English] — Rating: [rating]. [Brief explanation in English, quoting teacher]

- [Next item] — Rating: [rating]. [Brief explanation]


#### 📋 具体建议 (Specific Recommendations)

For courses with grades below 95%, provide AT LEAST 3 to 5 actionable, practical recommendations.
DO NOT limit yourself to only what the teacher wrote — extend recommendations with general best practices that address the specific weaknesses identified.

Consider these areas when generating recommendations:
- CLASS PARTICIPATION: If "Collaborates" or participation is low, suggest concrete strategies (e.g., prepare 1-2 discussion points before class, practice "think-pair-share", set a goal to speak at least once per class discussion)
- TIME MANAGEMENT: If assignments are late, suggest tools and habits (e.g., use a planner/calendar, break large assignments into daily tasks, set phone reminders for due dates, "eat the frog" — do hardest task first)
- STUDY HABITS: Suggest specific study techniques (e.g., active recall, spaced repetition, Cornell note-taking, teaching concepts to a family member)
- GROWTH MINDSET: If "Demonstrates curiosity" is low, suggest ways to engage more deeply (e.g., relate material to personal interests, ask "why" and "what if" questions, keep a learning journal)
- SEEKING HELP: If "Takes initiative" is low, suggest practical steps (e.g., visit teacher office hours weekly, form a study group, write down questions during class to ask later)
- SKILL-SPECIFIC: For subject-specific skills rated below top-level, suggest targeted practice strategies

Each recommendation must be specific and actionable — NOT vague platitudes like "work harder" or "try your best".

**中文：**

- **[具体建议标题]**: [详细、可操作的建议，包含具体步骤]

- **[下一条建议]**: [详细说明]

- **[再下一条建议]**: [详细说明]

(at least 3-5 bullet points, with a blank line between each)

**English:**

- **[Specific suggestion title]**: [Detailed, actionable suggestion with concrete steps]

- **[Next suggestion]**: [Details]

- **[Next suggestion]**: [Details]

(at least 3-5 bullet points, with a blank line between each)

If grade >= 95% and all ratings are top-level:

#### ✅ 表现优秀 (Excellent Performance)

**中文：**

- [Strength and encouragement in Chinese]

**English:**

- [Same in English]

For CR courses: use the same format above if any rating is below top-level.

---

## 📌 总结与建议

### 🇨🇳 中文总结

Use top-level bullet points only, with a blank line between each:

- 本季度共修X门课程...

- **改进重点1**: ...

- **改进重点2**: ...

- **鼓励与肯定**: ...

### 🇺🇸 English Summary

Same structure, matching bullet points:

- This quarter X courses were taken...

- **Priority 1**: ...

- **Priority 2**: ...

- **Encouragement**: ...
"""

    print("Step 2: Generating analysis report...")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    print("  Analysis report generated successfully.")
    return text


def convert_md_to_html(md_content):
    """Convert markdown to styled HTML suitable for viewing."""
    import markdown

    html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code"])

    # Style tables for readability
    html_body = html_body.replace(
        "<table>",
        '<table style="border-collapse: collapse; width: 100%; margin-bottom: 20px; font-family: sans-serif;">',
    )
    html_body = html_body.replace(
        "<th>",
        '<th style="border: 1px solid #cccccc; padding: 8px; text-align: left; background-color: #f2f2f2;">',
    )
    html_body = html_body.replace(
        "<td>",
        '<td style="border: 1px solid #cccccc; padding: 8px; text-align: left;">',
    )

    # Colorize rows with warning/success indicators
    def colorize_row(match):
        row_html = match.group(0)
        if "⚠️" in row_html or "需要关注" in row_html:
            return row_html.replace("<tr>", '<tr style="background-color: #fff3e0;">')
        elif "✅" in row_html:
            return row_html.replace("<tr>", '<tr style="background-color: #e8f5e9;">')
        return row_html

    html_body = re.sub(r"(?si)<tr>.*?</tr>", colorize_row, html_body)

    # Colorize rating cells in the 评分详情 tables
    def colorize_rating_cell(match):
        td_html = match.group(0)
        content = match.group(1).strip()
        # Behavior ratings: Sometimes = orange warning, Rarely = red
        if content == "Sometimes":
            return td_html.replace("<td", '<td style="background-color: #fff3e0; color: #e65100; font-weight: bold;"')
        elif content == "Rarely":
            return td_html.replace("<td", '<td style="background-color: #ffebee; color: #c62828; font-weight: bold;"')
        # Skill ratings: Developing or Not Yet Demonstrated = red
        elif content == "Developing" or "Not Yet" in content:
            return td_html.replace("<td", '<td style="background-color: #ffebee; color: #c62828; font-weight: bold;"')
        return td_html

    # Apply to the last <td> in each row (the rating column)
    html_body = re.sub(
        r'(<td[^>]*>)(Sometimes|Rarely|Developing|Not Yet\s*Demonstrated)</td>',
        lambda m: f'<td style="border: 1px solid #cccccc; padding: 8px; text-align: left; '
                  f'{"background-color: #fff3e0; color: #e65100;" if m.group(2) == "Sometimes" else "background-color: #ffebee; color: #c62828;"}'
                  f' font-weight: bold;">{m.group(2)}</td>',
        html_body
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Report Card Analysis</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.8;
            color: #333;
            background-color: #fafafa;
        }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #e74c3c; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
        h3 {{ color: #555; }}
        blockquote {{
            border-left: 4px solid #3498db;
            padding: 10px 20px;
            background-color: #f0f8ff;
            margin: 10px 0;
        }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th {{ background-color: #f2f2f2; padding: 10px; border: 1px solid #ddd; text-align: left; }}
        td {{ padding: 10px; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        hr {{ border: none; border-top: 2px solid #eee; margin: 30px 0; }}
        .warning {{ background-color: #fff3e0; padding: 15px; border-radius: 8px; border-left: 4px solid #ff9800; margin: 10px 0; }}
        .success {{ background-color: #e8f5e9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin: 10px 0; }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Analyze Overlake School report card.")
    parser.add_argument("input_path", help="Path to the report card HTML file (recommended) or PDF file")
    parser.add_argument(
        "--output-dir",
        default="/Users/zhijiebian/.gemini/cli-workspace",
        help="Output directory for report files",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not os.path.exists(args.input_path):
        print(f"Error: File not found: {args.input_path}")
        sys.exit(1)

    # Infer quarter from filename
    basename = os.path.splitext(os.path.basename(args.input_path))[0]
    quarter_label = basename  # e.g., "2025-Q3"

    # Initialize Gemini
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"Analyzing report card: {args.input_path}")
    print(f"{'='*60}\n")

    # Step 1: Extract structured data
    ext = os.path.splitext(args.input_path)[1].lower()
    if ext in (".html", ".htm"):
        print("Step 1: Extracting structured data from HTML (deterministic parsing)...")
        report_data = extract_courses_from_html(args.input_path)
    else:
        print(f"Error: Unsupported file format '{ext}'. Please provide an HTML file (.html).")
        print("  HTML parsing provides 100% accurate rating extraction.")
        sys.exit(1)

    # Save extracted data for debugging/verification
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, f"Report_Card_Data-{quarter_label}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"\n  Extracted data saved: {json_path}")

    # Step 2: Generate analysis report from extracted data
    md_report = generate_analysis_report(client, args.model, report_data)

    # Step 3: Save markdown
    md_path = os.path.join(args.output_dir, f"Report_Card_Analysis-{quarter_label}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"  Markdown report saved: {md_path}")

    # Step 4: Convert to HTML and save
    html_content = convert_md_to_html(md_report)
    html_path = os.path.join(args.output_dir, f"Report_Card_Analysis-{quarter_label}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  HTML report saved: {html_path}")

    # Step 5: Generate PDF from HTML
    try:
        # Ensure homebrew libraries are findable on macOS
        homebrew_lib = "/opt/homebrew/lib"
        if os.path.isdir(homebrew_lib):
            os.environ["DYLD_LIBRARY_PATH"] = homebrew_lib + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
        from weasyprint import HTML as WeasyHTML
        pdf_path = os.path.join(args.output_dir, f"Report_Card_Analysis-{quarter_label}.pdf")
        WeasyHTML(string=html_content).write_pdf(pdf_path)
        print(f"  PDF report saved: {pdf_path}")
    except ImportError:
        print("  ⚠️ weasyprint not installed, skipping PDF generation. Install with: pip3 install weasyprint")
    except Exception as e:
        print(f"  ⚠️ PDF generation failed: {e}")

    print(f"\n{'='*60}")
    print("Analysis complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
