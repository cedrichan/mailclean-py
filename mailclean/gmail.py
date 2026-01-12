import os.path
from functools import lru_cache
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

PRE_CLEANUP_LABEL = "PRE_CLEANUP"
POST_CLEANUP_LABEL = "POST_CLEANUP"


def get_gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def get_or_create_label(service, label_name):
    """Returns the ID of the specified label, creating it if it doesn't exist."""
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in labels:
        if label["name"] == label_name:
            return label["id"]

    # Label not found, create it
    label_body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    created_label = (
        service.users().labels().create(userId="me", body=label_body).execute()
    )
    return created_label["id"]


@lru_cache(maxsize=None)
def get_pre_cleanup_label_id(service):
    return get_or_create_label(service, PRE_CLEANUP_LABEL)


@lru_cache(maxsize=None)
def get_post_cleanup_label_id(service):
    return get_or_create_label(service, POST_CLEANUP_LABEL)
