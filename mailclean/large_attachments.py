import argparse
from typing import Any, Dict
from .gmail import get_gmail_service, get_pre_cleanup_label_id, GmailService


def print_message_info(message: Dict[str, Any]) -> None:
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


def apply_label_to_message(
    service: GmailService, message_id: str, label_id: str
) -> None:
    """Adds the specified label to a message."""
    service.users().messages().batchModify(
        userId="me", body={"ids": [message_id], "addLabelIds": [label_id]}
    ).execute()


def tag_large_emails(service: GmailService, size_bytes: int, label_id: str) -> None:
    """Queries Gmail for messages larger than the specified size (in bytes) and applies a label."""
    query = f"larger:{size_bytes}"
    results = service.users().messages().list(userId="me", q=query).execute()
    messages_summaries = results.get("messages", [])

    print(f"Applying label to {len(messages_summaries)} messages...")

    for msg_summary in messages_summaries:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_summary["id"], format="full")
            .execute()
        )
        print_message_info(msg)
        apply_label_to_message(service, msg["id"], label_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Label large Gmail messages.")
    parser.add_argument(
        "--size",
        type=int,
        default=20000000,
        help="Minimum email size in bytes (default: 20MB)",
    )
    args = parser.parse_args()

    service = get_gmail_service()
    threshold_bytes = args.size
    print(f"Searching for emails larger than {threshold_bytes} bytes...\n")

    label_id = get_pre_cleanup_label_id(service)
    tag_large_emails(service, threshold_bytes, label_id)


if __name__ == "__main__":
    main()
