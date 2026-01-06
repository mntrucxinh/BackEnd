"""
Facebook Graph API integration service.

Handles:
- Video uploads to Facebook Pages
- Image uploads to Facebook Pages
- Post publishing with media attachments
- Permission validation for Facebook tokens
"""
from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from app.models.tables import Asset, Post

logger = logging.getLogger(__name__)

# Facebook API configuration
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
FB_API_VERSION = os.getenv("FB_API_VERSION", "v19.0")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://your-site.com")


def _format_facebook_message(
    post: Post,
    post_url: Optional[str] = None,
    include_link_in_text: bool = False,
    max_length: int = 5000
) -> str:
    """
    Format message cho Facebook post - đơn giản như Facebook UI (1 input).
    
    Chỉ dùng content_html (strip HTML) để đăng lên Facebook.
    Giống như người dùng gõ vào "What's on your mind?" trên Facebook.
    
    Args:
        post: Post object
        post_url: Post URL (optional)
        include_link_in_text: Có thêm link vào text không (thường False, dùng link preview)
        max_length: Giới hạn độ dài message
        
    Returns:
        Formatted message string
    """
    import re
    
    # Chỉ dùng content_html (strip HTML tags)
    message = ""
    if post.content_html and post.content_html.strip():
        # Strip HTML tags
        text_content = re.sub(r'<[^>]+>', '', post.content_html)
        # Clean up whitespace (nhiều space → 1 space, newlines → space)
        text_content = re.sub(r'\s+', ' ', text_content).strip()
        
        if text_content:
            message = text_content
    
    # Nếu không có content_html, dùng title làm fallback
    if not message and post.title and post.title.strip():
        message = post.title.strip()
    
    # Thêm link vào message text nếu cần (thường không cần vì có link preview)
    if include_link_in_text and post_url and message:
        message += f"\n\n🔗 {post_url}"
    elif include_link_in_text and post_url:
        message = f"🔗 {post_url}"
    
    # Cắt nếu quá dài
    if len(message) > max_length:
        message = message[:max_length - 3] + "..."
    
    return message


def check_facebook_permissions(access_token: Optional[str] = None) -> dict:
    """
    Validate Facebook access token permissions.
    
    Page Access Tokens have permissions pre-granted and typically return
    empty permissions array. User Access Tokens require explicit permission checks.
    
    Args:
        access_token: Token to validate (defaults to FB_ACCESS_TOKEN from env)
        
    Returns:
        Dict with keys:
            - valid: bool - Whether token has required permissions
            - permissions: list[str] - Granted permissions
            - missing_permissions: list[str] - Required but missing permissions
            - error: Optional[str] - Error message if validation failed
    """
    token = access_token or FB_ACCESS_TOKEN
    if not token:
        return {
            "valid": False,
            "permissions": [],
            "missing_permissions": ["pages_manage_posts"],
            "error": "Token không được set",
        }
    
    try:
        # Check token validity và xác định loại token
        url = f"https://graph.facebook.com/{FB_API_VERSION}/me"
        params = {"access_token": token, "fields": "id,name"}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_data = response.json().get("error", {})
            return {
                "valid": False,
                "permissions": [],
                "missing_permissions": ["pages_manage_posts"],
                "error": f"Token không hợp lệ: {error_data.get('message', response.status_code)}",
            }
        
        # Token hợp lệ - check permissions
        # Với Page Access Token: /me/permissions thường trả về empty array
        # Với User Access Token: /me/permissions trả về danh sách permissions
        required_permissions = ["pages_manage_posts", "pages_read_engagement"]
        perm_url = f"https://graph.facebook.com/{FB_API_VERSION}/me/permissions"
        perm_response = requests.get(perm_url, params={"access_token": token}, timeout=10)
        
        if perm_response.status_code != 200:
            # Nếu không check được permissions nhưng token hợp lệ → có thể là Page token
            # Cho phép tiếp tục, Facebook API sẽ validate khi thực sự đăng bài
            logger.warning(
                "Could not check permissions, but token is valid. Proceeding...",
                extra={"action": "check_permissions", "status_code": perm_response.status_code}
            )
            return {
                "valid": True,
                "permissions": [],
                "missing_permissions": [],
                "error": None,
            }
        
        data = perm_response.json().get("data", [])
        
        # Nếu permissions array rỗng → đây là Page token (Page token không trả về permissions qua API này)
        if not data:
            logger.info(
                "Detected Page Access Token (permissions already granted)",
                extra={"action": "check_permissions", "token_type": "page"}
            )
            return {
                "valid": True,
                "permissions": ["pages_manage_posts", "pages_read_engagement"],  # Page token có sẵn
                "missing_permissions": [],
                "error": None,
            }
        
        # Nếu có permissions data → đây là User token → check từng permission
        granted_permissions = [
            perm["permission"] for perm in data if perm.get("status") == "granted"
        ]
        
        missing = [p for p in required_permissions if p not in granted_permissions]
        
        return {
            "valid": len(missing) == 0,
            "permissions": granted_permissions,
            "missing_permissions": missing,
            "error": None if len(missing) == 0 else f"Thiếu permissions: {', '.join(missing)}",
        }
    except Exception as e:
        logger.error(
            "Error checking Facebook permissions",
            extra={"action": "check_permissions", "error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        # Nếu có lỗi nhưng token đã test thành công trước đó → có thể là Page token
        # Cho phép tiếp tục và để Facebook API trả lỗi nếu thực sự thiếu quyền
        logger.warning(
            "Could not verify permissions, but will proceed (may be Page token)",
            extra={"action": "check_permissions"}
        )
        return {
            "valid": True,  # Cho phép thử, để Facebook API validate
            "permissions": [],
            "missing_permissions": [],
            "error": None,
        }


def upload_video_to_facebook(
    post: Post,
    video_asset: Asset,
    post_url: str,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> str:
    """
    Upload video file to Facebook Page.
    
    Validates file size (max 1GB), format, and permissions before uploading.
    Creates a video post with description and link to the article.
    
    Args:
        post: Post object containing article metadata
        video_asset: Asset object containing video file information
        post_url: Full URL to the article on website
        page_id: Facebook Page ID (nếu None → dùng từ env)
        access_token: Facebook Access Token (nếu None → dùng từ env)
        
    Returns:
        Facebook video/post ID
        
    Raises:
        ValueError: If validation fails or Facebook API returns error
        FileNotFoundError: If video file does not exist on server
    """
    # Ưu tiên dùng token từ User, fallback về env
    fb_page_id = page_id or FB_PAGE_ID
    fb_token = access_token or FB_ACCESS_TOKEN
    
    if not fb_page_id or not fb_token:
        raise ValueError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set (from user or environment)")
    
    # Kiểm tra permissions trước khi upload
    perm_check = check_facebook_permissions(fb_token)
    if not perm_check["valid"]:
        missing = ", ".join(perm_check["missing_permissions"])
        raise ValueError(
            f"Token Facebook thiếu quyền: {missing}. "
            f"Vui lòng tạo token mới với đầy đủ quyền:\n"
            f"- pages_manage_posts\n"
            f"- pages_read_engagement\n\n"
            f"Cách fix:\n"
            f"1. Vào https://developers.facebook.com/tools/explorer/\n"
            f"2. Chọn Page (không phải User)\n"
            f"3. Chọn permissions: pages_manage_posts, pages_read_engagement\n"
            f"4. Generate token mới\n"
            f"5. Update FB_ACCESS_TOKEN trong .env"
        )
    
    # Lấy đường dẫn file video - dùng cùng logic với asset_service
    upload_dir_env = os.getenv("UPLOAD_DIR")
    if upload_dir_env:
        upload_dir = Path(upload_dir_env)
    else:
        # Relative path cho local development
        upload_dir = Path("uploads")
    video_path = upload_dir / video_asset.url.lstrip("/uploads/")
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Validate video file
    file_size = video_path.stat().st_size
    max_size = 1024 * 1024 * 1024  # 1GB (Facebook limit)
    if file_size > max_size:
        raise ValueError(
            f"Video quá lớn ({file_size / (1024*1024):.1f}MB). "
            f"Facebook giới hạn {max_size / (1024*1024*1024):.0f}GB."
        )
    
    # Kiểm tra format video (Facebook hỗ trợ: mp4, mov, avi, mkv)
    valid_formats = ['.mp4', '.mov', '.avi', '.mkv']
    video_ext = video_path.suffix.lower()
    if video_ext not in valid_formats:
        logger.warning(
            "Video format may not be well supported",
            extra={
                "action": "upload_video",
                "post_id": post.id,
                "format": video_ext,
                "recommended_formats": valid_formats,
            }
        )
    
    # Tạo description cho video
    # Video description có thể dài hơn (5000 ký tự), và nên có link
    description = _format_facebook_message(
        post=post,
        post_url=post_url,
        include_link_in_text=True,
        max_length=5000
    )
    
    # Title (giới hạn 255 ký tự)
    title = (post.title or "")[:255]
    
    # Log thông tin upload
    log_context = {
        "action": "upload_video",
        "post_id": post.id,
        "post_slug": post.slug,
        "page_id": fb_page_id,
        "video_file": video_path.name,
        "video_size_mb": round(file_size / (1024*1024), 2),
        "video_format": video_ext,
        "api_version": FB_API_VERSION,
    }
    
    logger.info("Starting video upload to Facebook", extra=log_context)
    
    # Upload video lên Facebook
    try:
        with open(video_path, 'rb') as video_file:
            files = {'file': video_file}
            data = {
                'access_token': fb_token,
                'description': description,
                'title': title,
            }
            
            response = requests.post(
                f"https://graph-video.facebook.com/{FB_API_VERSION}/{fb_page_id}/videos",
                files=files,
                data=data,
                timeout=600,  # 10 phút cho video lớn
            )
        
        # Xử lý lỗi chi tiết từ Facebook
        if response.status_code != 200:
            error_detail = response.text
            error_code = ""
            error_type = ""
            error_subcode = ""
            
            try:
                error_json = response.json()
                fb_error = error_json.get("error", {})
                error_detail = fb_error.get("message", error_detail)
                error_code = fb_error.get("code", "")
                error_type = fb_error.get("type", "")
                error_subcode = fb_error.get("error_subcode", "")
                
                # Log chi tiết
                logger.error(
                    "Facebook video upload failed",
                    extra={
                        **log_context,
                        "error_code": error_code,
                        "error_type": error_type,
                        "error_subcode": error_subcode,
                        "error_message": error_detail,
                        "http_status": response.status_code,
                    }
                )
                
            except Exception:
                logger.error(
                    "Facebook API error (could not parse error details)",
                    extra={**log_context, "http_status": response.status_code, "raw_error": error_detail}
                )
            
            # Tạo error message chi tiết với hướng dẫn
            error_message = f"Facebook API Error {response.status_code}: {error_detail}"
            
            if error_code == 190:  # Invalid OAuth access token
                error_message = (
                    "Token Facebook không hợp lệ hoặc đã hết hạn. "
                    "Vui lòng tạo token mới từ Facebook Graph API Explorer."
                )
            elif error_code == 100:  # Invalid parameter
                if "No permission to publish" in error_detail or "permission" in error_detail.lower():
                    error_message = (
                        "Token không có quyền publish video lên Facebook Page. "
                        "Cần các permissions sau:\n"
                        "- pages_manage_posts\n"
                        "- pages_read_engagement\n"
                        "- pages_show_list\n\n"
                        "Cách fix:\n"
                        "1. Vào https://developers.facebook.com/tools/explorer/\n"
                        "2. Chọn Page (không phải User)\n"
                        "3. Chọn đầy đủ permissions trên\n"
                        "4. Generate token mới\n"
                        "5. Update FB_ACCESS_TOKEN trong .env"
                    )
                elif error_subcode == 1363030:  # Video format not supported
                    error_message = (
                        f"Format video không được hỗ trợ: {video_ext}. "
                        f"Facebook hỗ trợ: {', '.join(valid_formats)}"
                    )
                elif error_subcode == 1363019:  # Video too large
                    error_message = (
                        f"Video quá lớn ({file_size / (1024*1024):.1f}MB). "
                        f"Facebook giới hạn 1GB. Vui lòng nén video nhỏ hơn."
                    )
                else:
                    error_message = f"Tham số không hợp lệ: {error_detail} (Code: {error_code}, Subcode: {error_subcode})"
            elif error_code == 200:  # Permissions error
                error_message = (
                    "Token không có quyền upload video. "
                    "Cần permission: pages_manage_posts. "
                    "Vui lòng tạo token mới với đầy đủ quyền."
                )
            
            raise ValueError(error_message)
        
        result = response.json()
        video_id = result.get("id")
        
        if not video_id:
            logger.error(
                "Facebook did not return video ID",
                extra={**log_context, "response": result}
            )
            raise ValueError(f"Facebook không trả về video ID. Response: {result}")
        
        logger.info(
            "Video uploaded to Facebook successfully",
            extra={**log_context, "facebook_video_id": video_id}
        )
        return video_id
        
    except ValueError:
        # Re-raise ValueError (đã được format)
        raise
    except requests.exceptions.RequestException as e:
        logger.error(
            "Request error when uploading video to Facebook",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        raise ValueError(f"Lỗi kết nối khi upload video: {str(e)}")
    except Exception as e:
        logger.error(
            "Unexpected error when uploading video to Facebook",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        raise ValueError(f"Lỗi không xác định khi upload video: {str(e)}")


def upload_images_to_facebook(
    post: Post,
    post_url: str,
    content_assets: Optional[list[Asset]] = None,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> str:
    """
    Upload images and publish post to Facebook Page.
    
    Used when post has no video. Supports up to 10 images (Facebook limit).
    Creates a post with image carousel or single image attachment.
    
    Args:
        post: Post object containing article metadata
        post_url: Full URL to the article on website
        content_assets: List of image assets to upload (max 10)
        page_id: Facebook Page ID (nếu None → dùng từ env)
        access_token: Facebook Access Token (nếu None → dùng từ env)
        
    Returns:
        Facebook post ID
        
    Raises:
        requests.exceptions.HTTPError: If Facebook API returns error
    """
    # Ưu tiên dùng token từ User, fallback về env
    fb_page_id = page_id or FB_PAGE_ID
    fb_token = access_token or FB_ACCESS_TOKEN
    
    if not fb_page_id or not fb_token:
        raise ValueError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set (from user or environment)")
    
    # Thu thập tất cả ảnh
    all_images = content_assets or []
    
    # Upload ảnh lên Facebook
    photo_ids = []
    # Dùng cùng logic với asset_service
    upload_dir_env = os.getenv("UPLOAD_DIR")
    if upload_dir_env:
        upload_dir = Path(upload_dir_env)
    else:
        # Relative path cho local development
        upload_dir = Path("uploads")
    
    for asset in all_images[:10]:  # Facebook cho phép tối đa 10 ảnh
        if not asset or not asset.url:
            continue
        
        try:
            # Thử upload từ file trước (hỗ trợ localhost)
            image_path = upload_dir / asset.url.lstrip("/uploads/")
            
            logger.debug(
                "Checking image file for Facebook upload",
                extra={
                    "action": "upload_images",
                    "post_id": post.id,
                    "asset_id": asset.id,
                    "asset_url": asset.url,
                    "image_path": str(image_path),
                    "path_exists": image_path.exists(),
                    "upload_dir": str(upload_dir),
                }
            )
            
            if image_path.exists():
                # Upload từ file (tốt hơn cho localhost)
                with open(image_path, 'rb') as image_file:
                    files = {'file': image_file}
                    data = {
                        "access_token": fb_token,
                        "published": False,
                    }
                    photo_response = requests.post(
                        f"https://graph.facebook.com/{FB_API_VERSION}/{fb_page_id}/photos",
                        files=files,
                        data=data,
                        timeout=30,
                    )
                    photo_response.raise_for_status()
                    photo_id = photo_response.json().get("id")
                    if photo_id:
                        photo_ids.append({"media_fbid": photo_id})
                        logger.debug(
                            "Image uploaded to Facebook from file",
                            extra={
                                "action": "upload_images",
                                "post_id": post.id,
                                "asset_id": asset.id,
                                "facebook_photo_id": photo_id,
                                "source": "file",
                            }
                        )
            else:
                # Fallback: upload từ URL (chỉ khi không phải localhost)
                image_url = f"{APP_BASE_URL}{asset.url}"
                
                if "localhost" in image_url or "127.0.0.1" in image_url:
                    logger.warning(f"Skipping localhost image {image_url} (file not found: {image_path})")
                    continue
                
                photo_response = requests.post(
                    f"https://graph.facebook.com/{FB_API_VERSION}/{fb_page_id}/photos",
                    params={
                        "access_token": fb_token,
                        "url": image_url,
                        "published": False,
                    },
                    timeout=30,
                )
                photo_response.raise_for_status()
                photo_id = photo_response.json().get("id")
                if photo_id:
                    photo_ids.append({"media_fbid": photo_id})
                    logger.debug(
                        "Image uploaded to Facebook from URL",
                        extra={
                            "action": "upload_images",
                            "post_id": post.id,
                            "asset_id": asset.id,
                            "facebook_photo_id": photo_id,
                            "source": "url",
                        }
                    )
                    
        except Exception as e:
            logger.warning(
                "Failed to upload image to Facebook",
                extra={
                    "action": "upload_images",
                    "post_id": post.id,
                    "asset_id": asset.id,
                    "asset_url": asset.url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            continue
    
    # Kiểm tra xem URL có phải localhost không (Facebook không thể truy cập)
    is_localhost = "localhost" in post_url or "127.0.0.1" in post_url
    
    # Tạo message
    # Với ảnh: không thêm link vào text (Facebook tự tạo link preview khi có params["link"])
    # Không có ảnh: có thể thêm link vào text nếu cần
    # Note: Facebook sẽ tự crawl Open Graph tags (og:title, og:description) từ link
    # nên message không cần duplicate nội dung
    include_link_in_text = not is_localhost and len(photo_ids) == 0
    message = _format_facebook_message(
        post=post,
        post_url=post_url if not is_localhost else None,
        include_link_in_text=include_link_in_text,
        max_length=5000
    )
    
    # Đăng bài với ảnh
    params = {
        "access_token": fb_token,
    }
    
    # Chỉ thêm message nếu có nội dung
    if message.strip():
        params["message"] = message
    
    # Thêm media hoặc link
    if len(photo_ids) > 1:
        # Nhiều ảnh → Carousel
        params["attached_media"] = json.dumps(photo_ids)
        # Thêm link để có preview đẹp bên dưới carousel
        if not is_localhost:
            params["link"] = post_url
    elif len(photo_ids) == 1:
        # 1 ảnh → Ảnh lớn
        params["attached_media"] = json.dumps(photo_ids)
        # Thêm link để có preview đẹp bên dưới ảnh
        if not is_localhost:
            params["link"] = post_url
    else:
        # Không có ảnh → chỉ có text/link
        if not is_localhost:
            # Thêm link để Facebook tạo preview đẹp
            params["link"] = post_url
        # Nếu là localhost và không có ảnh, chỉ đăng message (không có link)
    
    log_context = {
        "action": "upload_images",
        "post_id": post.id,
        "post_slug": post.slug,
        "page_id": fb_page_id,
        "image_count": len(photo_ids),
        "has_message": bool(message.strip()),
    }
    
    logger.info("Publishing post to Facebook", extra=log_context)
    
    response = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{fb_page_id}/feed",
        params=params,
        timeout=30,
    )
    
    # Kiểm tra lỗi chi tiết từ Facebook
    if response.status_code != 200:
        error_detail = response.text
        error_code = ""
        error_type = ""
        try:
            error_json = response.json()
            fb_error = error_json.get("error", {})
            error_detail = fb_error.get("message", error_detail)
            error_code = fb_error.get("code", "")
            error_type = fb_error.get("type", "")
            logger.error(
                "Facebook API error when publishing post",
                extra={
                    **log_context,
                    "error_code": error_code,
                    "error_type": error_type,
                    "error_message": error_detail,
                    "http_status": response.status_code,
                    "request_url": str(response.url),
                }
            )
        except Exception:
            logger.error(
                "Facebook API error (could not parse error details)",
                extra={**log_context, "http_status": response.status_code, "raw_error": error_detail}
            )
        
        raise requests.exceptions.HTTPError(
            f"Facebook API Error {response.status_code}: {error_detail}"
        )
    
    result = response.json()
    fb_post_id = result.get("id")
    
    logger.info(
        "Post published to Facebook successfully",
        extra={**log_context, "facebook_post_id": fb_post_id}
    )
    
    return fb_post_id


def delete_facebook_post(
    fb_post_id: str,
    page_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> bool:
    """
    Xóa post trên Facebook.
    
    Args:
        fb_post_id: Facebook post ID cần xóa
        page_id: Facebook Page ID (nếu None thì dùng FB_PAGE_ID từ env)
        access_token: Facebook access token (nếu None thì dùng FB_ACCESS_TOKEN từ env)
        
    Returns:
        True nếu xóa thành công, False nếu không tìm thấy hoặc đã bị xóa
    """
    fb_page_id = page_id or FB_PAGE_ID
    fb_token = access_token or FB_ACCESS_TOKEN
    
    if not fb_page_id or not fb_token:
        logger.warning(
            "Cannot delete Facebook post: missing page_id or access_token",
            extra={"fb_post_id": fb_post_id}
        )
        return False
    
    log_context = {
        "action": "delete_facebook_post",
        "fb_post_id": fb_post_id,
        "page_id": fb_page_id,
    }
    
    try:
        # Facebook API: DELETE /{post-id}
        response = requests.delete(
            f"https://graph.facebook.com/{FB_API_VERSION}/{fb_post_id}",
            params={
                "access_token": fb_token,
            },
            timeout=30,
        )
        
        if response.status_code == 200:
            result = response.json()
            success = result.get("success", False)
            if success:
                logger.info(
                    "Facebook post deleted successfully",
                    extra={**log_context}
                )
                return True
            else:
                logger.warning(
                    "Facebook API returned success=false",
                    extra={**log_context, "response": result}
                )
                return False
        elif response.status_code == 404:
            # Post đã bị xóa hoặc không tồn tại
            logger.info(
                "Facebook post not found (already deleted?)",
                extra={**log_context}
            )
            return False
        else:
            error_detail = response.text
            try:
                error_json = response.json()
                fb_error = error_json.get("error", {})
                error_detail = fb_error.get("message", error_detail)
                error_code = fb_error.get("code", "")
                logger.error(
                    "Facebook API error when deleting post",
                    extra={
                        **log_context,
                        "error_code": error_code,
                        "error_message": error_detail,
                        "http_status": response.status_code,
                    }
                )
            except Exception:
                logger.error(
                    "Facebook API error (could not parse error details)",
                    extra={**log_context, "http_status": response.status_code, "raw_error": error_detail}
                )
            return False
            
    except Exception as e:
        logger.error(
            "Failed to delete Facebook post",
            extra={**log_context, "error": str(e), "error_type": type(e).__name__},
            exc_info=True
        )
        return False


# ============================================================================
# Facebook Token Management Functions
# ============================================================================

def exchange_long_lived_token(short_lived_token: str) -> dict:
    """
    Exchange Short-lived User Token → Long-lived User Token (60 days).
    
    Args:
        short_lived_token: Short-lived token từ Facebook OAuth
        
    Returns:
        Dict: { access_token, expires_in (seconds) }
        
    Raises:
        ValueError: Nếu không exchange được token
    """
    if not FB_APP_ID or not FB_APP_SECRET:
        raise ValueError("FB_APP_ID and FB_APP_SECRET must be set in environment")
    
    url = f"https://graph.facebook.com/{FB_API_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_lived_token,
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_data = response.json().get("error", {})
            raise ValueError(
                f"Không exchange được token: {error_data.get('message', 'Unknown error')}"
            )
        
        data = response.json()
        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 5184000),  # 60 days default
        }
    except requests.RequestException as e:
        raise ValueError(f"Lỗi khi gọi Facebook API: {e}")


def get_page_token_from_user_token(user_access_token: str) -> dict:
    """
    Lấy Page Access Token từ Long-lived User Token.
    
    Args:
        user_access_token: Long-lived User Access Token
        
    Returns:
        Dict: { page_id, access_token, name, expires_at }
        
    Raises:
        ValueError: Nếu không lấy được Pages hoặc thiếu quyền
    """
    url = f"https://graph.facebook.com/{FB_API_VERSION}/me/accounts"
    params = {
        "access_token": user_access_token,
        "fields": "id,name,access_token,tasks"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_data = response.json().get("error", {})
            raise ValueError(
                f"Không lấy được Pages: {error_data.get('message', 'Unknown error')}"
            )
        
        pages = response.json().get("data", [])
        if not pages:
            raise ValueError("User không quản lý Page nào")
        
        # Lấy Page đầu tiên
        page = pages[0]
        
        # Check permissions
        required_tasks = ["MANAGE", "CREATE_CONTENT"]
        page_tasks = page.get("tasks", [])
        if not all(task in page_tasks for task in required_tasks):
            raise ValueError(
                f"Page không có đủ quyền. Cần: {required_tasks}, có: {page_tasks}"
            )
        
        page_token = page.get("access_token")
        if not page_token:
            raise ValueError("Page không có access_token")
        
        return {
            "page_id": page["id"],
            "access_token": page_token,
            "name": page.get("name"),
            "expires_at": None,  # Page token thường không hết hạn nếu từ long-lived user token
        }
    except requests.RequestException as e:
        raise ValueError(f"Lỗi khi gọi Facebook API: {e}")


def refresh_facebook_page_token(db, user) -> tuple[str, str]:
    """
    Tự động refresh Facebook Page Token.
    
    Flow:
    1. Check Page Token còn hạn không?
    2. Nếu hết hạn → Dùng Long-lived User Token để lấy Page Token mới
    3. Update vào DB
    
    Args:
        db: Database session
        user: User object
        
    Returns:
        Tuple (page_id, access_token)
        
    Raises:
        ValueError: Nếu không thể refresh
    """
    from sqlalchemy.orm import Session
    
    now = datetime.now(timezone.utc)
    
    # Check Page Token còn hạn không?
    if user.facebook_access_token:
        if user.facebook_token_expires_at is None:
            # Long-lived Page Token (không hết hạn)
            return user.facebook_page_id, user.facebook_access_token
        elif user.facebook_token_expires_at > now:
            # Page Token còn hạn
            return user.facebook_page_id, user.facebook_access_token
    
    # Page Token hết hạn → Cần refresh
    
    # Check Long-lived User Token còn hạn không?
    if not user.facebook_user_access_token:
        raise ValueError(
            "Chưa có Long-lived User Token. "
            "Vui lòng đăng nhập lại Facebook để liên kết."
        )
    
    # Check User Token còn hạn không?
    if user.facebook_user_token_expires_at:
        if user.facebook_user_token_expires_at <= now:
            raise ValueError(
                "Long-lived User Token đã hết hạn (60 ngày). "
                "Vui lòng đăng nhập lại Facebook để liên kết lại."
            )
    
    # Dùng Long-lived User Token để lấy Page Token mới
    logger.info(
        "Refreshing Facebook Page token",
        extra={"user_id": user.id, "action": "refresh_page_token"}
    )
    
    page_info = get_page_token_from_user_token(user.facebook_user_access_token)
    
    # Update vào DB
    user.facebook_page_id = page_info["page_id"]
    user.facebook_access_token = page_info["access_token"]
    user.facebook_token_expires_at = page_info.get("expires_at")
    user.facebook_page_name = page_info.get("name")
    user.updated_at = now
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logger.info(
        "Facebook Page token refreshed successfully",
        extra={"user_id": user.id, "page_id": page_info["page_id"]}
    )
    
    return page_info["page_id"], page_info["access_token"]


def get_valid_facebook_token(db, user) -> tuple[str, str]:
    """
    Lấy valid Facebook Page Token (tự động refresh nếu cần).
    
    Args:
        db: Database session
        user: User object
        
    Returns:
        Tuple (page_id, access_token)
        
    Raises:
        ValueError: Nếu không có token hoặc không thể refresh
    """
    if not user.facebook_page_id or not user.facebook_access_token:
        raise ValueError("Chưa liên kết Facebook Page")
    
    # Tự động refresh nếu cần
    return refresh_facebook_page_token(db, user)

