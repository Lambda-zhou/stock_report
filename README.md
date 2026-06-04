# AI Codex Stock Daily Report 

宁在春

> 一段简单的提示词，仅供参考。 虽然提示词中给定了几个数据源参考，但是codex实际拿到的大部分是新浪财经的数据，其他获取好像会失败。可以再进行微调进行重试。如果要非常详细的数据，还是需要具体的api才行。此案例中使用的均是公开数据。

注意点：目前还没有评测每次跑可能会消耗多少额度，大家自行评测。

## 效果
![alt text](image.png)

![alt text](image-2.png)

![alt text](image-3.png)


## 完整提示词
1、完整提示词可以查看 README_PROMPT.md 文档

2、具体的脚本可以查看python 文件


## codex 总结

下面是让codex自己总结的：



在当前工作区复用现有稳定脚本生成当日 A 股日报，不要在正常执行中重新编写、重构或临时拼接代码。

执行命令：
午盘日报：python generate_a_share_daily.py --mode midday --json --output-dir ga_out
收盘日报：python generate_a_share_daily.py --mode close --json --output-dir ga_out

生成目标：
午盘：ga_out/A股午盘日报_YYYY-MM-DD.html
收盘：ga_out/A股收盘日报_YYYY-MM-DD.html
状态文件：ga_out/result.json（供 GitHub Actions summary / 飞书通知读取）

生成前先确认报告日期为北京时间当天；如当天不是 A 股交易日，按脚本逻辑生成非交易日观察简报。

报告关注方向保持精简，重点跟踪：
科技硬件 / AI 算力、通信设备 / 光模块、互联网软件 / 信创、有色金属 / 黄金、资源能源 / 高股息、电力 / 电网、化工材料、银行 / 国债。

数据原则：
优先复用脚本内已实现的数据源与清洗逻辑，包括行情数据、市场宽度、人民币中间价、央行公开市场操作、交易所 / 巨潮 / 主流行情终端可得信息。
不得编造数据。
无法稳定获取的数据保留为“暂无可靠数据”。
午盘阶段部分收盘后才披露的数据，可显示“等待收盘后披露”或“暂无可靠数据”。
不要恢复大量空表或无参考价值字段。

生成后必须做质量校验：
1. 确认 HTML 文件存在。
2. 确认标题和正文日期为当天。
3. 确认 JSON 输出中的 data_completeness >= 90；收盘日报优先要求 >= 95。
4. 检查文件中不得出现过期硬编码日期或旧数据字符串，例如旧报告日期、历史成交额、旧汇率、旧政策新闻等。
5. 确认关键字段已尽量填充：全 A 涨跌家数、人民币中间价、央行逆回购信息、主要指数、关注主线表现。
6. 统计“暂无可靠数据”的数量，并列出关键缺失项。

失败处理：
如果脚本退出非 0、文件不存在、data_completeness < 90、发现旧数据残留，等待 3-5 分钟后重跑一次。
若第二次仍失败，不要伪装成功；输出失败原因、成功获取的数据、缺失模块和下一步修复建议。
只有在明确是数据源接口变更或脚本错误导致失败时，才进行最小代码修复，并再次运行校验。

最终输出：
文件路径、生成时间、data_completeness、校验是否通过、剩余关键缺失字段。

## GA 推荐调用方式

面向 GenericAgent / 自动化场景，建议统一通过 `generate_a_share_daily.py` 调用，而不是分别直接运行午盘/收盘脚本。

### 基本命令

```bash
# 午盘
python generate_a_share_daily.py --mode midday --json --strict --output-dir ga_out

# 收盘
python generate_a_share_daily.py --mode close --json --strict --output-dir ga_out

# 自动模式（15:00前午盘，15:00后收盘）
python generate_a_share_daily.py --mode auto --json --strict --output-dir ga_out
```

### 参数说明

- `--mode {auto,midday,close}`：选择报告模式
- `--date YYYY-MM-DD`：显式指定报告日期；格式错误时返回错误 JSON 且退出码为 1
- `--output-dir PATH`：输出目录；不存在会自动创建
- `--json`：输出结构化 JSON，便于 GA 读取
- `--strict`：启用严格校验

### 严格校验口径

- 午盘：`data_completeness >= 90`
- 收盘：`data_completeness >= 95`
- 同时要求：
  - HTML 文件实际存在
  - 报告日期出现在正文中
  - 关键质量检查项通过（指数 / 宽度 / 汇率 / 逆回购 / 主线 / 数据来源）

### 退出码约定

- `0`：生成成功，且校验通过
- `1`：运行异常，例如日期格式错误、抓取过程抛异常
- `2`：脚本运行完成，但严格校验未通过

### JSON 输出关键字段

- `status`：`success` / `error`
- `mode`：实际执行模式
- `mode_requested`：请求模式
- `report_date`：报告日期
- `output_path`：HTML 输出路径
- `data_completeness`：完整度分数
- `data_quality`：底层质量检查结果
- `validation.ok`：是否通过当前校验
- `validation.failed_checks`：失败检查列表
- `validation.summary`：校验摘要

### 推荐校验流程

1. 先读取退出码
2. 再读取 JSON 中的 `status`
3. 若 `status == success`，继续核对：
   - `validation.ok == true`
   - `data_completeness` 达到对应阈值
   - `output_path` 指向的 HTML 文件存在
4. 如失败，优先保留原始 JSON / stderr 作为排障依据

## GitHub Actions 自动运行

仓库已新增 `.github/workflows/daily-report.yml`，可直接在 GitHub Actions 中运行，也支持工作日定时触发。

### Workflow 特性

- 手动触发 `workflow_dispatch`
- 工作日定时执行：
  - `35 4 * * 1-5`：北京时间 12:35 左右，适合午盘
  - `15 8 * * 1-5`：北京时间 16:15 左右，适合收盘
- 自动安装 `requirements.txt` 中依赖
- 统一通过 `generate_a_share_daily.py` 生成报告
- 将 `ga_out/` 与运行摘要作为 artifact 上传
- 预留飞书机器人通知步骤

### 手动触发参数

- `mode`：`auto` / `midday` / `close`
- `report_date`：可选，格式 `YYYY-MM-DD`
- `strict`：是否启用严格校验
- `upload_artifact`：是否上传产物

### GitHub Secrets 配置

如需启用飞书通知，请在仓库 `Settings -> Secrets and variables -> Actions` 中添加：

- `FEISHU_WEBHOOK_URL`：飞书机器人的 webhook 地址

未配置该 Secret 时，workflow 不会失败，通知脚本会自动输出 `missing webhook` 并跳过发送。

### 飞书通知脚本

新增脚本：`notify_feishu.py`

用途：
- 读取 `ga_out/result.json`
- 自动拼装任务状态、报告日期、完整度、校验摘要
- 将 GitHub Actions 运行链接一并发送到飞书

本地 dry-run 示例：

```bash
python notify_feishu.py --status-file ga_out/result.json --dry-run
```

实际发送示例：

```bash
python notify_feishu.py \
  --webhook "$FEISHU_WEBHOOK_URL" \
  --status-file ga_out/result.json \
  --workflow-url "https://github.com/<owner>/<repo>/actions/runs/<run_id>"
```

### 推荐仓库文件

最小 GitHub Actions 运行集合如下：

```text
generate_a_share_daily.py
generate_a_share_midday_report.py
generate_a_share_report.py
requirements.txt
notify_feishu.py
.github/workflows/daily-report.yml
```

### 上线建议

1. 先在本地执行 `midday` / `close` 两种模式确认输出正常
2. 再在 GitHub Actions 手动触发一次 `workflow_dispatch`
3. 最后补充 `FEISHU_WEBHOOK_URL` Secret，验证飞书消息格式
4. 如后续需要对外展示 HTML，可再增加 GitHub Pages 或对象存储发布步骤

