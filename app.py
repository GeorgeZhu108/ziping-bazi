# -*- coding: utf-8 -*-
"""
子平推演 - Web服务
"""

import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify

from engine import calculate_bazi
import city_coords

app = Flask(__name__)


def make_serializable(obj):
    """递归将对象转为JSON可序列化"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [make_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): make_serializable(v) for k, v in obj.items()}
    return str(obj)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json() or {}
    try:
        year = int(data.get("year", datetime.now().year))
        month = int(data.get("month", 1))
        day = int(data.get("day", 1))
        hour = int(data.get("hour", 12))
        minute = int(data.get("minute", 0))
        gender = data.get("gender", "男")
        current_year = data.get("current_year")
        if current_year is not None:
            current_year = int(current_year)

        # 出生地经度（真太阳时校正用）：空值/非法值视为不校正，向后兼容
        longitude = data.get("longitude")
        if longitude in (None, "", "null"):
            longitude = None
        else:
            try:
                longitude = float(longitude)
            except (TypeError, ValueError):
                longitude = None

        # 出生地城市：手动输入后由后台查询经纬度（真太阳时校正）
        city = (data.get("city") or "").strip()
        resolved_city = None
        if longitude is None and city:
            geo = city_coords.lookup(city)
            if geo.get("found"):
                longitude = geo["longitude"]
                resolved_city = geo["name"]

        # 晚子时口径，默认 current-day 与 lunar-python 一致
        late_zishi_rule = data.get("late_zishi_rule", "current-day")

        result = calculate_bazi(year, month, day, hour, minute=minute,
                                gender=gender, current_year=current_year,
                                longitude=longitude, late_zishi_rule=late_zishi_rule)
        result = make_serializable(result)
        # 回写解析到的城市信息，便于前端展示
        if resolved_city:
            result["input"]["city"] = resolved_city
            result["input"]["longitude"] = longitude
            result["input"]["city_resolved"] = True
        elif city:
            result["input"]["city"] = city
            result["input"]["city_resolved"] = bool(longitude is not None)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/geocode")
def api_geocode():
    """后台查询城市经纬度：GET /api/geocode?city=北京"""
    city = (request.args.get("city") or "").strip()
    geo = city_coords.lookup(city)
    return jsonify(geo)


@app.route("/api/example")
def api_example():
    result = calculate_bazi(1990, 7, 15, 10, gender="男", current_year=2026)
    return jsonify({"success": True, "data": make_serializable(result)})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
