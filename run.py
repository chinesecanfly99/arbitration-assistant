"""一键启动：python run.py [端口]

存在的理由：README 里那五条命令对评审来说还是太多，而且每条都要先设 PYTHONPATH——
Windows PowerShell、macOS 的 zsh、Linux 的 bash 写法还都不一样。这个脚本把三件事一次做完：

1. 把 `src` 加进 sys.path（不用再记 PYTHONPATH 怎么写）；
2. 端口被占（比如上一次没关干净）时自动换一个空闲端口，而不是抛 OSError 让人一脸问号；
3. 起服务后自动打开浏览器，并把真实地址打出来（换了端口也不会给错链接）。

只依赖标准库，三个平台行为一致。
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

DEFAULT_PORT = 8765


def _load_local_env(path: str | None = None) -> None:
    """读取本地 .env（仅在启动入口加载，不污染单测且不进 Git）。"""
    env_path = path or os.path.join(ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                os.environ.setdefault(k, v)


def free_port(preferred: int = DEFAULT_PORT, tries: int = 12) -> int:
    """从 preferred 开始找一个能绑的端口；全被占就让系统分配（返回 0 的实际端口）。"""
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _lan_ip() -> str | None:
    """获取本机主局域网 IP（仅查路由表，不对外发包）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("223.5.5.5", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith(("127.", "198.18.")):
                return ip
    except OSError:
        pass
    return None


def _resolve_bind(argv: list[str], environ: dict | None = None) -> tuple[str, int, bool, bool]:
    """解析绑定主机、端口、是否关闭浏览器与是否启用局域网提示。

    当云平台（Zeabur / Render / Railway）注入 PORT 环境变量时，自动监听 0.0.0.0:$PORT
    并禁用本地自动弹窗，避免云容器启动异常。
    """
    env = os.environ if environ is None else environ
    env_port = str(env.get("PORT") or "").strip()
    cloud_mode = env_port.isdigit()
    want = int(env_port) if cloud_mode else DEFAULT_PORT
    for a in argv:
        if a.isdigit():
            want = int(a)
    lan = ("--lan" in argv) or cloud_mode
    host = "0.0.0.0" if lan else "127.0.0.1"
    no_browser = ("--no-browser" in argv) or cloud_mode
    return host, want, no_browser, lan


def main(argv: list[str] | None = None) -> int:
    _load_local_env()
    from http.server import ThreadingHTTPServer

    from arb.console import enable_utf8
    from arb.web import Handler

    enable_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    host, want, no_browser, lan = _resolve_bind(argv)
    cloud_mode = str(os.environ.get("PORT") or "").strip().isdigit()

    port = want if cloud_mode else free_port(want)
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"劳动仲裁维权助手已启动： {url}  （Ctrl+C 退出）")
    if lan and not cloud_mode:
        ip = _lan_ip()
        if ip:
            print(f"[手机/局域网访问] 请在手机浏览器打开： http://{ip}:{port}")
        else:
            print(f"[手机/局域网访问] 已监听 0.0.0.0:{port}，请用本机局域网 IP:{port} 访问")
    elif cloud_mode:
        print(f"[云端托管模式] 正在监听 0.0.0.0:{port}")
    if port != want:
        print(f"[提示] 端口 {want} 被占用，已自动改用 {port}")
    if not no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
