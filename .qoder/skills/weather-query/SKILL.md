---
name: weather-query
description: 查询任意城市的天气信息。当用户询问"今天天气"、"明天天气"、"北京天气"、"上海天气怎么样"等天气相关问题时触发。
---

# 天气查询

## 使用方式

```bash
# 查询实况天气
python scripts/query_weather.py "城市名"

# 查询实况 + 未来三天预报
python scripts/query_weather.py "城市名" --full

# 指定 API Key
python scripts/query_weather.py "北京" --key 你的高德API密钥

# 或者通过环境变量
export AMAP_KEY=你的高德API密钥
python scripts/query_weather.py "北京"
```

## 获取 API Key

1. 注册并登录 [高德开放平台](https://console.amap.com/dev/key/app)
2. 创建应用，选择 **Web 服务** 类型
3. 将 Key 填入 `--key` 参数或设置 `AMAP_KEY` 环境变量

## 工作流程

1. 先通过地理编码 API 将城市名转为 adcode（高德内部城市编码）
2. 再通过天气 API 查询对应 adcode 的天气
3. 格式化输出：省份、城市、天气、温度、风向、湿度、更新时间、预报

## 注意事项

- 需要高德地图 **Web 服务**类型 Key，Android/iOS 类型 Key 无法使用
- 有日调用量限制，商业使用需申请更高配额
