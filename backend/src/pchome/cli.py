"""PChome 24h 搶購腳本入口：啟動網頁控制台"""

import argparse
import ipaddress


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="PChome 搶購控制台")
    parser.add_argument("--port", type=int, default=8787, help="監聽 port（預設 8787）")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="監聽位址（預設 127.0.0.1；遠端部署可設 0.0.0.0，請自行以反向代理保護）",
    )
    args = parser.parse_args()

    import uvicorn

    from .api.app import create_app

    if not _is_loopback(args.host):
        print(f"警告: 綁定 {args.host} 會讓控制台暴露在網路上（本身無認證），")
        print("請確保由反向代理（nginx basic auth / VPN 等）保護存取")
    print(f"PChome 搶購控制台: http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")
