"""
Admin API routes package.

Tất cả admin/CMS endpoints được tổ chức trong package này.
"""

# Re-export routers for easy import in main
from . import news, assets, push

__all__ = ["news", "assets", "push"]

