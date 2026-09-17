#!/usr/bin/env python3
# =============================================================================
#  iyf/patch.py —— 统一入口。让你选择给哪个客户端打补丁（安卓电视/机顶盒 或 Windows），
#  可直接从官方地址下载客户端，再分发到对应的打补丁流程。在 Linux / macOS 上运行。
#
#  用法：
#    python patch.py                                  # 交互式：选客户端 → 输入路径/URL/回车下载官方版
#    python patch.py windows --download               # 下载官方 Windows 安装包并打补丁
#    python patch.py tv --download -o out_vip.apk     # 下载官方 TV APK 并打补丁
#    python patch.py windows <本地文件或URL> [-o 输出]
#    python patch.py tv       <本地APK或URL> [-o 输出]
#
#  它是一个薄分发器：真正的工作在 tv/patch.py 和 windows/patch.py，二者共用同一套
#  engine.py + patches/。下载只用标准库 urllib，无额外依赖。
# =============================================================================
import sys, argparse, subprocess, urllib.request, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 每个客户端：说明、子脚本、官方默认下载地址、下载保存文件名（安卓电视 v2.4.5 / Windows v3.1.5）
CLIENTS = {
    "tv": (
        "安卓电视/机顶盒 客户端",
        HERE / "tv" / "patch.py",
        "https://app.anybound.vip/data/attachment/1-1779820631.apk",  # 安卓电视/机顶盒 v2.4.5
        "安卓电视_2.4.5.apk",
    ),
    "windows": (
        "Windows 客户端",
        HERE / "windows" / "patch.py",
        "https://app.anybound.vip/static/iyf/爱壹帆_Setup_3.1.5.exe",  # Windows v3.1.5
        "爱壹帆_Setup_3.1.5.exe",
    ),
}


def download(url, dest_dir=None, filename=None):
    """把 url 下载到 dest_dir（默认 <repo>/download/），返回本地文件路径。
    filename 指定保存文件名（否则取 URL 里的文件名）。URL 里的非 ASCII 会被百分号编码。"""
    dest_dir = Path(dest_dir or (HERE / "download"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    parts = urllib.parse.urlsplit(url)
    safe = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path), parts.query, parts.fragment))
    fname = filename or urllib.parse.unquote(parts.path.rsplit("/", 1)[-1]) or "download.bin"
    dest = dest_dir / fname
    print(f"下载：{url}")
    print(f"      -> {dest}", flush=True)
    req = urllib.request.Request(safe, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); done += len(chunk)
            mb = done / 1048576
            if total:
                print(f"\r   {mb:6.1f} / {total/1048576:.1f} MB ({done*100//total}%)", end="", flush=True)
            else:
                print(f"\r   {mb:6.1f} MB", end="", flush=True)
    print()
    return dest


def is_url(s):
    return bool(s) and s.lower().startswith(("http://", "https://"))


def resolve_source(client, source, do_download):
    """返回给子脚本用的本地输入路径；source 可为 本地路径 / URL / None。"""
    _, _, default_url, default_name = CLIENTS[client]
    if is_url(source):
        return str(download(source))                            # 用户给的 URL，用其自带文件名
    if source:
        return source                                           # 本地文件，原样传给子脚本
    if do_download:
        return str(download(default_url, filename=default_name))  # 官方默认地址，用规范文件名
    return None                                                 # 交给子脚本用它自己的默认值


def choose_interactively():
    """返回 (client, source, out, do_dl)；选择退出时返回 None。"""
    while True:
        print("选择要打补丁的客户端：")
        print("  1) 安卓电视/机顶盒 客户端")
        print("  2) Windows 客户端")
        print("  0) 退出")
        sel = input("> ").strip().lower()
        if sel in ("0", "q", "quit", "exit"):
            return None
        client = {"1": "tv", "tv": "tv", "2": "windows", "windows": "windows"}.get(sel)
        if not client:
            print("!! 无效选择\n")
            continue
        print(f"官方默认下载地址：{CLIENTS[client][2]}")
        src = input("输入文件路径或 URL（直接回车 = 下载上面的官方版）: ").strip().strip('"')
        out = input("输出文件路径（回车用默认）: ").strip().strip('"')
        return client, (src or None), (out or None), (src == "")


def run_once(client, source, out, do_dl):
    """执行一次打补丁，返回子脚本退出码。"""
    label, sub, _, _ = CLIENTS[client]
    if not sub.is_file():
        print(f"!! 找不到子脚本：{sub}")
        return 1
    print(f">>> 目标客户端：{label}", flush=True)

    inp = resolve_source(client, source, do_dl)

    # 未显式指定输出时，默认放到 <repo>/output/（已在 .gitignore 中忽略）
    if not out and inp:
        outdir = HERE / "output"
        outdir.mkdir(parents=True, exist_ok=True)
        out = str(outdir / (Path(inp).stem + ("_vip.zip" if client == "windows" else "_vip.apk")))

    # 在各自进程里运行子脚本 —— 避免两个同名 patch.py / engine.py 模块冲突，
    # 也让每个脚本用自己的 sys.path 找到同目录的 engine.py。
    cmd = [sys.executable, str(sub)]
    if inp:
        cmd.append(inp)
    if out:
        cmd.append(out)
    sys.stdout.flush()
    return subprocess.run(cmd).returncode


def main():
    ap = argparse.ArgumentParser(
        description="统一入口：选择客户端、（可选）下载官方版，然后打补丁。")
    ap.add_argument("client", nargs="?", choices=list(CLIENTS),
                    help="tv 或 windows（省略则进入交互式）")
    ap.add_argument("source", nargs="?", help="本地文件路径或 http(s) URL")
    ap.add_argument("-o", "--output", help="输出文件路径（省略用各流程默认值）")
    ap.add_argument("--download", action="store_true",
                    help="从官方地址下载该客户端（无 source 时使用）")
    a = ap.parse_args()

    # 带参数运行：一次性执行并退出
    if a.client:
        raise SystemExit(run_once(a.client, a.source, a.output, a.download))

    # 交互式运行：每次打完补丁回到主菜单，直到选择退出
    while True:
        choice = choose_interactively()
        if choice is None:
            print("已退出。")
            break
        run_once(*choice)
        print("\n———— 打补丁结束，返回主菜单 ————\n")


if __name__ == "__main__":
    main()
