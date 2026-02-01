#!/usr/bin/env python3
"""
Gmail Automated Email Sender using OAuth2

Setup:
1. Enable Gmail API in Google Cloud Console
2. Create OAuth 2.0 credentials (Desktop app)
3. Add http://localhost:8080/ to Authorized redirect URIs
4. Download credentials JSON and save as 'credentials.json' in same directory
5. Install dependencies: pip install google-auth-oauthlib google-api-python-client
6. Run once and follow the prompts to authenticate
"""

import os
import sys
import json
import base64
import argparse
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# If modifying scopes, delete token.json to re-authenticate
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Path to your OAuth credentials (downloaded from Google Cloud Console)
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
EMAIL_LISTS_FILE = 'email_lists.json'
TEMPLATES_DIR = 'templates'
LOG_FILE = 'email_log.txt'

# Store the auth code globally for the handler
auth_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    """Handle the OAuth redirect."""
    
    def do_GET(self):
        global auth_code
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: Arial; text-align: center; padding-top: 50px;">
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: No code received</h1></body></html>")
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logging


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    global auth_code
    creds = None
    
    # Load existing token if available
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("\n" + "=" * 60)
            print("FIRST-TIME AUTHENTICATION REQUIRED")
            print("=" * 60)
            
            redirect_uri = 'http://localhost:8080/'
            
            flow = Flow.from_client_secrets_file(
                CREDENTIALS_FILE,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            print("\nOpening browser for authentication...")
            print("\nIf the browser doesn't open, go to this URL manually:\n")
            print(auth_url)
            print("\n" + "=" * 60)
            
            # Try to open browser
            try:
                webbrowser.open(auth_url)
            except:
                pass
            
            # Start local server to catch the redirect
            print("\nWaiting for authorization...")
            server = HTTPServer(('localhost', 8080), OAuthHandler)
            server.handle_request()  # Handle one request
            
            if auth_code:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
            else:
                raise Exception("Failed to get authorization code")
        
        # Save credentials for future runs
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            print(f"\nToken saved to {TOKEN_FILE}")
            print("Future runs will not require authentication.\n")
    
    return build('gmail', 'v1', credentials=creds)


def load_email_lists(filepath=EMAIL_LISTS_FILE):
    """Load email lists from a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def load_template(template_name):
    """Load a template from the templates/ folder."""
    filepath = os.path.join(TEMPLATES_DIR, template_name)
    with open(filepath, 'r') as f:
        return f.read()


def fill_placeholders(text, fill_items):
    """Replace {} placeholders sequentially with items from fill_items list."""
    result = text
    for item in fill_items:
        result = result.replace('{}', item, 1)
    return result


def log_email(to, subject, body, list_name=None):
    """Log sent email details to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write(f"Timestamp: {timestamp}\n")
        if list_name:
            f.write(f"List: {list_name}\n")
        f.write(f"To: {to}\n")
        f.write(f"Subject: {subject}\n")
        f.write("-" * 40 + "\n")
        f.write(body)
        f.write("\n" + "=" * 60 + "\n\n")


def create_message(sender, to, subject, body_text, body_html=None, title=None, fill_items=None):
    """Create an email message with optional title greeting and placeholder filling."""
    if fill_items is None:
        fill_items = []

    # Fill placeholders in body text and HTML
    processed_text = fill_placeholders(body_text, fill_items)
    processed_html = fill_placeholders(body_html, fill_items) if body_html else None

    # Prepend greeting if title is provided
    if title:
        processed_text = f"Dear {title},\n\n{processed_text}"
        if processed_html:
            # Insert greeting after <body> tag
            processed_html = processed_html.replace('<body>', f'<body>\n<p>Dear {title},</p>\n', 1)

    if processed_html:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(processed_text, 'plain'))
        message.attach(MIMEText(processed_html, 'html'))
    else:
        message = MIMEText(processed_text, 'plain')

    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    # Encode as base64
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}


def send_email(service, sender, to, subject, body_text, body_html=None, title=None, fill_items=None, list_name=None):
    """Send an email and return the result."""
    try:
        message = create_message(sender, to, subject, body_text, body_html, title, fill_items)
        result = service.users().messages().send(userId='me', body=message).execute()
        print(f"✓ Email sent to {to} (Message ID: {result['id']})")

        # Log the sent email with processed body
        if fill_items is None:
            fill_items = []
        logged_body = fill_placeholders(body_text, fill_items)
        if title:
            logged_body = f"Dear {title},\n\n{logged_body}"
        log_email(to, subject, logged_body, list_name)

        return result
    except Exception as e:
        print(f"✗ Failed to send to {to}: {e}")
        return None


def send_to_list(service, sender, recipients, subject, body_text, body_html=None, list_name=None):
    """Send emails to a list of recipients.

    Each recipient should be a dict with:
        - email: recipient email address
        - title: greeting title (e.g., "Mr. Smith") for "Dear <title>,"
        - fill_items: list of strings to replace {} placeholders sequentially
    """
    results = []
    for recipient in recipients:
        email = recipient['email']
        title = recipient.get('title')
        fill_items = recipient.get('fill_items', [])
        result = send_email(service, sender, email, subject, body_text, body_html, title, fill_items, list_name)
        results.append((email, result))

    # Summary
    successful = sum(1 for _, r in results if r is not None)
    print(f"  Sent {successful}/{len(recipients)} emails successfully")

    return results


def send_email_lists(sender, email_lists, list_names=None):
    """Send multiple email lists.

    Args:
        sender: Sender email address
        email_lists: Dict of email list configurations, each with:
            - subject: Email subject line
            - template: Filename of template in templates/ folder (use {} for placeholders)
            - recipients: List of recipient dicts (email, title, fill_items)
        list_names: Optional list of specific list names to send. If None, sends all.
    """
    service = get_gmail_service()

    lists_to_send = list_names if list_names else list(email_lists.keys())
    all_results = {}

    for list_name in lists_to_send:
        if list_name not in email_lists:
            print(f"✗ Email list '{list_name}' not found, skipping")
            continue

        config = email_lists[list_name]
        print(f"\n[{list_name}]")

        # Load template from file
        body_text = load_template(config['template'])

        results = send_to_list(
            service=service,
            sender=sender,
            recipients=config['recipients'],
            subject=config['subject'],
            body_text=body_text,
            list_name=list_name
        )
        all_results[list_name] = results

    # Overall summary
    total_sent = sum(
        sum(1 for _, r in results if r is not None)
        for results in all_results.values()
    )
    total_recipients = sum(len(results) for results in all_results.values())
    print(f"\n{'=' * 40}")
    print(f"Total: {total_sent}/{total_recipients} emails sent across {len(all_results)} list(s)")

    return all_results


# =============================================================================
# CONFIGURATION - Edit these values
# =============================================================================

SENDER_EMAIL = "hpereira@andrew.cmu.edu"  # Your CMU email

# Email lists are loaded from email_lists.json
# Each list has: subject, template (filename in templates/ folder), recipients
# Use {} as placeholders in templates - replaced sequentially by each recipient's fill_items


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Gmail Automated Sender")
    print("=" * 40)

    # Load email lists from JSON file
    email_lists = load_email_lists()

    # Send all email lists
    #send_email_lists(
    #    sender=SENDER_EMAIL,
    #    email_lists=email_lists
    #)

    #Or send specific lists only:
    send_email_lists(
        sender=SENDER_EMAIL,
        email_lists=email_lists,
        list_names=["william"]
    )
