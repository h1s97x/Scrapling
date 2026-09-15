"""Flask Web API 服务"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from pipeline import PricePipeline
from core.models import Platform


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    CORS(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/platforms")
    def list_platforms():
        return jsonify({"platforms": [p.value for p in Platform.all()]})

    @app.route("/api/collect", methods=["POST"])
    def api_collect():
        """
        POST JSON:
          {
            "keyword": "手机",
            "mode": "mock",            // mock | real | hybrid
            "platforms": ["京东", "淘宝"],  // 可选
            "per_platform": 8
          }
        """
        data = request.get_json(silent=True) or {}
        keyword = (data.get("keyword") or "").strip()
        if not keyword:
            return jsonify({"error": "keyword 不能为空"}), 400

        mode = data.get("mode", "mock")
        platforms = data.get("platforms") or None
        per_platform = int(data.get("per_platform", 8))

        # 校验平台参数
        if platforms:
            valid = {p.value for p in Platform.all()}
            platforms = [p for p in platforms if p in valid] or None

        try:
            pipeline = PricePipeline(
                mode=mode,
                platforms=platforms,
                per_platform=per_platform,
            )
            result = pipeline.run(keyword)
            return jsonify(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
