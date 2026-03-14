import base64
import os
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Any

from pathvalidate import sanitize_filename

from .gmail import GmailService


class MailCleaner:
    def __init__(self, service: GmailService):
        self._service = service

    def print_message_info(self, message: dict[str, Any]) -> None:
        """Format and print message details including a direct browser link."""
        headers = message.get("payload", {}).get("headers", [])

        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
        )
        sender = next(
            (h["value"] for h in headers if h["name"] == "From"), "Unknown Sender"
        )
        date = next(
            (h["value"] for h in headers if h["name"] == "Date"), "Unknown Date"
        )

        size_bytes = int(message.get("sizeEstimate", 0))
        size_mb = size_bytes / 1024 / 1024

        msg_id = message.get("id")
        link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

        print(f"Subject: {subject}")
        print(f"From:    {sender}")
        print(f"Date:    {date}")
        print(f"Size:    {size_mb:.2f} MB")
        print(f"Link:    {link}")
        print("-" * 40)

    def apply_label_to_message(self, message_id: str, label_id: str) -> None:
        """Add the specified label to a message."""
        self._service.add_label_to_message(message_id, label_id)

    def tag_large_emails(self, size_bytes: int, label_id: str) -> None:
        """Apply a label to messages larger than the specified size."""
        query = f"larger:{size_bytes}"
        messages_summaries = self._service.list_messages(query=query)

        print(f"Applying label to {len(messages_summaries)} messages...")

        for msg_summary in messages_summaries:
            msg = self._service.get_message(msg_summary["id"], format="full")
            self.print_message_info(msg)
            self.apply_label_to_message(msg["id"], label_id)

    def fetch_messages_by_label(self, label_id: str) -> list[dict[str, Any]]:
        """Fetch all messages associated with the given label ID."""
        return self._service.list_messages(label_ids=[label_id])

    def _create_email_shortcut(self, directory: str, message_id: str) -> str:
        """Create a .url shortcut file pointing to the Gmail message."""
        link = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
        filename = "__LINK.url"
        filepath = os.path.join(directory, filename)

        with open(filepath, "w") as f:
            f.write("[InternetShortcut]\n")
            f.write(f"URL={link}\n")
        return filename

    def _save_attachments(
        self,
        raw_content: bytes,
        base_dir: str,
        original_message_id: str,
        new_message_id: str | None = None,
    ) -> list[str]:
        """Save attachments from raw email content and optionally add a shortcut."""
        msg = message_from_bytes(raw_content, policy=policy.default)

        subject = msg.get("Subject", "No Subject")
        date_str = msg.get("Date")

        try:
            dt = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            formatted_datetime = dt.strftime("%Y-%m-%d %H.%M.%S")
        except Exception:
            formatted_datetime = "UnknownDateTime"

        clean_subject = sanitize_filename(subject)
        folder_name = f"{formatted_datetime} - {original_message_id} - {clean_subject}"
        target_dir = os.path.join(base_dir, folder_name)

        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        if new_message_id:
            self._create_email_shortcut(target_dir, new_message_id)

        saved_files: list[str] = []

        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                clean_filename = sanitize_filename(filename)
                filepath = os.path.join(target_dir, clean_filename)

                payload = part.get_payload(decode=True)
                with open(filepath, "wb") as f:
                    f.write(payload)
                saved_files.append(clean_filename)

        return saved_files

    def _strip_attachments_from_raw(self, raw_content: bytes) -> bytes:
        """Return raw email bytes with only text/html body content preserved."""
        msg = message_from_bytes(raw_content, policy=policy.default)

        original_date = msg.get("Date")
        new_msg = EmailMessage()

        for header in msg.keys():
            if header.lower() not in [
                "content-type",
                "content-transfer-encoding",
                "mime-version",
                "date",
            ]:
                values = msg.get_all(header)
                for val in values:
                    try:
                        new_msg[header] = str(val).strip()
                    except Exception:
                        continue

        if original_date:
            new_msg["Date"] = original_date

        text_part = msg.get_body(preferencelist=("plain", "html"))
        html_part = msg.get_body(preferencelist=("html", "plain"))

        if text_part:
            subtype = "html" if text_part.get_content_subtype() == "html" else "plain"
            new_msg.set_content(text_part.get_content(), subtype=subtype)

            if html_part and html_part != text_part:
                new_msg.add_alternative(html_part.get_content(), subtype="html")
        elif html_part:
            new_msg.set_content(html_part.get_content(), subtype="html")
        else:
            new_msg.set_content("Body removed during cleanup.")

        return new_msg.as_bytes()

    def strip_attachments(
        self,
        messages: list[dict[str, Any]],
        download_dir: str,
        post_label_id: str,
    ) -> None:
        """Strip attachments, save them locally, and create cleaned versions."""
        print(f"Found {len(messages)} messages to process.")

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            msg_data = self._service.get_message(msg_id, format="raw")
            internal_date = msg_data.get("internalDate")
            thread_id = msg_data.get("threadId")
            raw_bytes = base64.urlsafe_b64decode(msg_data["raw"].encode("ASCII"))

            stripped_bytes = self._strip_attachments_from_raw(raw_bytes)

            encoded_message = base64.urlsafe_b64encode(stripped_bytes).decode("utf-8")
            message_body = {
                "raw": encoded_message,
                "labelIds": [post_label_id],
                "internalDate": internal_date,
                "threadId": thread_id,
            }

            try:
                created_msg = self._service.insert_message(message_body)

                new_id = created_msg["id"]
                print(f"Created cleaned duplicate: {new_id}")

                files = self._save_attachments(
                    raw_bytes, download_dir, msg_id, new_message_id=new_id
                )
                if files:
                    print(
                        f"Saved {len(files)} attachments for {msg_id} (Linked to {new_id})"
                    )

            except Exception as e:
                print(f"Error processing message {msg_id}: {e}")

    def delete_labeled_messages(self, pre_label_id: str, dry_run: bool = False) -> None:
        """Move PRE_CLEANUP-labelled messages to trash with a safety check."""
        post_label_id = self._service.get_post_cleanup_label_id()
        messages_to_process = self.fetch_messages_by_label(pre_label_id)

        if not messages_to_process:
            print("No messages found with PRE_CLEANUP label.")
            return

        print(f"Found {len(messages_to_process)} messages to remove.")

        for msg_meta in messages_to_process:
            msg_id = msg_meta["id"]
            msg_data = self._service.get_message(msg_id, fields="labelIds,snippet")
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
                    self._service.trash_message(msg_id)
                    print(f"Successfully moved message {msg_id} to Trash.")
                except Exception as e:
                    print(f"Error deleting message {msg_id}: {e}")

    def run_cleanup(self, size_bytes: int, download_dir: str) -> None:
        """Run the full cleanup workflow end to end."""
        pre_label_id = self._service.get_pre_cleanup_label_id()
        post_label_id = self._service.get_post_cleanup_label_id()

        print(f"--- Step 1: Tagging emails larger than {size_bytes} bytes ---")
        self.tag_large_emails(size_bytes, pre_label_id)

        print("--- Step 2: Stripping and saving attachments ---")
        messages = self.fetch_messages_by_label(pre_label_id)

        if not messages:
            print("No messages found to process.")
        else:
            self.strip_attachments(messages, download_dir, post_label_id)

        print("--- Step 3: Removing original messages ---")
        self.delete_labeled_messages(pre_label_id)

        print("--- Cleanup Complete ---")
