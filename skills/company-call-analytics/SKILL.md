---
name: company-call-analytics
description: Use when a user asks which phone number has the most calls for a company today or requests a daily company call-volume ranking.
metadata:
  author: OpenCat
version: 1
---

# 企业今日通话号码分析

用于查询指定企业在某个业务日期内，通话次数最多的号码。

## 数据表

首次使用或需要确认字段关系时，先阅读 [references/schema.sql](references/schema.sql)：

- `companies`：企业信息。
- `phone_numbers`：企业号码，一个企业可以有多个号码。
- `call_records`：通话记录，关联企业和号码，并保存开始时间、方向、时长和状态。

## 查询规则

1. 从用户问题中提取企业名称；名称不明确或存在多个匹配时，先让用户确认。
2. “今天”按业务日期处理。脚本默认使用运行环境的本地日期；跨时区场景必须显式传入 `--date YYYY-MM-DD`。
3. 默认只统计 `status = 'completed'` 的通话记录，不把未接、取消或失败记录算作已完成通话。
4. 按号码 `COUNT(*)` 统计通话次数，返回第一名的所有并列号码，不要只丢弃并列结果。
5. 结果至少说明企业、日期、号码、号码标签和通话次数；没有记录时明确返回“当天没有已完成通话”。

## 执行方式

SQLite 数据库使用脚本查询，避免把用户输入直接拼接进 SQL：

```bash
python skills/company-call-analytics/scripts/query_today_top_number.py \
  --db data/calls.db \
  --company "星河科技" \
  --date 2026-08-18
```

脚本输出 JSON。若只需要查看 SQL 或迁移表结构，使用 `references/schema.sql`；不要为了回答一次查询修改业务数据。

本项目的可复现测试库已使用 [references/demo_data.sql](references/demo_data.sql) 初始化到 `data/calls.db`。这只是演示数据，接入真实数据库时不要执行该种子文件。

## 注意事项

- 企业名称按精确匹配查询；不能根据模糊名称擅自选择企业。
- `started_at` 使用 ISO-8601 字符串，日期筛选按字符串中的业务日期部分执行；导入 UTC 数据前先转换到业务时区。
- 查询结果为空、数据库不存在或表结构不完整时，要报告具体原因，不要猜测号码。