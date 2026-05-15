"""数据库初始化模块"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.db.models import Base


def get_database_url(config: dict) -> str:
    """生成数据库连接URL"""
    return (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset=utf8mb4"
    )


def create_db_engine(config: dict):
    """创建数据库引擎"""
    db_url = get_database_url(config)
    engine = create_engine(db_url, pool_size=10, max_overflow=20, echo=False)
    return engine


def init_database(engine):
    """初始化数据库表结构"""
    Base.metadata.create_all(engine)
    print("数据库表结构初始化完成")


def get_session_factory(engine):
    """获取会话工厂"""
    return sessionmaker(bind=engine)
