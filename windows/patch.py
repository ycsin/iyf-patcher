#!/usr/bin/env python3
# =============================================================================
#  iyf/windows/patch.py —— 从官方 NSIS 安装包构建免安装、去广告、全 VIP 的爱壹帆（iyf）
#  Windows 客户端。用 Python 编写，在 Linux / macOS 上运行：
#      python patch.py [iyf_Setup_x.y.z.exe] [output.zip]
#
#  依赖（需自行装好并加入 PATH）：
#    - python3
#    - 7-Zip（7z）—— 用于解开 NSIS 安装包和 app-64.7z
#        macOS: brew install p7zip；Debian/Ubuntu: sudo apt install p7zip-full
#    - Node.js（asar，或用 npx @electron/asar）—— 用于解包/重打包 app.asar
#        https://nodejs.org ，然后 npm i -g @electron/asar
#  补丁引擎（engine.py）和补丁（patches/*.patch）直接 import 调用。
# =============================================================================
import sys, shutil, subprocess, tempfile, glob, zipfile, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHES = HERE / "patches"


def die(msg):
    print(msg); sys.exit(1)


def find_7z():
    for n in ("7z", "7za", "7zz"):
        p = shutil.which(n)
        if p:
            return p
    die("!! 找不到 7-Zip（7z）。macOS: brew install p7zip；Debian/Ubuntu: sudo apt install p7zip-full")


def find_asar():
    p = shutil.which("asar")
    if p:
        return [p]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "@electron/asar"]
    die("!! 需要 'asar' 或 'npx'（Node.js）。装 https://nodejs.org 后 npm i -g @electron/asar")


def run(cmd, quiet=True):
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL if quiet else None,
                   stderr=subprocess.DEVNULL if quiet else None)


def main():
    ap = argparse.ArgumentParser(description="Build the portable ad-free / full-VIP iyf Windows app.")
    ap.add_argument("installer", nargs="?", default=str(Path.home() / "iyf_Setup_3.1.5.exe"))
    ap.add_argument("output", nargs="?", default=str(Path.home() / "iyf_3.1.5_portable_vip.zip"))
    a = ap.parse_args()

    installer = Path(a.installer).expanduser().resolve()
    if not installer.is_file():
        die(f"!! 找不到安装包: {installer}")
    out = Path(a.output).expanduser().resolve()
    name = out.stem  # 压缩包内的顶层目录名

    print("== [1/7] 工具链 ==")
    sevenzip = find_7z()
    asar = find_asar()
    print(f"   7z={sevenzip}  asar={' '.join(asar)}  python={sys.version.split()[0]}")

    work = Path(tempfile.mkdtemp(prefix="iyfpatch."))
    try:
        print("== [2/7] 解开 NSIS 安装包 ==")
        run([sevenzip, "x", "-y", f"-o{work / 'nsis'}", str(installer)])
        hits = glob.glob(str(work / "nsis" / "**" / "app-64.7z"), recursive=True)
        if not hits:
            die("!! 找不到 app-64.7z（可能不是 electron-builder 的 NSIS 安装包？）")
        app7z = hits[0]

        print("== [3/7] 解开 Electron 应用负载 ==")
        run([sevenzip, "x", "-y", f"-o{work / 'app'}", app7z])
        asarf = work / "app" / "resources" / "app.asar"
        if not asarf.is_file():
            die("!! 找不到 resources/app.asar")

        print("== [4/7] 解包 app.asar ==")
        run(asar + ["extract", str(asarf), str(work / "asar_src")], quiet=False)

        print(f"== [5/7] 应用补丁 ({PATCHES}) ==")
        sys.path.insert(0, str(HERE))
        import engine  # 跨平台的补丁引擎
        engine.main(str(work / "asar_src"), str(PATCHES))

        print("== [6/7] 重新打包 app.asar ==")
        asarf.unlink()
        run(asar + ["pack", str(work / "asar_src"), str(asarf)], quiet=False)

        print("== [7/7] 打包成 zip ==")
        appdir = work / name
        (work / "app").rename(appdir)
        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=3) as z:
            for f in appdir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(work))  # 归档根目录带 name/

        size_mb = out.stat().st_size / (1024 * 1024)
        print()
        print(f">>> 完成: {out}  ({size_mb:.0f}M)")
        print(f">>> 在 Windows 上：解压后运行  {name}/爱壹帆.exe  （无需安装）")
        print(">>>   加上  --inspect  可启用右键 Inspect / DevTools")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
