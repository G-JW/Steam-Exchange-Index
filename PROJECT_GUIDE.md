# Steam Exchange Index v1.0 项目导读

这份文档面向希望理解和修改代码的项目维护者。它按“程序如何运行 → 每个文件负责什么 → 修改需求时从哪里入手”的顺序介绍整个项目。

## 1. 项目结构

```text
Steam Exchange Index/
├── .github/workflows/daily.yml   # GitHub Actions 定时任务
├── data/index_history.csv        # 每日指数历史
├── src/                          # 核心业务代码
│   ├── __init__.py               # 包信息与版本号
│   ├── calculator.py             # I5/I10/I20 计算
│   ├── collector.py              # CSQAQ API 采集
│   ├── config.py                 # YAML 加载与校验
│   ├── filters.py                # 数据转换、比例计算和过滤
│   ├── history.py                # CSV 历史与统计
│   ├── models.py                 # 数据对象定义
│   └── notifier.py               # ntfy 通知
├── tests/                        # 自动化测试
├── .env.example                  # 环境变量示例
├── .gitignore                    # Git 忽略规则
├── config.yaml                   # 非敏感运行配置
├── main.py                       # 命令行入口与流程编排
├── requirements.txt              # 运行依赖
├── requirements-dev.txt          # 开发和测试依赖
├── README.md                     # 使用说明
└── PROJECT_GUIDE.md              # 当前项目导读
```

本地还有一个 `run_local.command` 一键运行脚本。它可能包含明文 Token 和私有 ntfy topic，因此被 Git 忽略，不属于仓库或 Release 的内容。

## 2. 一次运行的完整流程

`main.py` 中的 `run()` 是总入口：

1. `src.config.load_config()` 读取并校验 `config.yaml`。
2. 从环境变量读取 `CSQAQ_API_TOKEN`。
3. `src.collector.fetch_items()` 先绑定当前出口 IP，再分页请求行情。
4. `src.filters.enrich_and_filter()` 将 API 原始记录转换为内部对象，计算比例并执行过滤。
5. `src.calculator.calculate_indexes()` 计算 I5、I10、I20。
6. `src.history.load_history()` 和 `calculate_statistics()` 计算 I10 的移动平均及历史位置。
7. `src.history.upsert_history()` 将当天结果写入 CSV；同日运行会替换旧记录。
8. 在终端打印摘要和低比例候选。
9. `send_notifications()` 发送每日日报；符合历史低位条件时再发送特别提醒。

配置、采集或计算失败时，程序返回 `1`。指数保存之后如果仅通知失败，返回 `2`，这样不会因为推送服务故障而丢失已经算出的数据。

## 3. 根目录文件

### `main.py`

程序的命令行入口，只负责组织各模块，不承载具体算法。

重要内容：

- `ROOT`、`HISTORY_PATH`：定位配置与历史文件。
- `PRIMARY_PERCENTILE = 0.10`：明确 I10 是 v1.0 的主指标。
- `parse_args()`：处理 `--config` 和 `--version`。
- `print_summary()`：向终端输出本次结果。
- `send_notifications()`：固定发日报，并按 p30/p180 判断特别提醒。
- `run()`：串联配置、采集、过滤、计算、保存和通知。

如果要改变整体执行顺序或命令行参数，应从这里开始；具体算法应继续保留在 `src/` 对应模块中。

### `config.yaml`

保存所有适合进入版本控制的非敏感配置。

- `data_source` 控制 API 地址、自动绑定 IP、超时、请求间隔、重试次数和分页上限。
- `platforms` 决定比较 BUFF、悠悠中的哪些平台。
- `steam.net_rate` 是 Steam 售出后的到账系数。
- `filters` 中每个过滤器都有 `enabled` 开关。
- `index.percentiles` 决定计算哪些指数，`min_valid_items` 防止样本过少。
- `history` 定义移动平均和历史百分位窗口。
- `notification.special_percentile` 默认 90，表示两个历史窗口都要达到 90%。
- `top_items` 只影响终端候选展示，不影响指数。

敏感值不能写进这个文件。

### `data/index_history.csv`

项目的持久化数据。每个北京时间日期最多一行，字段顺序由 `src/history.py` 的 `FIELDNAMES` 定义。GitHub Actions 会在内容变化后提交这个文件，所以主分支会保留可审计的每日历史。

不要手动改变表头；如需增加字段，应同步修改：

1. `FIELDNAMES`；
2. `make_history_row()`；
3. 读取或迁移逻辑；
4. 相应测试和 README。

### `.github/workflows/daily.yml`

GitHub Actions 工作流。它具有 `contents: write` 权限，以便把新的 CSV 数据提交回仓库。

主要步骤：

1. 检出代码；
2. 安装 Python 3.12 和依赖；
3. 运行全部测试；
4. 从 Actions Secrets 注入凭据并执行 `main.py`；
5. 只有 `data/` 有变化时才提交和推送。

`concurrency` 防止两个定时任务同时修改历史文件；`timeout-minutes` 防止网络异常导致任务无限等待。

### `requirements.txt` 与 `requirements-dev.txt`

`requirements.txt` 是程序运行所需依赖。`requirements-dev.txt` 在其基础上增加 pytest 等开发工具，GitHub Actions 和本地开发均安装后者。

增加依赖时应说明用途并尽量保持依赖最小化。

### `.env.example`

只列出环境变量名字，不包含真实值。它帮助新环境了解需要哪些 Secrets。实际 `.env` 已被 `.gitignore` 排除，而且程序不会自动加载它。

### `.gitignore`

排除凭据文件、虚拟环境、Python 缓存、测试缓存和本地一键运行脚本。修改本地运行方式时，应再次确认含凭据文件仍在忽略列表中。

### `README.md`

面向使用者，说明安装、算法、配置、通知和自动化操作。行为改变后应优先同步 README，避免代码和使用说明不一致。

### `PROJECT_GUIDE.md`

面向代码学习和维护，也就是当前文件。新增模块或改变模块边界时，应更新结构树和职责说明。

## 4. `src/` 核心模块

### `src/__init__.py`

把 `src` 标记为 Python 包，并集中定义 `__version__ = "1.0.0"`。`python main.py --version` 会读取这里的版本号。以后发布新版本时，应同时更新版本号和 Release 标签。

### `src/models.py`

定义一个 `MarketItem` dataclass。对象先保存从 API 标准化得到的行情字段，经过过滤层后，同一个对象会补充最佳平台、挂刀比例和市场价值等派生字段，再交给指数计算层使用。

数据对象让模块之间的输入输出更明确，避免在业务代码中到处读取含义不清的字典键。

### `src/config.py`

负责读取 YAML，并在网络请求开始前发现配置错误。

- `ConfigError`：统一的配置异常。
- `_require()`：检查必需字段和类型；整数配置会拒绝 Python 中看似整数的布尔值。
- `load_config()`：校验平台、过滤范围、百分位、窗口和正数/非负数限制。

新增配置项时，不应只修改 YAML，还应在这里补充类型和取值范围校验，并在 `tests/test_config.py` 添加测试。

### `src/collector.py`

负责所有 CSQAQ 网络通信。

- 创建带重试策略的 `requests.Session`。
- `bind_local_ip` 开启时，先调用绑定接口，把当前 Runner 出口 IP 加入 Token 白名单。
- 按页请求行情，直到 API 表示没有下一页。
- 在绑定后及分页之间按配置等待，避免请求过密。
- 对 HTTP、JSON、API 状态和分页上限异常统一抛出 `CollectionError`。

如果 CSQAQ 的地址、认证方式或响应结构变化，主要修改这里和 `tests/test_collector.py`。

### `src/filters.py`

这是从“API 数据”到“可计算样本”的转换层。

它会：

- 安全地把字符串或空值转换成数字；
- 校验价格、数量等基础字段；
- 分别计算 BUFF、悠悠挂刀比例；
- 选择启用平台中比例最低的平台；
- 使用 BUFF 售价和 BUFF 在售数量计算市场价值；
- 执行 `config.yaml` 中启用的各项过滤。

未通过解析、缺少关键值或触发过滤的记录都会计入 `skipped`，不会中断整批任务。

### `src/calculator.py`

实现指数核心算法。

- `calculate_indexes()`：按比例升序排列，累计市场价值，并对每个目标覆盖比例计算加权平均。
- `top_items()`：返回比例最低的前 N 个候选，仅用于终端展示。
- `CalculationError`：样本为空、市场价值无效或缺少目标指数时使用。

边界规则很重要：使累计价值跨过目标的最后一件饰品会完整计入，不会按剩余价值切片。

### `src/history.py`

管理 CSV 和基于 I10 的时间序列统计。

- `load_history()`：读取历史并兼容旧字段。
- `calculate_statistics()`：计算 ma7、ma30、p30、p180。
- `make_history_row()`：把本次结果格式化成 CSV 行。
- `upsert_history()`：按日期插入或替换，并保证日期顺序。

历史百分位只比较当前日之前的记录。这里的百分比越高，表示当前指数低于越多历史记录，也就是相对更有关注价值。

### `src/notifier.py`

封装 ntfy 通信和提醒判断。

- `resolve_ntfy_target()`：接受裸 topic 或完整 HTTPS URL，并生成安全的发布目标。
- `format_message()`：只生成 I5、I10、I20 三行客观数据。
- `is_special_alert()`：要求 p30、p180 都存在且达到门槛。
- `post_ntfy()`：向 ntfy 根 API 发送 UTF-8 JSON，避免中文标题被错误编码；异常信息会隐藏目标地址和已知敏感值。

通知失败不会撤销已经保存的指数。

## 5. `tests/` 测试文件

### `tests/conftest.py`

提供项目根目录、基础配置等复用 fixture，减少各测试文件的重复准备代码。

### `tests/test_calculator.py`

验证加权平均、多个覆盖比例、边界饰品完整计入、候选排序以及异常输入。

### `tests/test_collector.py`

使用模拟 HTTP 响应验证 IP 绑定、分页、认证参数、请求失败和数据合并，不会访问真实 CSQAQ API。

### `tests/test_config.py`

验证合法配置能够加载，同时拒绝平台重复、范围错误、缺少关键指数、非法窗口和非整数数量等配置。

### `tests/test_history.py`

验证同日覆盖、日期排序、移动平均、历史百分位、样本不足和旧 CSV 字段迁移。

### `tests/test_notifier.py`

验证 ntfy topic/URL 解析、UTF-8 JSON 格式、三个指数的正文、特别提醒条件以及错误消息脱敏。

## 6. 常见修改从哪里开始

| 需求 | 主要文件 | 需要同步检查 |
|---|---|---|
| 调整成交量或比例范围 | `config.yaml` | README 中的默认规则 |
| 新增过滤条件 | `src/filters.py`、`src/config.py` | YAML、配置测试、过滤测试 |
| 改指数算法 | `src/calculator.py` | 算法测试、README 算法说明 |
| 改主指标 | `main.py` | 历史语义、提醒语义、README |
| 改历史字段 | `src/history.py` | CSV、迁移、历史测试、文档 |
| 改通知格式或规则 | `src/notifier.py`、`main.py` | 通知测试、Secrets 文档 |
| API 响应变化 | `src/collector.py`、`src/filters.py` | 采集测试、数据模型 |
| 改定时运行时间 | `.github/workflows/daily.yml` | README 中的北京时间 |
| 发布新版本 | `src/__init__.py` | README 版本、Git 标签与 Release |

## 7. 建议的维护流程

1. 在本地创建分支或直接修改工作区。
2. 运行 `python -m pytest -q`。
3. 使用本地一键脚本做一次真实 API 验证。
4. 检查 `git diff`，确认没有 Token、私有 topic 或本地文件。
5. 提交并推送到 GitHub。
6. 手动运行一次 GitHub Actions，确认云端 IP 绑定、通知和 CSV 提交均正常。
7. 版本发布时，再创建与 `src.__version__` 一致的 GitHub Release。

## 8. v1.0 的范围边界

v1.0 专注于稳定地产生一个可长期观察的个人指数。它不会保存每件饰品的历史、生成网页图表、自动交易，也不会尝试复刻任何未公开的第三方指数算法。保持这个边界可以让采集、计算和提醒逻辑更容易验证与维护。
