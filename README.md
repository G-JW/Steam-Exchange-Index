# Steam Exchange Index

个人使用的 CS2 饰品挂刀指数监控工具。它从 CSQAQ 获取 BUFF、悠悠有品和 Steam 行情，筛选高流动性饰品，计算 I5、I10、I20，并将每日结果保存在 CSV；达到配置阈值时可通过 ntfy 提醒。

本项目计算的是基于所选数据源和过滤规则得到的个人参考型 Exchange Index，不保证与历史 iflow Exchange Index 数值完全一致，也不是 Steam 官方指标。

## 工作原理

每次采集前，程序会调用 CSQAQ 的 `bind_local_ip` 接口，将当前运行环境的出口 IP 绑定到 API Token。这样 GitHub 托管 Runner 即使每次使用动态 IP，也能在同一次任务中先更新白名单再读取行情。该行为可通过 `data_source.bind_local_ip` 开关控制。

每件饰品在启用平台中的挂刀比例为：

```text
平台最低售价 / (Steam 最高求购价 × Steam 到账系数)
```

程序取 BUFF / 悠悠中较低的比例，以 `BUFF 售价 × BUFF 在售数量` 作为市场价值，按比例由低到高累计。I5、I10、I20 分别是累计覆盖总市场价值 5%、10%、20% 时，所选饰品按市场价值加权的平均挂刀比例。越过边界的最后一件饰品会完整纳入。

默认只保留 Steam 当日成交量严格大于 100 的饰品；价格、比例、Steam 求购量和平台在售量过滤均可在 `config.yaml` 调整。

## 安装与本地运行

需要 Python 3.12：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export CSQAQ_API_TOKEN="你的 CSQAQ Token"
export NTFY_DAILY_URL="https://ntfy.sh/你的日报私有主题"
export NTFY_ALERT_URL="https://ntfy.sh/你的特别提醒私有主题"
python main.py
```

`CSQAQ_API_TOKEN` 和 `NTFY_DAILY_URL` 必填。`NTFY_ALERT_URL` 未设置时，特别提醒会发送到日报频道。ntfy 目标可以填写 ntfy.sh topic 名，也可以填写完整的 `https://` topic URL。

macOS 本地可直接双击仓库根目录下被 Git 忽略的 `run_local.command`。该文件用于保存本机明文凭据，不会被提交；首次使用前需要在文件内填入两个 ntfy URL。

运行测试：

```bash
pytest -q
```

## 配置

所有非敏感行为均在 `config.yaml`：

- `data_source`：CSQAQ 行情及 IP 绑定 endpoint、白名单开关、超时、重试次数和分页安全上限。
- `platforms`：启用 `BUFF`、`YYYP` 中的一个或两个。
- `steam.net_rate`：Steam 实际到账系数，默认 `0.869`。
- `filters`：成交量以及可选的价格、比例、求购量和在售量过滤。
- `index`：指数覆盖比例、主指标和最少有效饰品数量。
- `history`：移动平均和历史位置窗口。
- `notification.special_percentile`：特别提醒的历史位置门槛，默认 90%。
- `top_items.count`：日志及通知中的候选数量。

配置错误、API 失败、有效饰品不足或指数无效时，程序以非零状态退出且不写当天历史。通知失败发生在指数成功保存之后，程序返回状态码 2 并保留结果。

## 历史数据

`data/index_history.csv` 每天只保留一行；同日重跑会覆盖该日记录：

| 字段 | 含义 |
|---|---|
| `date` | 北京时间日期 |
| `run_timestamp` | 带时区的实际运行时间 |
| `index_5/10/20` | 三个挂刀指数 |
| `valid_items` | 有效饰品数 |
| `min_ratio` | 当日最低比例 |
| `ma7/ma30` | 包含当日的移动平均，样本不足留空 |
| `p30/p180` | 当前 I10 低于相应完整历史窗口中多少比例的日期，当前日不参与比较 |

## ntfy

每次成功计算后都会向 `NTFY_DAILY_URL` 发送日报，正文严格只包含 I5、I10、I20。当主指标 I10 同时低于过去 30 天和 180 天中至少 90% 的记录时，再向 `NTFY_ALERT_URL` 发送特别提醒，正文同样只包含三个指数。历史样本不足 180 天时不会触发特别提醒。没有固定指数阈值、提醒分级或冷却状态。

## GitHub Actions

在仓库 Settings → Secrets and variables → Actions 中创建：

- `CSQAQ_API_TOKEN`
- `NTFY_DAILY_URL`
- `NTFY_ALERT_URL`（可选；未设置时使用日报频道）

工作流每天 UTC 15:40（北京时间约 23:40）执行，也可在 Actions 页面手动触发。它先安装依赖和运行测试，再运行监控；只有 `data/` 变化时才提交并推送，提交信息为 `data: update daily exchange index`。

## 已知限制

- 数据完整性、刷新时间和接口可用性取决于 CSQAQ。
- GitHub Actions 的定时任务可能延迟。
- 程序不保存单品历史，也不执行任何自动购买或交易。
- 当前市场价值固定使用 BUFF 售价和在售数量。
