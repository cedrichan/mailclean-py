import argparse
import os

from .filesystem import FileSystem
from .gmail import get_gmail_service
from .mail_cleaner import MailCleaner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strip attachments and optionally save them."
    )
    parser.add_argument(
        "--download_dir", required=True, help="Directory to save attachments"
    )
    args = parser.parse_args()
    args.download_dir = os.path.expanduser(args.download_dir)

    if not os.path.exists(args.download_dir):
        os.makedirs(args.download_dir)

    service = get_gmail_service()
    cleaner = MailCleaner(service, FileSystem())

    pre_label_id = service.get_pre_cleanup_label_id()
    post_label_id = service.get_post_cleanup_label_id()

    messages = cleaner.fetch_messages_by_label(pre_label_id)
    if not messages:
        print("No messages found.")
        return

    cleaner.strip_attachments(messages, args.download_dir, post_label_id)


if __name__ == "__main__":
    main()
