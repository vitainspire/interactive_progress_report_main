import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
