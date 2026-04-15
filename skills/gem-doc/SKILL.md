---
name: gem-doc
description: Save a Gemini answer from the current session into an HTML report file under `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers`. Use when the user wants the last answer saved, wants a specific answered question exported, or asks to document a Gemini response as a standalone `.html` file with timestamped naming.
---

# Gem-Doc

## Overview

Save one answer from the current Gemini session as a standalone HTML report in `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers`.

Prefer this skill when the user wants durable answer files instead of only chat history.

## Workflow

1. Identify which answer to save.
   - If the user says "last answer", use the most recent assistant answer in the current session.
   - If the user names a specific question or topic, find the matching user question and the answer that responded to it.
   - If multiple prior questions are plausible, choose the most recent clear match and state that assumption.

2. Derive the question text.
   - Use the exact user question when practical.
   - If the user referred to a topic instead of quoting the full question, derive a concise question line that matches the answered request.

3. Derive a semantic summary for the filename.
   - Summarize the question and answer together into a short phrase of no more than 6 words.
   - Do not just take the first 6 words of the question.
   - Prefer a compact intent/result summary such as `gem_doc_skill_created` or `md_vs_html_speed`.
   - Use underscores in the final slug.

4. Capture the answer text exactly.
   - Preserve Markdown structure from the answer.
   - Do not rewrite, compress, shorten, or summarize unless the user explicitly asks for a cleaned-up version.
   - The saved/exported document must preserve the same level of detail as the chat answer by default.
   - When converting a chat answer into HTML or appending it into an existing HTML report, the document version must contain the full answer content at the same level of detail or more detail than the chat answer. Never silently omit reasoning, caveats, call paths, examples, or supporting detail that appeared in chat.
   - If any formatting conversion forces a choice, prefer preserving detail over brevity.
   - Exception: if the answer contains DBCPS code pointers or local DBCPS file links, use the `bitbucket-link` skill to convert them to Bitbucket source links before saving.
   - If the answer contains DBCPS git commit ids, use the `bitbucket-link` skill to confirm the repo mapping and convert each commit id into a full Bitbucket commit link before saving.

5. Write the file with the helper script:
   - `python3 /Users/zhijiebian/.gemini/skills/gem-doc/scripts/save_answer_html.py --summary "<summary>" --question-file <question_file> --answer-file <answer_file>`

6. Report the saved path back to the user.

## Output Rules

- Output directory: `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers`
- Filename format: `gemini_answer-<summary_of_the_question>-<date>_<time>.html`
- Use underscores inside the summary portion, not hyphens.
- The summary should be generated semantically from the question and answer together, then converted into a filesystem-safe slug.
- Keep the generated summary concise and capped at no more than 6 words.
- Prefer a custom AI-generated summary passed through `--summary`; the helper script's fallback summarizer is only a backup.

## File Content Format

Write the HTML report with these sections:

- Title: `Gemini Answer`
- Metadata row: saved timestamp and question summary
- Table of contents is generated automatically by the Python script at the top of the 'Answer' block, you do not need to manually create one.
- `Question` section rendered from the question text
- `Answer` section rendered from the answer markdown
- The `Answer` section must contain the full answer content from chat unless the user explicitly requests a shortened or cleaned-up variant
- Full-width layout by default; do not constrain the report to a narrow fixed content width
- Images should be rendered with a maximum width of `1500px` and a maximum height of `1500px`
- Do not use any global page-level background color. Leave the page/background unstyled at the global level rather than setting `body` or page-wrapper background fills.
- Avoid decorative gradients or random background colors anywhere in the document chrome
- Use clear heading hierarchy:
  - The generated HTML report uses CSS counters to automatically number all headings (`h2`, `h3`, `h4`).
  - DO NOT manually number your headings in the markdown (e.g. write `## Question`, NOT `## 1. Question`).
  - `h2` for major sections such as `Question`, `Answer`.
  - For follow-up sections, always append a summary to the section title, e.g., `Follow-up Question - 从smi计算公式解释为什么会出现顶背离` and `Follow-up Answer - 从smi计算公式解释为什么会出现顶背离`.
  - `h3` for subsections inside a major answer such as `Goal`, `Test Matrix`, `Decision Rules`.
  - `h4` for sub-subsections.

## Implementation Notes

- Prefer temporary files for the question and answer content when invoking the helper script so multiline content is preserved safely.
- Use `/tmp` for temporary files unless the current task already has a better local scratch location.
- If the answer includes code fences, tables, numbered lists, file links, or section structure, preserve them in the rendered HTML.
- Never replace a detailed chat answer with a shorter paraphrase just to make the HTML cleaner.
- Before saving or appending, sanity-check that the document contains all substantive sections and key supporting details from the chat answer.
- If appending into an existing HTML report instead of creating a standalone export, apply the same fidelity rule: append the exact answer text or a strictly more detailed version, not a condensed variant.
- If appending into an existing HTML report, preserve or improve the structure:
  - normalize heading levels so the document does not flatten every appended section to the same heading level
  - do not manually renumber headings; CSS handles it automatically
- If the answer includes images, constrain them in the rendered HTML to `max-width: min(100%, 1500px)` and `max-height: 1500px`.
- If the user's question or answer includes attached images or media artifacts:
  - ALWAYS copy the media files to a dedicated `images/` subfolder in the output directory (e.g., `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/images/`).
  - Embed them in the HTML report using relative markdown links (e.g., `![description](images/filename.png)`).
- Never set a global page-level background color in generated HTML. Do not assign background fills to `body`, `html`, or full-page wrapper elements unless the user explicitly asks for that styling.
- If the answer contains DBCPS code references, always use the `bitbucket-link` skill to generate code pointer links before saving the document.
- If the answer contains DBCPS git commit ids, always use the `bitbucket-link` skill to determine the repo context and replace those ids with full Bitbucket commit links before saving the document.
- Prefer commit-pinned Bitbucket browse links over local filesystem paths for saved documentation.
- Always generate full-width HTML reports; avoid fixed `max-width` page containers unless the user explicitly asks for a constrained reading width.
- If no earlier answer exists in the current session, say so clearly instead of creating a placeholder file.

## Script

Use:

- `python3 /Users/zhijiebian/.gemini/skills/gem-doc/scripts/save_answer_html.py --summary "<summary>" --question-file <question_file> --answer-file <answer_file>`
- `python3 /Users/zhijiebian/.gemini/skills/gem-doc/scripts/save_answer_html.py --summary "<summary>" --question <question> --answer-file <answer_file>`
- `python3 /Users/zhijiebian/.gemini/skills/gem-doc/scripts/save_answer_html.py --summary "<summary>" --question-file <question_file> --answer <answer>`

The script prints the final output path after writing the file.
