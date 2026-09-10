"""Canonical login numbers: Indian mobile numbers or explicit international numbers."""

import re


def normalize_phone(value):
    value = value.strip()
    if not value:
        return ""
    if not re.fullmatch(r"[+0-9 ()-]+", value):
        raise ValueError("Enter a valid mobile number, including country code outside India.")
    compact = re.sub(r"[ ()-]", "", value)
    if re.fullmatch(r"[6-9][0-9]{9}", compact):
        return "+91" + compact
    if re.fullmatch(r"91[6-9][0-9]{9}", compact):
        return "+" + compact
    if re.fullmatch(r"\+[1-9][0-9]{7,14}", compact):
        if compact.startswith("+91") and not re.fullmatch(r"\+91[6-9][0-9]{9}", compact):
            raise ValueError("Enter a valid 10-digit Indian mobile number.")
        return compact
    raise ValueError("Enter a valid mobile number, including country code outside India.")
