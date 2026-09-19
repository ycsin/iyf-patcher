#!/usr/bin/env python3
# =============================================================================
#  iyf/mobile/patch.py —— 给 com.cqcsy.ifvod（安卓手机客户端）打去广告 / 全 VIP 补丁。
#  用 Python 编写，在 Linux / macOS 上运行：
#      python patch.py <input.apk> [output.apk]
#
#  依赖（需自行装好并加入 PATH）：python3、apktool、apksigner、zipalign、keytool、java。
#  补丁引擎（engine.py）与换 dex（repackage.py）直接 import 调用。
# =============================================================================
import sys, shutil, subprocess, tempfile, glob, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHES = HERE / "patches"
TOOLHOME = Path.home() / ".vip_patch"
KS = TOOLHOME / "hw.keystore"


def die(msg):
    print(msg); sys.exit(1)


def need(tool):
    p = shutil.which(tool)
    if not p:
        die(f"!! 找不到工具: {tool}\n   请安装 apktool / Android SDK build-tools（apksigner、zipalign）"
            f"以及 JDK（keytool、java），并加入 PATH")
    return p


def run(cmd, quiet=True):
    subprocess.run(cmd, check=True,
                   stdout=subprocess.DEVNULL if quiet else None,
                   stderr=subprocess.DEVNULL if quiet else None)


def main():
    ap = argparse.ArgumentParser(description="Patch the com.cqcsy.ifvod APK (ad-free / full VIP).")
    ap.add_argument("input", help="输入 APK")
    ap.add_argument("output", nargs="?", help="输出 APK（默认 <input>_vip.apk）")
    a = ap.parse_args()

    src = Path(a.input).expanduser().resolve()
    if not src.is_file():
        die(f"!! 找不到文件: {src}")
    out = Path(a.output).expanduser().resolve() if a.output else src.with_name(src.stem + "_vip.apk")
    TOOLHOME.mkdir(parents=True, exist_ok=True)

    print("== [1/6] 工具链 ==")
    apktool = need("apktool"); apksigner = need("apksigner")
    zipalign = need("zipalign"); keytool = need("keytool"); need("java")
    print(f"   apktool={apktool}")

    work = Path(tempfile.mkdtemp(prefix="vippatch."))
    dec = work / "dec"
    try:
        print("== [2/6] 反编译 ==")
        run([apktool, "d", "-f", "-o", str(dec), str(src)])
        print(f"   已反编译 -> {dec}")

        print(f"== [3/6] 应用补丁 ({PATCHES}) ==")
        sys.path.insert(0, str(HERE))
        import engine  # 跨平台补丁引擎
        engine.main(str(dec), str(PATCHES))

        print("== [4/6] 组装 dex（资源原样保留；此处无法做 apktool 完整重建，")
        print("         因为 aapt1 和 aapt2 都会拒绝本应用的 $ 命名资源） ==")
        log = work / "apktool_build.log"
        with open(log, "w", encoding="utf-8", errors="replace") as lf:
            # apktool b 完整重建会失败，但仍会产出 dex —— 不 check，随后校验 dex 是否存在
            subprocess.run([apktool, "b", "-o", str(work / "rebuilt.apk"), str(dec)],
                           stdout=lf, stderr=subprocess.STDOUT)
        dexdir = dec / "build" / "apk"
        if not glob.glob(str(dexdir / "classes*.dex")):
            print("!! dex 组装失败。构建日志末尾：")
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))
            die("")
        print("   dex 已组装")

        print("== [5/6] 重新打包（把 dex 换回原始 apk） ==")
        import repackage  # 跨平台换 dex
        repackage.main(str(src), str(dexdir), str(work / "unsigned.apk"))

        print("== [6/6] align + 签名 ==")
        run([zipalign, "-f", "-p", "4", str(work / "unsigned.apk"), str(work / "aligned.apk")])
        run([zipalign, "-c", "-p", "4", str(work / "aligned.apk")])
        print("   对齐: OK")
        if not KS.is_file():
            print(f"   生成可复用的签名密钥 -> {KS}")
            run([keytool, "-genkeypair", "-v", "-keystore", str(KS), "-alias", "vip",
                 "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                 "-storepass", "android", "-keypass", "android", "-dname", "CN=VIP Patch"])
        if out.exists():
            out.unlink()
        run([apksigner, "sign", "--ks", str(KS), "--ks-pass", "pass:android",
             "--key-pass", "pass:android", "--out", str(out), str(work / "aligned.apk")])
        print()
        r = subprocess.run([apksigner, "verify", "--print-certs", str(out)],
                           capture_output=True, text=True)
        print("\n".join(r.stdout.splitlines()[:6]))
        print()
        print(f">>> 完成: {out}")
        print(f'>>> 安装:  adb uninstall com.cqcsy.ifvod ; adb install -r "{out}"')
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
