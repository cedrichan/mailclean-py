import base64
import os
import argparse
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from pathvalidate import sanitize_filename
from .large_attachments import get_gmail_service, get_or_create_label


def fetch_messages_by_label(service, label_id):
    """Fetches all messages associated with a specific label ID."""
    results = (
        service.users().messages().list(userId="me", labelIds=[label_id]).execute()
    )
    return results.get("messages", [])


def create_email_shortcut(directory, subject, message_id):
    """Creates a .url shortcut file pointing to the Gmail message."""
    link = f"https://mail.google.com/mail/u/0/#inbox/{message_id}"
    filename = "__LINK.url"
    filepath = os.path.join(directory, filename)

    with open(filepath, "w") as f:
        f.write("[InternetShortcut]\n")
        f.write(f"URL={link}\n")
    return filename


def save_attachments(raw_content, base_dir, original_message_id, new_message_id=None):
    """Finds and saves attachments from raw email content and adds a link to the new message."""
    msg = message_from_bytes(raw_content, policy=policy.default)

    subject = msg.get("Subject", "No Subject")
    date_str = msg.get("Date")

    # Format date and time: 2023-10-27 14.30.05
    try:
        dt = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        formatted_datetime = dt.strftime("%Y-%m-%d %H.%M.%S")
    except:
        formatted_datetime = "UnknownDateTime"

    clean_subject = sanitize_filename(subject)
    folder_name = f"{formatted_datetime} - {original_message_id} - {clean_subject}"
    target_dir = os.path.join(base_dir, folder_name)

    # Create folder if it has attachments or if we are adding a link
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    # Add the shortcut link
    if new_message_id:
        create_email_shortcut(target_dir, subject, new_message_id)

    saved_files = []

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


def strip_attachments_from_raw(raw_content):
    """Parses raw email bytes and returns a version with only text/html parts."""
    msg = message_from_bytes(raw_content, policy=policy.default)

    # Capture original date header before creating new message
    original_date = msg.get("Date")

    new_msg = EmailMessage()

    # Copy headers
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
                except:
                    continue

    # Explicitly set the original date back
    if original_date:
        new_msg["Date"] = original_date

    # Find text and html parts
    text_part = msg.get_body(preferencelist=("plain", "html"))
    html_part = msg.get_body(preferencelist=("html", "plain"))

    if text_part:
        # If the primary part found is actually HTML, set subtype='html'
        subtype = "html" if text_part.get_content_subtype() == "html" else "plain"
        new_msg.set_content(text_part.get_content(), subtype=subtype)

        # If we have an alternative HTML part that is different from the text part, add it
        if html_part and html_part != text_part:
            new_msg.add_alternative(html_part.get_content(), subtype="html")
    elif html_part:
        # Fallback for HTML-only emails
        new_msg.set_content(html_part.get_content(), subtype="html")
    else:
        new_msg.set_content("Body removed during cleanup.")

    return new_msg.as_bytes()


def main():
    parser = argparse.ArgumentParser(
        description="Strip attachments and optionally save them."
    )
    parser.add_argument("download_dir", help="Directory to save attachments to")
    args = parser.parse_args()

    if not os.path.exists(args.download_dir):
        os.makedirs(args.download_dir)

    service = get_gmail_service()

    pre_label_id = get_or_create_label(service, "PRE_CLEANUP")
    post_label_id = get_or_create_label(service, "POST_CLEANUP")

    messages = fetch_messages_by_label(service, pre_label_id)
    if not messages:
        print("No messages found with PRE_CLEANUP label.")
        return

    print(f"Found {len(messages)} messages to process.")

    for msg_meta in messages:
        msg_id = msg_meta["id"]
        # 1. Get raw message content, original internalDate, and threadId
        msg_data = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="raw")
            .execute()
        )
        internal_date = msg_data.get("internalDate")
        thread_id = msg_data.get("threadId")
        raw_bytes = base64.urlsafe_b64decode(msg_data["raw"].encode("ASCII"))

        # 2. Strip attachments from raw bytes
        stripped_bytes = strip_attachments_from_raw(raw_bytes)

        encoded_message = base64.urlsafe_b64encode(stripped_bytes).decode("utf-8")
        message_body = {
            "raw": encoded_message,
            "labelIds": [post_label_id],
            "internalDate": internal_date,
            "threadId": thread_id,
        }

        try:
            # 3. Create the cleaned duplicate first to get its ID
            created_msg = (
                service.users()
                .messages()
                .insert(userId="me", body=message_body, internalDateSource="dateHeader")
                .execute()
            )

            new_id = created_msg["id"]
            print(f"Created cleaned duplicate: {new_id}")

            # 4. Now save attachments and include the shortcut to the NEW ID
            # Pass original_message_id to the folder naming logic
            files = save_attachments(
                raw_bytes, args.download_dir, msg_id, new_message_id=new_id
            )
            if files:
                print(
                    f"Saved {len(files)} attachments for {msg_id} (Linked to {new_id})"
                )

        except Exception as e:
            print(f"Error processing message {msg_id}: {e}")


if __name__ == "__main__":
    main()
