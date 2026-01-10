import argparse
from .large_attachments import get_gmail_service


def fetch_messages_with_label(service, label_id):
    """Fetches all messages associated with a specific label ID."""
    results = (
        service.users().messages().list(userId="me", labelIds=[label_id]).execute()
    )
    return results.get("messages", [])


def main():
    parser = argparse.ArgumentParser(
        description="Remove original emails marked with PRE_CLEANUP."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List messages without deleting them."
    )
    args = parser.parse_args()

    service = get_gmail_service()

    # Get Label IDs
    labels_results = service.users().labels().list(userId="me").execute()
    labels = labels_results.get("labels", [])

    pre_label_id = next((l["id"] for l in labels if l["name"] == "PRE_CLEANUP"), None)
    post_label_id = next((l["id"] for l in labels if l["name"] == "POST_CLEANUP"), None)

    if not pre_label_id:
        print("Label 'PRE_CLEANUP' not found. Nothing to do.")
        return

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

        if args.dry_run:
            print(f"[DRY RUN] Would delete message: {msg_id} - {snippet[:50]}...")
        else:
            try:
                # trash() moves the message to the bin instead of permanent deletion (safer)
                service.users().messages().trash(userId="me", id=msg_id).execute()
                print(f"Successfully moved message {msg_id} to Trash.")
            except Exception as e:
                print(f"Error deleting message {msg_id}: {e}")

    print("Done.")


if __name__ == "__main__":
    main()
