#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from datetime import datetime
from html import escape
from pathlib import Path

import bs4
import markdown


OUTPUT_DIR = Path("/Users/zhijiebian/.gemini/cli-workspace/gemini-answers")


def read_text_arg(value: str | None, file_path: str | None, label: str, optional: bool = False) -> str | None:
    if value and file_path:
        raise SystemExit(f"Provide only one of --{label} or --{label}-file")
    if file_path:
        return Path(file_path).read_text()
    if value is not None:
        return value
    if optional:
        return None
    raise SystemExit(f"Missing --{label} or --{label}-file")


def slugify_summary(text: str, max_words: int = 6) -> str:
    cleaned = re.sub(r"`+", "", text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    words = re.findall(r"[A-Za-z0-9]+", cleaned.lower())
    if not words:
        return "untitled_question"
    summary = "_".join(words[:max_words])
    summary = re.sub(r"_{2,}", "_", summary).strip("_")
    return summary or "untitled_question"


def build_output_path(summary: str) -> Path:
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    return OUTPUT_DIR / f"gemini_answer-{summary}-{timestamp}.html"


def clean_latex(text: str) -> str:
    replacements = {
        r'\rightarrow': '→',
        r'\leftarrow': '←',
        r'\Rightarrow': '⇒',
        r'\Leftarrow': '⇐',
        r'\times': '×',
        r'\approx': '≈',
        r'\leq': '≤',
        r'\le': '≤',
        r'\geq': '≥',
        r'\ge': '≥',
        r'\neq': '≠',
        r'\ne': '≠',
        r'\pm': '±',
        r'\cdot': '·',
        r'\degree': '°',
        r'\quad': ' ',
        r'\qquad': '  ',
        r'\%': '%',
    }

    def replace_formula(match):
        formula = match.group(1)
        is_formula = (
            '\\' in formula 
            or any(op in formula for op in ['^', '_', '≈', '×', '±', '→', '≤', '≥', '≠'])
        )
        if not is_formula:
            return match.group(0)

        # 1. Replace \text{...} -> ...
        formula = re.sub(r'\\text\{([^{}]+)\}', r'\1', formula)
        # 2. Replace common LaTeX operators
        for latex_op, unicode_op in replacements.items():
            formula = formula.replace(latex_op, unicode_op)
        # 3. Clean up escapes
        formula = re.sub(r'\\([_#*+-\\%])', r'\1', formula)
        return formula

    # Process double dollar signs first (block equations)
    text = re.sub(r'\$\$(.*?)\$\$', replace_formula, text, flags=re.DOTALL)
    # Process single dollar signs (inline equations)
    text = re.sub(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', replace_formula, text)
    return text


def render_markdown(text: str, add_toc: bool = False) -> str:
    text = clean_latex(text)
    # Always include the core extensions, but 'toc' is now handled globally if requested
    return markdown.markdown(
        text.strip(),
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )


def update_global_toc(soup: bs4.BeautifulSoup) -> None:
    article = soup.find("article", class_="card")
    if not article:
        return

    # Find or create Global TOC container
    toc_div = soup.find("div", class_="global-toc")
    if toc_div:
        toc_div.decompose()
    
    toc_div = soup.new_tag("div", attrs={"class": "global-toc"})
    toc_title = soup.new_tag("div", attrs={"class": "toctitle"})
    toc_title.string = "Table of Contents"
    toc_div.append(toc_title)
    
    # Identify all headings inside the card
    headings = article.find_all(["h2", "h3", "h4"])
    
    # Clear existing IDs to ensure fresh unique generation
    for h in headings:
        if not h.find_parent("div", class_="global-toc"):
            h.attrs.pop("id", None)

    # Root list
    root_ul = soup.new_tag("ul")
    toc_div.append(root_ul)
    
    # Keep track of nesting
    stack = [(1, root_ul)] # (level, current_ul)
    
    id_counts = {}

    for h in headings:
        # Ignore headings inside a TOC already (should be none now)
        if h.find_parent("div", class_="global-toc"):
            continue
            
        # Ensure ID exists for linking
        if not h.get("id"):
            base_id = re.sub(r"\W+", "-", h.get_text().lower()).strip("-")
            if not base_id: base_id = "heading"
            if base_id in id_counts:
                id_counts[base_id] += 1
                unique_id = f"{base_id}-{id_counts[base_id]}"
            else:
                id_counts[base_id] = 1
                unique_id = base_id
            h["id"] = unique_id
        
        h_level = int(h.name[1]) # 2, 3, or 4
        
        # Adjust stack to current level
        while stack and stack[-1][0] >= h_level:
            stack.pop()
        
        if not stack:
            # Fallback for unexpected hierarchy
            stack.append((h_level - 1, root_ul))
            
        parent_ul = stack[-1][1]
        
        li = soup.new_tag("li")
        a = soup.new_tag("a", href=f"#{h['id']}")
        a.string = h.get_text().strip()
        li.append(a)
        parent_ul.append(li)
        
        # If we need a sub-list for next items
        sub_ul = soup.new_tag("ul")
        li.append(sub_ul)
        stack.append((h_level, sub_ul))

    # Clean up empty sub-lists
    for ul in toc_div.find_all("ul"):
        if not ul.find("li"):
            ul.decompose()

    # Insert TOC after header
    header = article.find("header")
    if header:
        header.insert_after(toc_div)
    else:
        article.insert(0, toc_div)


def build_html(question: str, answer: str, summary: str) -> str:
    saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question_html = render_markdown(question)
    answer_html = render_markdown(answer)
    title = escape(f"Gemini Answer - {summary}")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #ffffff;
      --panel: #ffffff;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #e5dccf;
      --accent: #9a3412;
      --accent-soft: #fff1e8;
      --code-bg: #f4efe7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.6;
    }}
    .page {{
      width: 100%;
      max-width: none;
      margin: 0;
      padding: 24px 24px 40px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 18px 50px rgba(79, 52, 28, 0.08);
      overflow: hidden;
    }}
    header {{
      padding: 28px 32px 20px;
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3, h4 {{
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.2;
      margin: 0 0 12px;
    }}
    h1 {{
      font-size: 2rem;
      color: #7c2d12;
      letter-spacing: 0.01em;
    }}

    /* Auto-numbering for headings */
    article.card {{
      counter-reset: h2-counter;
    }}
    h2 {{
      counter-reset: h3-counter;
      margin-top: 1.5em;
    }}
    h2::before {{
      counter-increment: h2-counter;
      content: counter(h2-counter) ". ";
    }}
    h3 {{
      counter-reset: h4-counter;
      margin-top: 1.2em;
    }}
    h3::before {{
      counter-increment: h3-counter;
      content: counter(h2-counter) "." counter(h3-counter) " ";
    }}
    h4 {{
      counter-reset: h5-counter;
    }}
    h4::before {{
      counter-increment: h4-counter;
      content: counter(h2-counter) "." counter(h3-counter) "." counter(h4-counter) " ";
    }}

    /* Global TOC Styles */
    .global-toc {{
      background: #faf8f5;
      border-bottom: 1px solid var(--line);
      padding: 24px 32px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    .global-toc .toctitle {{
      font-size: 1.3rem;
      font-weight: 600;
      color: #7c2d12;
      margin-top: 0;
      margin-bottom: 16px;
    }}
    .global-toc ul {{
      list-style: none;
      padding-left: 0;
      margin: 0;
      counter-reset: gtoc-counter;
    }}
    .global-toc ul ul {{
      padding-left: 24px;
      margin-top: 4px;
    }}
    .global-toc li {{
      margin-bottom: 8px;
      position: relative;
    }}
    .global-toc li::before {{
      counter-increment: gtoc-counter;
      content: counters(gtoc-counter, ".") ". ";
      color: #7c2d12;
      font-weight: 600;
      margin-right: 8px;
    }}
    .global-toc a {{
      color: var(--ink);
      font-weight: 500;
    }}
    .global-toc a:hover {{
      color: var(--accent);
      text-decoration: underline;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .meta span {{
      display: inline-flex;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      border: 1px solid #f6d1bd;
      color: #7c2d12;
      font-size: 0.92rem;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    section {{
      padding: 26px 32px;
      border-top: 1px solid var(--line);
    }}
    section:first-of-type {{ border-top: 0; }}
    p, li {{
      font-size: 1rem;
    }}
    pre {{
      overflow-x: auto;
      padding: 14px 16px;
      background: var(--code-bg);
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    code {{
      font-family: "SFMono-Regular", "Menlo", "Consolas", monospace;
      font-size: 0.92em;
    }}
    :not(pre) > code {{
      background: var(--code-bg);
      padding: 0.12em 0.38em;
      border-radius: 6px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0;
      font-size: 0.98rem;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #faf1e4;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    img {{
      display: block;
      max-width: min(100%, 1500px);
      max-height: 1500px;
      width: auto;
      height: auto;
      margin: 16px auto;
    }}
    blockquote {{
      margin: 16px 0;
      padding: 10px 16px;
      border-left: 4px solid #f1b58f;
      color: #5b4636;
      background: #fff8f2;
    }}
  </style>
</head>
<body>
  <main class="page">
    <article class="card">
      <header>
        <h1>Gemini Answer</h1>
        <div class="meta">
          <span>Saved: {escape(saved_at)}</span>
          <span>Question summary: {escape(summary)}</span>
        </div>
      </header>
      <section>
        <h2>Question</h2>
        {question_html}
      </section>
      <section>
        <h2>Answer</h2>
        {answer_html}
      </section>
    </article>
  </main>
</body>
</html>
"""
    soup = bs4.BeautifulSoup(html, "html.parser")
    update_global_toc(soup)
    return str(soup)


def append_to_html(target_path: Path, question: str, answer: str, summary: str) -> None:
    content = target_path.read_text()
    soup = bs4.BeautifulSoup(content, "html.parser")
    article = soup.find("article", class_="card")
    if not article:
        raise SystemExit(f"Could not find <article class='card'> in {target_path}")

    question_html = render_markdown(question)
    answer_html = render_markdown(answer)

    # Check for restructuring if currently in single mode (has exactly 2 sections: Question & Answer)
    sections = article.find_all("section", recursive=False)
    is_single_mode = (
        len(sections) == 2 
        and sections[0].find("h2") and sections[0].find("h2").get_text() == "Question"
        and sections[1].find("h2") and sections[1].find("h2").get_text() == "Answer"
    )
    
    if is_single_mode:
        # Extract old summary from metadata if possible
        meta_div = soup.find("div", class_="meta")
        old_summary = "Original Analysis"
        if meta_div:
            spans = meta_div.find_all("span")
            for span in spans:
                if "Question summary:" in span.get_text():
                    old_summary = span.get_text().replace("Question summary:", "").strip()
        
        # Restructure existing sections (demote h2 to h3)
        for sec in sections:
            h2 = sec.find("h2")
            if h2: h2.name = "h3"
        
        # Create new parent section for original content
        orig_parent = soup.new_tag("section")
        orig_h2 = soup.new_tag("h2")
        orig_h2.string = old_summary
        orig_parent.append(orig_h2)
        for sec in list(sections):
            orig_parent.append(sec.extract())
        
        article.append(orig_parent)

    # Append new Q&A as a new top-level h2 section
    new_parent = soup.new_tag("section")
    new_h2 = soup.new_tag("h2")
    new_h2.string = summary
    new_parent.append(new_h2)
    
    q_h3 = soup.new_tag("h3")
    q_h3.string = "Question"
    new_parent.append(q_h3)
    new_parent.append(bs4.BeautifulSoup(question_html, "html.parser"))
    
    a_h3 = soup.new_tag("h3")
    a_h3.string = "Answer"
    new_parent.append(a_h3)
    new_parent.append(bs4.BeautifulSoup(answer_html, "html.parser"))
    
    article.append(new_parent)

    update_global_toc(soup)
    target_path.write_text(str(soup))


def append_to_md(target_path: Path, question: str, answer: str, summary: str) -> None:
    content = target_path.read_text().strip()
    
    # Determine if it's single mode: does it contain `# Gemini Answer` and exactly one `## Question` and one `## Answer`?
    h2_count = len(re.findall(r'^##\s', content, re.MULTILINE))
    
    if h2_count == 2 and "## Question" in content and "## Answer" in content:
        # Extract the original summary from the title
        title_match = re.search(r'^# Gemini Answer - (.*)', content, re.MULTILINE)
        old_summary = title_match.group(1).strip() if title_match else "Original Analysis"
        
        # Demote existing ## to ###
        restructured = content
        # Remove the main title
        restructured = re.sub(r'^# Gemini Answer - .*\n+', '', restructured)
        # Demote ## to ###
        restructured = re.sub(r'^##\s', '### ', restructured, flags=re.MULTILINE)
        
        content = f"# Gemini Answer\n\n## {old_summary}\n{restructured}"
        
    # Append the new section
    new_section = f"\n\n## {summary}\n\n### Question\n{question}\n\n### Answer\n{answer}\n"
    content += new_section
    target_path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Save a Gemini question/answer pair as an HTML report with automated Global TOC."
    )
    parser.add_argument("--question")
    parser.add_argument("--question-file")
    parser.add_argument("--answer")
    parser.add_argument("--answer-file")
    parser.add_argument("--summary")
    parser.add_argument("--summary-file")
    parser.add_argument("--append-to", help="Existing HTML file to append to")
    parser.add_argument("--md", action="store_true", help="Also generate/append to markdown (.md) file")
    args = parser.parse_args()

    question = read_text_arg(args.question, args.question_file, "question")
    answer = read_text_arg(args.answer, args.answer_file, "answer")
    summary_input = (
        read_text_arg(args.summary, args.summary_file, "summary", optional=True)
        if (args.summary or args.summary_file)
        else question
    )
    summary = slugify_summary(summary_input)

    if args.append_to:
        target = Path(args.append_to)
        if not target.exists():
            raise SystemExit(f"Target file {target} does not exist for appending.")
        append_to_html(target, question, answer, summary)
        print(target)
        if args.md:
            md_target = target.with_suffix(".md")
            if md_target.exists():
                append_to_md(md_target, question, answer, summary)
                print(md_target)
            else:
                md_content = f"# Gemini Answer - {summary}\n\n## Question\n{question}\n\n## Answer\n{answer}\n"
                md_target.write_text(md_content)
                print(md_target)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = build_output_path(summary)
        output_path.write_text(build_html(question, answer, summary))
        print(output_path)
        if args.md:
            md_path = output_path.with_suffix(".md")
            md_content = f"# Gemini Answer - {summary}\n\n## Question\n{question}\n\n## Answer\n{answer}\n"
            md_path.write_text(md_content)
            print(md_path)


if __name__ == "__main__":
    main()
