import argparse
import os
from .filesystem import FileSystem
from .gmail import (
    get_gmail_service,
)
from .mail_cleaner import MailCleaner


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
    cleaner = MailCleaner(service, FileSystem())
    cleaner.run_cleanup(args.size, args.download_dir)


if __name__ == "__main__":
    main()
