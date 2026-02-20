import imaplib
import email
from email import policy
from email.parser import BytesParser
from datetime import datetime, timedelta
import os
import re
import argparse
from bs4 import BeautifulSoup
import lxml
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

import json
import settings
from hashing import sha256_hash

# ANSI escape codes for colors
PINK = '\033[95m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
NEON_GREEN = '\033[92m'
RESET_COLOR = '\033[0m'

def chunk_text(text, max_length=1000):
    # Normalize Unicode characters to the closest ASCII representation
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Remove sequences of '>' used in email threads
    text = re.sub(r'\s*(?:>\s*){2,}', ' ', text)

    # Remove sequences of dashes, underscores, or non-breaking spaces
    text = re.sub(r'-{3,}', ' ', text)
    text = re.sub(r'_{3,}', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)  # Collapse multiple spaces into one

    # Replace URLs with a single space, or remove them
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # Normalize whitespace to single spaces, strip leading/trailing whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Split text into sentences while preserving punctuation
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 < max_length:
            current_chunk += (sentence + " ").strip()
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + " "
    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def write_chunks_file(chunks_list, source_path=None, chunks_file=None, append_vault=True):
    repo_dir = os.path.dirname(__file__)
    if chunks_file is None:
        chunks_file = os.path.join(repo_dir, 'data', 'chunks.jsonl')
    os.makedirs(os.path.dirname(chunks_file), exist_ok=True)

    # load existing chunk ids
    existing = set()
    if os.path.exists(chunks_file):
        try:
            with open(chunks_file, 'r', encoding='utf-8') as cf:
                for line in cf:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and 'chunk_id' in obj:
                            existing.add(obj['chunk_id'])
                    except Exception:
                        continue
        except Exception:
            pass

    new_written = 0
    with open(chunks_file, 'a', encoding='utf-8') as cf:
        for chunk_text in chunks_list:
            text = chunk_text.strip()
            if not text:
                continue
            cid = sha256_hash(text)
            if cid in existing:
                continue
            obj = {
                'chunk_id': cid,
                'doc_id': os.path.basename(source_path) if source_path else f'email',
                'source': source_path or '',
                'text': text,
                'token_count': len(text.split())
            }
            cf.write(json.dumps(obj, ensure_ascii=False) + '\n')
            existing.add(cid)
            new_written += 1

    print(f"Wrote {new_written} new chunks to {chunks_file}")

def save_chunks_to_vault(chunks, source_path=None):
    try:
        write_chunks_file(chunks, source_path=source_path)
    except Exception as e:
        print(f"Failed to save chunks to structured file: {e}")


def get_text_from_html(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    return soup.get_text()

def save_plain_text_content(email_bytes, email_id):
    try:
        msg = BytesParser(policy=policy.default).parsebytes(email_bytes)
    except Exception as e:
        print(f"Failed to parse email ID {email_id}: {e}")
        return ""

    text_content = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                try:
                    part_text = payload.decode(charset, errors='replace')
                except Exception:
                    part_text = payload.decode('utf-8', errors='replace')
                if ctype == 'text/plain':
                    text_content += part_text
                elif ctype == 'text/html':
                    text_content += get_text_from_html(part_text)
        else:
            ctype = msg.get_content_type()
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                try:
                    content = payload.decode(charset, errors='replace')
                except Exception:
                    content = payload.decode('utf-8', errors='replace')
                if ctype == 'text/plain':
                    text_content = content
                elif ctype == 'text/html':
                    text_content = get_text_from_html(content)
    except Exception as e:
        print(f"Error extracting text for email ID {email_id}: {e}")

    chunks = chunk_text(text_content)
    try:
        save_chunks_to_vault(chunks, source_path=f"email_{email_id}")
    except Exception as e:
        print(f"Failed to save chunks for email ID {email_id}: {e}")
    return text_content

def search_and_process_emails(imap_client, email_source, search_keyword, start_date, end_date):
    if imap_client is None:
        print(YELLOW + f"No IMAP client for {email_source}, skipping." + RESET_COLOR)
        return

    search_criteria = 'ALL'
    if start_date and end_date:
        search_criteria = f'(SINCE "{start_date}" BEFORE "{end_date}")'
    if search_keyword:
        search_criteria += f' BODY "{search_keyword}"'

    print(f"Using search criteria for {email_source}: {search_criteria}")
    try:
        typ, data = imap_client.search(None, search_criteria)
    except imaplib.IMAP4.error as e:
        print(YELLOW + f"IMAP search error for {email_source}: {e}" + RESET_COLOR)
        return
    except Exception as e:
        print(YELLOW + f"Unexpected error during IMAP search for {email_source}: {e}" + RESET_COLOR)
        return

    if typ == 'OK' and data:
        email_ids = data[0].split()
        print(f"Found {len(email_ids)} emails matching criteria in {email_source}.")

        for num in email_ids:
            try:
                typ, email_data = imap_client.fetch(num, '(RFC822)')
            except imaplib.IMAP4.error as e:
                print(YELLOW + f"IMAP fetch error for message {num} in {email_source}: {e}" + RESET_COLOR)
                continue
            except Exception as e:
                print(YELLOW + f"Unexpected error fetching message {num} in {email_source}: {e}" + RESET_COLOR)
                continue

            if typ == 'OK' and email_data and email_data[0]:
                try:
                    email_id = num.decode('utf-8') if isinstance(num, bytes) else str(num)
                except Exception:
                    email_id = str(num)
                print(f"Downloading and processing email ID: {email_id} from {email_source}")
                try:
                    save_plain_text_content(email_data[0][1], email_id)
                except Exception as e:
                    print(YELLOW + f"Error processing email ID {email_id} from {email_source}: {e}" + RESET_COLOR)
            else:
                try:
                    id_str = num.decode('utf-8') if isinstance(num, bytes) else str(num)
                except Exception:
                    id_str = str(num)
                print(YELLOW + f"Failed to fetch email ID: {id_str} from {email_source}" + RESET_COLOR)
    else:
        print(YELLOW + f"Failed to find emails with given criteria in {email_source}. No emails found." + RESET_COLOR)


def main():
    parser = argparse.ArgumentParser(description="Search and process emails based on optional keyword and date range.")
    parser.add_argument("--keyword", help="The keyword to search for in the email bodies.", default="")
    parser.add_argument("--startdate", help="Start date in DD.MM.YYYY format.", required=False)
    parser.add_argument("--enddate", help="End date in DD.MM.YYYY format.", required=False)
    args = parser.parse_args()

    start_date = None
    end_date = None

    # Check if both start and end dates are provided and valid
    if args.startdate and args.enddate:
        try:
            start_date = datetime.strptime(args.startdate, "%d.%m.%Y").strftime("%d-%b-%Y")
            end_date = datetime.strptime(args.enddate, "%d.%m.%Y").strftime("%d-%b-%Y")
        except ValueError as e:
            print(f"Error: Date format is incorrect. Please use DD.MM.YYYY format. Details: {e}")
            return
    elif args.startdate or args.enddate:
        print("Both start date and end date must be provided together.")
        return

    # Retrieve email credentials from environment variables
    gmail_username = os.getenv('GMAIL_USERNAME')
    gmail_password = os.getenv('GMAIL_PASSWORD')
    outlook_username = os.getenv('OUTLOOK_USERNAME')
    outlook_password = os.getenv('OUTLOOK_PASSWORD')

    # Helper to connect/login/select a mailbox with error handling
    def connect_imap(server, username, password, source_name):
        if not username or not password:
            print(YELLOW + f"No credentials for {source_name}, skipping connection." + RESET_COLOR)
            return None
        try:
            client = imaplib.IMAP4_SSL(server)
        except Exception as e:
            print(YELLOW + f"Failed to connect to {source_name} IMAP server {server}: {e}" + RESET_COLOR)
            return None
        try:
            client.login(username, password)
        except imaplib.IMAP4.error as e:
            print(YELLOW + f"Login failed for {source_name}: {e}" + RESET_COLOR)
            try:
                client.logout()
            except Exception:
                pass
            return None
        try:
            typ, data = client.select('inbox')
            if typ != 'OK':
                print(YELLOW + f"Failed to select inbox for {source_name}: {data}" + RESET_COLOR)
                return None
        except Exception as e:
            print(YELLOW + f"Error selecting inbox for {source_name}: {e}" + RESET_COLOR)
            return None
        return client

    # Connect to servers (skip if credentials missing or login fails)
    M = connect_imap('imap.gmail.com', gmail_username, gmail_password, 'Gmail')
    H = connect_imap('imap-mail.outlook.com', outlook_username, outlook_password, 'Outlook')

    # Search and process emails from Gmail and Outlook
    search_and_process_emails(M, "Gmail", args.keyword, start_date, end_date)
    search_and_process_emails(H, "Outlook", args.keyword, start_date, end_date)

    # Logout only clients that connected successfully
    for client, name in ((M, 'Gmail'), (H, 'Outlook')):
        if client:
            try:
                client.logout()
            except Exception as e:
                print(YELLOW + f"Failed to logout {name}: {e}" + RESET_COLOR)


if __name__ == "__main__":
    main()
