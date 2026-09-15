"""价格分析与性价比计算"""
from __future__ import annotations

import statistics
from typing import Sequence

from .models import Product, Platform


class PriceAnalyzer:
    """价格分析器：排序、性价比、推荐"""

    # 推荐标签
    TAG_BEST_PRICE = "💰 最低价"
    TAG_BEST_VALUE = "⭐ 性价比之选"
    TAG_TOP_RATED = "🏆 高评分"
    TAG_HOT_SALES = "🔥 爆款热销"
    TAG_ALL_AROUND = "✨ 综合最优"

    @classmethod
    def analyze(cls, products: Sequence[Product]) -> list[Product]:
        """完整分析：排序 → 性价比打分 → 推荐标注"""
        if not products:
            return []

        # 1. 基础排序（价格低到高）
        sorted_products = sorted(products, key=lambda p: p.price)
        for rank, p in enumerate(sorted_products, start=1):
            p.price_rank = rank

        # 2. 计算性价比与填充字段
        stats = cls._compute_stats(sorted_products)
        for p in sorted_products:
            p.value_score = cls._calc_value_score(p, stats)

        # 3. 生成推荐标签
        cls._apply_recommendations(sorted_products)

        # 4. 最终排序：按性价比得分从高到低（但价格排名保留）
        print(f"📊 分析完成: {len(sorted_products)} 件商品")
        return sorted_products

    @classmethod
    def _compute_stats(cls, products: list[Product]) -> dict:
        prices = [p.price for p in products]
        ratings = [p.rating for p in products]
        sales = [p.sales for p in products]
        return {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": statistics.mean(prices),
            "median_price": statistics.median(prices),
            "stdev_price": statistics.stdev(prices) if len(prices) > 1 else 0,
            "min_rating": min(ratings),
            "max_rating": max(ratings),
            "avg_rating": statistics.mean(ratings),
            "max_sales": max(sales),
            "platforms": sorted({p.platform.value if isinstance(p.platform, Platform) else str(p.platform) for p in products}),
        }

    @classmethod
    def _calc_value_score(cls, p: Product, stats: dict) -> float:
        """
        性价比得分（0-100）
        综合考虑：价格优势（越低越好）、评分（越高越好）、销量（越高越好）
        """
        # 价格得分：0-50 分
        price_range = max(stats["max_price"] - stats["min_price"], 0.01)
        price_norm = (stats["max_price"] - p.price) / price_range  # 越便宜越高
        price_score = price_norm * 50

        # 评分得分：0-25 分
        rating_norm = (p.rating - stats["min_rating"]) / max(stats["max_rating"] - stats["min_rating"], 0.1)
        rating_score = rating_norm * 25

        # 销量得分：0-25 分（对数平滑）
        import math
        if stats["max_sales"] > 0:
            sales_norm = math.log1p(p.sales) / math.log1p(stats["max_sales"])
        else:
            sales_norm = 0
        sales_score = sales_norm * 25

        return round(price_score + rating_score + sales_score, 1)

    @classmethod
    def _apply_recommendations(cls, products: list[Product]) -> None:
        """为每个商品打上推荐标签"""
        if not products:
            return

        best_price = products[0]  # 已经按价格排序
        best_value = max(products, key=lambda p: p.value_score)
        top_rated = max(products, key=lambda p: p.rating)
        hot_sales = max(products, key=lambda p: p.sales)

        for p in products:
            tags = []
            if p is best_price:
                tags.append(cls.TAG_BEST_PRICE)
            if p is best_value:
                tags.append(cls.TAG_BEST_VALUE)
            if p is top_rated:
                tags.append(cls.TAG_TOP_RATED)
            if p is hot_sales:
                tags.append(cls.TAG_HOT_SALES)
            if len(tags) >= 2:
                tags.append(cls.TAG_ALL_AROUND)
            p.recommendation = " | ".join(tags) if tags else ""

    # ------------------------------------------------------------------
    # 生成各种汇总视图
    # ------------------------------------------------------------------

    @classmethod
    def summary(cls, products: Sequence[Product]) -> dict:
        """生成市场汇总统计"""
        if not products:
            return {}
        stats = cls._compute_stats(list(products))

        # 各平台均价
        platform_avg: dict[str, float] = {}
        for platform in Platform.all():
            p_prices = [p.price for p in products if p.platform == platform]
            if p_prices:
                platform_avg[platform.value] = round(statistics.mean(p_prices), 2)

        # 各平台商品数量
        platform_count: dict[str, int] = {}
        for platform in Platform.all():
            platform_count[platform.value] = sum(
                1 for p in products if p.platform == platform
            )

        # 价格分布区间
        prices = [p.price for p in products]
        bins = [
            ("0-500", 0, 500),
            ("500-2000", 500, 2000),
            ("2000-5000", 2000, 5000),
            ("5000-10000", 5000, 10000),
            ("10000+", 10000, float("inf")),
        ]
        price_dist: dict[str, int] = {}
        for label, lo, hi in bins:
            price_dist[label] = sum(1 for x in prices if lo <= x < hi)

        return {
            "keyword": products[0].keyword if products else "",
            "total_count": len(products),
            "stats": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in stats.items()},
            "platform_avg": platform_avg,
            "platform_count": platform_count,
            "price_distribution": price_dist,
        }

    @classmethod
    def price_trend(cls, products: Sequence[Product]) -> list[dict]:
        """
        价格趋势（用于图表）
        由于单次采集只有一个时间点，这里用"价格排名 vs 价格"作为趋势示意
        未来可扩展为多次采集的时间序列
        """
        sorted_products = sorted(products, key=lambda p: p.price)
        return [
            {
                "rank": i + 1,
                "price": p.price,
                "platform": p.platform.value if isinstance(p.platform, Platform) else str(p.platform),
                "name": p.name[:20],
            }
            for i, p in enumerate(sorted_products)
        ]

    @classmethod
    def to_comparison_table(cls, products: Sequence[Product]) -> list[dict]:
        """
        生成横向对比表：以最便宜的商品为基准
        其他商品显示"贵多少%"
        """
        if not products:
            return []
        sorted_by_price = sorted(products, key=lambda p: p.price)
        baseline = sorted_by_price[0].price

        table = []
        for p in sorted_by_price:
            premium = ((p.price - baseline) / baseline * 100) if baseline > 0 else 0
            table.append({
                "rank": p.price_rank,
                "name": p.name,
                "platform": p.platform.value if isinstance(p.platform, Platform) else str(p.platform),
                "shop": p.shop_name,
                "price": p.price,
                "premium_pct": round(premium, 1),
                "sales": p.sales,
                "rating": p.rating,
                "value_score": p.value_score,
                "recommendation": p.recommendation,
                "url": p.url,
            })
        return table
