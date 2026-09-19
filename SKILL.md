---
name: iyf-patcher
description: >-
  Build, extend, and maintain the ad-free / full-VIP client patchers for the 爱壹帆
  (iyf / ifvod) video app — the Android TV client (package tv.ifvod.classic) and the
  Electron Windows client (爱壹帆.exe). Use when patching a new version of the APK or the
  Windows installer, adding or changing a behaviour (remove ads, unlock VIP/download/speed,
  hide UI, add a Settings toggle), diagnosing why a patch stopped applying, finding the
  anchor/selector for a new UI element, or auditing the app's telemetry.
---

# iyf / ifvod client patcher

Portable instructions for the patcher toolkit that lives in **this repository**. It produces an
ad-free, full-VIP build of the 爱壹帆 clients from the stock APK / Windows installer, using
**semantic, content-anchored** patches that survive version updates.

> This file is a plain Markdown skill / agent-instructions document. It is tool-agnostic: it works
> as an Anthropic Agent Skill (the `name`/`description` frontmatter above), and it can equally be
> loaded as system/instructions context by any other LLM agent (e.g. OpenAI). Nothing here depends
> on a specific agent runtime. Paths are relative to this repository's root unless noted.

> Scope & honesty: these are **client-side** patches for local reverse-engineering. Real
> premium/HD **content and download URLs are issued by the backend to genuine VIP tokens** — no
> client patch crosses that "server ceiling" (see the last section). Don't promise server-gated
> unlocks, and don't help distribute the unsigned builds as if they were genuine/official.

## Layout (source of truth)

```
<repo root>/
├── patch.py             # unified entry: detect OS → pick client → optional download → dispatch
├── README.md            # canonical doc (Chinese); helper API tables + current patch list
├── SKILL.md             # this file
├── tv/                  # Android TV client
│   ├── patch.py         # pipeline (Linux/macOS, pure Python)
│   ├── patch.sh         # same pipeline in bash (Linux/macOS; auto-installs deps via apt on Debian/Ubuntu)
│   ├── engine.py        # applies patches/*.patch to the decoded smali tree
│   ├── repackage.py     # swaps the new dex back into the ORIGINAL apk
│   └── patches/         # NN-name.patch, applied in filename order
└── windows/             # Electron client
    ├── patch.py         # pipeline (Linux/macOS, pure Python)
    ├── patch.sh         # same pipeline in bash (Linux/macOS; auto-installs deps via apt on Debian/Ubuntu)
    ├── engine.py        # applies patches/*.patch to the extracted asar tree
    └── patches/         # NN-name.patch, applied in filename order
```

Read `README.md` first — it has the full helper API tables and the up-to-date patch list.

## Run it

**Unified entry** `patch.py` (runs on Linux/macOS; lets you pick the client, and can download the
official build first):
```
python patch.py                                # interactive: pick client → path/URL/Enter=download
python patch.py windows --download             # download official Windows installer, then patch
python patch.py tv      --download -o out.apk  # download official TV APK (v2.4.5), then patch
python patch.py windows <local-file-or-URL> [-o out]
python patch.py tv      <local-apk-or-URL>  [-o out]
```
Known official URLs live in `patch.py`'s `CLIENTS` map (download via stdlib `urllib`, no deps).
Pinned versions: **Android TV v2.4.5, Android mobile v1.7.8, Windows v3.1.5**.
Windows (v3.1.5) `https://app.anybound.vip/static/iyf/爱壹帆_Setup_3.1.5.exe` (Chinese name is
percent-encoded automatically); TV (v2.4.5) `https://app.anybound.vip/data/attachment/1-1779820631.apk`;
mobile (v1.7.8, `com.cqcsy.ifvod`) `https://app.anybound.vip/data/attachment/1-1777202801.apk`.
The `mobile/` target reuses `tv/`'s engine + repackage; its model is `com.ppde.library.bean.UserInfoBean`
and its video ads flow through `u9/c` (media3). Its ad/UI surfaces differ from TV — patch per its own anchors.

Or call a client's sub-patcher directly:
```
python tv/patch.py       <input.apk>            [output.apk]   # → signed patched APK
python windows/patch.py  <iyf_Setup_x.y.z.exe>  [output.zip]   # → portable patched app (zip)
```
Or the bash equivalents (Linux/macOS; auto-install deps via apt on Debian/Ubuntu):
```
bash tv/patch.sh <input.apk> [output.apk]   ·   bash windows/patch.sh <installer.exe> [output.zip]
```
`patch.py` (root) dispatches to the sub `patch.py`; sub `patch.py` and `patch.sh` are two
front-ends over the SAME `engine.py` + `patches/` — pick any.
Windows build runs via `爱壹帆.exe`; add `--inspect` to force-enable DevTools/right-click.
APK installs with `adb install -r`; the signing key is reused from `~/.vip_patch`.

Requirements (put tools on `PATH`): `python3`; patching the TV client also needs `apktool`,
`apksigner`, `zipalign`, a JDK; patching the Windows client also needs `7z` (7-Zip) and
`node`/`npm` (`@electron/asar`). `patch.py` finds tools via `shutil.which` and prints an install
hint if one is missing — it does NOT auto-install (only `patch.sh` does, and only on Debian/Ubuntu
via apt).

## How patches work

`patch.sh` (bash) does the packaging; `engine.py` (Python) loads every `patches/*.patch` in
filename order and executes it with helper functions in scope. A `.patch` is a **small Python
snippet** — comments + calls to helpers — and never touches packaging logic. Each helper prints
`[ok] file: label xN`, or `[warn]`/`[FAIL]` when its anchor is missing, so a broken patch is loud.

- **Windows helpers** (paths relative to asar root): `repl(glob, old, new, label)`,
  `repl_re(glob, pat, new, label)`, `resub(relpath, pat, new, label)`,
  `force_method(glob, name, decide, label)`, `inject_css(rule, marker)`.
- **TV helpers** (smali tree): `method_patch(name, body_fn, files=None, need=None, label=None)`,
  `regex_patch(pattern, repl, need=None, only=None, label=None)`,
  `apply_over(fn, need=None, only=None, label=None)`, plus primitives `patch_method`,
  `smali_files`, `read`, `write`, `RET_RE`, `re`, `os`, `glob`.

## Golden rules

1. **Anchor on content the app can't rename without breaking itself** — method names, DataBinding
   field names (`ActivityMineBinding->tvVipEnd`), resource ids (`0x7f0f0051`), stable API strings,
   distinctive class combos. NEVER anchor on line numbers, chunk-hash filenames, or minified local
   variable names.
2. **Verify the anchor is UNIQUE before writing** — grep with a count; a good literal anchor should
   appear exactly once (or a known small N). An ambiguous anchor silently corrupts.
3. **Add, don't rewrite** — one `NN-name.patch` per concern; `NN` sets order; delete/rename to
   disable. Multiple patches may stack on the same anchor (e.g. several settings inserting after
   `isDohv2Enabled`) — that's fine because each helper appends *after* the still-intact anchor.
4. **Always rebuild and check** the run output: every intended patch shows `[ok]`, zero `[FAIL]`.
5. For edits to the readable **main-process JS** (`main.js`, `globalconfig.js`, `updater.js`,
   `backgroundUpdate.js`) run `node --check` on the patched file after building.

## Adding / changing a patch — workflow

1. Extract a working copy to grep against (the pipelines clean up their temp dirs):
   - Windows: `7z x installer → app-64.7z → app.asar`, then `npx @electron/asar extract app.asar src`.
   - TV: `apktool d -f -o dec <apk>`.
2. **Find the anchor.** grep the extracted tree. For the Windows renderer bundle
   (`dist.app/main/*.js`), it's **minified single-line webpack** — search by content. Some chunks
   store Chinese as `\uXXXX` escapes, so decode before matching:
   `re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1),16)), text)`.
3. Confirm uniqueness (count == 1, or a deliberate N).
4. Write `patches/NN-name.patch` with a short comment + the helper call(s). Keep anchor strings
   byte-exact.
5. Rebuild; confirm `[ok]` and no `[FAIL]`; for main-process JS, `node --check`.

### Finding a Windows UI element's selector/anchor
The Settings window (`config.html`) is plain jQuery, but the main UI is compiled Angular Ivy —
identify elements live rather than by static analysis:
- Enable the DevTools Settings toggle (or launch `爱壹帆.exe --inspect`), then right-click →
  **Inspect** and read the element's class / DOM chain.
- Or inject a DOM probe via `webContents.executeJavaScript` that writes matches to a file (the
  renderer has `require('fs')`). Historically used to locate `.dabf`, `.ps.pggf`,
  `app-dn-user-menu-item.top-item.mx-2`.

### Adding a Settings toggle (Windows)
The Settings window is **data-driven** from `globalconfig.js`, so a new checkbox needs no HTML:
1. `globalconfig.js` constructor — add a default field (`this.myFlag = false;`).
2. `globalconfig.js` `getConfig()` — add a `{name, value:this.myFlag, type:"checkbox", key:"myFlag"}` row.
3. `main.js` `ipcMain.on("configChange")` — add a `case "myFlag": config.myFlag = !config.myFlag; …`.
4. Read `config.myFlag` where it matters. For a **live** effect (no restart) register listeners
   unconditionally and check the flag at event time (that's how the DevTools context menu works).
5. RAM-only setting (resets each launch, never written): exclude the key from the constructor's
   saved-config merge AND strip it in `saveConfig()` (see `windows/patches/50-devtools-contextmenu.patch`).

## Hard-won gotchas

- **APK: never do a full apktool rebuild.** Both aapt1 AND aapt2 reject this app's `$`-named
  resources. The pipeline assembles only the dex (`apktool b` → `build/apk/classes*.dex`) and
  `repackage.py` swaps them into the original apk, keeping resources/.so byte-identical.
- **Windows: no exe re-signing needed** — a repacked `app.asar` loads as-is.
- **TV VIP tiers are 1..3** — use `getVipLevel → 3` (9999 is out of range and won't render a badge).
- **User model landmark:** find the smali class declaring `isGiveVip(` (not the obfuscated helper).
- **Sandboxed agent environments** may refuse to run build/read commands; if a command is blocked,
  run it directly in a normal shell.
- **Verify equivalence** after a refactor: build old vs new and diff the extracted asar / decoded
  smali — they should be identical apart from cosmetic comment text.
- **smali: `apktool b` passing ≠ it runs.** The assembler is lax; ART is strict. Prefer
  **self-contained control flow** (own labels + registers dead at the injection point) over editing a
  foreign method's loop — a `goto` back into an existing loop head can also trip the runtime verifier.
- **RecyclerView: removing feed items can crash a *different*, later incremental update.** Symptom:
  `StaggeredGridLayoutManager … LazySpanLookup.invalidateAfter` → `ArrayIndexOutOfBoundsException: -1`,
  i.e. a `notifyItemRangeInserted(-1, …)`. This app's home feed has incremental loaders
  (`util/b.c()`/`e()`) that **anchor-search the list** for a bean (a section `ItemTitleBean`/
  `MovieModuleBean` by type) and return **-1** when not found. Some callers guard -1 (`U0` returns),
  others don't (`getFollowingData$1` fired `notifyItemRangeInserted(-1,2)`). Removing a section (今日热点)
  took out the anchor another loader searched for → -1 → crash — and it happened no matter WHERE the
  removal was done (`util/b.d()` build, or `MultiTypeAdapter.h()` setItems). Lessons: (1) removing feed
  data has non-local effects — grep every `util/b.c()/e()` (or indexOf-based) caller and confirm each
  guards the not-found/-1 result before `notifyItemRange*`; add the guard where missing (mirror the
  sibling that already guards). (2) still prefer filtering at the full-refresh choke (`h()` setItems →
  `notifyDataSetChanged`) over a shared builder that also feeds incremental appends. Reference:
  `22-feed-ads` (AdvertBean rows + 今日热点 `ItemTitleBean` section via a `dropping` state machine) +
  `36-feed-following-guard` (the -1 guard) — both are needed together.
- **Don't `finish()` a splash to "skip" it — it kills lifecycle-scoped init.** A splash often kicks
  off async startup (global config / API-base / "backup server") whose callbacks are
  `LiveData.observe(this, …)` bound to the splash's lifecycle. Jumping straight to the main screen by
  calling the enter-app method + `finish()` in the splash's `onCreate` tears those observers down before
  the async result returns, so the config never loads and every later request fails (symptoms:
  login stuck on "初始化中…", home "加载失败了" — looks like "no server connection", not a crash).
  To remove a splash **ad**, keep the splash alive and only neutralize the ad branch (e.g. replace the
  ad-display call with the no-ad timer path), so init still completes. See
  `mobile/patches/20-splash-ad` (replaces `A1(show ad)` with `t1()`), and the failed first attempt
  documented there.
- **A register is reused across a whole method — never clobber one with an injected `const`.** smali
  reuses the same `vN` for unrelated values within one (often huge, R8-merged) method. Injecting e.g.
  `const/4 v2, 0x0` to change one call's argument can silently corrupt a *later* use of `v2` in the same
  method. Real case: a fragment's `M()` did both the SmartRefresh setup (`t0(v2)` with `v2=1`) and the
  drakeet delegate registration further down, where `v2` was reused as an **array index**
  (`aput WatchingDelegate, v10, v2`); forcing `v2=0` put the delegate at index 0 and left index 1 null →
  `com.drakeet.multitype` NPE (null delegate) on `onResume`. Fix: to change one call's arg, point it at an
  existing register that already holds the value you want (there `v1` was already `0` and stayed the
  array's index-0), rather than mutating a live register. Before injecting a `const vN`, grep the rest of
  the method for `vN` and confirm it's dead until its next write.
- **New injected classes are fine** (`write(os.path.join(root,"smali_classes3/…/X.smali"), …)`;
  `apktool b` compiles them, cross-dex refs resolve at runtime) — see `AutoSign`/`UiHide` in the
  mobile patches. Keep helper methods `static` and give the class a no-arg `<init>` calling its super.

## Telemetry (audited)

Stock app phones home three ways on launch, ALL already neutralized by patches: `updater` (version
check → anybound.vip), `backgroundUpdate` (github remote config + `ipapi.co` geo-IP — leaks your
IP), and the **ad/gg beacon** (`get-gg-block-content` carrying `window.extra_data` = a persistent
random install UUID + platform + version). Killed by `40-updater`, `41-telemetry`, `12-ads-banner`
respectively. The Alibaba **Umeng/aplus** SDK (`scripts/203467608.js`) ships but its loader is
commented out — inert unless re-enabled. Account-level calls (watch history, favorites, recharge)
are functional, tied to the account, not silent telemetry.

## The server ceiling (state this honestly)

VIP flags, ads, buttons, and download *gates* are client-enforced and unlock cleanly. But real
premium/HD **content and download URLs come from the backend for genuine VIP tokens only** — e.g.
the APK's `GetPlayAddress` / `ERROR_CODE_PREMIUM_ACCOUNT_REQUIRED`, and the Windows download flow
returning "暂无该清晰度" for a premium clarity. No client patch changes that; don't imply otherwise.
