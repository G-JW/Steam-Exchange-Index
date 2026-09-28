# PLAN.md

## 1. Goal

实现一个个人使用的 Steam 挂刀指数监控工具，用于每天自动评估高流动性饰品的整体挂刀折扣水平，并在指数进入较低区间时通过 ntfy 发送提醒。

当前版本采用：

- Python
- CSQAQ 挂刀行情数据
- CSV 历史记录
- GitHub Actions 定时执行
- ntfy 通知

最终每天得到：

- `I5`
- `I10`
- `I20`
- 当日有效饰品数量
- 当前最低挂刀比例
- Top N 挂刀候选
- 基于历史数据计算的移动均值和历史位置（数据足够时）

其中 `I10` 为主要参考指标。

---

# 2. Scope & Requirements

## 2.1 Must Have

### 数据采集

使用 CSQAQ 挂刀行情 API 获取当前饰品行情。

首版默认关注：

- BUFF
- 悠悠有品 / YYYP
- Steam 求购价格
- Steam 当日成交量

如果 CSQAQ 实际接口返回字段或鉴权方式与当前预期不同，Codex 应首先根据实际 API 文档和返回结果调整数据适配层，不改变上层计算逻辑。

### 饰品筛选

当前唯一确定的主要流动性条件：

```text
Steam 当日成交量 > 100
```

注意：

- 使用当天累计成交量。
- 不计算 7 日、30 日等平均成交量。
- 默认 GitHub Actions 在北京时间约 `23:40` 执行，以尽量获得接近完整的当日成交数据。
- 成交量阈值必须配置化。

还需支持以下可配置过滤条件，但默认可关闭：

- 饰品价格上下限
- 挂刀比例上下限
- Steam 求购数量下限
- 第三方平台在售数量下限

### 挂刀比例

对饰品 `i` 在平台 `p`：

\[
R_{i,p}
=
\frac{P_{i,p}}
{P^{SteamBuy}_i \times C_{steam}}
\]

其中：

- \(P_{i,p}\)：第三方平台最低有效买入价格
- \(P^{SteamBuy}_i\)：Steam 当前最高求购价格
- \(C_{steam}\)：Steam 实际到账系数
- 默认 `C_steam = 0.869`

同一个饰品存在多个第三方平台时：

\[
R_i = \min_p(R_{i,p})
\]

同时记录产生最低比例的平台 `best_platform`。

### 挂刀指数

至少计算：

```text
I5
I10
I20
```

分别对应最低挂刀比例商品累计覆盖市场价值：

```text
5%
10%
20%
```

的市值加权平均挂刀比例。

`I10` 为主指数。

### 市场价值

首版使用：

\[
V_i
=
P^{BUFF}_i
\times
Q^{BUFF}_i
\]

其中：

- \(P^{BUFF}_i\)：BUFF 当前参考出售价格
- \(Q^{BUFF}_i\)：BUFF 当前在售数量

如果某个饰品缺少计算市场价值必需的 BUFF 数据，则不得参与指数计算。

### 指数计算

1. 对所有通过过滤的饰品计算 \(R_i\) 和 \(V_i\)。
2. 删除无效数据。
3. 按 `R_i` 从低到高排序。
4. 计算全部有效商品市场价值：

\[
V_{total}=\sum_i V_i
\]

5. 对目标比例 \(q\)，从最低 `R_i` 开始累计市场价值，直到覆盖：

\[
q \times V_{total}
\]

6. 对选中的商品按市场价值加权：

\[
I_q=
\frac{\sum_iR_iV_i}
{\sum_iV_i}
\]

分别得到：

```text
I5
I10
I20
```

边界商品如果使累计市值越过目标值，首版允许整个商品纳入计算，不要求拆分边界商品市值。

### 历史记录

长期仅保存每天的指数级历史数据。

使用：

```text
data/index_history.csv
```

不得为了当前需求长期保存所有饰品的每日历史。

建议 Schema：

```csv
date,run_timestamp,index_5,index_10,index_20,valid_items,min_ratio,ma7,ma30,p30,p90,p365
```

其中历史数据不足时，相应统计字段留空。

同一天重复执行时必须保持幂等：

- 默认覆盖该日期已有记录
- 不得为同一天生成多条重复历史记录

### Top 挂刀候选

每次运行从最终有效商品中按挂刀比例升序输出 Top N。

至少包含：

```text
name
ratio
best_platform
platform_price
steam_buy_price
today_volume
```

Top N 数量配置化。

Top N 默认只用于：

- GitHub Actions 日志
- ntfy 提醒内容

无需长期保存完整 Top N 历史。

### 历史统计

当历史数据足够时计算：

```text
MA7
MA30
30 日历史位置
90 日历史位置
365 日历史位置
```

历史位置定义：

> 当前 I10 比指定窗口内多少比例的历史日期更低。

例如：

```text
90 日位置 = 92%
```

表示当前指数低于过去 90 日中约 92% 的记录。

历史样本不足时：

- 不报错
- 返回空值
- 不触发依赖该统计值的提醒规则

### ntfy 通知

通知系统使用 ntfy。

至少支持：

- 固定指数阈值提醒
- 不同阈值对应不同 ntfy priority
- 是否发送每日运行报告
- Top N 挂刀商品
- 可选通知冷却
- 更低级别突破时可绕过冷却

默认通知级别可先配置为：

```yaml
0.73: 值得关注
0.71: 较好机会
0.69: 极低区间
```

这些值只是默认配置，不能硬编码进业务逻辑。

### GitHub Actions

每天北京时间：

```text
23:40
```

自动执行一次。

GitHub Actions cron 使用 UTC，因此默认：

```cron
40 15 * * *
```

同时支持：

```yaml
workflow_dispatch
```

以便手动运行。

Actions 执行结束后，如果：

```text
data/index_history.csv
```

发生变化，则自动 commit 并 push。

---

## 2.2 Configuration

除 API Secret 外的重要行为全部放入：

```text
config.yaml
```

不得散落硬编码在 Python 文件中。

至少支持：

```yaml
data_source:
  provider: csqaq

platforms:
  - BUFF
  - YYYP

steam:
  net_rate: 0.869

filters:
  volume:
    enabled: true
    min_today_volume: 100

  price:
    enabled: false
    min: 1
    max: 5000

  ratio:
    enabled: true
    min: 0.50
    max: 1.00

  steam_buy_orders:
    enabled: false
    min: 0

  platform_sell_orders:
    enabled: false
    min: 0

index:
  percentiles:
    - 0.05
    - 0.10
    - 0.20

  primary: 0.10

  market_value_platform: BUFF

  min_valid_items: 100

history:
  moving_averages:
    - 7
    - 30

  percentile_windows:
    - 30
    - 90
    - 365

notification:
  enabled: true
  provider: ntfy
  daily_report: false

  thresholds:
    - value: 0.73
      label: "值得关注"
      priority: 3

    - value: 0.71
      label: "较好机会"
      priority: 4

    - value: 0.69
      label: "极低区间"
      priority: 5

  cooldown:
    enabled: true
    days: 3

  notify_on_level_upgrade: true

top_items:
  enabled: true
  count: 10
```

配置加载时必须进行基本校验。

无效配置应：

- 明确打印错误
- 返回非零退出码
- 不写入错误历史数据

---

## 2.3 Runtime

目标运行环境：

```text
GitHub Actions Ubuntu
Python 3.12
```

同时应能够在普通本地环境直接运行：

```bash
python main.py
```

不要求：

- Docker
- VPS
- Redis
- PostgreSQL
- Web Server
- 浏览器自动化

---

## 2.4 Error Handling

以下情况不得写入当天指数历史：

- API 请求完全失败
- API 返回结构无法解析
- 有效商品数量低于 `min_valid_items`
- 无有效 Steam 求购价格
- 无法计算市场总价值
- 指数结果为 NaN / Infinity
- 配置文件错误

程序失败时：

- 输出明确错误日志
- 返回非零状态码
- GitHub Actions 应显示失败
- 不产生伪造或默认指数

通知失败与指数计算失败应区分。

如果指数已经成功计算并写入 CSV，但 ntfy 发送失败：

- 保留指数结果
- 记录通知失败
- 可返回非零状态码或 warning，但不得删除成功计算的数据

首版优先简单实现。

---

## 2.5 Non-goals

当前版本明确不实现：

- Web 前端
- 用户账号
- 多用户系统
- 数据库服务器
- Redis
- Docker 部署
- 分钟级实时监控
- BUFF / 悠悠 / Steam 自建爬虫
- Selenium
- Playwright
- Steam 单品长期 K 线
- 所有饰品的长期历史快照
- 自动购买饰品
- 自动交易
- Steam 登录
- BUFF 登录
- 交易机器人
- 盈利计算系统
- 移动端 App

---

# 3. Technical Design

## 3.1 Technology Stack

使用：

```text
Python 3.12
requests
PyYAML
pandas
pytest
GitHub Actions
CSV
ntfy HTTP API
```

如使用标准库可以明显减少依赖，则优先标准库。

不要引入 Web Framework、ORM 或任务队列。

---

## 3.2 Program Flow

```text
main.py
  │
  ├─ 加载 config.yaml
  │
  ├─ 读取环境变量
  │
  ├─ 请求 CSQAQ API
  │
  ├─ 标准化 API 数据
  │
  ├─ 过滤无效 / 低成交量商品
  │
  ├─ 计算每件商品 Ratio
  │
  ├─ 计算市场价值
  │
  ├─ 计算 I5 / I10 / I20
  │
  ├─ 读取历史 CSV
  │
  ├─ 更新当日历史记录
  │
  ├─ 计算 MA / 历史位置
  │
  ├─ 输出运行摘要和 Top N
  │
  └─ 根据配置发送 ntfy
```

---

## 3.3 Internal Data Model

API 数据必须先转换为内部统一格式，再进入计算模块。

建议使用 dataclass 或简单 TypedDict。

单个商品至少包含：

```text
item_id
name

steam_buy_price
steam_buy_num
today_volume

buff_sell_price
buff_sell_num

yyyp_sell_price
yyyp_sell_num

best_platform
best_platform_price

ratio
market_value
```

字段名称不得直接耦合整个计算模块到 CSQAQ 原始 JSON。

只有 collector / adapter 层负责：

```text
CSQAQ JSON -> Internal Item Model
```

---

## 3.4 Data Validation

商品只有满足以下条件才能进入最终计算：

```text
today_volume > configured minimum

steam_buy_price > 0

存在至少一个启用平台价格 > 0

BUFF price > 0

BUFF sell quantity > 0

ratio 为有限正数

market_value > 0
```

如果启用了额外过滤条件，则同时满足相应条件。

缺失单个商品数据时：

- 跳过该商品
- 不终止整个任务
- 在汇总日志显示跳过数量

---

## 3.5 Index Boundary Rules

当前实现使用：

```text
ratio 升序
+
完整商品累计市值
```

例如 10% 阈值被最后一个商品跨过时：

```text
整个商品纳入 I10
```

不进行部分市值切分。

该规则应写入测试，避免未来无意改变。

---

## 3.6 Historical Percentile

对于历史窗口 `N`：

读取当前日期之前最多 N 条有效 `I10`。

定义：

\[
Percentile_N =
\frac{
\#\{I_{historic} > I_{current}\}
}{
N_{valid}
}
\times100
\]

因为挂刀指数越低通常越有利，所以：

```text
值越高 = 当前指数比更多历史日期更低
```

当前日期不得参与自己的历史百分位计算。

---

## 3.7 Notification Rules

通知逻辑首先根据当前 `I10` 找到满足条件的最高提醒等级。

例如：

```text
I10 = 0.705
```

同时满足：

```text
<= 0.73
<= 0.71
```

则只发送：

```text
0.71 较好机会
```

对应等级的通知。

不要发送两个重复通知。

如果：

```text
daily_report = false
```

且没有达到任何提醒条件，则不发送 ntfy。

---

## 3.8 Cooldown

如果开启 cooldown：

保存最少量的通知状态。

建议使用：

```text
data/notification_state.json
```

内容例如：

```json
{
  "last_notification_date": "2026-09-29",
  "last_level": 2,
  "last_index": 0.708
}
```

规则：

- 同一提醒等级在 cooldown 内不重复发送
- 如果当前进入更高级提醒等级，且 `notify_on_level_upgrade=true`，立即通知
- 状态文件不包含任何 secret

如果实现 cooldown 明显增加不必要复杂度，可保持状态文件逻辑简单，不引入数据库。

---

## 3.9 ntfy

ntfy URL 从环境变量读取：

```text
NTFY_URL
```

不得写入：

```text
config.yaml
GitHub workflow
Python source
Git history
```

使用 HTTP POST。

通知建议包含：

```text
Steam 挂刀指数
日期
I5
I10
I20
有效商品数
MA7
MA30
历史位置
Top N 商品
```

历史数据不足时省略对应字段。

通知发送必须设置合理 HTTP timeout。

---

# 4. Repository Structure

修改代码前，Codex 必须首先检查实际仓库。

如果已经存在合理结构：

> 保留已有结构和规范，不要机械重建。

对于全新仓库，推荐最小结构：

```text
.
├── PLAN.md
├── README.md
├── config.yaml
├── requirements.txt
├── main.py
├── src/
│   ├── __init__.py
│   ├── collector.py
│   ├── models.py
│   ├── filters.py
│   ├── calculator.py
│   ├── history.py
│   ├── notifier.py
│   └── config.py
├── tests/
│   ├── test_calculator.py
│   ├── test_filters.py
│   └── test_history.py
├── data/
│   └── index_history.csv
└── .github/
    └── workflows/
        └── daily.yml
```

仅在 cooldown 实现后增加：

```text
data/notification_state.json
```

不要创建没有实际用途的 service / repository / domain 等多层抽象结构。

---

# 5. Configuration & Secrets

## 5.1 config.yaml

非敏感业务参数放在：

```text
config.yaml
```

包括：

| 配置 | 默认值 | 用途 |
|---|---:|---|
| `filters.volume.min_today_volume` | `100` | 最低当日 Steam 成交量 |
| `steam.net_rate` | `0.869` | Steam 到账比例 |
| `index.percentiles` | `[0.05,0.10,0.20]` | 指数范围 |
| `index.primary` | `0.10` | 主指数 |
| `index.min_valid_items` | `100` | 最少有效饰品数量 |
| `top_items.count` | `10` | 通知展示商品数 |
| `notification.daily_report` | `false` | 是否每日推送 |
| `notification.cooldown.days` | `3` | 同级提醒冷却天数 |

所有默认值可通过 `config.yaml` 修改。

---

## 5.2 Environment Variables

敏感信息使用环境变量：

```text
CSQAQ_API_TOKEN
NTFY_URL
```

本地可使用：

```text
.env
```

但 Python 不强制依赖 `python-dotenv`。

如果增加 `.env.example`：

```text
CSQAQ_API_TOKEN=
NTFY_URL=
```

不得提供真实 Secret。

---

## 5.3 GitHub Secrets

GitHub Actions 使用：

```text
CSQAQ_API_TOKEN
NTFY_URL
```

路径：

```text
Repository Settings
→ Secrets and variables
→ Actions
```

---

## 5.4 .gitignore

至少覆盖：

```gitignore
.env
.venv/
venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.DS_Store
```

`config.yaml` 可以提交，因为不得包含 Secret。

`data/index_history.csv` 应提交，以 Git 作为个人历史数据备份。

`notification_state.json` 如果存在，也可提交，以保证 GitHub Actions 跨运行保持 cooldown 状态。

---

# 6. Git & GitHub Workflow

开始开发前：

```text
检查 Git 状态
检查当前 branch
检查 remote
检查现有 commit convention
检查现有 GitHub Actions
```

已有规范优先。

如果为全新个人项目：

```text
主分支：main
开发模式：直接在 main 分阶段提交
```

建议阶段性 commit：

```text
chore: initialize steam exchange index monitor

feat: add market data collection and filtering

feat: calculate exchange indexes

feat: add history and ntfy notifications

ci: add daily exchange index workflow

test: cover index calculation edge cases

docs: add usage documentation
```

不得：

- 提交 Secret
- 把全部开发压成一个最终 commit
- 为微小改动制造大量无意义 commit

---

# 7. Implementation Plan

## Phase 1 — Initialize Project

### Tasks

- [ ] 检查现有仓库结构和 Git 状态。
- [ ] 如果为空仓库，创建最小 Python 项目结构。
- [ ] 添加 `config.yaml`。
- [ ] 添加配置加载与校验。
- [ ] 添加 `.gitignore`。
- [ ] 添加最小 `requirements.txt`。
- [ ] 确保 `python main.py` 可以启动并读取配置。

### Verification

```bash
python main.py
```

能够：

- 正常读取配置
- 缺少必要 Secret 时给出明确错误
- 配置错误时非零退出

### Suggested Commit

```text
chore: initialize project configuration
```

---

## Phase 2 — Data Collection & Normalization

### Tasks

- [ ] 实现 CSQAQ API client。
- [ ] 设置连接和读取 timeout。
- [ ] 加入有限重试。
- [ ] 将 API 返回转换为内部 Item Model。
- [ ] 支持 BUFF + YYYP。
- [ ] 从环境变量读取 CSQAQ Token。
- [ ] 对缺失字段和异常商品安全跳过。
- [ ] 输出原始商品数、解析成功数、跳过数。

### Key Files

```text
src/collector.py
src/models.py
```

### Verification

真实 API 环境下手动运行。

能够输出类似：

```text
Fetched items: 4823
Parsed items: 4701
Skipped invalid: 122
```

不得把 Token 打印进日志。

### Suggested Commit

```text
feat: add csqaq market data collection
```

---

## Phase 3 — Filtering & Exchange Index

### Tasks

- [ ] 实现 `today_volume > min_today_volume`。
- [ ] 实现可选价格过滤。
- [ ] 实现可选 ratio 过滤。
- [ ] 实现可选求购量 / 在售量过滤。
- [ ] 计算多平台 Ratio。
- [ ] 选择最低 Ratio 平台。
- [ ] 计算 BUFF 市场价值。
- [ ] 实现 I5 / I10 / I20 通用算法。
- [ ] 实现有效商品数量检查。
- [ ] 输出 Top N。

### Key Files

```text
src/filters.py
src/calculator.py
```

### Verification

使用人工构造固定数据验证。

例如：

```text
商品 A ratio=0.68 value=10
商品 B ratio=0.70 value=20
商品 C ratio=0.75 value=70
```

确保：

- 排序正确
- 累计市值正确
- 加权平均正确
- 边界商品完整纳入
- 缺失 Steam / BUFF 数据的商品被过滤

### Suggested Commit

```text
feat: calculate configurable exchange indexes
```

---

## Phase 4 — CSV History & Statistics

### Tasks

- [ ] 创建 `data/index_history.csv`。
- [ ] 写入每日 I5 / I10 / I20。
- [ ] 保证同一天幂等更新。
- [ ] 实现 MA7 / MA30。
- [ ] 实现 30 / 90 / 365 日历史位置。
- [ ] 历史不足时返回空值。
- [ ] 不长期保存完整商品快照。

### Key Files

```text
src/history.py
data/index_history.csv
```

### Verification

重复运行同一个日期两次：

```text
CSV 中仍然只有一行该日期记录。
```

构造历史数据验证百分位定义。

### Suggested Commit

```text
feat: persist daily index history and statistics
```

---

## Phase 5 — ntfy Notification

### Tasks

- [ ] 从 `NTFY_URL` 读取通知目标。
- [ ] 根据 I10 判断最高匹配通知等级。
- [ ] 支持 ntfy priority。
- [ ] 支持 `daily_report`。
- [ ] 通知包含 I5 / I10 / I20。
- [ ] 通知包含有效商品数量。
- [ ] 通知包含 Top N。
- [ ] 数据足够时加入 MA 和历史位置。
- [ ] 实现简单 cooldown 状态。
- [ ] 支持更高等级绕过 cooldown。

### Verification

使用测试 ntfy topic 手动运行：

- 正常情况不发通知
- 达到 0.73 阈值发送 priority 3
- 达到 0.71 只发送更高等级
- 达到 0.69 发送 priority 5
- cooldown 生效
- 更高级别突破可以通知

### Suggested Commit

```text
feat: add ntfy threshold notifications
```

---

## Phase 6 — GitHub Actions

### Tasks

创建：

```text
.github/workflows/daily.yml
```

至少：

```yaml
name: Daily Steam Exchange Index

on:
  schedule:
    - cron: "40 15 * * *"
  workflow_dispatch:

permissions:
  contents: write
```

Workflow：

1. checkout
2. setup Python 3.12
3. install dependencies
4. run tests if present
5. execute `python main.py`
6. commit changed `data/`
7. push

Secrets：

```yaml
CSQAQ_API_TOKEN: ${{ secrets.CSQAQ_API_TOKEN }}
NTFY_URL: ${{ secrets.NTFY_URL }}
```

自动 commit：

```text
data: update daily exchange index
```

如果 `data/` 无变化：

```text
正常结束，不创建空 commit。
```

### Verification

使用：

```text
Actions → Run workflow
```

手动触发。

确认：

- API 正常访问
- CSV 正常更新
- Commit 正常生成
- ntfy 正常工作
- Secret 不出现在日志

### Suggested Commit

```text
ci: add daily exchange index workflow
```

---

## Phase 7 — Final Reliability & Documentation

### Tasks

- [ ] 补齐核心算法单元测试。
- [ ] 补齐 API 失败测试。
- [ ] 补齐 CSV 幂等测试。
- [ ] 补齐配置错误测试。
- [ ] 确认无 Secret 进入 Git。
- [ ] 检查 GitHub Actions。
- [ ] 根据最终真实实现编写 README。
- [ ] README 不描述不存在的功能。

### Suggested Commit

```text
test: cover core monitoring workflow
```

最终文档 commit：

```text
docs: add project usage guide
```

---

# 8. Testing & Validation

不追求高覆盖率数字，只测试核心行为。

## 必须测试

### Ratio

验证：

\[
R=
\frac{PlatformPrice}
{SteamBuyPrice \times NetRate}
\]

输入固定值时结果正确。

---

### Multi-platform Selection

例如：

```text
BUFF  ratio = 0.72
YYYP  ratio = 0.70
```

结果：

```text
ratio = 0.70
best_platform = YYYP
```

---

### Volume Filter

配置：

```text
min_today_volume = 100
```

要求：

```text
100 -> 不通过
101 -> 通过
```

因为规则明确为：

```text
> 100
```

而不是：

```text
>= 100
```

---

### Invalid Data

以下商品必须跳过：

```text
Steam Buy = 0
Steam Buy = null
BUFF Sell = 0
BUFF Sell Num = 0
Ratio = NaN
Ratio = Infinity
```

---

### Exchange Index

使用固定小型数据集测试：

- 排序
- 累计市场价值
- 目标百分比
- 边界商品处理
- 加权平均

---

### Minimum Valid Items

如果：

```text
valid_items < min_valid_items
```

程序必须失败。

不得写入历史 CSV。

---

### CSV Idempotency

同一天重复运行：

```text
只能存在一个 date。
```

---

### Historical Percentile

历史数据：

```text
0.75
0.73
0.72
0.70
```

当前：

```text
0.71
```

应按本文档定义正确计算“比多少历史记录更低”。

---

### Notification Levels

确保同一次运行只发送最高匹配等级。

---

# 9. GitHub Actions / Automation

当前项目必须使用 GitHub Actions，因为定时运行是核心需求。

默认：

```text
北京时间 23:40
```

即：

```cron
40 15 * * *
```

同时支持：

```text
workflow_dispatch
```

GitHub Actions 的定时执行可能存在一定延迟。

项目不得假定 cron 会精确到秒或分钟。

如果任务实际延迟跨过北京时间 00:00，日志必须保留实际 API 数据对应的运行时间。

当前版本不为此增加额外复杂补偿机制。

---

# 10. Acceptance Criteria

- [ ] `python main.py` 可以本地运行。
- [ ] CSQAQ API Token 通过环境变量读取。
- [ ] ntfy URL 通过环境变量读取。
- [ ] Secret 未写入代码、配置或 Git 历史。
- [ ] 当前筛选规则默认只保留 `Steam 当日成交量 > 100` 的商品。
- [ ] 成交量阈值可通过 `config.yaml` 修改。
- [ ] 能从 BUFF / YYYP 中选择较低挂刀比例。
- [ ] Steam 到账系数可配置。
- [ ] 能正确计算 I5 / I10 / I20。
- [ ] I10 为默认主指标。
- [ ] 指数算法包含市场价值权重。
- [ ] 无效商品不会污染指数。
- [ ] 有效商品数量过少时任务失败。
- [ ] 每天结果写入 `data/index_history.csv`。
- [ ] 同一天重复运行不会生成重复记录。
- [ ] 能计算 MA7 / MA30。
- [ ] 数据足够时能计算 30 / 90 / 365 日历史位置。
- [ ] 能输出 Top N 挂刀候选。
- [ ] 达到配置阈值时能够通过 ntfy 通知。
- [ ] 同次运行只发送最高匹配提醒级别。
- [ ] cooldown 开启时能够避免同等级连续重复通知。
- [ ] GitHub Actions 支持每天北京时间约 23:40 自动执行。
- [ ] GitHub Actions 支持手动执行。
- [ ] GitHub Actions 能自动 commit 更新后的历史数据。
- [ ] 无数据变化时不会创建空 commit。
- [ ] 核心计算测试通过。
- [ ] GitHub Actions 实际运行成功。
- [ ] README 与最终实现一致。

---

# 11. Documentation

README 在核心功能实现并验证后编写。

最终 README 至少包括：

```text
项目简介
工作原理
安装
config.yaml 配置
GitHub Secrets 配置
本地运行
GitHub Actions 使用
ntfy 配置
CSV 字段说明
指数算法简述
测试方法
已知限制
```

明确说明：

> 本项目计算的是基于所选数据源和过滤规则得到的个人参考型 Exchange Index，不保证与历史 iflow Exchange Index 数值完全一致。

不得将当前指标描述为官方 Steam 指标。

---

# 12. Open Questions

只有以下事项需要 Coding Agent 在实际实现过程中依据真实 API 状况确认。

## CSQAQ API Schema

需要在实现 collector 时确认：

- 当前可用 endpoint
- API Token 传递方式
- 分页方式
- BUFF 字段名称
- YYYP 字段名称
- Steam 求购字段名称
- Steam 当日成交量字段名称
- Steam 求购数量字段名称
- 平台在售数量字段名称
- 是否能一次获得计算指数需要的完整数据

如果字段与计划不同：

> 只调整 `collector.py` / 数据适配层。

不得因此改变指数算法、历史格式和业务规则。

如果普通 API 无法获取计算市场价值或 Ratio 所需的关键字段，则明确记录限制，不得伪造数据。

---

# 13. Agent Rules

- 开始修改前完整阅读 `PLAN.md`。
- 首先检查实际仓库、Git 状态、已有代码、依赖和工程规范。
- 已有合理实现优先复用。
- 不机械重建已有项目。
- 不做无关重构。
- 不扩大当前 Scope。
- 不增加 Web UI、数据库服务器、Docker 等当前不需要的基础设施。
- 重要业务参数必须配置化。
- 普通实现细节自行选择简单、稳定方案。
- 不因为小问题频繁停止询问。
- API 字段差异优先通过适配层解决。
- 只有无法获得核心必需数据时才提出阻塞问题。
- 不提交任何 Secret。
- 不在日志打印 API Token 或完整敏感 URL。
- 外部 HTTP 请求设置合理 timeout。
- API 临时失败允许有限重试，不无限循环。
- 不因为通知失败而伪造或删除已经正确计算的指数。
- 不为了让测试通过删除有效测试或降低关键校验标准。
- 每完成主要 Phase 后执行对应验证。
- 核心行为变更时同步修改测试。
- 完成后运行全部适用测试。
- 最终逐项检查 Acceptance Criteria。
- 最终报告实际完成内容、测试结果、Git 状态和仍存在的真实限制。