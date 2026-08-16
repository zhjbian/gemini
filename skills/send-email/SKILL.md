---
name: send-email
description: Sends mobile-optimized, formatted HTML emails to a specified destination address using the project's native SMTP backend (BBSms.send_to_gmail_html). Use whenever the user asks to send an email, mail an itinerary, or forward daily summaries to an email address.
---

# Send Email Skill

Sends mobile-optimized, beautifully styled HTML emails (such as travel itineraries, daily plans, market summaries, or alerts) using the project's native `BBSms.send_to_gmail_html` SMTP engine in `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/py_lib/sms.py`.

## Capabilities & Usage

Trigger this skill whenever the user requests:
- "发邮件到 [email]" (Send email to [email])
- "把行程/内容发送到邮箱" (Send itinerary/content to email)
- "用手机方便阅读的格式重发邮件" (Resend email formatted for mobile reading)

### Command Execution

Always use the dedicated Python script located at `/Users/zhijiebian/.gemini/skills/send-email/scripts/send_email.py`:

```bash
python3 /Users/zhijiebian/.gemini/skills/send-email/scripts/send_email.py --to "<recipient_email>" --subject "<subject_title>" --content-file "<path_to_content_file>"
```

Alternatively, pass raw content via `--content`:

```bash
python3 /Users/zhijiebian/.gemini/skills/send-email/scripts/send_email.py --to "<recipient_email>" --subject "<subject_title>" --content "<raw_text_content>"
```

### Key Parameters

1. **`--to`**: Destination email address (e.g. `zhjbian@gmail.com`). Defaults to `zhjbian@gmail.com` if unspecified.
2. **`--subject`**: Email subject line (e.g. `🏛️ Day 5: 8月6日 (周四) — 大英博物馆与西区人文风情`).
3. **`--content-file` / `--content`**: The text or HTML body to be sent.

### Mobile-Optimized HTML Styling Rules

The script automatically formats input content into a iOS native-style card layout if plain text is provided:
- **Header & Navigation**: Clean title block with blue rounded button for Google Maps links (`#2563eb`).
- **Cards**: White rounded cards (`border-radius: 14px`, `box-shadow: 0 1px 3px rgba(0,0,0,0.08)`).
- **Time Badges**: Dark navy time badges (`#1e3a8a`) for schedule items (e.g. `08:00 – 08:40`).
- **Highlights & Confirmations**: Light green background cards (`#f0fdf4`, `#dcfce7`) with green badges (`#059669`) for ticket confirmations or critical booking numbers.
- **Alert Boxes**: Light yellow highlight boxes (`#fffbeb`, `#fef3c7`) for entry rules and warnings.

### Backend Mechanism

The script uses `BBSms.send_to_gmail_html` from `PyTools/py_lib/sms.py` directly, executing via Python `smtplib` on `smtp.gmail.com:587`. It runs without opening any external macOS applications (such as Mail.app).
