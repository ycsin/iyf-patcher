#!/usr/bin/env python3
# =============================================================================
#  engine.py —— Windows（Electron）版应用的补丁引擎。
#
#  用法：  python3 engine.py <asar_src_root> <patches_dir>
#
#  按文件名顺序把每个 <patches_dir>/*.patch 应用到解包出的 asar 目录。每个 *.patch
#  都是一小段 Python，在下方这套辅助 API 的作用域里执行；锚点是按内容匹配的，因此能
#  扛住 chunk 文件名 hash 的变化。由 patch.sh 调用 —— 一般不直接运行。
# =============================================================================
import sys, glob, os, re


def main(root, patches_dir):
    def rel(f):
        return os.path.relpath(f, root)

    def repl(globpat, old, new, label, required=True):
        hits = 0
        for f in glob.glob(os.path.join(root, globpat)):
            s = open(f, encoding="utf-8", errors="surrogatepass").read(); c = s.count(old)
            if c:
                open(f, "w", encoding="utf-8", errors="surrogatepass").write(s.replace(old, new))
                hits += c; print(f"[ok] {rel(f)}: {label} x{c}")
        if hits == 0:
            print(f"[{'FAIL' if required else 'warn'}] {label}: pattern NOT found")
        return hits

    def resub(relpath, pat, new, label):
        f = os.path.join(root, relpath)
        if not os.path.exists(f):
            print(f"[warn] {label}: {relpath} missing"); return 0
        s = open(f, encoding="utf-8", errors="surrogatepass").read(); s2, n = re.subn(pat, new, s, count=1)
        if n:
            open(f, "w", encoding="utf-8", errors="surrogatepass").write(s2); print(f"[ok] {relpath}: {label} x{n}")
        else:
            print(f"[warn] {label}: pattern NOT found in {relpath}")
        return n

    def repl_re(globpat, pat, new, label):
        hits = 0
        for f in glob.glob(os.path.join(root, globpat)):
            s = open(f, encoding="utf-8", errors="surrogatepass").read(); s2, n = re.subn(pat, new, s)
            if n:
                open(f, "w", encoding="utf-8", errors="surrogatepass").write(s2); hits += n
                print(f"[ok] {rel(f)}: {label} x{n}")
        if hits == 0:
            print(f"[FAIL] {label}: pattern NOT found")
        return hits

    def _matchbrace(s, ob):
        depth = 0; j = ob
        while j < len(s):
            c = s[j]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return -1

    def force_method(globpat, name, decide, label):
        hits = 0; pat = re.compile(re.escape(name) + r'\(([A-Za-z_$])\)\{')
        for f in glob.glob(os.path.join(root, globpat)):
            s = open(f, encoding="utf-8", errors="surrogatepass").read(); out = []; i = 0; ch = 0
            while True:
                m = pat.search(s, i)
                if not m:
                    out.append(s[i:]); break
                ob = m.end() - 1; cb = _matchbrace(s, ob)
                if cb < 0:
                    out.append(s[i:]); break
                nb = decide(m.group(1), s[ob + 1:cb]); out.append(s[i:m.start()])
                if nb is not None:
                    out.append(f"{name}({m.group(1)}){{{nb}}}"); ch += 1
                else:
                    out.append(s[m.start():cb + 1])
                i = cb + 1
            if ch:
                open(f, "w", encoding="utf-8", errors="surrogatepass").write("".join(out)); hits += ch
                print(f"[ok] {rel(f)}: {label} x{ch}")
        if hits == 0:
            print(f"[warn] {label}: no methods matched")
        return hits

    def inject_css(rule, marker):
        hits = 0
        for f in glob.glob(os.path.join(root, "dist.app/main/styles.*.css")):
            s = open(f, encoding="utf-8", errors="surrogatepass").read()
            if ("iyf_patch: " + marker) not in s:
                open(f, "a", encoding="utf-8", errors="surrogatepass").write(
                    "\n/* iyf_patch: " + marker + " */\n" + rule + "\n")
                hits += 1; print(f"[ok] {rel(f)}: css +{marker}")
        if hits == 0:
            print(f"[warn] css '{marker}': no stylesheet found (or already injected)")
        return hits

    ns = dict(repl=repl, resub=resub, repl_re=repl_re, force_method=force_method,
              inject_css=inject_css, root=root, re=re, glob=glob, os=os)

    patch_files = sorted(glob.glob(os.path.join(patches_dir, "*.patch")))
    if not patch_files:
        raise SystemExit(f"[FAIL] no *.patch files in {patches_dir}")
    for pf in patch_files:
        print(f"-- {os.path.basename(pf)}")
        exec(compile(open(pf, encoding="utf-8").read(), pf, "exec"), dict(ns))
    print("[done] all patches applied")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: engine.py <asar_src_root> <patches_dir>")
    main(sys.argv[1], sys.argv[2])
