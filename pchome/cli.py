"""命令列介面：login / buy / web 三個子指令（輔助工具，主要介面是網頁控制台）

所有 input()/print 互動集中在這層，核心流程透過 ConsoleReporter 輸出。
"""

import argparse
import ipaddress
import sys

from .core import session
from .core.config import AUTH_STATE_FILE, DEFAULT_INTERVAL_SECS, DEFAULT_LEAD_SECS
from .core.reporter import ConsoleReporter
from .core.runner import JobConfig, run_snapup_job
from .core.timing import parse_sale_time


def cmd_login(args) -> None:
    """開啟瀏覽器讓使用者手動登入，完成後儲存 session"""
    print("正在開啟瀏覽器，請手動登入 PChome...")

    def wait_for_user():
        print("請在瀏覽器中完成登入...")
        print("登入完成後，按 Enter 鍵儲存 session...")
        input()

    session.login_flow(wait_for_user)
    print(f"登入狀態已儲存至 {AUTH_STATE_FILE}")
    print("提示：遠端部署時，可把這個檔案的內容貼到網頁控制台的「登入」視窗匯入")


def cmd_buy(args) -> None:
    """搶購商品（支援多個商品 ID）"""
    try:
        sale_ts = parse_sale_time(args.sale_time) if args.sale_time else None
    except ValueError as e:
        print(f"錯誤: {e}")
        sys.exit(1)

    cfg = JobConfig(
        product_ids=args.product_ids,
        sale_ts=sale_ts,
        interval=args.interval,
        lead=args.lead,
        headless=args.headless,
    )

    def hold(_result):
        # 保持瀏覽器開啟，讓使用者手動完成結帳
        print("\n瀏覽器保持開啟中，完成結帳後按 Enter 關閉...")
        input()

    result = run_snapup_job(cfg, ConsoleReporter(), hold=hold)
    if not result.ok:
        sys.exit(1)


def cmd_web(args) -> None:
    """啟動網頁控制台"""
    import uvicorn

    from .api.app import create_app

    if not _is_loopback(args.host):
        print(f"警告: 綁定 {args.host} 會讓控制台暴露在網路上（本身無認證），")
        print("請確保由反向代理（nginx basic auth / VPN 等）保護存取")
    print(f"PChome 搶購控制台: http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="PChome 24h 搶購腳本")
    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    subparsers.add_parser("login", help="開啟瀏覽器手動登入，儲存 session")

    buy_parser = subparsers.add_parser("buy", help="搶購指定商品")
    buy_parser.add_argument(
        "product_ids",
        nargs="+",
        help="商品編號，可指定多個 (如 DGCQ39-A900JESMM DGCQ39-A900JL925)",
    )
    buy_parser.add_argument(
        "--headless", action="store_true", help="無頭模式（不顯示瀏覽器）"
    )
    buy_parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECS,
        help=f"輪詢間隔秒數（預設 {DEFAULT_INTERVAL_SECS}）",
    )
    buy_parser.add_argument(
        "--sale-time",
        help='開賣時間 "YYYY-MM-DD HH:MM"；距開賣超過 --lead 秒會先睡眠等待，開賣前 15 秒才全速輪詢',
    )
    buy_parser.add_argument(
        "--lead",
        type=float,
        default=DEFAULT_LEAD_SECS,
        help=f"搭配 --sale-time：開賣前幾秒啟動監控（預設 {DEFAULT_LEAD_SECS:.0f}）",
    )

    web_parser = subparsers.add_parser(
        "web", help="啟動網頁控制台（預設 http://127.0.0.1:8787）"
    )
    web_parser.add_argument(
        "--port", type=int, default=8787, help="監聽 port（預設 8787）"
    )
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="監聽位址（預設 127.0.0.1；遠端部署可設 0.0.0.0，請自行以反向代理保護）",
    )

    args = parser.parse_args()

    if args.command == "login":
        cmd_login(args)
    elif args.command == "buy":
        cmd_buy(args)
    elif args.command == "web":
        cmd_web(args)
    else:
        parser.print_help()
