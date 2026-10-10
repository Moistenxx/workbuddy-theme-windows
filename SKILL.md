---
name: workbuddy-theme-windows
description: WorkBuddy 主题变更（Windows 版）—— 给桌面端换照片背景 wallpaper。上传/指定一张图，一条命令生成 2560x1440 壁纸并注入消息区背景，支持双旋钮调透明度（白纱 alpha + 模糊 blur），可随时卸载恢复官方原版。当用户说"换背景""把这张图设成背景""改壁纸""看不清字调下透明度"时使用。仅适用于 Windows，macOS 请用 workbuddy-theme-macos。
date: 2026-10-11
tags: [workbuddy, theme, skin, wallpaper, background, appearance, windows]
agent_created: true
---

# WorkBuddy 主题变更（Windows 版）

给 Windows 版WorkBuddy 桌面端换照片背景。**从给一张图到最终完成，一条命令。**

> macOS 用户请改用 `workbuddy-theme-macos`。两个包共用同一套 CSS 逻辑，
> 但 `local-file://` URL 拼法与 Python 解释器调用方式在两个平台不同，故分开维护。

给 WorkBuddy 桌面端换照片背景。**从给一张图到最终完成，一条命令。**

## ⚠️ 七条铁律（两天实战换来的，先读这段）

**1. 官方 skin.css 必须"追加"，绝不能"替换"。**
踩过：整文件写入导致部署文件只剩 77 行、官方 1229 行样式全丢，界面崩坏。脚本已处理（优先读根`skin.css`，缺失时从内层 `workbuddy-skin-*/skin.css` 复制；重复安装先剥旧片段保证幂等）。

**2. 会话主体那块白底由 `--wb-color-bg-primary-default` 刷，不是容器。**
官方原码：`.cr-agent__body, .cr-frame__content { background: var(--wb-color-bg-primary-default, #f2f2f2) }`。
踩过：只改了容器 → 中间整块仍是白色。这个变量**必须**跟着`--alpha` 一起半透。

**3. 找不到元素时，去 app.asar 挖官方 CSS，不要猜 class 名。**
踩过：连续 5 轮凭猜测改class，全部无效。正确做法：
```python
# macOS
d = open('/Applications/WorkBuddy.app/Contents/Resources/app.asar','rb').read()
# Windows（本机）
d = open(r'D:\浏览器下载地址\WorkBuddy\resources\app.asar','rb').read()
txt = d.decode('latin1')
re.findall(r'\.([A-Za-z0-9_-]+)\s*\{([^}]{0,300})\}', txt)   # 提取全部规则
```
官方 CSS 原文是唯一可靠依据，皮肤文件里的选择器可能过时。

**4. ★白纱只能有一层，而且必须烤进图片里，不能刷在容器上。★**
这是老板反复反馈"中间还是白纱"的**唯一根因**。踩过两次：
- 第一次：每个容器都刷 `rgba(255,255,255,.25)` → 容器嵌套三层，25% 叠成 **43%**，再叠一层 58%，看起来就是"蒙了层白纱"
- 第二次：改用 `::before` 覆盖层 → 图片已烤过一次白纱，又叠一层，还是白

**正确做法（当前实现）**：
```python
# setup.py —— 白纱在图片层面只混一次
veil = Image.new("RGB", im.size, (255,255,255))
im = Image.blend(im, veil, alpha)     # ★alpha 默认为 0 → 这行直接跳过，零发白
im.save(WALL)
```
```css
/* CSS 里一个白都不刷 */
body .workbuddy-app *, body .teams-container *, body .claw-workspace *,
body .cr-agent *, body .cr-frame *, body .cr-message-list * {
  background-color: transparent !important;
  background-image: none !important;
  box-shadow: none !important;
}
/* 官方那 522 个背景变量一律 transparent 兜底 */
:root, body, .cr-theme, .cr-agent__body, .cr-frame__content {
  --wb-home-bg-secondary: transparent !important;
  --wb-bg-primary: transparent !important;
  --wb-color-bg-primary-default: transparent !important;
  /* ... 共 11 个 */
}
```
**模糊也烤进图片**（`GaussianBlur`），不要用 CSS `backdrop-filter` —— 多层容器下它行为不可控。

**5. 调透明度必须从 base 重新生成，不能在旧图上叠加。**
存一份 `wallpaper_base.png`（只裁剪 + 亮度，无白纱无模糊），每次 `tune` 都从它重新 mix。否则调三次就变成三层白。
```python
def regenerate_wallpaper(alpha, blur):
    im = Image.open(BASE_WALL)          # ← 永远从 base 读
    if blur > 0: im = im.filter(GaussianBlur(blur))
    im = Image.blend(im, white, alpha)
```

**6. 官方有 522 个背景类变量，所以必须用通配 + 变量兜底，不要枚举。**

**7. 「老板说透明」= 完全透出背景，不是半透白纱；而且「全部」是硬要求。**
老板原话：「我要的是纯透明的那种」「全部整体都是我给的背景，并不存在对话框还是原来的白色，是全部」。
**"全部"是硬指标**：侧栏、输入框、消息卡片、顶栏、弹窗 —— 全部 `transparent`，不允许任何一块保留白色卡片。
`--alpha` **必须是 0**。任何大于 0 的值都会让画面发白（`1-(1-a)ⁿ`），违背需求。字看不清请调 `--blur`（模糊不发白），**不要动 alpha**。

> 📄 完整逆向笔记（含加载机制、已排除的无效路径、变量清单、六轮失败复盘）见
> `reference/逆向笔记.md` —— **改这个 skill 前建议先读一遍**，能省掉大量试错。

## 快速使用（Windows）

```bash
S=~/.workbuddy/skills/workbuddy-theme-windows/scripts/setup.py
P=python     # 已实测：Python 3.13.14 + Pillow 12.3.0

# 1) 从照片生成并安装（核心命令）
$P $S <图片路径> --alpha 0 --blur 0      # ★双 0 = 原片零处理，默认值

# 2) 生效：WorkBuddy 设置→外观 切走再切回（不用重启）

# 3) 调效果
$P $S tune --blur 10# 字看不清时加模糊（不会发白）
$P $S show                # 看当前值
$P $S tune 0                    # alpha 归零（纯透明）
$P $S reset                   # 恢复默认 alpha 0 / blur 0

# 4) 卸载，恢复官方原版
$P $S uninstall
```

**Windows 上先确认解释器带Pillow**：
```powershell
python -c "import PIL; print(PIL.__version__)"
# 缺则：python -m pip install Pillow
```

### Windows 专属陷阱

**★`local-file://` URL 必须逐段 URI 编码，路径分隔符转正斜杠 ★**
这是 Windows 版最容易踩的坑，macOS 版不会暴露（因为 posix 路径恰好拼得对）。
官方 `app.asar` → appearance 模块的权威写法：
```js
const encoded = absPath.replace(/\\/g, "/")              // 反斜杠 → 正斜杠
  .split("/").map(p => p === "" ? "" : encodeURIComponent(p)).join("/");
return `local-file://${encoded.startsWith("/") ? "" : "/"}${encoded}`;
```
Windows 上产出：
```
local-file:///C%3A/Users/<你>/.workbuddy/appearance-resources/theme-xxx/assets/wallpaper.png
│          │  │    └── 目录分隔符已转成 /，冒号被 encode 成 %3A
│          │  └── encodeURIComponent 不转义冒号，所以是 %3A
│          └── 三斜杠（少一个就解析失败）
```
踩过的错法：`"local-file://" + os.path.join(...)` → `local-file://C:\Users\...\wallpaper.png`
（反斜杠 + 两斜杠），`net.fetch` 直接加载失败，表现为「配了但没背景」。
脚本已用 `to_local_file_url()` 处理，与官方 JS 输出**逐字节一致**（已用 Node 交叉验证）。

**用户目录含中文或空格时尤其重要**：不做 encode 一定加载不出来
（例：`C:\Users\张三\...` → 必须是 `%E5%BC%A0%E4%B8%89`）。

**挖 app.asar 的 Windows 路径**：
```python
d = open(r'D:\浏览器下载地址\WorkBuddy\resources\app.asar','rb').read()
txt = d.decode('utf-8', 'ignore')
import re
re.findall(r'\.([A-Za-z0-9_-]+)\s*\{([^}]{0,300})\}', txt)
```

**找可用的Python**：脚本只依赖标准库 + Pillow，`python` / `py -3` 均可。

>脚本内部全用 `os.path.expanduser("~")` 和 `os.path.join`，路径本身跨平台无需改动。
> 需要覆盖主题缓存目录时设环境变量 `WB_BASE`。

## 参数说明

| 参数 | 管什么 | 范围 | 默认 |
|---|---|---|---|
| `--alpha` | **加白强度**（在图片层面混一次白） | 0~1 | **0** |
| `--blur` | 背景模糊 px（烤进图片，**不会加白**） | 0~30 | **0** |

**`--alpha` 默认 0 = 纯透明，一丝白都不加。**
它**只作用于图片本身**（决定壁纸里混多少白），**不作用于任何容器** —— CSS 里所有容器一律 `transparent`。

| alpha | 效果 |
|---|---|
| **0** | **★纯透明：原图直接透出，零发白（老板要求）** |
| 0.1 | 极轻微雾感 |
| 0.3 | 明显朦胧，字更清楚 |
| 0.6 | 很朦胧 |
| 1 | 全白，等于没皮肤 |

> **老板原话（最重要）**：
> 「我不要你上面有发白的效果，我要的就是透明，纯透明那种，**一定不要有发白的效果**，就只是透明」
>
> 翻译成参数：**`--alpha 0`**。任何大于 0 的值都会让画面发白（`1-(1-a)ⁿ`），违背需求。
> 若因正文难读需要加白，优先调 `--blur`（加模糊**不会发白**），而不是加 alpha。

**`--blur` 不发白**：`GaussianBlur` 只做邻域平均，不引入任何白色。所以「文字看不清」的正确解法是 `--blur 10~15`，**不是** `--alpha`。

## 前置条件

**必须先在 WorkBuddy 设置→外观 里任选一个主题**。这一步会在本地建立主题缓存目录：
```
~/.workbuddy/appearance-resources/theme-<id>-<时间戳>/
```
没有这个目录，脚本会提示找不到。

## 照片要求

| 项 | 要求 |
|---|---|
| 比例 | **16:9 横图**（脚本自动裁成 2560×1440，不变形） |
| 尺寸 | ≥1600px 宽即可，脚本会放大 |
| 格式 | PNG / JPG / JPEG / WebP 均可 |
| 内容 | 人物别放正中间（被文字盖住），建议偏一侧；避开顶部 15%、底部 20% |

**★不做亮度调整**：脚本**不会**自动压暗。老板要「原片一样清楚」，压暗会让画面发灰、看着不真实。

## 脚本行为

1. 把照片裁/放成 2560×1440 + 亮度校正 → `scripts/assets/wallpaper_base.png`（无滤镜）
2. 从 base 生成 `scripts/assets/wallpaper.png`：模糊 + **混一次 alpha 白纱（唯一一层）**
3. 复制到每个主题缓存目录的 `assets/wallpaper.png`
4. 读取该目录的**官方 skin.css 作为基底**，在末尾追加一段背景规则
5. 图片路径改写成该目录的 `local-file://` 绝对路径（相对路径注入时解析不到）
6. 配置存 `scripts/state.json`，`tune` 时读取

## 官方 CSS 结构速查（实测，勿推翻）

**① 外观云端驱动**：本地缓存不校验内容，`tryReadCachedCss` 命中即注入。覆盖 `skin.css` 即可生效。

**② 生效方式**：设置→外观 **切走再切回**，实测无需重启。

**③ 右侧区域靠 `data-view-id` 属性划分，不是 class**：
```css
.teams-container [data-view-id="sidebar"] { background: var(--wb-home-bg-primary); }
.teams-container [data-view-id]:not([data-view-id="sidebar"]) { background: var(--wb-home-bg-secondary); }
.teams-container.is-mac { --wb-home-bg-primary:#f2f2f2; --wb-home-bg-secondary:#ffffff; }
```
`data-view-id` 只有 `sidebar`（左栏）和 `detail-panel` 两个值。

**④ 需要半透化的变量清单**（缺一项就有一块不变）：

| 变量 | 服务于 |
|---|---|
| `--wb-home-bg-secondary` | 首页/新建任务主区 |
| `--wb-home-bg-primary` | 左栏 |
| `--wb-bg-primary` | 对话页 `.claw-workspace` |
| **`--wb-color-bg-primary-default`** | **会话主体 `.cr-agent__body` / `.cr-frame__content`** ← 最易漏 |
| `--cr-bg-canvas` | 会话画布 |
| `--cr-bg-primary-default` / `--cr-bg-secondary` | 会话内部 |

**⑤ 覆盖必须加 `body` 前缀**提高特异性——官方皮肤里已有 `body .teams-container.is-mac { ... }` 且位置更靠前。

**⑥ 内容层要放行**（否则壁纸被盖住）：
`.cr-message-list` / `.cr-message-list__content` / `.cr-message-list-viewport` / `.cr-message-list__bottom-mask` / `.cr-agent__body` / `.cr-frame__content` 全部 `background-color: transparent`。

**⑦ 用 `background-attachment: fixed`** 让壁纸不随内容滚动。

## 排错

| 现象 | 原因与对策 |
|---|---|
| 完全没变化 | ① 没切走切回刷新缓存 ② 没先选过主题（无缓存目录） |
| **只有顶部有背景** | 只覆盖了两套视图之一，或漏了 ⑥ 的内容层放行 |
| **中间整块仍白** | 漏了 `--wb-color-bg-primary-default`（见铁律 2） |
| 界面样式错乱 | 官方基底被替换掉了（见铁律 1），确认部署文件行数 ≈1229+ |
| 字看不清 | **调高 `--blur`**（模糊不发白）。**绝不要调高 `--alpha`** —— 那会让画面发白，违背需求 |
| **画面发白** | `--alpha` 不是 0。执行 `$P $S tune 0` 归零 |
| 图片不显示 | 确认 `scripts/assets/wallpaper.png` 存在；看脚本打印的亮度处理信息 |
| 改了没反应 | 改的是 `scripts/assets/wallpaper.png`（源），不是主题目录里的副本 |

**自查命令**（部署后跑一次）：
```bash
D=~/.workbuddy/appearance-resources/theme-*/skin.css
grep -c '' $D            # 行数应≈1399（官方1229+追加约170），若<200 说明基底丢了
grep -c "照片背景（由 setup.py 生成" $D          # 应=1
grep -E "wb-color-bg-primary-default: transparent|cr-bg-canvas: transparent" $D   # 应≥1
# 注意：最终覆盖值是 transparent（不是 rgb！）。早期版本曾写 rgb，故此法对旧文档会误报"未写入"。
# 行数不是硬指标——基底可能已被用户加过自定义规则；以「脚本标记 + transparent 覆盖」两条grep为准。
```

## 修改脚本时的注意事项

**别用 `str.replace()` 或正则回填改这个脚本里的三引号 CSS 模板**——实测反复踩坑两次：
- 用正则 `re.sub(r'VAR_DECL = """(.*?)\n"""', ...)` 回填 → 会把 `VAR_DECL = """` 前缀一起带进来，产生 `VAR_DECL = """VAR_DECL = """` 这种重复声明
- 重复声明会让三引号不闭合，报错还指向后面无关的行

**正确做法：用 Edit 工具精确编辑，改完立刻验语法。**
```python
import ast; ast.parse(open('setup.py', encoding='utf-8').read())   # 必须通过
```

其他踩过的坑：
- **`local-file://` URL 的坑详见上文「Windows 专属陷阱」，改脚本时务必回看。**
- CSS 模板不能用 `str.format()`——花括号会被当占位符。脚本用 `__NAME__` 占位符 + `.replace()`。
- 从 `state.json` 读出的数值可能是字符串，比较前要 `int(float(x))`。
- `sys.argv[1:]` 才是完整参数（`argv[1]` 是子命令，`argv[2]` 才是图片路径）。
- BSD `grep` 的 `|` 需转义，否则误判"规则不存在"。
- `grep` 匹配中文段落后数出来的行数可能不准（**用 `awk` 从起始行往后截取再统计**，我因此误判过"规则没写入"）。
- 校验部署结果时，别拿"总行数"当唯一依据——基底 skin.css 可能已被用户加过自定义规则，行数对不上是正常的。**直接 grep 我自己的标记**（`照片背景（由 setup.py 生成`、`③ 关键容器直接半透`）确认。

## 合规提醒

只修改用户自己数据目录里的主题样式文件，**不改 app.asar、不破坏代码签名**。

失效情况：官方更新主题后会新建缓存目录，旧目录不再被读取；也可能被 LRU 清理（缓存上限 8 个）。**重新跑一次安装命令即可恢复。**

图片版权由用户自行负责，建议只用自己的照片或已获授权的图。