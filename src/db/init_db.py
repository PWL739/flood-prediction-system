"""数据库初始化模块 —— PostgreSQL + TimescaleDB 支持"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.db.models import Base, RawWaterData, CleanedWaterData, FeatureData
from src.config.settings import DATABASE_CONFIG, TIMESCALEDB_CONFIG


def get_database_url(config: dict = None) -> str:
    """生成PostgreSQL数据库连接URL"""
    if config is None:
        config = DATABASE_CONFIG
    return (
        f"postgresql+psycopg2://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
    )


def create_db_engine(config: dict = None):
    """创建PostgreSQL数据库引擎"""
    db_url = get_database_url(config)
    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        echo=False,
        pool_pre_ping=True,
    )
    return engine


def init_database(engine):
    """初始化数据库表结构"""
    Base.metadata.create_all(engine)
    print("数据库表结构初始化完成")


def setup_timescaledb(engine):
    """配置TimescaleDB扩展和时序超表"""
    hypertables = [
        {
            "table": "raw_water_data",
            "time_column": "timestamp",
            "partition_column": "location_id",
        },
        {
            "table": "cleaned_water_data",
            "time_column": "timestamp",
            "partition_column": "location_id",
        },
        {
            "table": "feature_data",
            "time_column": "timestamp",
            "partition_column": "location_id",
        },
        {
            "table": "water_monitoring_data",
            "time_column": "timestamp",
            "partition_column": "location_id",
        },
    ]

    with engine.connect() as conn:
        # 启用TimescaleDB扩展
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            conn.commit()
            print("TimescaleDB扩展已启用")
        except Exception as e:
            print(f"TimescaleDB扩展启用跳过（可能已启用）: {e}")

        # 将普通表转换为超表（hypertable）
        for ht in hypertables:
            try:
                # 检查表是否存在
                result = conn.execute(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                        f"WHERE table_name = '{ht['table']}')"
                    )
                )
                if not result.scalar():
                    continue

                # 转换为超表
                sql = (
                    f"SELECT create_hypertable('{ht['table']}', '{ht['time_column']}', "
                    f"partitioning_column => '{ht['partition_column']}', "
                    f"chunk_time_interval => INTERVAL '{TIMESCALEDB_CONFIG['hypertable_chunk_interval']}', "
                    f"if_not_exists => TRUE)"
                )
                conn.execute(text(sql))
                conn.commit()
                print(f"超表 {ht['table']} 已配置")

                # 启用压缩
                if TIMESCALEDB_CONFIG["compression_enabled"]:
                    try:
                        compress_sql = (
                            f"SELECT add_compression_policy('{ht['table']}', "
                            f"INTERVAL '{TIMESCALEDB_CONFIG['compression_after_days']} days', "
                            f"if_not_exists => TRUE)"
                        )
                        conn.execute(text(compress_sql))
                        conn.commit()
                    except Exception:
                        pass

            except Exception as e:
                print(f"超表 {ht['table']} 配置失败（可能非TimescaleDB环境）: {e}")

        # 设置数据保留策略
        try:
            from src.config.settings import DATA_TIER_CONFIG
            for tier, tier_config in DATA_TIER_CONFIG.items():
                table_name = f"{tier}_water_data" if tier != "cleaned" else "cleaned_water_data"
                if tier == "raw":
                    table_name = "raw_water_data"
                elif tier == "feature":
                    table_name = "feature_data"
                try:
                    retention_sql = (
                        f"SELECT add_retention_policy('{table_name}', "
                        f"INTERVAL '{tier_config['retention_days']} days', "
                        f"if_not_exists => TRUE)"
                    )
                    conn.execute(text(retention_sql))
                    conn.commit()
                except Exception:
                    pass
        except Exception:
            pass

    print("TimescaleDB时序表优化配置完成")


def get_session_factory(engine):
    """获取会话工厂"""
    return sessionmaker(bind=engine)


def init_database_with_timescale(engine):
    """完整初始化：创建表 + 配置TimescaleDB"""
    init_database(engine)
    setup_timescaledb(engine)


def get_sqlite_url(db_path: str = "flood_prediction.db"):
    """获取SQLite连接URL（开发/测试用）"""
    return f"sqlite:///{db_path}"


def create_dev_engine(db_path: str = "flood_prediction.db"):
    """创建SQLite开发环境引擎（无需安装PostgreSQL）"""
    engine = create_engine(get_sqlite_url(db_path), echo=False)
    return engine


# ==================== 便捷会话管理 ====================

_dev_session_factory = None

def get_session():
    """获取数据库会话（开发环境使用 SQLite 单例）"""
    global _dev_session_factory
    if _dev_session_factory is None:
        db_url = os.getenv("DATABASE_URL", "sqlite:///flood_prediction.db")
        engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(engine)
        _dev_session_factory = sessionmaker(bind=engine)
    return _dev_session_factory()
