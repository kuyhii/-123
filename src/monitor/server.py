"""
src/monitor/server.py - 简易 Web 监控面板

启动一个 HTTP 服务器,浏览器访问 http://localhost:8000 看实时状态。

页面:
- /         总览(账户、持仓、PnL、状态)
- /health   JSON 健康检查
- /signals  最近 20 个信号
- /trades   最近 20 笔成交

依赖:仅用标准库(http.server),不引入 flask/fastapi,保持轻量。
"""
import sys
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import CONFIG
from src.logger import get_logger
from src.utils.health import HealthMonitor
from src.strategy.trading_pairs import load_pairs
from src.storage.db import init_db, SignalsRepository, TradesRepository, OrdersRepository

log = get_logger("monitor")


class MonitorHandler(BaseHTTPRequestHandler):
    """HTTP 处理器"""

    def log_message(self, format, *args):
        """覆盖默认日志,用我们自己的 logger"""
        log.debug(f"{self.address_string()} - {format % args}")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send_html(_render_dashboard())
            elif path == "/health":
                self._send_json(HealthMonitor.get().snapshot())
            elif path == "/signals":
                init_db()
                signals = SignalsRepository().recent(limit=20)
                self._send_json({"count": len(signals), "signals": signals})
            elif path == "/trades":
                init_db()
                trades = TradesRepository().recent(limit=20)
                self._send_json({"count": len(trades), "trades": trades})
            elif path == "/orders":
                init_db()
                orders = OrdersRepository().recent(limit=20)
                self._send_json({"count": len(orders), "orders": orders})
            elif path == "/api/summary":
                self._send_json(_get_summary())
            else:
                self._send_json({"error": "Not Found"}, status=404)
        except Exception as e:
            log.error(f"请求 {path} 失败: {e}")
            self._send_json({"error": str(e)}, status=500)


def _get_summary() -> dict:
    """获取系统摘要"""
    pairs = load_pairs()
    h = HealthMonitor.get()
    return {
        "uptime": True,
        "trading_pairs_count": len(pairs),
        "trading_pairs": pairs[:10],  # 只列前 10
        "config": {
            "env": CONFIG.binance.env,
            "leverage": CONFIG.trading.leverage,
            "order_pct": CONFIG.trading.order_pct_of_margin,
            "intervals": CONFIG.trading.kline_intervals,
        },
        "health": h.snapshot(),
    }


def _render_dashboard() -> str:
    """渲染仪表盘 HTML"""
    pairs = load_pairs()
    health = HealthMonitor.get()
    snap = health.snapshot()
    cfg = CONFIG

    overall_color = {"HEALTHY": "#16a34a", "DEGRADED": "#f59e0b", "UNHEALTHY": "#dc2626"}.get(snap["overall"], "#64748b")

    components_html = ""
    for name, c in snap["components"].items():
        icon = {"HEALTHY": "✅", "DEGRADED": "⚠️ ", "UNHEALTHY": "❌"}.get(c["status"], "?")
        components_html += f"""
<tr>
  <td>{icon} {name}</td>
  <td>{c['status']}</td>
  <td>{c['success_count']}</td>
  <td>{c['error_count']}</td>
  <td>{c['last_error'] or '—'}</td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="5">
<title>量化系统监控</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       max-width: 1100px; margin: 30px auto; padding: 20px; background: #f8fafc; color: #0f172a; }}
h1 {{ color: #0f172a; }}
.card {{ background: white; border-radius: 8px; padding: 20px; margin: 16px 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.status-big {{ font-size: 2em; font-weight: 700; color: {overall_color}; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
th {{ background: #f1f5f9; font-weight: 600; }}
.tag {{ display: inline-block; background: #dbeafe; color: #1e40af; padding: 2px 8px;
       border-radius: 4px; margin: 2px; font-size: 0.85em; }}
.nav a {{ display: inline-block; padding: 6px 14px; margin-right: 8px;
         background: #2563eb; color: white; text-decoration: none;
         border-radius: 6px; font-size: 0.9em; }}
.nav a:hover {{ background: #1d4ed8; }}
.refresh {{ color: #64748b; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>📊 量化合约交易系统 - 监控面板</h1>

<div class="nav">
  <a href="/">总览</a>
  <a href="/health">健康</a>
  <a href="/signals">信号</a>
  <a href="/trades">成交</a>
  <a href="/orders">订单</a>
</div>

<div class="card">
  <h2>系统状态</h2>
  <div class="status-big">{snap['overall']}</div>
  <p class="refresh">⏱ 自动刷新:5秒 | 运行时长: {snap['uptime_sec']:.0f}秒</p>
</div>

<div class="card">
  <h2>运行配置</h2>
  <p>
    <span class="tag">环境: {cfg.binance.env}</span>
    <span class="tag">杠杆: {cfg.trading.leverage}x</span>
    <span class="tag">每单保证金: {cfg.trading.order_pct_of_margin}%</span>
    <span class="tag">K线: {",".join(cfg.trading.kline_intervals)}</span>
    <span class="tag">交易对池: {len(pairs)} 个</span>
  </p>
</div>

<div class="card">
  <h2>组件健康</h2>
  <table>
    <tr>
      <th>组件</th><th>状态</th><th>成功</th><th>失败</th><th>最近错误</th>
    </tr>
    {components_html or '<tr><td colspan="5">无组件注册</td></tr>'}
  </table>
</div>

<div class="card">
  <h2>交易对池 (前 10)</h2>
  <p>{"".join(f'<span class="tag">{p}</span>' for p in pairs[:10])}</p>
  <p class="refresh">完整 {len(pairs)} 个币种,见 config/trading_pairs.json</p>
</div>

<div class="card">
  <h2>API 端点</h2>
  <ul>
    <li><a href="/api/summary">/api/summary</a> - JSON 摘要</li>
    <li><a href="/health">/health</a> - 健康快照</li>
    <li><a href="/signals">/signals</a> - 最近信号</li>
    <li><a href="/trades">/trades</a> - 最近成交</li>
    <li><a href="/orders">/orders</a> - 最近订单</li>
  </ul>
</div>

</body>
</html>"""


class MonitorServer:
    """Web 监控服务器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """启动(非阻塞,放后台线程)"""
        self.server = HTTPServer((self.host, self.port), MonitorHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        log.info(f"🌐 监控面板已启动: http://{self.host}:{self.port}/")
        log.info(f"   API 端点: /api/summary /health /signals /trades /orders")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            log.info("监控面板已停止")


# ==================== 单独运行 ====================
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Web 监控面板")
    p.add_argument("--host", default="0.0.0.0", help="监听地址")
    p.add_argument("--port", type=int, default=8000, help="端口")
    args = p.parse_args()

    init_db()
    server = MonitorServer(host=args.host, port=args.port)
    server.start()
    print(f"\n✅ 监控面板运行中: http://localhost:{args.port}/")
    print("按 Ctrl+C 停止\n")
    try:
        server.thread.join()
    except KeyboardInterrupt:
        server.stop()
        print("\n⏹️  停止")
