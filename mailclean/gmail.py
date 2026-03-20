import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

PRE_CLEANUP_LABEL = "PRE_CLEANUP"
POST_CLEANUP_LABEL = "POST_CLEANUP"


class GmailService:
    def __init__(self, resource: Resource):
        self._resource = resource
        self._label_id_cache: dict[str, str] = {}

    def _list_labels(self) -> list[dict]:
        results = self._resource.users().labels().list(userId="me").execute()
        return results.get("labels", [])

    def list_messages(
        self, *, query: str | None = None, label_ids: list[str] | None = None
    ) -> list[dict]:
        response = (
            self._resource.users()
            .messages()
            .list(userId="me", q=query, labelIds=label_ids)
            .execute()
        )
        return response.get("messages", [])

    def get_message(
        self, message_id: str, *, format: str | None = None, fields: str | None = None
    ) -> dict:
        return (
            self._resource.users()
            .messages()
            .get(userId="me", id=message_id, format=format, fields=fields)
            .execute()
        )

    def add_label_to_message(self, message_id: str, label_id: str) -> None:
        self._resource.users().messages().batchModify(
            userId="me", body={"ids": [message_id], "addLabelIds": [label_id]}
        ).execute()

    def insert_message(
        self, message_body: dict, *, internal_date_source: str = "dateHeader"
    ) -> dict:
        return (
            self._resource.users()
            .messages()
            .insert(
                userId="me",
                body=message_body,
                internalDateSource=internal_date_source,
            )
            .execute()
        )

    def trash_message(self, message_id: str) -> None:
        self._resource.users().messages().trash(userId="me", id=message_id).execute()

    def get_or_create_label(self, label_name: str) -> str:
        """Return the specified label ID, creating the label if it does not exist."""
        if label_name in self._label_id_cache:
            return self._label_id_cache[label_name]

        for label in self._list_labels():
            if label["name"] == label_name:
                label_id = label["id"]
                self._label_id_cache[label_name] = label_id
                return label_id

        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created_label = (
            self._resource.users()
            .labels()
            .create(userId="me", body=label_body)
            .execute()
        )
        label_id = created_label["id"]
        self._label_id_cache[label_name] = label_id
        return label_id

    def get_pre_cleanup_label_id(self) -> str:
        return self.get_or_create_label(PRE_CLEANUP_LABEL)

    def get_post_cleanup_label_id(self) -> str:
        return self.get_or_create_label(POST_CLEANUP_LABEL)


def get_gmail_service() -> GmailService:
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
    return GmailService(build("gmail", "v1", credentials=creds))
