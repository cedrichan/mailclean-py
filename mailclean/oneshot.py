import argparse
import os
from .gmail import (
    get_gmail_service,
    get_pre_cleanup_label_id,
    get_post_cleanup_label_id,
)
from .large_attachments import tag_large_emails
from .strip_attachments import (
    fetch_messages_by_label,
    process_messages,
)
from .remove_originals import delete_labeled_messages


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-shot Gmail cleanup: Tag, Save/Strip, and Remove originals."
    )
    parser.add_argument(
        "--size",
        type=int,
        default=20000000,
        help="Minimum email size in bytes (default: 20MB)",
    )
    parser.add_argument(
        "--download_dir", required=True, help="Directory to save attachments"
    )
    args = parser.parse_args()
    args.download_dir = os.path.expanduser(args.download_dir)

    if not os.path.exists(args.download_dir):
        os.makedirs(args.download_dir)

    service = get_gmail_service()

    # Labels
    pre_label_id = get_pre_cleanup_label_id(service)
    post_label_id = get_post_cleanup_label_id(service)

    # 1. Tag large emails
    print(f"--- Step 1: Tagging emails larger than {args.size} bytes ---")
    tag_large_emails(service, args.size, pre_label_id)

    # 2. Process tagged emails
    print("--- Step 2: Stripping and saving attachments ---")
    messages = fetch_messages_by_label(service, pre_label_id)

    if not messages:
        print("No messages found to process.")
    else:
        process_messages(service, messages, args.download_dir, post_label_id)

    # 3. Remove original tagged messages
    print("--- Step 3: Removing original messages ---")
    # We call the logic to delete messages that have the PRE_CLEANUP label
    delete_labeled_messages(service, pre_label_id)

    print("--- Cleanup Complete ---")


if __name__ == "__main__":
    main()
