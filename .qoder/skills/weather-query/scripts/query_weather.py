#!/usr/bin/env python3
"""
天气查询脚本（高德地图 API）
Usage:
    python query_weather.py "北京"
    python query_weather.py "上海" --full    # 包含预报
    python query_weather.py "杭州" --key 你的API密钥
"""
import argparse
import os
import sys
from pathlib import Path
import requests

os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)

# 加载 .env 环境变量
dotenv_path = Path(__file__).resolve().parents[4] / "backend" / ".env"
if dotenv_path.exists():
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

GEO_URL = "https://restapi.amap.com/v3/config/district"
WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


def get_adcode(city: str, key: str) -> str:
    """城市名 -> adcode，优先取 city 级别"""
    resp = requests.get(GEO_URL, params={
        "keywords": city,
        "subdistrict": 0,
        "key": key,
    }, timeout=10)
    data = resp.json()
    districts = data.get("districts", [])
    if not districts:
        return None
    # 优先取 city 级别，其次取第一个
    for d in districts:
        if d.get("level") == "city":
            return d["adcode"]
    return districts[0]["adcode"]


def get_weather(city: str, key: str, extensions: str = "base") -> dict:
    """查询天气，返回原始 JSON"""
    adcode = get_adcode(city, key)
    if not adcode:
        return {"error": f"未找到城市: {city}"}

    resp = requests.get(WEATHER_URL, params={
        "city": adcode,
        "key": key,
        "extensions": extensions,
        "output": "JSON",
    }, timeout=10)
    return resp.json()


def format_weather(data: dict, extensions: str = "base") -> str:
    """格式化天气数据为易读文本"""
    if "error" in data:
        return f"查询失败: {data['error']}"

    lines = []

    # extensions=base 时返回 lives（实况）
    lives = data.get("lives", [])
    if lives:
        for live in lives:
            lines.append(f"{live['province']} {live['city']}")
            lines.append(f"天气: {live['weather']}")
            lines.append(f"温度: {live['temperature']}°C")
            lines.append(f"风向: {live['winddirection']} {live['windpower']}级")
            lines.append(f"湿度: {live['humidity']}%")
            lines.append(f"更新时间: {live['reporttime']}")

    # extensions=all 时返回 forecasts（预报），包含在 casts 里
    forecasts_list = data.get("forecasts", [])
    if forecasts_list:
        forecast_data = forecasts_list[0]
        week_map = {
            "1": "周一", "2": "周二", "3": "周三",
            "4": "周四", "5": "周五", "6": "周六", "7": "周日",
        }
        lines.append("\n📅 未来天气预报:")
        for day in forecast_data.get("casts", []):
            lines.append(
                f"  {day['date']} {week_map.get(day['week'], '周' + day['week'])}: "
                f"白天{day['dayweather']} {day['daytemp']}°C → "
                f"夜间{day['nightweather']} {day['nighttemp']}°C"
            )

    if not lines:
        return "未查到天气数据"

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="高德地图天气查询")
    parser.add_argument("city", help="城市名称，如北京、上海、杭州")
    parser.add_argument("--key", default=os.getenv("AMAP_KEY", ""), help="高德 API Key（也可设置 AMAP_KEY 环境变量）")
    parser.add_argument("--full", action="store_true", help="包含未来三天预报")
    args = parser.parse_args()

    if not args.key:
        print("❌ 未提供 API Key，请通过 --key 或环境变量 AMAP_KEY 设置")
        print("   申请地址: https://console.amap.com/dev/key/app")
        sys.exit(1)

    extensions = "all" if args.full else "base"
    result = get_weather(args.city, args.key, extensions)
    print(format_weather(result, extensions))


if __name__ == "__main__":
    main()
