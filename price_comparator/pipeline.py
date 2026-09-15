"""
电商价格采集与对比 - 完整管道
封装 采集 → 清洗 → 分析 的全流程
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

# 让 core 包可直接 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import MultiPlatformCollector, DataCleaner, PriceAnalyzer
from core.models import Platform

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class PricePipeline:
    """端到端采集分析管道"""

    def __init__(
        self,
        mode: str = "mock",
        platforms: Optional[list[str]] = None,
        per_platform: int = 8,
    ):
        platform_objs = None
        if platforms:
            platform_objs = [Platform(p) for p in platforms]
        self.collector = MultiPlatformCollector(
            platforms=platform_objs,
            mode=mode,
            mock_per_platform=per_platform,
        )
        self.cleaner = DataCleaner()
        self.analyzer = PriceAnalyzer()

    def run(self, keyword: str) -> dict:
        """执行完整流程，返回分析结果"""
        # Step 1: 采集
        raw = self.collector.collect(keyword)
        if not raw:
            return {"error": "采集失败，没有获取到任何数据", "keyword": keyword}

        # Step 2: 清洗
        cleaned = self.cleaner.clean(raw)
        if not cleaned:
            return {"error": "清洗后无有效数据", "keyword": keyword}

        # Step 3: 分析
        analyzed = self.analyzer.analyze(cleaned)

        # Step 4: 汇总输出
        summary = self.analyzer.summary(analyzed)
        trend = self.analyzer.price_trend(analyzed)
        table = self.analyzer.to_comparison_table(analyzed)

        return {
            "keyword": keyword,
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "price_trend": trend,
            "comparison_table": table,
            "raw_products": [p.to_dict() for p in analyzed],
        }


def save_result(result: dict, out_path: str) -> str:
    """保存结果到 JSON 文件"""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return out_path


def print_report(result: dict) -> None:
    """在终端打印格式化报告"""
    if "error" in result:
        print(f"\n❌ 错误: {result['error']}")
        return

    keyword = result["keyword"]
    summary = result["summary"]
    table = result["comparison_table"]

    print("\n" + "=" * 72)
    print(f"  🛒 电商价格对比报告  |  关键词: 「{keyword}」")
    print("=" * 72)

    s = summary["stats"]
    print(f"\n📊 概览")
    print(f"  商品总数      : {summary['total_count']}")
    print(f"  价格范围      : ¥{s['min_price']:.2f}  ~  ¥{s['max_price']:.2f}")
    print(f"  平均价格      : ¥{s['avg_price']:.2f}")
    print(f"  中位价格      : ¥{s['median_price']:.2f}")
    print(f"  覆盖平台      : {', '.join(summary['platform_avg'].keys())}")

    print(f"\n🏪 各平台均价")
    for platform, avg in summary["platform_avg"].items():
        count = summary["platform_count"].get(platform, 0)
        print(f"  {platform:6s}  ¥{avg:>10.2f}  ({count} 件)")

    print(f"\n📦 价格分布")
    for band, count in summary["price_distribution"].items():
        bar = "█" * int(count * 2)
        print(f"  {band:>10s}  {bar} ({count})")

    print(f"\n🔍 横向对比（按价格从低到高）")
    print("-" * 72)
    header = f"{'#':>3}  {'平台':<4}  {'价格':>10}  {'差价比':>8}  {'评分':>4}  {'销量':>8}  {'性价比':>6}  推荐"
    print(header)
    print("-" * 72)
    for row in table[:20]:  # 最多 20 条
        rec = row["recommendation"][:18] if row["recommendation"] else ""
        premium = f"+{row['premium_pct']:.1f}%" if row["premium_pct"] > 0 else "基础价"
        print(
            f"{row['rank']:>3}  {row['platform']:<4}  ¥{row['price']:>9.2f}  {premium:>8}  "
            f"{row['rating']:>4.1f}  {row['sales']:>8,}  {row['value_score']:>6.1f}  {rec}"
        )
    print("-" * 72)

    # 打印 TOP 推荐
    top_picks = [r for r in table if r["recommendation"]]
    if top_picks:
        print(f"\n⭐ 精选推荐")
        for pick in top_picks[:3]:
            print(f"  {pick['recommendation']}")
            print(f"    {pick['name'][:50]}")
            print(f"    平台: {pick['platform']}  店铺: {pick['shop']}  价格: ¥{pick['price']:.2f}")
            print(f"    链接: {pick['url']}")
            print()
