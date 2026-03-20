import base64
from email.message import EmailMessage
from typing import Any
from unittest.mock import Mock

import pytest

from mailclean.filesystem import FileSystem
from mailclean.gmail import GmailService
from mailclean.mail_cleaner import MailCleaner


@pytest.fixture
def mock_service():
    return Mock(spec=GmailService)


@pytest.fixture
def mock_fs():
    mock = Mock(spec=FileSystem)
    # Make join behave like os.path.join for predictable paths
    mock.join.side_effect = lambda *parts: "/".join(parts)
    return mock


@pytest.fixture
def cleaner(mock_service, mock_fs):
    return MailCleaner(mock_service, mock_fs)


def make_message(
    msg_id: str = "msg123",
    subject: str = "Test Subject",
    sender: str = "alice@example.com",
    date: str = "Mon, 01 Jan 2024 12:00:00 +0000",
    size_estimate: int = 10_000_000,
    label_ids: list[str] | None = None,
    snippet: str = "Preview text...",
) -> dict[str, Any]:
    """Build a Gmail API message dict with standard headers."""
    return {
        "id": msg_id,
        "threadId": f"thread_{msg_id}",
        "labelIds": label_ids or [],
        "snippet": snippet,
        "sizeEstimate": size_estimate,
        "internalDate": "1704067200000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
                {"name": "Date", "value": date},
            ],
        },
    }


def make_raw_email(
    subject: str = "Test Subject",
    sender: str = "alice@example.com",
    date: str = "Mon, 01 Jan 2024 12:00:00 +0000",
    body: str = "Hello, this is the body.",
    attachments: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Build a raw MIME email with optional attachments."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = "bob@example.com"
    msg["Date"] = date
    msg.set_content(body)

    for filename, content in (attachments or []):
        msg.add_attachment(
            content,
            maintype="application",
            subtype="octet-stream",
            filename=filename,
        )

    return msg.as_bytes()


def encode_raw_email(raw_bytes: bytes) -> str:
    """Base64url-encode raw email bytes, matching Gmail API format."""
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
