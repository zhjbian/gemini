---
name: gem-doc
description: Save a Gemini answer from the current session into an HTML report file under `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers`. Use when the user wants the last answer saved, wants a specific answered question exported, or asks to document a Gemini response as a standalone `.html` file with timestamped naming.
---

# Gem-Doc

## Critical Rules

> [!IMPORTANT]
> **NO CONDENSING**: Never summarize, paraphrase, or condense a chat answer when saving it. The goal of this skill is total technical preservation.
> **FULL GRANULARITY**: Always include the exact logic, code blocks, database queries, and specific parameter values (e.g., "06:30 - 07:30 inclusive") used in the conversation.
> **APPENDING FIDELITY**: When appending, ensure the new content is at least as detailed as the source chat response.

## Overview

Save one answer from the current Gemini session as a standalone HTML report in `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers`.

Prefer this skill when the user wants durable answer files instead of only chat history.

## Workflow

1. Identify which answer to save.
   - If the user says "last answer", use the most recent assistant answer in the current session.
   - If the user names a specific question or topic, find the matching user question and the answer that responded to it.

2. Determine if creating a NEW report or APPENDING to an existing one.
   - **APPENDING Rule**: All appends must result in a flat list of Level 1 heading sections (`h2`).
   - **First-Time Append Restructuring**: If the existing report contains only a single Q/A (i.e., it is a fresh standalone export), the first append MUST wrap that original Q/A into its own `h2` section (labeled with the original summary) and demote the original `h2` headings to `h3`.
   - **Subsequent Appends**: Every new Q/A pair added thereafter should be its own `h2` section.

3. Capture the answer text exactly and generate a summary (slug).

4. Write/Append the file using the helper script:
   - `python3 /Users/zhijiebian/.gemini/skills/gem-doc/scripts/save_answer_html.py --summary "<summary>" --question-file <question_file> --answer-file <answer_file> --append-to <path>`

5. Report the saved path back to the user.

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
- **Section Structure**: 
  - `h2` for major Section Titles (e.g., "Institutional Flow Analysis", "Follow-up Query").
  - `h3` for `Question` and `Answer` labels within each section.
  - `h4` for subsections inside a major answer such as `Goal`, `Test Matrix`, `Decision Rules`.
- Full-width layout by default; do not constrain the report to a narrow fixed content width
- Images should be rendered with a maximum width of `1500px` and a maximum height of `1500px`
- Do not use any global page-level background color.
- Use clear heading hierarchy:
  - The generated HTML report uses CSS counters to automatically number all headings (`h2`, `h3`, `h4`).
  - DO NOT manually number your headings in the markdown.
  - `h2` for major Section Titles.
  - `h3` for `Question` and `Answer` labels within those sections.
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
- **NEVER use dark backgrounds or dark mode**: All generated HTML reports must use a light background theme (e.g., white or very light gray). Dark themes or dark backgrounds are strictly prohibited. Do not assign dark background fills to `body`, `html`, or card elements.
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
