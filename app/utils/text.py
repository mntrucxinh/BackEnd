from __future__ import annotations

import re
import unicodedata


def _remove_vietnamese_accents(text: str) -> str:
    """
    Chuyển đổi ký tự tiếng Việt có dấu thành không dấu.
    Ví dụ: "Những khoảnh khắc đáng nhớ năm học 2024-2025" -> "nhung-khoanh-khac-dang-nho-nam-hoc-2024-2025"
    """
    # Mapping cho các ký tự tiếng Việt đặc biệt
    vietnamese_map = {
        'à': 'a', 'á': 'a', 'ạ': 'a', 'ả': 'a', 'ã': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ậ': 'a', 'ẩ': 'a', 'ẫ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ặ': 'a', 'ẳ': 'a', 'ẵ': 'a',
        'è': 'e', 'é': 'e', 'ẹ': 'e', 'ẻ': 'e', 'ẽ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ệ': 'e', 'ể': 'e', 'ễ': 'e',
        'ì': 'i', 'í': 'i', 'ị': 'i', 'ỉ': 'i', 'ĩ': 'i',
        'ò': 'o', 'ó': 'o', 'ọ': 'o', 'ỏ': 'o', 'õ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ộ': 'o', 'ổ': 'o', 'ỗ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ợ': 'o', 'ở': 'o', 'ỡ': 'o',
        'ù': 'u', 'ú': 'u', 'ụ': 'u', 'ủ': 'u', 'ũ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ự': 'u', 'ử': 'u', 'ữ': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỵ': 'y', 'ỷ': 'y', 'ỹ': 'y',
        'đ': 'd',
        'À': 'a', 'Á': 'a', 'Ạ': 'a', 'Ả': 'a', 'Ã': 'a',
        'Â': 'a', 'Ầ': 'a', 'Ấ': 'a', 'Ậ': 'a', 'Ẩ': 'a', 'Ẫ': 'a',
        'Ă': 'a', 'Ằ': 'a', 'Ắ': 'a', 'Ặ': 'a', 'Ẳ': 'a', 'Ẵ': 'a',
        'È': 'e', 'É': 'e', 'Ẹ': 'e', 'Ẻ': 'e', 'Ẽ': 'e',
        'Ê': 'e', 'Ề': 'e', 'Ế': 'e', 'Ệ': 'e', 'Ể': 'e', 'Ễ': 'e',
        'Ì': 'i', 'Í': 'i', 'Ị': 'i', 'Ỉ': 'i', 'Ĩ': 'i',
        'Ò': 'o', 'Ó': 'o', 'Ọ': 'o', 'Ỏ': 'o', 'Õ': 'o',
        'Ô': 'o', 'Ồ': 'o', 'Ố': 'o', 'Ộ': 'o', 'Ổ': 'o', 'Ỗ': 'o',
        'Ơ': 'o', 'Ờ': 'o', 'Ớ': 'o', 'Ợ': 'o', 'Ở': 'o', 'Ỡ': 'o',
        'Ù': 'u', 'Ú': 'u', 'Ụ': 'u', 'Ủ': 'u', 'Ũ': 'u',
        'Ư': 'u', 'Ừ': 'u', 'Ứ': 'u', 'Ự': 'u', 'Ử': 'u', 'Ữ': 'u',
        'Ỳ': 'y', 'Ý': 'y', 'Ỵ': 'y', 'Ỷ': 'y', 'Ỹ': 'y',
        'Đ': 'd',
    }
    
    result = []
    for char in text:
        if char in vietnamese_map:
            result.append(vietnamese_map[char])
        else:
            # Dùng NFD (Normalization Form Decomposed) để tách dấu
            nfd_char = unicodedata.normalize('NFD', char)
            # Loại bỏ các ký tự combining (dấu)
            no_accent = ''.join(c for c in nfd_char if unicodedata.category(c) != 'Mn')
            result.append(no_accent)
    return ''.join(result)


def slugify(value: str) -> str:
    """
    Sinh slug từ một chuỗi tiếng Việt:
    - Chuyển đổi ký tự tiếng Việt có dấu thành không dấu
    - Lowercase
    - Thay khoảng trắng/underscore/ký tự đặc biệt bằng '-'
    - Loại bỏ ký tự không hợp lệ
    - Gộp nhiều '-' liên tiếp và strip đầu/cuối
    
    Ví dụ: "Những khoảnh khắc đáng nhớ năm học 2024-2025" 
    -> "nhung-khoanh-khac-dang-nho-nam-hoc-2024-2025"
    """
    if not value:
        return ""
    
    # Chuyển đổi tiếng Việt có dấu thành không dấu
    value = _remove_vietnamese_accents(value)
    
    # Lowercase
    value = value.strip().lower()
    
    # Thay khoảng trắng, underscore, và các ký tự đặc biệt bằng '-'
    value = re.sub(r"[\s_\.\,\!\?\:\;\(\)\[\]\{\}\"\'\/\\]+", "-", value)
    
    # Loại bỏ ký tự không phải a-z, 0-9, '-'
    value = re.sub(r"[^a-z0-9-]+", "", value)
    
    # Gộp nhiều '-' liên tiếp thành một '-'
    value = re.sub(r"-{2,}", "-", value)
    
    # Strip '-' ở đầu và cuối
    return value.strip("-")


