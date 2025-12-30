"""Seed dữ liệu ban đầu vào database."""

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.tables import User, Block


def seed_data() -> None:
    """Seed dữ liệu mẫu vào database nếu chưa có."""
    db: Session = SessionLocal()
    try:
        # Kiểm tra và seed User admin nếu chưa có
        admin_user = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin_user:
            # Tạo user admin mẫu
            admin_user = User(
                email="admin@example.com",
            )
            db.add(admin_user)
            print("✅ Seeded admin user (email: admin@example.com)")

        # Kiểm tra và seed Blocks nếu chưa có
        blocks_count = db.query(Block).count()
        if blocks_count == 0:
            # Tạo các blocks mẫu cho announcements
            sample_blocks = [
                Block(code="bee", name="Bee (Nhà trẻ)", sort_order=1, is_active=True),
                Block(code="mouse", name="Mouse (MGB)", sort_order=2, is_active=True),
                Block(code="bear", name="Bear (MGN)", sort_order=3, is_active=True),
                Block(code="dolphin", name="Dolphin (MGL)", sort_order=4, is_active=True),
            ]
            db.add_all(sample_blocks)
            print("✅ Seeded sample blocks: Bee, Mouse, Bear, Dolphin")

        db.commit()
        print("✅ Initial data seeding completed")
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding data: {e}")
        # Không raise exception để app vẫn có thể chạy được
    finally:
        db.close()

