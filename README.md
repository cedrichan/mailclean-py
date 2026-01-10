# MailClean-Py

A suite of Python scripts designed to help you declutter your Gmail inbox by identifying large emails, saving their attachments locally, and replacing them with lightweight, attachment-free versions.

## Project Structure

*   `large_attachments.py`: Finds large emails and marks them for processing.
*   `strip_attachments.py`: Downloads attachments locally and creates "cleaned" versions of the emails in Gmail.
*   `remove_originals.py`: Safely removes the original large emails after you've verified the cleanup.

---

## Prerequisites

1.  **Google Cloud Project**: You need a Google Cloud project with the **Gmail API** enabled.
2.  **Credentials**: Download your `credentials.json` from the Google Cloud Console and place it in the project root.
3.  **Python 3.13+**: This project uses modern Python features.
4.  **Package Manager**: This project uses `uv`. Install it via [astral.sh/uv](https://astral.sh/uv).

### Installation

Install the required dependencies using `uv`:

```shell script
uv sync
```


---

## Usage Workflow

The cleanup process is designed in three distinct steps to ensure no data is lost.

### Step 1: Identify and Label Large Emails
Run `large_attachments.py` to scan your inbox. By default, it looks for emails larger than 15MB and applies a `PRE_CLEANUP` label to them.

```shell script
# Search for emails > 15MB (default)
uv run mailclean/large_attachments.py

# Or specify a custom threshold in MB
uv run mailclean/large_attachments.py --threshold 5
```


### Step 2: Strip and Save Attachments
Run `strip_attachments.py` to process the emails marked `PRE_CLEANUP`.
- It downloads attachments to a local directory.
- It creates a `.url` shortcut in the local folder pointing to the new email.
- It creates a "cleaned" copy of the email in Gmail (body only) with a `POST_CLEANUP` label.

```shell script
uv run mailclean/strip_attachments.py ./my_attachments_folder
```


### Step 3: Remove Original Emails
Once you are satisfied that your attachments are safe and the cleaned emails are correct, run `remove_originals.py` to move the original large emails to the Trash.

```shell script
# First, perform a dry run to see what would be deleted
uv run mailclean/remove_originals.py --dry-run

# Perform the actual deletion (moves to Trash)
uv run mailclean/remove_originals.py
```


---

## Labels Used
- **PRE_CLEANUP**: Applied to original large emails found by the scanner.
- **POST_CLEANUP**: Applied to the new, attachment-free versions of your emails.

## Safety Features
- **Trash instead of Delete**: `remove_originals.py` moves files to the Gmail Trash rather than permanently deleting them, giving you a 30-day window to recover them.
- **Safety Checks**: The removal script checks for the presence of the `POST_CLEANUP` label on messages to prevent accidental deletion of already cleaned content.
