import argparse
from .filesystem import FileSystem
from .gmail import get_gmail_service
from .mail_cleaner import MailCleaner


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
    cleaner = MailCleaner(service, FileSystem())
    threshold_bytes = args.size
    print(f"Searching for emails larger than {threshold_bytes} bytes...\n")

    label_id = service.get_pre_cleanup_label_id()
    cleaner.tag_large_emails(threshold_bytes, label_id)


if __name__ == "__main__":
    main()
