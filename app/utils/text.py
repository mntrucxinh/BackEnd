from __future__ import annotations

import re


def slugify(value: str) -> str:
    """
    Sinh slug đơn giản từ một chuỗi:
    - Lowercase
    - Thay khoảng trắng/underscore bằng '-'
    - Loại bỏ ký tự không phải a-z, 0-9, '-'
    - Gộp nhiều '-' liên tiếp và strip đầu/cuối
    """
    value = value.strip().lower()
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"[^a-z0-9-]+", "", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


