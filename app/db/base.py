"""SQLAlchemy 声明基类。所有 ORM 模型都继承此处 Base。"""
from sqlalchemy.orm import declarative_base

Base = declarative_base()
