"""初始化管理员账户脚本

用法:
    python scripts/create_admin.py
    ADMIN_USERNAME=myadmin ADMIN_PASSWORD=mypass python scripts/create_admin.py
"""

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.models import User, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 密码哈希：优先使用 passlib，失败时回退到 sha256
def hash_password(password: str) -> str:
    try:
        from passlib.hash import bcrypt
        return bcrypt.hash(password)
    except Exception:
        return hashlib.sha256(password.encode()).hexdigest()

DB_URL = os.getenv("DATABASE_URL", "sqlite:///flood_prediction.db")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def create_admin():
    engine = create_engine(DB_URL, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existing = session.query(User).filter(User.username == ADMIN_USERNAME).first()
        if existing:
            print(f"管理员 '{ADMIN_USERNAME}' 已存在，跳过创建")
            return

        admin = User(
            username=ADMIN_USERNAME,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            display_name="系统管理员",
            is_active=1,
        )
        session.add(admin)

        # 创建默认角色用户
        defaults = [
            ("commander", "指挥员", "commander123"),
            ("researcher", "科研人员", "researcher123"),
            ("grassroots", "基层人员", "grassroots123"),
        ]
        for username, display_name, password in defaults:
            if not session.query(User).filter(User.username == username).first():
                session.add(User(
                    username=username,
                    password_hash=hash_password(password),
                    role=username,
                    display_name=display_name,
                    is_active=1,
                ))

        session.commit()
        print(f"管理员 '{ADMIN_USERNAME}' 创建成功")
        print("默认用户已创建: commander, researcher, grassroots")
        print("默认密码: commander123 / researcher123 / grassroots123")
    except Exception as e:
        session.rollback()
        print(f"创建失败: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    print(f"数据库: {DB_URL}")
    create_admin()
    print("完成")
