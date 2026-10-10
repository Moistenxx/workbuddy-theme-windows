# WorkBuddy 主题变更 · Windows 版

给 [WorkBuddy](https://www.workbuddy.cn) Windows 桌面端换照片背景的完整工具。**从上传照片到最终完成，一条命令。**

macOS 用户请用 **[workbuddy-theme-macos](../workbuddy-theme-macos)**。

## 效果

- 整窗一整块背景，侧栏 / 输入框 / 消息卡片 / 顶栏 **全部零白卡片**
- 背景固定不随内容滚动（`background-attachment: fixed`）
- **纯透明**：默认 `alpha=0`，一丝白都不加，**绝不发白**
- **原片清晰**：默认 `blur=0`，不做亮度调整，无损 PNG

## 快速使用

```powershell
# 0) 确认解释器带 Pillow
python -c "import PIL; print(PIL.__version__)"

# 1) 从照片生成并安装
python scripts\setup.py <图片路径> --alpha 0 --blur 0

# 2) 生效：WorkBuddy 设置→外观 切走再切回（不用重启）

# 3) 调效果
python scripts\setup.py tune --blur 8      # 字看不清时加模糊（不会发白）
python scripts\setup.py show               # 看当前值
python scripts\setup.py reset              # 恢复默认

# 4) 卸载，恢复官方原版
python scripts\setup.py uninstall
```

## 两个参数

| 参数 | 管什么 | 范围 | 默认 |
|---|---|---|---|
| `--alpha` | **加白强度**（在图片层面混一次白） | 0~1 | **0** |
| `--blur` | 背景模糊 px（**不会发白**） | 0~30 | **0** |

**默认双 0 = 原片零处理。**

> **想让字清楚就加 `--blur`，绝不要加 `--alpha`** ——
> 模糊是邻域平均，不引入白色；加白会让整幅画面发灰发白。

## 照片要求

| 项 | 要求 |
|---|---|
| 比例 | 16:9 横图（脚本自动裁成 2560×1440，不变形） |
| 尺寸 | ≥1600px 宽即可 |
| 格式 | PNG / JPG / JPEG / WebP 均可 |
| 内容 | 人物别放正中间（会被文字盖住），建议偏一侧 |

## 工作原理（实测，勿推翻）

WorkBuddy 外观是**云端驱动**的：App 从服务器拉主题 zip → 解压缓存到
`~/.workbuddy/appearance-resources/theme-<id>/`（每个主题一个 `skin.css` + `assets/`），
加载时**直接读这个缓存文件注入为 `<style>`，不做校验**。

所以：把 `skin.css` **追加**一段背景规则即可生效。关键前提是
**用户必须先在「设置→外观」里选中一个主题**，缓存目录才会建立。
生效动作是「切走再切回」，**不需要重启**。

⚠️ 缓存目录上限 8 个，LRU 按 mtime 淘汰；App 升级后可能重置，重跑一次安装命令即可。

## ⚠️ Windows 专属坑：`local-file://` URL

这是本 Windows 版修掉的**唯一一个真 bug**，macOS 版不会暴露同样症状。

官方 `app.asar` → appearance 模块的权威写法：
```js
const encoded = absPath.replace(/\\/g, "/")
  .split("/").map(p => p === "" ? "" : encodeURIComponent(p)).join("/");
return `local-file://${encoded.startsWith("/") ? "" : "/"}${encoded}`;
```

Windows 上必须产出：
```
local-file:///C%3A/Users/<你>/.workbuddy/appearance-resources/theme-xxx/assets/wallpaper.png
```

| 要求 | 原因 |
|---|---|
| 分隔符转成 `/` | `net.fetch` 不认反斜杠 |
| **三**斜杠 `:///` | posix 分支会补 `/`，Windows 路径无前导斜杠 |
| 逐段 `encodeURIComponent` | 用户名含中文 / 空格时不编码直接解析失败 |

踩过的错法：`"local-file://" + os.path.join(...)` → `local-file://C:\Users\...\wallpaper.png`，
表现为「配了但没背景」。本仓库已用 `to_local_file_url()` 修掉，与官方 JS 输出逐字节一致
（用 Node 跑官方实现交叉验证过）。

## ⚠️ 七条铁律（实战换来的）

1. **官方 skin.css 必须"追加"，绝不能"替换"** —— 替换会丢全部官方样式。
2. **会话主体白底由 `--wb-color-bg-primary-default` 刷**，不是容器。
3. **找不到元素时去 `app.asar` 挖官方 CSS，不要猜 class 名**：
   ```python
   d = open(r'D:\浏览器下载地址\WorkBuddy\resources\app.asar','rb').read()
   re.findall(r'\.([A-Za-z0-9_-]+)\s*\{([^}]{0,300})\}', d.decode('utf-8','ignore'))
   ```
4. **★白纱只能有一层，且必须烤进图片里，不能刷在容器上。★**
   半透明叠加是**乘法** `1-(1-a)ⁿ`：25% 刷 2 层 = 43%，刷 4 层 = 68%。
   正确做法：`Image.blend(im, white, alpha)` 只混这一次，CSS 里一个白都不刷。
5. **调透明度必须从 `wallpaper_base.png` 重新生成**，不能在旧图上叠加。
6. **官方有 522 个背景类变量**，必须用通配 + 变量兜底，不要枚举。
7. **「要透明」= 完全透出背景，不是半透白纱**。alpha 必须是 0；
   字看不清请调 `--blur`，不要动 alpha。

完整逆向笔记（含加载机制、已排除的无效路径、官方 CSS 变量清单、失败复盘）见
[`reference/逆向笔记.md`](reference/逆向笔记.md)。

## 环境变量（可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `WB_BASE` | `~/.workbuddy/appearance-resources` | 主题缓存目录 |

## 安全与合规

- 只修改用户自己数据目录下的主题样式文件，**不改 app bundle、不破坏代码签名**。
- 无网络请求、无数据外发，只读你指定的那张图片。
- 图片版权由使用者自行负责，建议只用自己的照片或已获授权的图。

## License

MIT