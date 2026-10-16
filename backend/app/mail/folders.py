"""Map server folders by metadata first, then by a known name. Never create folders."""

SPECIAL_USE = {
    "\\Inbox": "inbox",
    "\\Drafts": "drafts",
    "\\Sent": "sent",
    "\\Junk": "spam",
    "\\Archive": "archive",
}
NAME_ROLES = {
    "inbox": "inbox",
    "drafts": "drafts",
    "draft": "drafts",
    "sent": "sent",
    "sent items": "sent",
    "sent mail": "sent",
    "junk": "spam",
    "junk mail": "spam",
    "spam": "spam",
    "bulk mail": "spam",
    "archive": "archive",
    "archives": "archive",
}
ROLES = ("inbox", "drafts", "sent", "spam", "archive")


def assign_roles(folders: list[tuple[set[str], str]]) -> dict[str, str]:
    """Return one mailbox name per role. Special-use wins over a duplicate name."""
    chosen: dict[str, str] = {}
    named: dict[str, str] = {}
    for flags, name in folders:
        if not name or "\\Noselect" in flags:
            continue
        special = next((SPECIAL_USE[flag] for flag in flags if flag in SPECIAL_USE), None)
        if special and special not in chosen:
            chosen[special] = name
            continue
        fallback = NAME_ROLES.get(name.casefold())
        if fallback and fallback not in named:
            named[fallback] = name
    for role, name in named.items():
        chosen.setdefault(role, name)
    return chosen
