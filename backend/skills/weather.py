"""
天气查询技能
调用高德地图API查询城市天气
"""
import os
import requests
from pathlib import Path

SKILL_NAME = "天气查询"
SKILL_DESCRIPTION = "查询任意城市的天气信息（需要配置高德API密钥）"
SKILL_TRIGGER = ["天气", "温度", "下雨", "晴天", "预报", "几度"]

# 加载 .env 环境变量
dotenv_path = Path(__file__).resolve().parents[2] / ".env"
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


def _get_adcode(city: str, key: str) -> str:
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
    for d in districts:
        if d.get("level") == "city":
            return d["adcode"]
    return districts[0]["adcode"]


def _get_weather(city: str, key: str, extensions: str = "base") -> dict:
    """查询天气"""
    adcode = _get_adcode(city, key)
    if not adcode:
        return {"error": f"未找到城市: {city}"}

    resp = requests.get(WEATHER_URL, params={
        "city": adcode,
        "key": key,
        "extensions": extensions,
        "output": "JSON",
    }, timeout=10)
    return resp.json()


def _format_weather(data: dict, extensions: str = "base") -> str:
    """格式化天气数据"""
    if "error" in data:
        return f"查询失败: {data['error']}"

    lines = []
    lives = data.get("lives", [])
    if lives:
        for live in lives:
            lines.append(f"📍 {live['province']} {live['city']}")
            lines.append(f"🌤️ 天气: {live['weather']}")
            lines.append(f"🌡️ 温度: {live['temperature']}°C")
            lines.append(f"💨 风向: {live['winddirection']} {live['windpower']}级")
            lines.append(f"💧 湿度: {live['humidity']}%")
            lines.append(f"🕐 更新时间: {live['reporttime']}")

    forecasts_list = data.get("forecasts", [])
    if forecasts_list:
        forecast_data = forecasts_list[0]
        week_map = {"1": "周一", "2": "周二", "3": "周三", "4": "周四", "5": "周五", "6": "周六", "7": "周日"}
        lines.append("\n📅 未来天气预报:")
        for day in forecast_data.get("casts", [])[:3]:
            lines.append(
                f"  {day['date']} {week_map.get(day['week'], '周' + day['week'])}: "
                f"白天{day['dayweather']} {day['daytemp']}°C → "
                f"夜间{day['nightweather']} {day['nighttemp']}°C"
            )

    if not lines:
        return "未查到天气数据"

    return "\n".join(lines)


def run(city: str = "北京"):
    """
    查询城市天气
    
    参数:
        city: 城市名称，如北京、上海、杭州
    
    返回:
        str: 天气信息文本
    """
    # 清除代理环境变量
    os.environ.pop('all_proxy', None)
    os.environ.pop('ALL_PROXY', None)
    
    key = os.getenv("AMAP_KEY", "")
    if not key:
        return "⚠️ 未配置高德API密钥，请在 backend/.env 中设置 AMAP_KEY=你的密钥"
    
    result = _get_weather(city, key, "all")
    return _format_weather(result, "all")
