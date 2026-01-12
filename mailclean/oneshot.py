import argparse
import os
import base64
from .large_attachments import get_gmail_service, get_or_create_label, tag_large_emails
from .strip_attachments import (
    fetch_messages_by_label,
    strip_attachments_from_raw,
    save_attachments,
)
from .remove_originals import delete_labeled_messages


def main():
    parser = argparse.ArgumentParser(
        description="One-shot Gmail cleanup: Tag, Save/Strip, and Remove originals."
    )
    parser.add_argument(
        "--size",
        type=int,
        default=5000000,
        help="Minimum email size in bytes (default: 5MB)",
    )
    parser.add_argument(
        "--download_dir", required=True, help="Directory to save attachments"
    )
    args = parser.parse_args()

    if not os.path.exists(args.download_dir):
        os.makedirs(args.download_dir)

    service = get_gmail_service()

    # Labels
    pre_label_name = "PRE_CLEANUP"
    post_label_name = "POST_CLEANUP"
    pre_label_id = get_or_create_label(service, pre_label_name)
    post_label_id = get_or_create_label(service, post_label_name)

    # 1. Tag large emails
    print(f"--- Step 1: Tagging emails larger than {args.size} bytes ---")
    tag_large_emails(service, args.size, pre_label_id)

    # 2. Process tagged emails
    print(f"--- Step 2: Stripping and saving attachments ---")
    messages = fetch_messages_by_label(service, pre_label_id)

    if not messages:
        print("No messages found to process.")
    else:
        for msg_meta in messages:
            msg_id = msg_meta["id"]
            try:
                # Fetch raw content
                msg_data = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="raw")
                    .execute()
                )

                internal_date = msg_data.get("internalDate")
                thread_id = msg_data.get("threadId")
                raw_bytes = base64.urlsafe_b64decode(msg_data["raw"].encode("ASCII"))

                # Create stripped version
                stripped_bytes = strip_attachments_from_raw(raw_bytes)
                encoded_message = base64.urlsafe_b64encode(stripped_bytes).decode(
                    "utf-8"
                )

                message_body = {
                    "raw": encoded_message,
                    "labelIds": [post_label_id],
                    "internalDate": internal_date,
                    "threadId": thread_id,
                }

                # Insert cleaned message
                created_msg = (
                    service.users()
                    .messages()
                    .insert(
                        userId="me", body=message_body, internalDateSource="dateHeader"
                    )
                    .execute()
                )

                new_id = created_msg["id"]

                # Save attachments
                files = save_attachments(
                    raw_bytes, args.download_dir, msg_id, new_message_id=new_id
                )

                status = f"Saved {len(files)} files" if files else "No files to save"
                print(f"Processed {msg_id} -> {new_id} ({status})")

            except Exception as e:
                print(f"Error processing message {msg_id}: {e}")

    # 3. Remove original tagged messages
    print(f"--- Step 3: Removing original messages ---")
    # We call the logic to delete messages that have the PRE_CLEANUP label
    delete_labeled_messages(service, pre_label_id)

    print("--- Cleanup Complete ---")


if __name__ == "__main__":
    main()
