# 爱壹帆优化

爱壹帆客户端优化补丁

```
iyf/
├── patch.py            统一入口：识别系统 → 选客户端 → 可下载官方版 → 分发（跨平台）
├── tv/                 Android TV 客户端
│   ├── patch.py        Python 流水线（Linux/macOS）
│   ├── patch.sh        同一流水线的 bash 版（Linux/macOS；Debian/Ubuntu 自动装依赖）
│   ├── engine.py       把 patches/*.patch 应用到反编译出的 smali
│   ├── repackage.py    把新 dex 换回原始 apk
│   └── patches/        每个功能点一个 *.patch（按文件名顺序应用）
└── windows/            Windows 客户端（Electron，爱壹帆.exe）
    ├── patch.py        Python 流水线（Linux/macOS）
    ├── patch.sh        同一流水线的 bash 版（Linux/macOS；Debian/Ubuntu 自动装依赖）
    ├── engine.py       把 patches/*.patch 应用到解包出的 asar 目录
    └── patches/        每个功能点一个 *.patch（按文件名顺序应用）
```

## 使用方法

**统一入口 `patch.py`**（在 Linux / macOS 上运行）—— 选择客户端、可直接从官方地址下载再打补丁。
官方版本：**安卓电视/机顶盒客户端 v2.4.5，Windows 客户端 v3.1.5**。

```
python patch.py                                # 交互式：选客户端 → 路径/URL/回车下载官方版
python patch.py windows --download             # 下载官方 Windows 安装包（v3.1.5）并打补丁
python patch.py tv      --download -o out.apk  # 下载官方 TV APK（v2.4.5）并打补丁
python patch.py windows <本地文件或URL> [-o 输出]
python patch.py tv      <本地APK或URL>  [-o 输出]
```

下载的客户端会存到 `download/`，未用 `-o` 指定时默认输出到 `output/`（两者都已在 `.gitignore` 里忽略）。

也可以直接调用某个客户端的子脚本（同样跨平台）：

```
python tv/patch.py       <input.apk>            [output.apk]   # -> 已签名的补丁 APK
python windows/patch.py  <iyf_Setup_x.y.z.exe>  [output.zip]   # -> 免安装的补丁版应用（zip）
```

在 Linux / macOS 上也可以用等价的 bash 版（Debian/Ubuntu 上会通过 apt 自动装依赖）：

```bash
bash tv/patch.sh  ~/1-1779820631.apk   [~/atv_patched.apk]
bash windows/patch.sh  ~/iyf_Setup_3.1.5.exe   [~/iyf_3.1.5_portable_vip.zip]
```

`patch.py` 与 `patch.sh` 是同一套 `engine.py` + `patches/` 的两个入口，任选其一。依赖需放进 `PATH`：
`python3`；打 TV 客户端还需 `apktool`/`apksigner`/`zipalign`/JDK；打 Windows 客户端还需 `7z` 与
`node`/`npm`（`@electron/asar`）。`patch.py` 用 `shutil.which` 找工具，缺哪个会提示怎么装
（但不会自动安装 —— 只有 `patch.sh` 会，且仅限 Debian/Ubuntu）。

## 工作原理

`patch.sh` 负责打包流水线（用 bash，因为调用 apktool/asar/7z/zipalign/apksigner 这类外部工具是它的强项），然后把解包出来的源码目录交给 **`engine.py`**；engine 按文件名顺序加载并应用每个 `patches/*.patch`。所有补丁都是**语义化、按内容锚定**的 —— 锚点是方法名、binding 字段、资源 id 或应用无法改名（否则会自破）的代码片段 —— 因此能跨版本继续生效（不是按字节/行号的 diff）。（TV 侧还有 `repackage.py`，负责把重新组装的 dex 换回原始 apk，同时保持其余条目逐字节不变。）

每个 `.patch` 都是一小段 Python，在解包目录上运行，作用域里带有一组辅助函数。它不碰打包逻辑。

### Windows 辅助函数（Electron asar 目录；路径相对于 asar 根）
| 辅助函数 | 作用 |
|---|---|
| `repl(glob, old, new, label)` | 在匹配文件中做字面量字符串替换 |
| `repl_re(glob, pat, new, label)` | 在匹配文件中做正则 `re.sub` |
| `resub(relpath, pat, new, label)` | 在单个文件中做一次正则 `re.sub` |
| `force_method(glob, name, decide, label)` | 用大括号配对的方式重写某个 JS 方法体；`decide(arg, body)` 返回新方法体，返回 `None` 则跳过 |
| `inject_css(rule, marker)` | 往全局样式表追加一条 CSS 规则（幂等） |

### TV 辅助函数（apktool smali 目录）
| 辅助函数 | 作用 |
|---|---|
| `method_patch(name, body_fn, files=None, need=None, label=None)` | 替换某个 smali 方法体；`body_fn(returnType)` 返回新方法体 |
| `regex_patch(pattern, repl, need=None, only=None, label=None)` | 对 smali 文件做 `re.subn`（可用子串 `need` / glob `only` 过滤） |
| `apply_over(fn, need=None, only=None, label=None)` | 对 smali 文件运行任意 `fn(text)->(text,count)` |
| `patch_method`、`smali_files`、`read`、`write`、`RET_RE`、`re`、`os`、`glob` | 基础原语，供需要特殊处理的补丁使用 |

每个辅助函数都会打印 `[ok] file: label xN`，锚点找不到时打印 `[warn]`/`[FAIL]` —— 所以某个补丁一旦失效会报错，而不是悄无声息。

## 新增 / 修改一项行为

在对应的 `patches/` 目录里丢一个新的 `NN-name.patch`（`NN` 前缀决定顺序）并调用辅助函数即可，无需改动其它任何地方。要停用某项行为，删掉或改名它的文件即可。

## 已打的补丁

**Android TV v2.4.5（`tv/patches/`）**
- `10-vip-core` — `getVipLevel`→3、`isGiveVip`→true、`getVipTypeName`→至尊VIP（最高档）
- `11-ads-pause` — 关闭暂停画面的广告横幅
- `20-store-launcher` — 移除 VIP 商店入口
- `30-watermark-logo` — 隐藏视频内的水印 logo
- `31-topbar-vip` — 隐藏首页顶栏的 VIP 按钮
- `32-mine-vip-button` — 隐藏「我的」页的「开通VIP」按钮
- `33-mine-expiry` — 到期时间显示为「永不到期」
- `40-feed-ads` — 过滤掉首页的跳转/广告卡片
- `41-skip-ad-tip` — 抑制「VIP已跳过广告」横幅（播放继续）

**Windows v3.1.5（`windows/patches/`）**
- `10/11/12/13-ads-*` — 片头、暂停、横幅（`hideAds`）广告，以及残留的空广告容器
- `20-vip-permissions` — 解锁按权限控制的功能（2倍速、表情、弹幕颜色、投票）
- `21-vip-membership` — 会员标识 → royalVip
- `22-vip-userstate` — 生效的最高档 VIP（`roleId=3`、`daysOfMembership=9999`、`token.gid=3`）
- `23/24/25-download-*` — 解锁下载页、下载按钮、清晰度选择
- `30-ui-topbar-vip` — 移除顶栏「VIP{n}折」优惠按钮
- `40-updater` / `41-telemetry` — 停用自动更新与 geo-IP 调用
- `50-devtools-contextmenu` — 新增设置项「启用开发者工具（右键检查）」，提供右键 Inspect/DevTools 菜单；仅存内存（每次启动都为关，且不写盘），`--inspect` 启动参数仍可开启
- `60-setting-close-quits` — 新增设置项「关闭时退出程序（不最小化到托盘）」，让窗口 ✕ 直接退出而非缩小到托盘（默认关）

## 给 AI 代理

要用 AI 代理来给新版本打补丁、新增/修改补丁、排查失效、或审计遥测，请让它先读并遵循
[`SKILL.md`](./SKILL.md) —— 那里有完整的方法论、辅助函数 API、以及踩过的坑。它是与工具无关的
可移植说明文档，可作为 Anthropic Agent Skill，也可作为任意 LLM 代理（如 OpenAI/Codex，见
[`AGENTS.md`](./AGENTS.md)）的指令加载。
