"""数据模型定义"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    """支持的电商平台"""
    JD = "京东"
    TAOBAO = "淘宝"
    PDD = "拼多多"
    SUNING = "苏宁"
    DANGDANG = "当当"

    @classmethod
    def all(cls) -> list["Platform"]:
        return list(cls)


@dataclass
class Product:
    """商品数据模型"""
    name: str
    price: float
    platform: Platform
    url: str
    shop_name: str = ""
    sales: int = 0           # 月销量
    rating: float = 0.0      # 店铺评分 0-5
    image_url: str = ""
    keyword: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # 分析后填充的字段
    price_rank: int = 0      # 价格排名（由 analyzer 填充）
    value_score: float = 0.0  # 性价比得分
    recommendation: str = "" # 推荐标签
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["platform"] = self.platform.value if isinstance(self.platform, Platform) else self.platform
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        platform_val = data.get("platform", "")
        if isinstance(platform_val, str):
            for p in Platform:
                if p.value == platform_val:
                    data["platform"] = p
                    break
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
