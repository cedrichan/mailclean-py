import os.path
import argparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def fetch_large_messages(service, size_mb=5):
    """Queries Gmail for messages larger than the specified size and returns full message objects."""
    query = f"larger:{size_mb}M"
    results = service.users().messages().list(userId="me", q=query).execute()
    messages_summaries = results.get("messages", [])

    detailed_messages = []
    for msg in messages_summaries:
        # Fetching full metadata for each message
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata")
            .execute()
        )
        detailed_messages.append(detail)

    # Sort messages by internalDate (ascending)
    detailed_messages.sort(key=lambda x: int(x.get("internalDate", 0)))

    return detailed_messages


def print_message_info(message):
    """Formats and prints message details including a direct browser link."""
    headers = message.get("payload", {}).get("headers", [])

    subject = next(
        (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
    )
    sender = next(
        (h["value"] for h in headers if h["name"] == "From"), "Unknown Sender"
    )
    date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown Date")

    size_bytes = int(message.get("sizeEstimate", 0))
    size_mb = size_bytes / 1024 / 1024

    # Gmail deep link uses the threadId or messageId
    msg_id = message.get("id")
    link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

    print(f"Subject: {subject}")
    print(f"From:    {sender}")
    print(f"Date:    {date}")
    print(f"Size:    {size_mb:.2f} MB")
    print(f"Link:    {link}")
    print("-" * 40)


def get_or_create_label(service, label_name="PRE_CLEANUP"):
    """Returns the ID of the specified label, creating it if it doesn't exist."""
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    # Label not found, create it
    label_body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    created_label = (
        service.users().labels().create(userId="me", body=label_body).execute()
    )
    return created_label["id"]


def apply_label_to_message(service, message_id, label_id):
    """Adds the specified label to a message."""
    body = {"addLabelIds": [label_id]}
    service.users().messages().batchModify(
        userId="me", body={"ids": [message_id], "addLabelIds": [label_id]}
    ).execute()


def main():
    parser = argparse.ArgumentParser(description="Label large Gmail messages.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=15,
        help="Minimum size of messages in MB (default: 15)",
    )
    args = parser.parse_args()

    service = get_gmail_service()
    threshold = args.threshold
    print(f"Searching for emails larger than {threshold}MB...\n")
