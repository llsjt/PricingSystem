"""数据库基类模块，定义 SQLAlchemy 模型继承使用的 Declarative Base。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
