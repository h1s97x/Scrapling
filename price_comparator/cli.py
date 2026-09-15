#!/usr/bin/env python3
"""
电商价格采集与对比 - 命令行工具
示例:
  python3 cli.py 手机
  python3 cli.py 笔记本 --mode mock --platforms 京东 淘宝 --output result.json
  python3 cli.py --demo          # 运行演示
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

# 确保能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import PricePipeline, print_report, save_result
from core.models import Platform


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="price-comparator",
        description="🛒 电商价格自动化采集与对比工具（京东 / 淘宝 / 拼多多）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  price-comparator 手机
  price-comparator "无线耳机" --platforms 京东 淘宝 --mode mock
  price-comparator 空调 --output report.json --per-platform 10
  price-comparator --demo              # 内置演示关键词列表
  price-comparator --serve --port 5000 # 启动 Web 演示服务
        """,
    )
    p.add_argument("keyword", nargs="?", help="搜索关键词，例如：手机、笔记本、耳机")
    p.add_argument("--platforms", nargs="+", choices=[x.value for x in Platform.all()],
                   help="限定平台（默认全部）")
    p.add_argument("--mode", choices=["mock", "real", "hybrid"], default="mock",
                   help="采集模式：mock=模拟数据(默认), real=真实采集, hybrid=混合")
    p.add_argument("--per-platform", type=int, default=8,
                   help="每个平台采集的商品数量（默认 8）")
    p.add_argument("--output", "-o", help="JSON 结果输出路径")
    p.add_argument("--demo", action="store_true", help="运行内置关键词演示列表")
    p.add_argument("--serve", action="store_true", help="启动 Web 演示服务")
    p.add_argument("--port", type=int, default=5000, help="Web 服务端口（默认 5000）")
    return p


def run_demo(args) -> None:
    """内置演示：对多个关键词运行采集"""
    demo_keywords = ["手机", "笔记本", "耳机"]
    print("🎬 开始内置演示（关键词: {}）\n".format(", ".join(demo_keywords)))
    pipeline = PricePipeline(mode=args.mode, platforms=args.platforms,
                             per_platform=args.per_platform)
    all_results = {}
    for kw in demo_keywords:
        result = pipeline.run(kw)
        print_report(result)
        all_results[kw] = result

    if args.output:
        save_result(all_results, args.output)
        print(f"\n💾 所有演示结果已保存到: {args.output}")


def run_single(args) -> None:
    """单关键词运行"""
    pipeline = PricePipeline(mode=args.mode, platforms=args.platforms,
                             per_platform=args.per_platform)
    result = pipeline.run(args.keyword)
    print_report(result)
    if args.output:
        path = save_result(result, args.output)
        print(f"\n💾 结果已保存到: {path}")


def run_serve(args) -> None:
    """启动 Web 演示服务"""
    from server.app import create_app
    app = create_app()
    print(f"\n🌐 启动 Web 演示服务 -> http://127.0.0.1:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=False)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.serve:
        run_serve(args)
        return

    if args.demo:
        run_demo(args)
        return

    if not args.keyword:
        parser.print_help()
        print("\n❌ 错误：请提供搜索关键词，或使用 --demo / --serve 模式")
        sys.exit(1)

    run_single(args)


if __name__ == "__main__":
    main()
