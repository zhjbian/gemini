---
name: report-card-analysis
description: Analyzes Overlake School report card PDFs - translates comments to Chinese and provides improvement suggestions for grades below 95.
---

# Report Card Analysis

This skill analyzes Overlake School quarterly report card PDFs. It extracts course data, translates comments to Chinese, and provides comprehensive analysis with improvement suggestions.

## Capabilities

When the user requests a report card analysis, follow these steps:

### 1. Identify Requirements
- **PDF Path**: The path to the report card PDF file
- **Quarter/Semester**: Infer from filename (e.g., 2025-Q3)
- **Output Directory**: Default to `/Users/zhijiebian/.gemini/cli-workspace/`

### 2. Run the Analysis Script

Use the analysis script at `/Users/zhijiebian/.gemini/skills/report-card-analysis/scripts/analyze_report_card.py`:

```bash
GEMINI_API_KEY=AIzaSyBJym4pn4X2zf60gvWGXI3orUCTEBEZRpM /usr/local/bin/python3 /Users/zhijiebian/.gemini/skills/report-card-analysis/scripts/analyze_report_card.py "<pdf_path>" [--output-dir <output_dir>]
```

The script will:
1. Send the PDF to Gemini for structured extraction of all courses
2. For each course, extract: course name, grade, curriculum comment, teacher comment, behaviors ratings, skills ratings
3. Send a second Gemini call to generate the analysis report

### 3. Output Files

The script generates two files in the output directory:
- `Report_Card_Analysis-<quarter>.md` — Markdown format
- `Report_Card_Analysis-<quarter>.html` — HTML format with styled tables

### 4. Report Structure

For each course, the report includes:

#### A. Original Comments (原文)
- **Curriculum Comment** with Chinese translation
- **Teacher Comment** with Chinese translation

#### B. Ratings Summary (评分摘要)
- **Behaviors and Learning Dispositions** — table of all behavior ratings
- **Skills and Content** — table of all skill ratings

#### C. Comprehensive Analysis (综合分析)
- Strengths highlighted
- If grade < 95%: **focused improvement suggestions** with specific actionable advice
- If grade >= 95%: brief encouragement and areas to maintain

### 5. Analysis Guidelines

When analyzing, consider:
- **Behaviors and Learning Dispositions**: Look for anything not rated "Consistently" — these indicate areas needing attention
- **Skills and Content**: Look for anything not rated "Accomplished" or "Exemplary"
- **Teacher Comments**: Extract specific teacher suggestions and feedback
- **Grade threshold**: 95% — below this, provide detailed improvement plan
- All analysis text should be bilingual (Chinese primary, English secondary)
