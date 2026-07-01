"""
src/backtest/report.py - 回测报告生成

把 BacktestResult 导出为:
- HTML(可打印,带样式)
- JSON(机器可读)
- CSV(交易明细)

便于分享和归档。
"""
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from io import StringIO

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.backtest.engine import BacktestResult


def to_json(result: BacktestResult, metadata: dict = None) -> str:
    """导出 JSON 报告"""
    data = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "initial_equity": result.initial_equity,
            "final_equity": result.final_equity,
            "total_pnl": result.total_pnl,
            "total_return_pct": result.total_return * 100,
            "trades": result.trades,
            "wins": result.wins,
            "losses": result.losses,
            "win_rate_pct": result.win_rate * 100,
            "max_drawdown_pct": result.max_drawdown * 100,
            "sharpe_ratio": result.sharpe_ratio,
        },
        "metadata": metadata or {},
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_csv(result: BacktestResult) -> str:
    """导出交易明细 CSV

    注意:BacktestResult 不直接存交易列表,只有统计;
    真实交易明细在 engine.trade_log 里,本函数只导出汇总统计。
    """
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(["指标", "值"])
    writer.writerow(["初始资金", f"{result.initial_equity:.2f}"])
    writer.writerow(["最终资金", f"{result.final_equity:.2f}"])
    writer.writerow(["总盈亏", f"{result.total_pnl:.2f}"])
    writer.writerow(["收益率%", f"{result.total_return*100:.2f}"])
    writer.writerow(["交易次数", result.trades])
    writer.writerow(["盈利次数", result.wins])
    writer.writerow(["亏损次数", result.losses])
    writer.writerow(["胜率%", f"{result.win_rate*100:.2f}"])
    writer.writerow(["最大回撤%", f"{result.max_drawdown*100:.2f}"])
    writer.writerow(["夏普比率", f"{result.sharpe_ratio:.2f}"])
    return buf.getvalue()


def to_html(result: BacktestResult, metadata: dict = None) -> str:
    """导出 HTML 报告(打印友好,带颜色)"""
    md = metadata or {}
    symbol = md.get("symbol", "—")
    interval = md.get("interval", "—")
    days = md.get("days", "—")
    strategy = md.get("strategy", "—")

    pnl_color = "#16a34a" if result.total_pnl >= 0 else "#dc2626"  # 绿/红
    pnl_sign = "+" if result.total_pnl >= 0 else ""
    return_color = "#16a34a" if result.total_return >= 0 else "#dc2626"
    return_sign = "+" if result.total_return >= 0 else ""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>回测报告 {symbol} {interval}</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       max-width: 900px; margin: 40px auto; padding: 20px; background: #f8fafc; color: #0f172a; }}
h1 {{ color: #0f172a; border-bottom: 3px solid #2563eb; padding-bottom: 10px; }}
h2 {{ color: #1e40af; margin-top: 30px; }}
.meta {{ background: #e0e7ff; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
.meta span {{ margin-right: 20px; }}
table {{ width: 100%; border-collapse: collapse; background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }}
th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
th {{ background: #1e40af; color: white; font-weight: 600; }}
tr:last-child td {{ border-bottom: none; }}
tr:hover {{ background: #f1f5f9; }}
.pnl-positive {{ color: {pnl_color}; font-weight: 600; font-size: 1.2em; }}
.pnl-return {{ color: {return_color}; font-weight: 600; }}
.big-number {{ font-size: 1.8em; font-weight: 700; }}
.metric-card {{ display: inline-block; background: white; padding: 16px 24px;
               margin: 8px; border-radius: 8px; min-width: 160px;
               box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.metric-label {{ color: #64748b; font-size: 0.9em; }}
.metric-value {{ font-size: 1.4em; font-weight: 700; margin-top: 4px; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #cbd5e1;
         color: #64748b; font-size: 0.9em; text-align: center; }}
</style>
</head>
<body>
<h1>📊 量化回测报告</h1>

<div class="meta">
  <span><b>交易对:</b> {symbol}</span>
  <span><b>周期:</b> {interval}</span>
  <span><b>回测天数:</b> {days}</span>
  <span><b>策略:</b> {strategy}</span>
  <span><b>生成时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
</div>

<h2>核心结果</h2>
<div>
  <div class="metric-card">
    <div class="metric-label">总盈亏</div>
    <div class="metric-value pnl-positive">{pnl_sign}{result.total_pnl:.2f} USDT</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">收益率</div>
    <div class="metric-value pnl-return">{return_sign}{result.total_return*100:.2f}%</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">最终资金</div>
    <div class="metric-value">{result.final_equity:.2f}</div>
  </div>
</div>

<h2>风险指标</h2>
<table>
  <tr><th>指标</th><th>值</th><th>说明</th></tr>
  <tr><td>最大回撤</td><td><b>{result.max_drawdown*100:.2f}%</b></td>
    <td>资金从峰值下跌的最大幅度,越低越好</td></tr>
  <tr><td>夏普比率</td><td><b>{result.sharpe_ratio:.2f}</b></td>
    <td>收益风险比,&gt;1 为合格,&gt;2 为优秀</td></tr>
</table>

<h2>交易统计</h2>
<table>
  <tr><th>指标</th><th>值</th></tr>
  <tr><td>总交易次数</td><td>{result.trades}</td></tr>
  <tr><td>盈利次数</td><td style="color:#16a34a">{result.wins}</td></tr>
  <tr><td>亏损次数</td><td style="color:#dc2626">{result.losses}</td></tr>
  <tr><td>胜率</td><td><b>{result.win_rate*100:.2f}%</b></td></tr>
</table>

<div class="footer">
  本报告由 quant-futures 自动生成 | 仅供参考,不构成投资建议
</div>
</body>
</html>"""
    return html


def save_report(result: BacktestResult, output_dir: str = "backtest_results",
                formats: list = None, metadata: dict = None) -> dict:
    """
    保存报告到文件

    Returns: {format: filepath}
    """
    if formats is None:
        formats = ["html", "json", "csv"]

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    md = metadata or {}
    symbol = md.get("symbol", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{symbol}_{timestamp}"

    paths = {}
    if "html" in formats:
        p = out_dir / f"{base}.html"
        p.write_text(to_html(result, metadata), encoding="utf-8")
        paths["html"] = str(p)
    if "json" in formats:
        p = out_dir / f"{base}.json"
        p.write_text(to_json(result, metadata), encoding="utf-8")
        paths["json"] = str(p)
    if "csv" in formats:
        p = out_dir / f"{base}.csv"
        p.write_text(to_csv(result), encoding="utf-8")
        paths["csv"] = str(p)
    return paths


# ==================== 单独测试 ====================
if __name__ == "__main__":
    from src.backtest.engine import BacktestResult

    # 模拟结果
    r = BacktestResult(
        initial_equity=10000, final_equity=12350,
        total_pnl=2350, total_return=0.235,
        trades=42, wins=28, losses=14,
        win_rate=0.667, max_drawdown=0.08, sharpe_ratio=1.85
    )
    paths = save_report(
        r, output_dir="backtest_results",
        metadata={"symbol": "BTCUSDT", "interval": "1h", "days": 90, "strategy": "dual_ma"}
    )
    print("📁 报告已生成:")
    for fmt, p in paths.items():
        print(f"  {fmt}: {p}")
