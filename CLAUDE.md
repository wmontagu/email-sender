# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Gmail automated email sender using OAuth2. Sends templated emails to multiple recipients with personalization (greeting titles and placeholder substitution).

## Running

```bash
# Activate conda environment
mamba activate email-sender

# Send all email lists
python email-sender.py

# First run will open browser for Google OAuth authentication
```

## Architecture

**Configuration files:**
- `email_lists.json` - Defines email campaigns with subject, template reference, and recipients
- `templates/*.txt` - Plain text email body templates with `{}` placeholders

**Email list structure:**
```json
{
    "list_name": {
        "subject": "Email subject",
        "template": "template_file.txt",
        "recipients": [
            {
                "email": "recipient@example.com",
                "title": "Mr. Smith",
                "fill_items": ["value1", "value2"]
            }
        ]
    }
}
```

**Personalization:**
- `title` - Prepends "Dear {title}," to each email
- `fill_items` - Array of strings that sequentially replace `{}` placeholders in the template

**Key functions in email-sender.py:**
- `send_email_lists()` - Main entry point, processes all or specific lists
- `load_template()` - Reads template from `templates/` folder
- `fill_placeholders()` - Sequential `{}` replacement with fill_items
- `get_gmail_service()` - OAuth2 authentication flow with local redirect server

## Required Files

- `credentials.json` - OAuth credentials from Google Cloud Console (not committed)
- `token.json` - Auto-generated after first authentication (not committed)
