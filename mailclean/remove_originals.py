import argparse
from .filesystem import FileSystem
from .gmail import (
    get_gmail_service,
)
from .mail_cleaner import MailCleaner


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove original emails marked with PRE_CLEANUP."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List messages without deleting them."
    )
    args = parser.parse_args()

    service = get_gmail_service()
    cleaner = MailCleaner(service, FileSystem())

    pre_label_id = service.get_pre_cleanup_label_id()

    cleaner.delete_labeled_messages(pre_label_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
