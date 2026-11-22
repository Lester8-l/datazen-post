#!/usr/bin/env python3
"""
共用小工具：起一個臨時 local http server，令所有出圖／量測走 http://127.0.0.1。

為什麼要這樣做？
    1. `file://` 下字型是 CORS 受限資源，Chrome 會靜默拒絕載入 @font-face。
       結果就是我哋自己嘅 Iansui / 霞鶩文楷全部冇載入，出圖用咗系統字，
       但畫面「睇落正常」，冇人會發現——手寫體整批消失。
    2. headless Chrome 喺部分環境連 fonts.gstatic.com 都上唔到。
    3. 同一份 HTML 喺 file:// 同 http:// 下的字型行為唔一致，量出嚟嘅高度都唔同。

    所以：出一張圖之前，先起 server，用 http:// 開頁，字型由本地檔案直出。

    `/fonts/<name>` 會 alias 到本 skill 的 `assets/fonts/`，
    所以產出目錄唔需要複製 21MB 字型檔。

用法：
    import _serve

    with _serve.serve(deck.parent) as base:
        url = _serve.url(base, deck)          # http://127.0.0.1:PORT/xxx/deck.html
        subprocess.run([chrome, "--screenshot=...", url])
"""
import contextlib
import functools
import http.server
import pathlib
import threading
import urllib.parse

FONT_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts"


class _Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = urllib.parse.urlparse(path).path
        if clean.startswith("/fonts/"):
            return str(FONT_DIR / pathlib.Path(clean).name)
        return super().translate_path(path)

    def log_message(self, *args):  # 靜音
        pass

    def end_headers(self):
        # 避免 Chrome 快取舊版字型／HTML
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # Chrome 截完圖就斷連，會噴 ConnectionReset；呢個唔係錯誤，靜音
        pass

    def handle_error(self, request, client_address):
        # Chrome 截完圖就斷連，會噴 ConnectionReset；呢個唔係錯誤，靜音
        pass


@contextlib.contextmanager
def serve(root):
    """root 係要對外提供的目錄；yield 出 base URL。"""
    root = pathlib.Path(root).resolve()
    handler = functools.partial(_Handler, directory=str(root))
    httpd = _Server(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def url(base, path, root=None):
    """把本地檔案路徑轉成 server URL。path 必須在 root 之下。"""
    path = pathlib.Path(path).resolve()
    if root is None:
        # 由 URL 無法反推 root，呼叫方通常傳同一層，這裡退回檔名
        return f"{base}/{path.name}"
    root = pathlib.Path(root).resolve()
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        raise SystemExit(f"{path} 不在 server root {root} 之下，無法以 http 提供。")
    return f"{base}/{rel}"
