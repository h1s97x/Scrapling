"""数据清洗与去重"""
from __future__ import annotations

import re
from typing import Sequence
from difflib import SequenceMatcher

from .models import Product


class DataCleaner:
    """电商数据清洗管道"""

    # 商品名中的噪声关键词
    NOISE_WORDS = [
        "官方", "正品", "旗舰", "特惠", "限时", "包邮", "直降", "秒杀",
        "现货", "全新", "原装", "授权", "专柜", "清仓", "特价",
    ]

    @classmethod
    def clean(cls, products: Sequence[Product]) -> list[Product]:
        """完整清洗流程：字段标准化 → 去重 → 过滤异常"""
        if not products:
            return []
        step1 = [cls._normalize(p) for p in products]
        step2 = cls._filter_invalid(step1)
        step3 = cls._dedup(step2)
        print(f"🧹 清洗: {len(products)} → {len(step2)} (过滤) → {len(step3)} (去重后)")
        return step3

    @classmethod
    def _normalize(cls, p: Product) -> Product:
        """字段标准化"""
        # 商品名：去除多余空白和噪声词
        name = re.sub(r"\s+", " ", p.name).strip()
        for noise in cls.NOISE_WORDS:
            name = name.replace(noise, "")
        p.name = name.strip()

        # 价格：限制范围
        p.price = round(max(0.01, p.price), 2)

        # 销量：至少为 0
        p.sales = max(0, p.sales)

        # 评分：限制在 0-5
        p.rating = max(0.0, min(5.0, p.rating))

        return p

    @classmethod
    def _filter_invalid(cls, products: list[Product]) -> list[Product]:
        """过滤异常数据"""
        valid = []
        for p in products:
            if not p.name or p.price <= 0:
                continue
            valid.append(p)
        return valid

    @classmethod
    def _dedup(cls, products: list[Product]) -> list[Product]:
        """
        去重策略：
        1. 同平台内：URL 完全相同视为重复
        2. 跨平台：商品名高度相似（相似度 > 0.85）且价格差 < 10% 视为同一商品不同店铺
        """
        # 第一步：同平台 URL 去重
        seen_urls: set[str] = set()
        dedup1: list[Product] = []
        for p in products:
            if p.url and p.url in seen_urls:
                continue
            seen_urls.add(p.url)
            dedup1.append(p)

        # 第二步：跨平台名称相似去重（保留价格最低的那个）
        final: list[Product] = []
        for p in dedup1:
            dup_idx = None
            for i, existing in enumerate(final):
                if existing.platform == p.platform:
                    continue  # 同平台已通过 URL 去重
                similarity = SequenceMatcher(None, p.name, existing.name).ratio()
                if similarity > 0.85:
                    price_diff = abs(p.price - existing.price) / max(p.price, existing.price)
                    if price_diff < 0.10:
                        dup_idx = i
                        break
            if dup_idx is None:
                final.append(p)
            elif p.price < final[dup_idx].price:
                final[dup_idx] = p  # 保留更便宜的
        return final
