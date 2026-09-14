#!/usr/bin/env python3
# =============================================================================
#  engine.py —— Android（apktool smali 目录）的补丁引擎。
#
#  用法：  python3 engine.py <decoded_root> <patches_dir>
#
#  按文件名顺序把每个 <patches_dir>/*.patch 应用到反编译出的 smali 目录。每个 *.patch
#  都是一小段 Python，在下方这套辅助 API 的作用域里执行；锚点是语义化的（方法名 / binding
#  字段 / 应用无法改名否则会自破的资源 id）。由 patch.sh 调用。
# =============================================================================
import re, sys, os, glob


def main(root, patches_dir):
    smali_files = glob.glob(os.path.join(root, "smali*", "**", "*.smali"), recursive=True)
    if not smali_files:
        raise SystemExit(f"[FAIL] no smali under {root}")

    def rel(f):
        return os.path.relpath(f, root)

    def read(p):
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()

    def write(p, txt):
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)

    RET_RE = re.compile(r'\)(\[*(?:L[^;]+;|[VZBSCIJFD]))\s*$')

    def patch_method(txt, name, body_fn):
        """把 .method ...<name>(...) 的方法体替换为 body_fn(returnType) 的结果。"""
        pat = re.compile(r'(?ms)^(\.method\b[^\n]*\b' + re.escape(name) + r'\([^\n]*)\n.*?^\.end method[ \t]*$')

        def _r(m):
            decl = m.group(1); rt = RET_RE.search(decl).group(1)
            return decl + "\n" + body_fn(rt) + ".end method"
        return pat.subn(_r, txt)

    def _files(only):
        return glob.glob(os.path.join(root, only), recursive=True) if only else smali_files

    def apply_over(fn, need=None, only=None, label="patch"):
        """对 smali 文件运行 fn(text)->(text,count)（可用 glob / 子串过滤）。"""
        tot = 0
        for f in _files(only):
            t = read(f)
            if need and need not in t:
                continue
            t2, n = fn(t)
            if n:
                write(f, t2); tot += n; print(f"[ok] {rel(f)}: {label} x{n}")
        if tot == 0:
            print(f"[warn] {label}: no match")
        return tot

    def regex_patch(pattern, repl, need=None, only=None, label="patch"):
        pat = pattern if hasattr(pattern, "sub") else re.compile(pattern)
        return apply_over(lambda t: pat.subn(repl, t), need=need, only=only, label=label)

    def method_patch(name, body_fn, files=None, need=None, label=None):
        label = label or (name + " patched")
        tgt = files if files is not None else smali_files
        tot = 0
        for f in tgt:
            t = read(f)
            if need and need not in t:
                continue
            t2, n = patch_method(t, name, body_fn)
            if n:
                write(f, t2); tot += n; print(f"[ok] {rel(f)}: {label} x{n}")
        if tot == 0:
            print(f"[warn] {label}: not found")
        return tot

    ns = dict(re=re, os=os, glob=glob, root=root, smali_files=smali_files, read=read, write=write,
              RET_RE=RET_RE, patch_method=patch_method, apply_over=apply_over,
              regex_patch=regex_patch, method_patch=method_patch)

    patch_files = sorted(glob.glob(os.path.join(patches_dir, "*.patch")))
    if not patch_files:
        raise SystemExit(f"[FAIL] no *.patch files in {patches_dir}")
    for pf in patch_files:
        print(f"-- {os.path.basename(pf)}")
        exec(compile(open(pf, encoding="utf-8").read(), pf, "exec"), dict(ns))
    print("[done] all patches applied")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: engine.py <decoded_root> <patches_dir>")
    main(sys.argv[1], sys.argv[2])
