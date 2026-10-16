"""Mail failures that are safe to explain. Exception text stays on the server."""


class MailFailure(Exception):
    def __init__(
        self,
        code: str,
        *,
        accepted: list[str] | None = None,
        refused: list[str] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.accepted = list(accepted or [])
        self.refused = list(refused or [])


PUBLIC_MESSAGES = {
    "auth": (
        "The mailbox could not be connected. The InMotion mailbox password "
        "may differ from the AMAFH Core password."
    ),
    "tls": "The mail service connection could not be secured.",
    "timeout": "The mail service did not respond in time. Try again.",
    "unavailable": "The mail service is unavailable. Try again.",
    "key": "Mailbox connection is unavailable until the encryption key is configured.",
    "folder": "That folder is not available in this mailbox.",
    "missing": "The message is not available in this mailbox.",
    "refused": "The mail server refused the message.",
    "partial": (
        "The mail server accepted some recipients and refused others. "
        "Accepted recipients were not sent the message again. "
        "Acceptance is not proof of delivery."
    ),
    "unknown": (
        "The connection ended before the mail server accepted the message. It was not sent again."
    ),
    "too_large": "The message exceeds the outgoing size limit.",
    "append": "The mailbox folder could not store the message.",
    "reconnect": "Connect the mailbox again. The AMAFH Core password was not changed.",
    "address": "An Official/Login email is required before connecting a mailbox.",
    "expired": "That attachment has expired. Add it again.",
    "ownership": "That mailbox item is not available for this account.",
}
