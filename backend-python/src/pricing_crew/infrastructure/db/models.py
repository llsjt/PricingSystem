"""数据库 ORM 模型模块，定义业务表与决策日志表。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BIGINT, Boolean, Column, Date, DateTime, DECIMAL, ForeignKey, Integer, String, Text

from pricing_crew.infrastructure.db.database import Base


class BizProduct(Base):
    __tablename__ = "biz_product"

    id = Column(BIGINT, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100))
    cost_price = Column(DECIMAL(10, 2), nullable=False)
    market_price = Column(DECIMAL(10, 2))
    current_price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0)
    monthly_sales = Column(Integer, default=0)
    click_rate = Column(DECIMAL(5, 4), default=0.0)
    conversion_rate = Column(DECIMAL(5, 4), default=0.0)
    source = Column(String(50), default="IMPORT")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BizSalesDaily(Base):
    __tablename__ = "biz_sales_daily"

    id = Column(BIGINT, primary_key=True, index=True)
    product_id = Column(BIGINT, ForeignKey("biz_product.id"), nullable=False, index=True)
    stat_date = Column(Date, nullable=False, index=True)
    daily_sales = Column(Integer, default=0)
    daily_revenue = Column(DECIMAL(12, 2), default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class BizPromotionHistory(Base):
    __tablename__ = "biz_promotion_history"

    id = Column(BIGINT, primary_key=True, index=True)
    product_id = Column(BIGINT, ForeignKey("biz_product.id"), nullable=False, index=True)
    promotion_name = Column(String(255))
    promotion_type = Column(String(50))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    discount_rate = Column(DECIMAL(5, 4))
    discount_price = Column(DECIMAL(10, 2))
    sales_before = Column(Integer)
    sales_during = Column(Integer)
    sales_lift = Column(DECIMAL(6, 4))
    created_at = Column(DateTime, default=datetime.utcnow)


class DecTask(Base):
    __tablename__ = "dec_task"

    id = Column(BIGINT, primary_key=True, index=True)
    task_no = Column(String(64), unique=True, index=True, nullable=False)
    product_names = Column(Text)
    strategy_type = Column(String(50), nullable=False)
    constraints = Column(Text)
    status = Column(String(20), nullable=False, default="PENDING")
    product_count = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecResult(Base):
    __tablename__ = "dec_result"

    id = Column(BIGINT, primary_key=True, index=True)
    task_id = Column(BIGINT, ForeignKey("dec_task.id"), nullable=False, index=True)
    product_id = Column(BIGINT, nullable=False)
    decision = Column(String(20), nullable=False)
    discount_rate = Column(DECIMAL(5, 4), nullable=False)
    suggested_price = Column(DECIMAL(10, 2), nullable=False)
    profit_change = Column(DECIMAL(10, 2))
    core_reasons = Column(Text)
    is_accepted = Column(Boolean, default=False)
    adopt_status = Column(String(20), default="PENDING")
    reject_reason = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)


class DecAgentLog(Base):
    __tablename__ = "dec_agent_log"

    id = Column(BIGINT, primary_key=True, index=True)
    task_id = Column(BIGINT, ForeignKey("dec_task.id"), nullable=False, index=True)
    role_name = Column(String(50), nullable=False)
    speak_order = Column(Integer, nullable=False)
    thought_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
