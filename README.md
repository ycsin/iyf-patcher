# 爱壹帆优化

爱壹帆客户端优化补丁

```
iyf/
├── patch.py            统一入口：选客户端 → 可下载官方版 → 分发（Linux/macOS）
├── tv/                 安卓电视/机顶盒 客户端（tv.ifvod.classic）
│   ├── patch.py        Python 流水线（Linux/macOS）
│   ├── patch.sh        同一流水线的 bash 版（Linux/macOS；Debian/Ubuntu 自动装依赖）
│   ├── engine.py       把 patches/*.patch 应用到反编译出的 smali
│   ├── repackage.py    把新 dex 换回原始 apk
│   └── patches/        每个功能点一个 *.patch（按文件名顺序应用）
├── mobile/             安卓手机 客户端（com.cqcsy.ifvod）—— 复用同一套引擎/换 dex
│   ├── patch.py        Python 流水线（Linux/macOS）
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
官方版本：**安卓电视/机顶盒客户端 v2.4.5，安卓手机客户端 v1.7.8，Windows 客户端 v3.1.5**。

```
python patch.py                                # 交互式：选客户端 → 路径/URL/回车下载官方版
python patch.py tv      --download -o out.apk  # 下载官方 TV APK（v2.4.5）并打补丁
python patch.py mobile  --download -o out.apk  # 下载官方安卓手机 APK（v1.7.8）并打补丁
python patch.py windows --download             # 下载官方 Windows 安装包（v3.1.5）并打补丁
python patch.py <client> <本地文件或URL> [-o 输出]   # client = tv | mobile | windows
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

**安卓手机 v1.7.8（`mobile/patches/`）**（复用 `tv/` 的引擎与换 dex 流程）
- `10-vip-core` — 同上（模型为 `com.ppde.library.bean.UserInfoBean`）：`getVipLevel`→3、`isGiveVip`→true、`getVipTypeName`→至尊VIP ✅
- `11-verifytrust` — 修复重签名后无法登录：`com.ppde.verifytrust` 签名校验 —— 让请求头哈希 `c.a()` 恒为原版签名、`c.b()`/启动门禁 `d.b(Context)` 恒为 true ✅
- `20-splash-ad` — 开屏广告：保留开屏页与其初始化（`F1()` 拉全局配置/备用服务器，绑在开屏页生命周期上），只把 `w1()` 广告分支里的 `A1(showURL)`（显示广告图+自带倒计时进主页）替换为 `t1()`（无广告分支的 2 秒进主页）。于是开屏页照常显示与初始化，只是不显示广告图，2 秒后正常进主页。`A1` 全类仅此一处调用。⚠️ 早期用“`onCreate` 末尾直接 `E1()`+finish 跳过整个开屏”会在 `F1()` 异步配置返回前销毁其生命周期观察者 → 全局配置永不加载 → 登录“初始化中…”、首页“加载失败了”；故改为只抑制广告、保留开屏初始化 ✅
- `21-video-ads` — 前贴/中插广告：`u9/c.e(J)`（按进度查找广告插入点）返回 null ✅
- `22-feed-ads` — 首页信息流过滤，都在 drakeet `MultiTypeAdapter.h(List)`（setItems，之后 `notifyDataSetChanged` 整表刷新）里就地进行：①广告卡片 `AdvertBean`（`j9/c` 委托）——交错网格+间距装饰下折叠行会留空隙，故直接不入列表；②「今日热点」板块——`util/b.d()` 拍平成 `ItemTitleBean(itemName="今日热点")` 表头+`MovieModuleBean` 内容，用 dropping 状态机整段删（板块边界 `HomeNetBean`/`util/c`(历史记录)/`RecommendMultiBean` 复位保留，不误伤相邻板块）。就地删、仅对 ArrayList、保持 `items===p` 引用相等。**必须配合 `35`**：删今日热点会带走历史记录插入所依赖的锚点 ✅
- `22`（顶部轮播）— `com.youth.banner.Banner<AdvertBean>`（`HomeNetBean.bannerList`）**混合**广告位与内容位，App 用 `BannerViewAdapter.d()` 的 `resourceType==1` 判定广告位——故 `getBannerList()` 只滤掉 `resourceType==1`、保留内容位 ✅
- `23-danmu-ads` — 弹幕广告：快手 akdanmaku 渲染，`danmaku/e.h(I,BarrageBean)` 转成 DanmakuItemData（`isAdvert` 的会做成带按钮的广告弹幕）。转换/入队都在协程 `e$f` 循环里，在 `check-cast` 出 BarrageBean 后判 `isAdvert()`：是广告就推进下标并跳过入队 —— 广告弹幕不渲染，真实弹幕照常（覆盖批量+socket 两种来源） ✅
- `24-pause-ad` — 暂停贴片广告：`LiteVideoPlayer.p0(AdvertBean,…)`（把广告加载进播放器内浮层）置空 ✅
- `25-detail-banner` — 详情页“点赞/评论”上方的广告横幅（`com.youth.banner.Banner<AdvertBean>`）：`VideoIntroductionFragment.I0(list)` 入参强制置空，走 App 自带“无广告”分支——横幅与占位 Space 一起 GONE，无残留间距 ✅
- `30-mine-expiry` — 「我的」页 VIP 到期时间显示为“永不到期”：卡片 `vipTime`（`LayoutMineBinding` 字段 `y`）原用 `getEDate()` 拼 “%1$s到期”（string `0x7f1305b1`）；在 `MineFragment.d0()` 的 setText 前把字符串寄存器覆盖为字面量（不改 res，走 dex） ✅
- `31-mine-open-vip` — 「我的」页隐藏 VIP 区：①非会员提示图 `notVipTip`（字段 `l`）恒 GONE；②整张「至尊VIP」会员卡片 `vipInfo`（字段 `w`）在 d0 设为可见后立即置 GONE（VIP 标识/到期/续费按钮整块都不显示）；③宿主 `MainActivity.startBuySelf(View)` 置空（防御性，即使卡片可点也不跳购买）。（因整卡隐藏，`30-mine-expiry` 的“永不到期”已看不到，保留无害）✅
- `32-mine-ad-center` — 「我的」页“个人服务”里删除「广告中心」「VIP开通记录」「大V认证」三项：菜单标题来自 string-array `person_menu`（可变 List），动作来自并行整型表（字段 `c`，`c.get(pos)` 决定 sparse-switch 路由）。在 `bigVSwitch` 分支合流处用 `indexOf(标题)` 从两张表同下标删除（各段用不同标签），其余项标题/路由仍对齐 ✅
- `33-hide-bottom-nav` — 隐藏底部导航「发现」+「VIP」：底部是 `activity_main.xml` 的 RadioGroup，各项 `button_find`(0x7f0a010f)/`button_vip`(0x7f0a0114)。新增自带类 `com.ppde.ppcd.patch.UiHide.hideBottomTabs(Activity)`（findViewById→GONE，找不到就跳过），在 `MainActivity.onCreate` 末尾调用 ✅
- `34-hide-home-recommend` — 隐藏首页「为你推荐」板块：它由专用加载器 `RecommendFragment.S0()`（getRecommendedData）拉取并拼装（`ItemTitleBean(标题=为你推荐)` + 内容）。把 `S0()` 置空即不再加载/拼装该板块 ✅
- `35-home-hot-history` — 删今日热点后保住「历史记录」：历史记录由 `getFollowingData$1 -> util/b.c()` 反查“最后一个 `type==1` 的 `MovieModuleBean`”锚点后插入（`ItemTitleBean(历史记录)`+`util/c` 内容），而那锚点正是今日热点的内容。①`c()` 找不到锚点时把插入位置从 -1 改为 0（插到列表顶部），不再返回 -1；②`getFollowingData$1` 那次插入的通知从 `notifyItemRangeInserted(pos,2)` 改为 `notifyDataSetChanged()`（顶部插入后位置与按位通知对不上，改整表刷新，交错网格才不会 `LazySpanLookup.invalidateAfter(-1)` 越界崩）。于是今日热点没了、历史记录仍在（移到信息流顶部）✅
- `37-home-no-loadmore` — 首页底部“精彩内容即将呈现…”加载器：那是 SmartRefreshLayout 上拉加载更多页脚（`RefreshFooter`/`refresh_tip`），加载的是已被 `34` 移除的「为你推荐」下一页，故一直挂着。`RecommendFragment.M()` 里 `t0(v2)`=`setEnableLoadMore`、`u0(v2)`=`setEnableRefresh`（`v2=1`）。把 `t0` 的入参从 `v2` 改读 `v1`（此处恒为 0）→ `setEnableLoadMore(false)`，页脚不再出现，下拉刷新不受影响。⚠️ 不能像早前那样注入 `const/4 v2,0x0`：同一个 `M()` 后面把 **`v2` 复用为 util/c 一对多注册第二个委托的数组下标**（`aput WatchingDelegate, v10, v2`，v2=1），改 v2 会让下标 1 变 null → drakeet 收到 null 委托 → onResume 崩溃 ✅
- `40-auto-sign` — 启动静默自动签到：新增自带类 `com.ppde.ppcd.patch.AutoSign`（`o8/b` 空回调 + 静态 `fire()` 复刻 `SignGetGiftActivity.k2()` 经 `network.d.i(url=base.b.q1(),…)` 的签到请求，自动带鉴权头），在 `MainActivity.onCreate` 末尾调用一次。在主界面起来后才发请求、不碰开屏初始化。（连不上服务器排查时曾临时禁用以隔离，实为 `20` 早期做法所致，已恢复）✅

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
