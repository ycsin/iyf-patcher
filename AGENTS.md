# Agent instructions

This repository is a patcher toolkit for the 爱壹帆 (iyf / ifvod) video clients — an Android TV
client (`tv/`) and an Electron Windows client (`windows/`) — producing ad-free, full-VIP builds via
semantic, content-anchored patches.

**Read and follow [`SKILL.md`](./SKILL.md).** It is the full, tool-agnostic guide: architecture,
how to run the pipelines, the helper API, the workflow for adding/changing a patch, how to find
stable anchors and UI selectors, verification steps, and the hard-won gotchas. Everything below is
just the essentials so you don't miss them if you only read this file.

## Run
```bash
bash tv/patch.sh       <input.apk>            [output.apk]   # → signed patched APK
bash windows/patch.sh  <iyf_Setup_x.y.z.exe>  [output.zip]   # → portable patched app (zip)
```
Requirements: `python3`, `bash`, `7z`; TV also `apktool`/`apksigner`/`zipalign`/JDK; Windows also
`node`/`npm` (`@electron/asar`). Patches live in `tv/patches/` and `windows/patches/` as
`NN-name.patch` (small Python snippets), applied in filename order by `engine.py`.

## Non-negotiable rules
- **Anchor on rename-proof content** (method names, DataBinding fields, resource ids, stable API
  strings) — never line numbers, chunk-hash filenames, or minified locals.
- **Verify each anchor is unique** (grep + count) before writing a patch.
- **Rebuild after any change**; every intended patch must print `[ok]` with zero `[FAIL]`. For
  edits to readable main-process JS, also run `node --check`.
- **One `NN-name.patch` per concern**; add/rename/delete rather than editing the pipeline.

## Honesty guardrail (important)
These are **client-side** patches. VIP flags, ads, buttons, and download *gates* unlock cleanly,
but real premium/HD **content and download URLs are issued by the backend to genuine VIP tokens
only** — no client patch crosses that "server ceiling". Do not claim otherwise, and do not help
distribute the unsigned builds as if they were genuine/official. This is local reverse-engineering.
