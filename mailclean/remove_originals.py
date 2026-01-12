import argparse
from typing import Any, List, Dict
from .gmail import (
    get_gmail_service,
    get_pre_cleanup_label_id,
    get_post_cleanup_label_id,
    GmailService,
)


def fetch_messages_with_label(
    service: GmailService, label_id: str
) -> List[Dict[str, Any]]:
    """Fetches all messages associated with a specific label ID."""
    results = (
        service.users().messages().list(userId="me", labelIds=[label_id]).execute()
    )
    return results.get("messages", [])


def delete_labeled_messages(
    service: GmailService, pre_label_id: str, dry_run: bool = False
) -> None:
    """Deletes messages with the specified label, with a safety check."""
    # Get Label IDs for safety check
    post_label_id = get_post_cleanup_label_id(service)

    # Fetch messages that have the PRE_CLEANUP label
    messages_to_process = fetch_messages_with_label(service, pre_label_id)

    if not messages_to_process:
        print("No messages found with PRE_CLEANUP label.")
        return

    print(f"Found {len(messages_to_process)} messages to remove.")

    for msg_meta in messages_to_process:
        msg_id = msg_meta["id"]

        # Double-check labels to ensure it's not also marked as POST_CLEANUP (extra safety)
        msg_data = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, fields="labelIds,snippet")
            .execute()
        )
        label_ids = msg_data.get("labelIds", [])
        snippet = msg_data.get("snippet", "")

        if post_label_id and post_label_id in label_ids:
            print(
                f"Skipping {msg_id} - safety check failed: message also has POST_CLEANUP label."
            )
            continue

        if dry_run:
            print(f"[DRY RUN] Would delete message: {msg_id} - {snippet[:50]}...")
        else:
            try:
                # trash() moves the message to the bin instead of permanent deletion (safer)
                service.users().messages().trash(userId="me", id=msg_id).execute()
                print(f"Successfully moved message {msg_id} to Trash.")
            except Exception as e:
                print(f"Error deleting message {msg_id}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove original emails marked with PRE_CLEANUP."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List messages without deleting them."
    )
    args = parser.parse_args()

    service = get_gmail_service()

    pre_label_id = get_pre_cleanup_label_id(service)

    delete_labeled_messages(service, pre_label_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
