# Facebook Integration - Hướng dẫn triển khai

## Đã triển khai

✅ Migration: Thêm Facebook fields vào User table
✅ User Model: Thêm Facebook token fields
✅ Facebook Service: Exchange token, get page token, auto refresh
✅ API Endpoints: `/auth/facebook/link`, `/auth/facebook/status`
✅ News Service: Tự động dùng token từ User, auto refresh khi cần
✅ Authentication: Dependency `get_current_user` để lấy user từ JWT

## Environment Variables cần thêm

Thêm vào `.env`:

```env
# Facebook App (để exchange token)
FB_APP_ID=your_facebook_app_id
FB_APP_SECRET=your_facebook_app_secret

# Facebook API Version (optional, default: v19.0)
FB_API_VERSION=v19.0

# App Base URL (cho link preview)
APP_BASE_URL=https://your-site.com
```

**Lưu ý:** `FB_PAGE_ID` và `FB_ACCESS_TOKEN` trong `.env` giờ chỉ dùng làm fallback. Mỗi user sẽ có token riêng.

## Chạy Migration

```bash
alembic upgrade head
```

## API Endpoints mới

### 1. Liên kết Facebook Page
```
POST /auth/facebook/link
Authorization: Bearer <JWT>
Body: {
  "user_access_token": "EAABwzLix..." // Short-lived từ Facebook OAuth
}
```

### 2. Kiểm tra trạng thái
```
GET /auth/facebook/status
Authorization: Bearer <JWT>
```

## Frontend Integration

### 1. Liên kết Facebook Page

```javascript
// Sau khi user đăng nhập Facebook OAuth
async function linkFacebookPage(userAccessToken) {
  const response = await fetch('/auth/facebook/link', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${appAccessToken}`, // JWT từ Google login
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      user_access_token: userAccessToken, // Từ Facebook OAuth
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.message || 'Failed to link Facebook');
  }
  
  return response.json();
}
```

### 2. Kiểm tra trạng thái

```javascript
async function checkFacebookStatus() {
  const response = await fetch('/auth/facebook/status', {
    headers: {
      'Authorization': `Bearer ${appAccessToken}`,
    },
  });
  
  return response.json();
}
```

### 3. Xử lý lỗi khi đăng bài

```javascript
try {
  const response = await fetch('/admin/news', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${appAccessToken}`,
    },
    body: formData,
  });
  
  if (!response.ok) {
    const error = await response.json();
    
    if (error.detail?.code === 'facebook_token_expired') {
      // Hiển thị modal: "Facebook token đã hết hạn, vui lòng liên kết lại"
      showFacebookLinkModal();
    } else {
      showError(error.detail?.message || 'Có lỗi xảy ra');
    }
  }
} catch (error) {
  showError('Có lỗi xảy ra');
}
```

## Luồng hoạt động

1. User đăng nhập Google → Có JWT token
2. User liên kết Facebook (1 lần) → Lưu Long-lived User Token (60 ngày) + Page Token
3. User đăng bài → Backend tự động:
   - Check Page Token còn hạn không?
   - Hết hạn → Tự động refresh (dùng Long-lived User Token)
   - Đăng bài lên Facebook
4. Sau 60 ngày → User cần liên kết Facebook lại (1 lần)

## Testing

1. Đăng nhập Google → Lấy JWT token
2. Đăng nhập Facebook OAuth → Lấy User Access Token
3. Gọi `/auth/facebook/link` với User Access Token
4. Tạo bài viết và publish → Kiểm tra đăng lên Facebook thành công

