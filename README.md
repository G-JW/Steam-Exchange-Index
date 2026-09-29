# Steam Exchange Index

一个用于观察 CS2 饰品“挂刀”水平的个人指数工具。程序从 CSQAQ 获取 BUFF、悠悠有品和 Steam 行情，计算 I5、I10、I20，保存每日历史，并通过 ntfy 发送日报与低位提醒。

当前稳定版本：**v1.0.0**

> 本项目输出的是依据当前数据源、过滤条件和算法生成的个人参考指标，不是 Steam 官方指数，也不构成交易建议。

## v1.0 功能

- 启动采集前自动调用 CSQAQ `bind_local_ip`，适应 GitHub 托管 Runner 的动态出口 IP。
- 同时比较 BUFF 和悠悠有品价格，选择每件饰品更低的挂刀比例。
- 计算覆盖市场价值 5%、10%、20% 的 I5、I10、I20。
- 每日数据写入 `data/index_history.csv`，同一天重复运行会覆盖当天记录。
- 每次成功运行均向 ntfy 日志频道发送三个指数。
- 只有当前 I10 同时优于过去 30 天和 180 天中 90% 的记录时，才向特别提醒频道额外推送。
- 支持 GitHub Actions 定时运行和手动运行。
- 包含自动化测试与 macOS 本地一键运行脚本方案。

## 指数如何计算

每件饰品在某个平台的挂刀比例为：

```text
平台最低售价 / (Steam 最高求购价 × Steam 到账系数)
```

程序执行以下步骤：

1. 计算 BUFF、悠悠有品各自的挂刀比例，并选择较低者。
2. 使用 `BUFF 售价 × BUFF 在售数量` 估算该饰品的市场价值。
3. 过滤成交量、价格、比例、求购量和在售量不符合配置的记录。
4. 按挂刀比例从低到高排序，并累计市场价值。
5. I5、I10、I20 分别是累计覆盖总市场价值 5%、10%、20% 时，已选饰品按市场价值加权的平均挂刀比例；跨过边界的最后一件饰品会完整计入。

指数越低，表示样本中高流动性饰品相对 Steam 求购价越便宜。v1.0 固定使用 I10 作为历史位置与特别提醒的主指标。

## 安装

需要 Python 3.12：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

复制环境变量示例并填入自己的凭据：

```bash
cp .env.example .env
```

项目不会自动读取 `.env`。在终端中可这样加载并运行：

```bash
set -a
source .env
set +a
python main.py
```

必需环境变量：

| 变量 | 用途 |
|---|---|
| `CSQAQ_API_TOKEN` | 调用 CSQAQ API，并在采集前绑定当前出口 IP |
| `NTFY_DAILY_URL` | 每次成功运行后的日报频道，可填 topic 名或完整 HTTPS URL |
| `NTFY_ALERT_URL` | 特别提醒频道；未设置时回退到日报频道 |

macOS 本地可以创建并双击根目录下的 `run_local.command`。本机现有脚本已被 `.gitignore` 排除，其中的明文凭据不会被提交，也不会进入 Release。

## 常用命令

```bash
# 运行
python main.py

# 使用另一份配置
python main.py --config /path/to/config.yaml

# 查看版本
python main.py --version

# 运行测试
python -m pytest -q
```

## 配置说明

非敏感配置集中在 `config.yaml`：

| 配置段 | 作用 |
|---|---|
| `data_source` | API 地址、IP 绑定、超时、请求间隔、重试和最大页数 |
| `platforms` | 参与比较的平台，目前支持 `BUFF`、`YYYP` |
| `steam.net_rate` | Steam 出售后的实际到账系数，默认 `0.869` |
| `filters` | 成交量、价格、比例、求购量、平台在售量过滤 |
| `index.percentiles` | 需要计算的市场价值覆盖比例 |
| `index.min_valid_items` | 允许计算指数的最少有效饰品数 |
| `history` | 移动平均和历史位置窗口 |
| `notification` | 是否通知及特别提醒所需历史百分位 |
| `top_items` | 控制台展示的低比例候选数量 |

默认筛选要求 Steam 当日成交量严格大于 100。`request_interval_seconds` 默认是 1 秒，用于降低连续请求对 CSQAQ API 的压力。

## ntfy 通知规则

每次指数成功计算并保存后，日报频道都会收到一条消息，正文只包含客观数据：

```text
I5 = 0.7223
I10 = 0.7543
I20 = 0.7913
```

当且仅当当前 I10 的 `p30 >= 90` 且 `p180 >= 90` 时，再向特别提醒频道发送相同三个数值。180 天完整历史不足时，不会触发特别提醒。v1.0 没有固定数值阈值、提醒分级或冷却时间。

## 历史数据

`data/index_history.csv` 每天保留一行：

| 字段 | 含义 |
|---|---|
| `date` | 北京时间日期 |
| `run_timestamp` | 带时区的实际运行时间 |
| `index_5` / `index_10` / `index_20` | 当日三个挂刀指数 |
| `valid_items` | 通过校验和过滤的饰品数 |
| `min_ratio` | 当日样本中的最低挂刀比例 |
| `ma7` / `ma30` | 包含当日在内的 I10 移动平均；样本不足时留空 |
| `p30` / `p180` | 当前 I10 优于对应历史窗口中记录的百分比；当天不参与比较 |

## GitHub Actions

工作流位于 `.github/workflows/daily.yml`，每天 UTC 15:40（北京时间约 23:40）自动运行，也可以在 Actions 页面手动触发。

仓库需要配置以下 Actions Secrets：

- `CSQAQ_API_TOKEN`
- `NTFY_DAILY_URL`
- `NTFY_ALERT_URL`

工作流会安装依赖、运行测试、计算指数，并在 `data/` 发生变化时提交 `data: update daily exchange index`。运行环境固定为 Ubuntu 24.04 和 Python 3.12。

## 退出状态

| 状态码 | 含义 |
|---|---|
| `0` | 指数、历史数据和通知均成功 |
| `1` | 配置、采集、校验或计算失败；不写入无效结果 |
| `2` | 指数已成功保存，但 ntfy 通知失败 |

## 安全说明

- Token 和 ntfy 私有 topic 只能放在本地忽略文件或 GitHub Actions Secrets 中。
- `.env`、虚拟环境和 `run_local.command` 已被 Git 忽略。
- 日志会对已知凭据进行脱敏，但仍应避免公开完整运行日志和私有 topic。
- 发布 Release 前应确认 `git status --ignored`，防止本地脚本被意外跟踪。

## 进一步阅读

项目结构、每个文件的职责、数据流和常见修改入口见 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)。

## 已知限制

- 数据完整性、刷新时间和接口可用性取决于 CSQAQ。
- GitHub Actions 的定时任务可能延迟。
- 市场价值目前固定使用 BUFF 售价和 BUFF 在售数量估算。
- 项目不保存单品历史，也不会执行购买、出售或其他自动交易。
