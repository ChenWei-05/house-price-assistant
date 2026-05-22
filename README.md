# 房价助手 MVP

基于 `MVP开发文档.md` 搭建的二手房房源追踪 MVP 后端骨架。当前正式应用只接入幸福里公开页面适配器，其他平台适配暂不实现。

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

启动后可访问：

- `GET /health`
- `GET /api/tasks`
- `GET /api/listings`
- `GET /`
- `GET /tasks`：新建幸福里任务、立即采集、跳转查看房源
- `GET /listings`：查看房源列表

## 幸福里任务示例

幸福里的关键词搜索通常依赖站点生成的 `filter_params_url`，建议先从浏览器复制公开搜索页 URL，再创建任务：

```json
{
  "name": "",
  "source": "xingfuli",
  "city": "fz",
  "district": "",
  "keyword": "",
  "filters_json": {
    "url": ""
  },
  "frequency_minutes": 360,
  "enabled": true
}
```

也可以只传：

```json
{
  "filters_json": {
    "city_code": "fz",
    "filter_params_url": "neighborhood_id[]="
  }
}
```
