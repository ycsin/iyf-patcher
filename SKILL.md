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
├── README.md            # canonical doc (Chinese); helper API tables + current patch list
├── SKILL.md             # this file
├── tv/                  # Android TV client
│   ├── patch.sh         # pipeline: deps → apktool decode → engine → assemble dex → repackage → sign
│   ├── engine.py        # applies patches/*.patch to the decoded smali tree
│   ├── repackage.py     # swaps the new dex back into the ORIGINAL apk
│   └── patches/         # NN-name.patch, applied in filename order
└── windows/             # Electron client
    ├── patch.sh         # pipeline: deps → NSIS→app-64.7z→app.asar → engine → repack asar → zip
    ├── engine.py        # applies patches/*.patch to the extracted asar tree
    └── patches/         # NN-name.patch, applied in filename order
```

Read `README.md` first — it has the full helper API tables and the up-to-date patch list.

## Run it

```bash
bash tv/patch.sh       <input.apk>              [output.apk]   # → signed patched APK
bash windows/patch.sh  <iyf_Setup_x.y.z.exe>    [output.zip]   # → portable patched app (zip)
```
Windows build runs via `爱壹帆.exe`; add `--inspect` to force-enable DevTools/right-click.
APK installs with `adb install -r`; the signing key is reused from `~/.vip_patch`.

Requirements: `python3`, `bash`, `7z`; TV also needs `apktool`, `apksigner`, `zipalign`, a JDK;
Windows also needs `node`/`npm` (`@electron/asar`). On Debian/Ubuntu `patch.sh` installs missing
tools via `apt`; on other OSes install the equivalents and put them on `PATH`.

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
- **Windows: no exe re-signing needed.** The asar integrity fuse
  (`EnableEmbeddedAsarIntegrityValidation`) is OFF, so a repacked `app.asar` loads as-is.
- **TV VIP tiers are 1..3** — use `getVipLevel → 3` (9999 is out of range and won't render a badge).
- **User model landmark:** find the smali class declaring `isGiveVip(` (not the obfuscated helper).
- **Sandboxed agent environments** may refuse to run build/read commands; if a command is blocked,
  run it directly in a normal shell.
- **Verify equivalence** after a refactor: build old vs new and diff the extracted asar / decoded
  smali — they should be identical apart from cosmetic comment text.

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
