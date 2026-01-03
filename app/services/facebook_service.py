"""
Service upload video và đăng bài lên Facebook.

Bước 1: Upload video lên Facebook (nếu có)
Bước 2: Upload ảnh lên Facebook (nếu có)
Bước 3: Đăng bài với video/ảnh + link website
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

import requests

from app.models.tables import Asset, Post

# Facebook API configuration
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_ACCESS_TOKEN = os.getenv("FB_ACCESS_TOKEN")
FB_API_VERSION = os.getenv("FB_API_VERSION", "v19.0")
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://your-site.com")


def upload_video_to_facebook(
    post: Post,
    video_asset: Asset,
    post_url: str,
) -> str:
    """
    Upload video file lên Facebook.
    
    Bước 1: Đọc video file từ server
    Bước 2: Upload lên Facebook Graph API
    Bước 3: Trả về Facebook video ID
    
    Args:
        post: Post object
        video_asset: Asset object chứa video
        post_url: URL bài viết trên website
        
    Returns:
        Facebook video/post ID
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        raise ValueError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set in environment")
    
    # Lấy đường dẫn file video
    # Sử dụng UPLOAD_DIR từ environment (không hardcode /app)
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
    video_path = upload_dir / video_asset.url.lstrip("/uploads/")
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Tạo description cho video
    description = post.title
    if post.excerpt:
        description += f"\n\n{post.excerpt}"
    description += f"\n\nXem thêm: {post_url}"
    
    # Upload video lên Facebook
    # Note: Facebook có thể upload video lớn, cần timeout dài
    with open(video_path, 'rb') as video_file:
        files = {'file': video_file}
        data = {
            'access_token': FB_ACCESS_TOKEN,
            'description': description,
            'title': post.title,
        }
        
        response = requests.post(
            f"https://graph-video.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/videos",
            files=files,
            data=data,
            timeout=600,  # 10 phút cho video lớn
        )
    
    response.raise_for_status()
    result = response.json()
    
    return result.get("id")  # Facebook video/post ID


def upload_images_to_facebook(
    post: Post,
    post_url: str,
    cover_asset: Optional[Asset] = None,
    content_assets: Optional[list[Asset]] = None,
) -> str:
    """
    Upload ảnh và đăng bài lên Facebook (khi không có video).
    
    Bước 1: Upload tất cả ảnh lên Facebook
    Bước 2: Đăng bài với ảnh đính kèm
    
    Args:
        post: Post object
        post_url: URL bài viết trên website
        cover_asset: Ảnh cover (nếu có)
        content_assets: Danh sách ảnh nội dung (nếu có)
        
    Returns:
        Facebook post ID
    """
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        raise ValueError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set in environment")
    
    # Thu thập tất cả ảnh
    all_images = []
    if cover_asset:
        all_images.append(cover_asset)
    if content_assets:
        all_images.extend(content_assets)
    
    # Upload ảnh lên Facebook
    photo_ids = []
    upload_dir = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
    
    for asset in all_images[:10]:  # Facebook cho phép tối đa 10 ảnh
        if not asset or not asset.url:
            continue
        
        try:
            # Thử upload từ file trước (hỗ trợ localhost)
            image_path = upload_dir / asset.url.lstrip("/uploads/")
            
            if image_path.exists():
                # Upload từ file (tốt hơn cho localhost)
                with open(image_path, 'rb') as image_file:
                    files = {'file': image_file}
                    data = {
                        "access_token": FB_ACCESS_TOKEN,
                        "published": False,
                    }
                    photo_response = requests.post(
                        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos",
                        files=files,
                        data=data,
                        timeout=30,
                    )
                    photo_response.raise_for_status()
                    photo_id = photo_response.json().get("id")
                    if photo_id:
                        photo_ids.append({"media_fbid": photo_id})
                        print(f"✅ Uploaded image from file: {image_path}")
            else:
                # Fallback: upload từ URL (chỉ khi không phải localhost)
                image_url = f"{APP_BASE_URL}{asset.url}"
                
                if "localhost" in image_url or "127.0.0.1" in image_url:
                    print(f"⚠️ Warning: Skipping localhost image {image_url} (file not found: {image_path})")
                    continue
                
                photo_response = requests.post(
                    f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/photos",
                    params={
                        "access_token": FB_ACCESS_TOKEN,
                        "url": image_url,
                        "published": False,
                    },
                    timeout=30,
                )
                photo_response.raise_for_status()
                photo_id = photo_response.json().get("id")
                if photo_id:
                    photo_ids.append({"media_fbid": photo_id})
                    print(f"✅ Uploaded image from URL: {image_url}")
                    
        except Exception as e:
            print(f"⚠️ Warning: Could not upload image {asset.url}: {e}")
            continue
    
    # Tạo message
    message = post.title or ""
    if post.excerpt:
        message += f"\n\n{post.excerpt}"
    
    # Kiểm tra xem URL có phải localhost không (Facebook không thể truy cập)
    is_localhost = "localhost" in post_url or "127.0.0.1" in post_url
    
    # Chỉ thêm link vào message nếu không phải localhost
    if not is_localhost:
        message += f"\n\nXem thêm: {post_url}"
    
    # Đăng bài với ảnh
    params = {
        "access_token": FB_ACCESS_TOKEN,
    }
    
    # Chỉ thêm message nếu có nội dung
    if message.strip():
        params["message"] = message
    
    if len(photo_ids) > 1:
        # Nhiều ảnh → Carousel
        params["attached_media"] = json.dumps(photo_ids)
    elif len(photo_ids) == 1:
        # 1 ảnh → Ảnh lớn
        params["attached_media"] = json.dumps(photo_ids)
        # Không cần link khi có ảnh
    else:
        # Không có ảnh
        if not is_localhost:
            # Chỉ thêm link nếu không phải localhost
            if not params.get("message"):
                # Nếu không có message, bắt buộc phải có link
                params["link"] = post_url
            else:
                # Có message thì link là optional (nhưng vẫn thêm để có preview)
                params["link"] = post_url
        # Nếu là localhost và không có ảnh, chỉ đăng message (không có link)
    
    response = requests.post(
        f"https://graph.facebook.com/{FB_API_VERSION}/{FB_PAGE_ID}/feed",
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
            print(f"❌ Facebook API Error:")
            print(f"   Code: {error_code}")
            print(f"   Type: {error_type}")
            print(f"   Message: {error_detail}")
            print(f"   Request URL: {response.url}")
        except:
            print(f"❌ Facebook API Error {response.status_code}: {error_detail}")
        
        raise requests.exceptions.HTTPError(
            f"Facebook API Error {response.status_code}: {error_detail}"
        )
    
    result = response.json()
    
    return result.get("id")  # Facebook post ID

