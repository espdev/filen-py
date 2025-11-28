from typing import Final
from secrets import token_bytes, token_hex

B64_CHARSET: Final = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
B64_CHARSET_LENGTH: Final = len(B64_CHARSET)


def generate_random_bytes(nbytes: int) -> bytes:
    return token_bytes(nbytes)


def generate_random_hex_string(nbytes: int) -> str:
    return token_hex(nbytes)


def generate_random_string(length: int) -> str:
    """Generate random string with given size

    This guarantees that the length of the string will be equal to the size in bytes,
    but there is a loss of entropy.

    This is used in metadata encryption v2 and public link v2.
    """

    return ''.join(B64_CHARSET[b % B64_CHARSET_LENGTH] for b in token_bytes(length))
