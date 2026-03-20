import base64
import sys
from pathlib import Path
from unittest.mock import call

# Allow importing helpers from conftest
sys.path.insert(0, str(Path(__file__).parent))
from conftest import encode_raw_email, make_message, make_raw_email

from mailclean.mail_cleaner import MailCleaner


class TestGmailUrl:
    def test_returns_correct_url(self, cleaner: MailCleaner):
        url = cleaner._gmail_url("abc123")
        assert url == "https://mail.google.com/mail/u/0/#inbox/abc123"


class TestPrintMessageInfo:
    def test_prints_subject_sender_date_size_link(self, cleaner, capsys):
        msg = make_message(
            msg_id="id42",
            subject="Big File",
            sender="eve@example.com",
            date="Tue, 02 Jan 2024 08:30:00 +0000",
            size_estimate=5_242_880,
        )

        cleaner.print_message_info(msg)
        output = capsys.readouterr().out

        assert "Big File" in output
        assert "eve@example.com" in output
        assert "Tue, 02 Jan 2024 08:30:00 +0000" in output
        assert "5.00 MB" in output
        assert "https://mail.google.com/mail/u/0/#inbox/id42" in output

    def test_missing_headers_fallback(self, cleaner, capsys):
        msg = {"id": "nohdr", "payload": {"headers": []}, "sizeEstimate": 0}

        cleaner.print_message_info(msg)
        output = capsys.readouterr().out

        assert "No Subject" in output
        assert "Unknown Sender" in output
        assert "Unknown Date" in output


class TestTagLargeEmails:
    def test_queries_labels_and_prints(self, cleaner, mock_service, capsys):
        summaries = [{"id": "m1"}, {"id": "m2"}]
        mock_service.list_messages.return_value = summaries
        mock_service.get_message.side_effect = [
            make_message("m1", subject="Email 1"),
            make_message("m2", subject="Email 2"),
        ]

        cleaner.tag_large_emails(size_bytes=20_000_000, label_id="lbl_pre")

        mock_service.list_messages.assert_called_once_with(query="larger:20000000")
        assert mock_service.get_message.call_count == 2
        mock_service.add_label_to_message.assert_any_call("m1", "lbl_pre")
        mock_service.add_label_to_message.assert_any_call("m2", "lbl_pre")

    def test_no_messages_found(self, cleaner, mock_service, capsys):
        mock_service.list_messages.return_value = []

        cleaner.tag_large_emails(size_bytes=1000, label_id="lbl")

        mock_service.get_message.assert_not_called()
        mock_service.add_label_to_message.assert_not_called()
        assert "0 messages" in capsys.readouterr().out


class TestFetchMessagesByLabel:
    def test_delegates_to_service(self, cleaner, mock_service):
        mock_service.list_messages.return_value = [{"id": "x"}]

        result = cleaner.fetch_messages_by_label("lbl_123")

        mock_service.list_messages.assert_called_once_with(label_ids=["lbl_123"])
        assert result == [{"id": "x"}]


class TestCreateEmailShortcut:
    def test_writes_url_file(self, cleaner, mock_fs):
        filename = cleaner._create_email_shortcut("/downloads/folder", "msg99")

        assert filename == "__LINK.url"
        mock_fs.write_text.assert_called_once_with(
            "/downloads/folder/__LINK.url",
            "[InternetShortcut]\nURL=https://mail.google.com/mail/u/0/#inbox/msg99\n",
        )


class TestStripAttachmentsFromRaw:
    def test_preserves_body_removes_attachment(self, cleaner):
        raw = make_raw_email(
            body="Keep this text.",
            attachments=[("report.pdf", b"fake-pdf-content")],
        )

        stripped = cleaner._strip_attachments_from_raw(raw)

        from email import message_from_bytes, policy

        result = message_from_bytes(stripped, policy=policy.default)

        body = result.get_body(preferencelist=("plain",))
        assert body is not None
        assert "Keep this text." in body.get_content()

        attachment_filenames = [
            part.get_filename() for part in result.walk() if part.get_filename()
        ]
        assert attachment_filenames == []

    def test_preserves_date_header(self, cleaner):
        raw = make_raw_email(date="Fri, 15 Mar 2024 10:00:00 +0000")

        stripped = cleaner._strip_attachments_from_raw(raw)

        from email import message_from_bytes, policy

        result = message_from_bytes(stripped, policy=policy.default)
        assert "15 Mar 2024" in result["Date"]

    def test_preserves_subject_header(self, cleaner):
        raw = make_raw_email(subject="Important Email")

        stripped = cleaner._strip_attachments_from_raw(raw)

        from email import message_from_bytes, policy

        result = message_from_bytes(stripped, policy=policy.default)
        assert result["Subject"] == "Important Email"

    def test_email_with_no_body_gets_fallback(self, cleaner):
        # Build a message with only an attachment (no text/html body)
        # by manually crafting the MIME structure
        raw = (
            b"Subject: Empty\r\n"
            b"From: a@b.com\r\n"
            b"Date: Mon, 01 Jan 2024 00:00:00 +0000\r\n"
            b"MIME-Version: 1.0\r\n"
            b"Content-Type: application/octet-stream; name=\"file.bin\"\r\n"
            b"Content-Disposition: attachment; filename=\"file.bin\"\r\n"
            b"Content-Transfer-Encoding: base64\r\n"
            b"\r\n"
            b"AQIDBA==\r\n"
        )

        stripped = cleaner._strip_attachments_from_raw(raw)

        from email import message_from_bytes, policy

        result = message_from_bytes(stripped, policy=policy.default)
        body = result.get_body(preferencelist=("plain",))
        assert body is not None
        assert "removed during cleanup" in body.get_content()


class TestSaveAttachments:
    def test_saves_attachment_files(self, cleaner, mock_fs):
        raw = make_raw_email(
            subject="Report",
            date="Mon, 01 Jan 2024 12:00:00 +0000",
            attachments=[
                ("report.pdf", b"pdf-data"),
                ("image.png", b"png-data"),
            ],
        )

        saved = cleaner._save_attachments(raw, "/dl", "orig_id")

        assert "report.pdf" in saved
        assert "image.png" in saved
        mock_fs.makedirs.assert_called_once()
        assert mock_fs.write_bytes.call_count == 2

    def test_creates_shortcut_when_new_message_id_provided(self, cleaner, mock_fs):
        raw = make_raw_email(attachments=[("f.txt", b"data")])

        cleaner._save_attachments(raw, "/dl", "orig", new_message_id="new123")

        # Should write the shortcut file plus the attachment
        mock_fs.write_text.assert_called_once()
        shortcut_content = mock_fs.write_text.call_args[0][1]
        assert "new123" in shortcut_content

    def test_no_shortcut_without_new_message_id(self, cleaner, mock_fs):
        raw = make_raw_email(attachments=[("f.txt", b"data")])

        cleaner._save_attachments(raw, "/dl", "orig")

        mock_fs.write_text.assert_not_called()

    def test_unparseable_date_uses_fallback(self, cleaner, mock_fs):
        raw = make_raw_email(date="not-a-date", attachments=[("f.txt", b"x")])

        cleaner._save_attachments(raw, "/dl", "orig")

        target_dir = mock_fs.makedirs.call_args[0][0]
        assert "UnknownDateTime" in target_dir

    def test_folder_name_contains_message_id_and_subject(self, cleaner, mock_fs):
        raw = make_raw_email(
            subject="Quarterly Report",
            date="Mon, 01 Jan 2024 12:00:00 +0000",
            attachments=[("f.txt", b"x")],
        )

        cleaner._save_attachments(raw, "/dl", "msg_abc")

        target_dir = mock_fs.makedirs.call_args[0][0]
        assert "msg_abc" in target_dir
        assert "Quarterly Report" in target_dir
        assert "2024-01-01" in target_dir


class TestStripAttachments:
    def test_processes_messages_and_inserts_cleaned(self, cleaner, mock_service, mock_fs):
        raw = make_raw_email(attachments=[("a.txt", b"data")])
        encoded = encode_raw_email(raw)

        messages = [{"id": "m1"}]
        mock_service.get_message.return_value = {
            "id": "m1",
            "raw": encoded,
            "internalDate": "1704067200000",
            "threadId": "t1",
        }
        mock_service.insert_message.return_value = {"id": "new_m1"}

        cleaner.strip_attachments(messages, "/dl", "post_lbl")

        mock_service.get_message.assert_called_once_with("m1", format="raw")
        mock_service.insert_message.assert_called_once()

        insert_body = mock_service.insert_message.call_args[0][0]
        assert insert_body["labelIds"] == ["post_lbl"]
        assert insert_body["internalDate"] == "1704067200000"
        assert insert_body["threadId"] == "t1"

    def test_continues_on_per_message_error(self, cleaner, mock_service, mock_fs, capsys):
        raw = make_raw_email(attachments=[("a.txt", b"data")])
        encoded = encode_raw_email(raw)

        messages = [{"id": "m1"}, {"id": "m2"}]
        mock_service.get_message.return_value = {
            "id": "m1",
            "raw": encoded,
            "internalDate": "1704067200000",
            "threadId": "t1",
        }
        mock_service.insert_message.side_effect = [
            RuntimeError("API failure"),
            {"id": "new_m2"},
        ]

        cleaner.strip_attachments(messages, "/dl", "post_lbl")

        assert mock_service.insert_message.call_count == 2
        output = capsys.readouterr().out
        assert "Error processing message m1" in output
        assert "Created cleaned duplicate: new_m2" in output


class TestDeleteLabeledMessages:
    def test_trashes_messages_without_post_label(self, cleaner, mock_service, capsys):
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"
        mock_service.list_messages.return_value = [{"id": "m1"}, {"id": "m2"}]
        mock_service.get_message.side_effect = [
            {"labelIds": ["pre_lbl"], "snippet": "Email one"},
            {"labelIds": ["pre_lbl"], "snippet": "Email two"},
        ]

        cleaner.delete_labeled_messages("pre_lbl")

        assert mock_service.trash_message.call_count == 2
        mock_service.trash_message.assert_any_call("m1")
        mock_service.trash_message.assert_any_call("m2")

    def test_skips_messages_with_post_cleanup_label(self, cleaner, mock_service, capsys):
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"
        mock_service.list_messages.return_value = [{"id": "m1"}]
        mock_service.get_message.return_value = {
            "labelIds": ["pre_lbl", "post_lbl"],
            "snippet": "Has both labels",
        }

        cleaner.delete_labeled_messages("pre_lbl")

        mock_service.trash_message.assert_not_called()
        assert "safety check failed" in capsys.readouterr().out

    def test_dry_run_does_not_trash(self, cleaner, mock_service, capsys):
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"
        mock_service.list_messages.return_value = [{"id": "m1"}]
        mock_service.get_message.return_value = {
            "labelIds": ["pre_lbl"],
            "snippet": "Dry run message",
        }

        cleaner.delete_labeled_messages("pre_lbl", dry_run=True)

        mock_service.trash_message.assert_not_called()
        assert "[DRY RUN]" in capsys.readouterr().out

    def test_no_messages_found(self, cleaner, mock_service, capsys):
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"
        mock_service.list_messages.return_value = []

        cleaner.delete_labeled_messages("pre_lbl")

        mock_service.trash_message.assert_not_called()
        assert "No messages found" in capsys.readouterr().out

    def test_continues_on_trash_error(self, cleaner, mock_service, capsys):
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"
        mock_service.list_messages.return_value = [{"id": "m1"}, {"id": "m2"}]
        mock_service.get_message.side_effect = [
            {"labelIds": ["pre_lbl"], "snippet": "First"},
            {"labelIds": ["pre_lbl"], "snippet": "Second"},
        ]
        mock_service.trash_message.side_effect = [RuntimeError("fail"), None]

        cleaner.delete_labeled_messages("pre_lbl")

        assert mock_service.trash_message.call_count == 2
        output = capsys.readouterr().out
        assert "Error deleting message m1" in output
        assert "Successfully moved message m2 to Trash" in output


class TestRunCleanup:
    def test_orchestrates_all_steps(self, cleaner, mock_service, mock_fs, capsys):
        mock_service.get_pre_cleanup_label_id.return_value = "pre_lbl"
        mock_service.get_post_cleanup_label_id.return_value = "post_lbl"

        # Step 1: tag_large_emails
        mock_service.list_messages.side_effect = [
            [],  # tag_large_emails query
            [],  # fetch_messages_by_label
            [],  # delete_labeled_messages -> fetch_messages_by_label
        ]

        cleaner.run_cleanup(size_bytes=20_000_000, download_dir="/dl")

        output = capsys.readouterr().out
        assert "Step 1" in output
        assert "Step 2" in output
        assert "Step 3" in output
        assert "Cleanup Complete" in output

        mock_service.get_pre_cleanup_label_id.assert_called_once()
        mock_service.get_post_cleanup_label_id.assert_called()
