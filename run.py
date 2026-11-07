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


def main(argv: list[str] | None = None) -> int:
    from http.server import ThreadingHTTPServer

    from arb.console import enable_utf8
    from arb.web import Handler

    enable_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    want = DEFAULT_PORT
    for a in argv:
        if a.isdigit():
            want = int(a)
    no_browser = "--no-browser" in argv

    port = free_port(want)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"劳动仲裁维权助手已启动： {url}  （Ctrl+C 退出）")
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
