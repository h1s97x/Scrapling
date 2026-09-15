"""
数据采集核心模块
支持三种采集模式：
1. real    - 真实 API/HTTP 抓取（需要网络）
2. mock    - 模拟数据（离线可用，用于演示）
3. hybrid  - 优先真实采集，失败回退到模拟数据
"""
from __future__ import annotations

import hashlib
import random
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .models import Product, Platform

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 模拟数据生成器（核心演示模式）
# ---------------------------------------------------------------------------

class MockDataGenerator:
    """基于关键词生成逼真的模拟电商数据"""

    # 每个关键词对应的"品牌/型号"模板，让模拟数据更真实
    PRODUCT_TEMPLATES: dict[str, list[str]] = {
        "手机": [
            "{brand} {model} Pro Max 5G",
            "{brand} {model} 标准版",
            "{brand} {model} Ultra 旗舰版",
            "小米 {model} 全网通",
            "华为 {model} Pro 麒麟版",
            "OPPO {model} Reno 系列",
            "vivo {model} 旗舰影像手机",
            "三星 Galaxy {model}",
        ],
        "笔记本": [
            "{brand} MacBook {model}",
            "联想 {model} Pro 14",
            "ThinkPad {model} 商务本",
            "戴尔 {model} 灵越系列",
            "华硕 {model} 轻薄本",
            "红米Book {model} 增强版",
        ],
        "耳机": [
            "{brand} AirPods {model}",
            "索尼 WH-{model} 降噪耳机",
            "BOSE QuietComfort {model}",
            "华为 FreeBuds {model}",
            "小米真无线耳机 {model}",
            "漫步者 NeoBuds {model}",
        ],
        "空调": [
            "格力 {model} 变频节能空调",
            "美的 {model} 新一级能效",
            "海尔 {model} 自清洁空调",
            "奥克斯 {model} 大1.5匹",
            "小米空调 {model} 智能互联",
        ],
        "默认": [
            "{brand} {keyword} {model} 旗舰版",
            "{brand} {keyword} 经典款 {model}",
            "{keyword} {model} 官方正品",
            "{keyword} {model} 限时特惠",
        ],
    }

    BRANDS = [
        "Apple", "Huawei", "Xiaomi", "Samsung", "OPPO", "vivo",
        "Lenovo", "Dell", "ASUS", "HP", "Sony", "BOSE",
        "格力", "美的", "海尔", "飞利浦", "罗技",
    ]

    SHOPS = {
        Platform.JD: [
            "京东自营旗舰店", "京东电器旗舰店", "京东超市",
            "京东数码专营店", "京东品牌专卖店",
        ],
        Platform.TAOBAO: [
            "淘宝官方旗舰店", "天猫超市", "天猫国际",
            "品牌直销店", "淘宝优选",
        ],
        Platform.PDD: [
            "拼多多百亿补贴", "拼多多优选品牌馆",
            "拼多多工厂店", "拼多多旗舰馆",
        ],
        Platform.SUNING: [
            "苏宁易购官方旗舰店", "苏宁电器",
        ],
        Platform.DANGDANG: [
            "当当自营", "当当品牌直销",
        ],
    }

    MODEL_SUFFIXES = ["2024", "2025", "Pro", "Max", "Plus", "Ultra", "Lite", "标准版", "旗舰版"]

    @classmethod
    def generate(cls, keyword: str, platform: Platform, count: int = 8,
                 price_range: tuple[float, float] = (200, 15000)) -> list[Product]:
        """为指定平台生成模拟商品列表"""
        # 根据关键词选模板
        template_key = "默认"
        for k in cls.PRODUCT_TEMPLATES:
            if k in keyword:
                template_key = k
                break
        templates = cls.PRODUCT_TEMPLATES[template_key]
        shops = cls.SHOPS.get(platform, ["官方旗舰店"])

        # 基于关键词生成价格锚点，让各平台之间有合理差异
        seed = int(hashlib.md5(keyword.encode()).hexdigest(), 16) % 10000
        random.seed(seed + platform.value.__hash__())

        results: list[Product] = []
        for i in range(count):
            brand = random.choice(cls.BRANDS)
            template = random.choice(templates)
            model = random.choice(cls.MODEL_SUFFIXES)
            name = template.format(brand=brand, keyword=keyword, model=model)

            # 价格分布：京东略贵、拼多多略便宜、淘宝居中
            base = random.uniform(*price_range)
            platform_multiplier = {
                Platform.JD: 1.08,
                Platform.TAOBAO: 1.00,
                Platform.PDD: 0.92,
                Platform.SUNING: 1.02,
                Platform.DANGDANG: 0.98,
            }[platform]
            price = round(base * platform_multiplier * (0.85 + random.random() * 0.3), 2)

            sales = int(random.triangular(50, 50000, 5000))
            rating = round(random.uniform(3.8, 5.0), 1)

            shop = random.choice(shops)
            url = cls._make_url(platform, keyword, i)

            results.append(Product(
                name=name,
                price=price,
                platform=platform,
                url=url,
                shop_name=shop,
                sales=sales,
                rating=rating,
                keyword=keyword,
            ))
        return results

    @staticmethod
    def _make_url(platform: Platform, keyword: str, idx: int) -> str:
        encoded = quote(keyword)
        bases = {
            Platform.JD: "https://search.jd.com/Search?keyword={k}",
            Platform.TAOBAO: "https://s.taobao.com/search?q={k}",
            Platform.PDD: "https://mobile.yangkeduo.com/search_result.html?search_key={k}",
            Platform.SUNING: "https://search.suning.com/{k}/",
            Platform.DANGDANG: "http://search.dangdang.com/?key={k}",
        }
        return bases[platform].format(k=encoded) + f"&psort=1&pvid={idx}"


# ---------------------------------------------------------------------------
# 真实采集（尽力而为，失败不影响主流程）
# ---------------------------------------------------------------------------

class RealCollector:
    """真实采集实现（使用各平台公开搜索接口或搜索页面）"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    TIMEOUT = 10

    @classmethod
    def collect(cls, keyword: str, platform: Platform, count: int = 10) -> list[Product]:
        """尝试从真实平台采集，失败返回空列表"""
        try:
            if platform == Platform.JD:
                return cls._collect_jd(keyword, count)
            elif platform == Platform.TAOBAO:
                return cls._collect_taobao(keyword, count)
            elif platform == Platform.PDD:
                return cls._collect_pdd(keyword, count)
        except Exception as e:
            logger.warning(f"真实采集 {platform.value} 失败: {e}")
            return []
        return []

    @classmethod
    def _collect_jd(cls, keyword: str, count: int) -> list[Product]:
        url = f"https://search.jd.com/Search?keyword={quote(keyword)}&enc=utf-8"
        resp = requests.get(url, headers=cls.HEADERS, timeout=cls.TIMEOUT)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.gl-item")[:count]
        results = []
        for item in items:
            try:
                name = item.select_one(".p-name a")["title"].strip()
                price = float(item.select_one(".p-price strong i").text)
                link = item.select_one(".p-name a")["href"]
                if not link.startswith("http"):
                    link = "https:" + link
                results.append(Product(
                    name=name, price=price, platform=Platform.JD,
                    url=link, keyword=keyword,
                ))
            except Exception:
                continue
        return results

    @classmethod
    def _collect_taobao(cls, keyword: str, count: int) -> list[Product]:
        url = f"https://s.taobao.com/search?q={quote(keyword)}"
        resp = requests.get(url, headers=cls.HEADERS, timeout=cls.TIMEOUT)
        if resp.status_code != 200:
            return []
        # 淘宝新版搜索结果通过 JS 渲染，这里尝试解析旧版或移动版
        import re
        prices = re.findall(r'"price":"([\d.]+)"', resp.text)[:count]
        titles = re.findall(r'"raw_title":"([^"]+)"', resp.text)[:count]
        results = []
        for i in range(min(len(prices), len(titles))):
            try:
                results.append(Product(
                    name=titles[i].encode().decode("unicode_escape"),
                    price=float(prices[i]), platform=Platform.TAOBAO,
                    url=f"https://item.taobao.com/item.htm?q={keyword}",
                    keyword=keyword,
                ))
            except Exception:
                continue
        return results

    @classmethod
    def _collect_pdd(cls, keyword: str, count: int) -> list[Product]:
        # 拼多多没有公开 PC 搜索页，这里直接返回空，依赖 mock
        return []


# ---------------------------------------------------------------------------
# 顶层统一接口
# ---------------------------------------------------------------------------

class MultiPlatformCollector:
    """多平台统一采集器"""

    def __init__(
        self,
        platforms: Optional[list[Platform]] = None,
        mode: str = "hybrid",
        mock_per_platform: int = 8,
        max_workers: int = 5,
    ):
        self.platforms = platforms or Platform.all()
        self.mode = mode
        self.mock_per_platform = mock_per_platform
        self.max_workers = max_workers

    def collect(self, keyword: str) -> list[Product]:
        """采集指定关键词的所有平台数据"""
        print(f"\n🔍 开始采集关键词: 「{keyword}」  [模式={self.mode}]")
        t0 = time.time()
        all_products: list[Product] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._collect_one, keyword, p): p
                for p in self.platforms
            }
            for future in as_completed(futures):
                platform = futures[future]
                try:
                    products = future.result()
                    all_products.extend(products)
                    print(f"  ✅ {platform.value}: 获取 {len(products)} 条")
                except Exception as e:
                    print(f"  ❌ {platform.value}: 采集失败 - {e}")

        elapsed = time.time() - t0
        print(f"  ⏱️  采集完成，共 {len(all_products)} 条，耗时 {elapsed:.1f}s\n")
        return all_products

    def _collect_one(self, keyword: str, platform: Platform) -> list[Product]:
        """单平台采集"""
        if self.mode == "mock":
            return MockDataGenerator.generate(keyword, platform, self.mock_per_platform)

        if self.mode == "real":
            products = RealCollector.collect(keyword, platform, self.mock_per_platform)
            if not products:
                logger.info(f"{platform.value} 真实采集无结果")
            return products

        # hybrid：先真实再回退
        products = RealCollector.collect(keyword, platform, self.mock_per_platform)
        if products:
            return products
        # 回退到 mock 并标记
        mocked = MockDataGenerator.generate(keyword, platform, self.mock_per_platform)
        logger.info(f"{platform.value} 使用模拟数据回退")
        return mocked
