"""Gmail API connector for pulling travel booking emails."""

import os
import json
import base64
import re
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDS_FILE = Path(__file__).parent / 'credentials.json'
TOKEN_FILE = Path(__file__).parent / 'token.json'
OUTPUT_DIR = Path(__file__).parent / 'bookings'


def authenticate():
    """Authenticate with Gmail API, opening browser for OAuth if needed."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"ERROR: {CREDS_FILE} not found.")
                print("Download OAuth credentials from Google Cloud Console")
                print("and save as credentials.json in E:\\Vacation_Planning\\")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print("Authentication successful — token saved.")
    return creds


def search_booking_emails(service, query, max_results=50):
    """Search Gmail for emails matching query, return message list."""
    results = service.users().messages().list(
        userId='me', q=query, maxResults=max_results
    ).execute()
    return results.get('messages', [])


def get_email_detail(service, msg_id):
    """Fetch full email content and metadata."""
    msg = service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()

    headers = {h['name'].lower(): h['value'] for h in msg['payload']['headers']}
    subject = headers.get('subject', '(no subject)')
    from_addr = headers.get('from', '')
    date_str = headers.get('date', '')

    # Extract body text
    body = extract_body(msg['payload'])

    return {
        'id': msg_id,
        'subject': subject,
        'from': from_addr,
        'date': date_str,
        'snippet': msg.get('snippet', ''),
        'body': body,
        'labels': msg.get('labelIds', []),
    }


def extract_body(payload):
    """Recursively extract text body from email payload."""
    body_text = ''

    if payload.get('body', {}).get('data'):
        body_text = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')

    for part in payload.get('parts', []):
        mime = part.get('mimeType', '')
        if mime == 'text/plain' and part.get('body', {}).get('data'):
            body_text += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        elif mime == 'text/html' and not body_text and part.get('body', {}).get('data'):
            body_text += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        elif 'parts' in part:
            body_text += extract_body(part)

    return body_text


def pull_travel_bookings():
    """Main function: authenticate, search, and save booking emails."""
    creds = authenticate()
    if not creds:
        return

    service = build('gmail', 'v1', credentials=creds)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Search queries targeting booking/confirmation emails for the trip
    queries = [
        'subject:(confirmation OR booking OR reservation OR itinerary OR e-ticket) newer_than:6m',
        'subject:(flight OR airline) (confirmation OR booking) newer_than:6m',
        'subject:(hotel OR airbnb OR accommodation OR check-in) newer_than:6m',
        'from:(booking.com OR airbnb OR expedia OR hotels.com OR tripadvisor) newer_than:6m',
        'from:(united OR delta OR american OR southwest OR lufthansa OR austrian OR swiss OR aegean OR ryanair OR easyjet) newer_than:6m',
        '(Vienna OR Crete OR Zurich OR Heraklion OR Chania) (confirmation OR booking OR reservation) newer_than:6m',
    ]

    all_msg_ids = set()
    for query in queries:
        messages = search_booking_emails(service, query)
        for m in messages:
            all_msg_ids.add(m['id'])
        print(f"  Query matched {len(messages)} emails: {query[:60]}...")

    print(f"\nTotal unique emails found: {len(all_msg_ids)}")

    # Fetch details for each
    all_emails = []
    for i, msg_id in enumerate(all_msg_ids):
        print(f"  Fetching {i+1}/{len(all_msg_ids)}...", end='\r')
        detail = get_email_detail(service, msg_id)
        all_emails.append(detail)

    # Sort by date
    all_emails.sort(key=lambda x: x.get('date', ''))

    # Save raw emails as JSON
    raw_file = OUTPUT_DIR / 'raw_emails.json'
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump(all_emails, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved {len(all_emails)} emails to {raw_file}")

    # Save a summary index
    summary = []
    for email in all_emails:
        summary.append({
            'subject': email['subject'],
            'from': email['from'],
            'date': email['date'],
            'snippet': email['snippet'][:200],
        })

    summary_file = OUTPUT_DIR / 'email_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Saved summary index to {summary_file}")

    return all_emails


if __name__ == '__main__':
    pull_travel_bookings()
