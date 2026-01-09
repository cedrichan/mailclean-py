import base64
from email import message_from_bytes, policy
from email.message import EmailMessage
from .large_attachments import get_gmail_service, get_or_create_label

def fetch_messages_by_label(service, label_id):
    """Fetches all messages associated with a specific label ID."""
    results = service.users().messages().list(userId='me', labelIds=[label_id]).execute()
    return results.get('messages', [])

def strip_attachments_from_raw(raw_content):
    """Parses raw email bytes and returns a version with only text/html parts."""
    msg = message_from_bytes(raw_content, policy=policy.default)

    # Capture original date header before creating new message
    original_date = msg.get('Date')

    new_msg = EmailMessage()

    # Copy headers
    for header in msg.keys():
        if header.lower() not in ['content-type', 'content-transfer-encoding', 'mime-version', 'date']:
            values = msg.get_all(header)
            for val in values:
                try:
                    new_msg[header] = str(val).strip()
                except: continue

    # Explicitly set the original date back
    if original_date:
        new_msg['Date'] = original_date

        # Find text and html parts
        text_part = msg.get_body(preferencelist=('plain', 'html'))
        html_part = msg.get_body(preferencelist=('html', 'plain'))

        if text_part:
            new_msg.set_content(text_part.get_content())
            if html_part and html_part != text_part:
                new_msg.add_alternative(html_part.get_content(), subtype='html')
        else:
            new_msg.set_content("Body removed during cleanup.")

        return new_msg.as_bytes()

def main():
    service = get_gmail_service()

    pre_label_id = get_or_create_label(service, "PRE_CLEANUP")
    post_label_id = get_or_create_label(service, "POST_CLEANUP")

    messages = fetch_messages_by_label(service, pre_label_id)
    if not messages:
        print("No messages found with PRE_CLEANUP label.")
        return

    print(f"Found {len(messages)} messages to process.")

    for msg_meta in messages:
        msg_id = msg_meta['id']
        # Get raw message content and original internalDate
        msg_data = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
        internal_date = msg_data.get('internalDate')
        raw_bytes = base64.urlsafe_b64decode(msg_data['raw'].encode('ASCII'))

        stripped_bytes = strip_attachments_from_raw(raw_bytes)

        encoded_message = base64.urlsafe_b64encode(stripped_bytes).decode('utf-8')
        message_body = {
            'raw': encoded_message,
            'labelIds': [post_label_id],
            'internalDate': internal_date  # Pass the original timestamp directly
        }

        try:
            # internalDateSource='dateHeader' tells Gmail to trust the header or the provided internalDate
            created_msg = service.users().messages().insert(
                userId='me',
                body=message_body,
                internalDateSource='dateHeader'
            ).execute()
            print(f"Created cleaned duplicate: {created_msg['id']} (Original Date: {internal_date})")
        except Exception as e:
            print(f"Error processing message {msg_id}: {e}")

if __name__ == '__main__':
    main()
