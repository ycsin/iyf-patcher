#!/usr/bin/env python3
# =============================================================================
#  repackage.py —— 把新组装好的 dex 换回**原始** apk。
#
#  用法：  python3 repackage.py <original.apk> <dex_dir> <output_unsigned.apk>
#
#  逐字节复制原始 apk（resources/.so 完全一致，逐条目的压缩方式也保留），只有两处例外：
#  classes*.dex 用 <dex_dir> 里的替换掉；旧的签名文件（META-INF/*.RSA|DSA|EC|SF、MANIFEST.MF）
#  被丢弃，以便结果能干净地重新签名。由 patch.sh 调用。
# =============================================================================
import zipfile, sys, os, re, glob


def main(orig, dexdir, out):
    newdex = {}
    for p in glob.glob(os.path.join(dexdir, "classes*.dex")):
        with open(p, "rb") as f:
            data = f.read()
        if not data.startswith(b"dex\n"):
            raise SystemExit(f"[FAIL] {p} not a dex")
        newdex[os.path.basename(p)] = data
    if not newdex:
        raise SystemExit(f"[FAIL] no dex in {dexdir}")
    print("[info] dex: " + ", ".join(f"{k}({len(v)}B)" for k, v in sorted(newdex.items())))

    sig_re = re.compile(r'^META-INF/([^/]*\.(RSA|DSA|EC|SF)|MANIFEST\.MF)$', re.I)
    zin = zipfile.ZipFile(orig, "r")
    if os.path.exists(out):
        os.remove(out)
    zout = zipfile.ZipFile(out, "w")
    present, replaced, dropped, copied = set(), [], [], 0
    for item in zin.infolist():
        name = item.filename; present.add(name)
        if sig_re.match(name):
            dropped.append(name); continue
        if name in newdex:
            data = newdex[name]; replaced.append(name)
        else:
            data = zin.read(name); copied += 1
        zout.writestr(item, data)  # 复用 ZipInfo -> 保留逐条目的压缩方式
    for name, data in sorted(newdex.items()):
        if name not in present:
            zout.writestr(name, data); replaced.append(name + " (new)")
    zin.close(); zout.close()
    print(f"[ok] replaced={replaced} dropped={dropped} copied={copied}")
    print(f"[ok] wrote {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: repackage.py <original.apk> <dex_dir> <output_unsigned.apk>")
    main(sys.argv[1], sys.argv[2], sys.argv[3])
