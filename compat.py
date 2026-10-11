"""Red-cell blood group compatibility."""
BLOOD_GROUPS = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]

# recipient -> donor groups whose red cells they can safely receive
_CAN_RECEIVE_FROM = {
    "O-":  ["O-"],
    "O+":  ["O+", "O-"],
    "A-":  ["A-", "O-"],
    "A+":  ["A+", "A-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}


def compatible_donor_groups(recipient_group: str) -> list[str]:
    return list(_CAN_RECEIVE_FROM[recipient_group])


def can_donate_to(donor_group: str, recipient_group: str) -> bool:
    return donor_group in _CAN_RECEIVE_FROM[recipient_group]
