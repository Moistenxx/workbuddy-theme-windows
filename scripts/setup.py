#!/usr/bin/env python3
"""workbuddy-theme —— WorkBuddy 主题变更（照片背景版，Windows）

用法：
  python setup.py <图片路径> [选项]      # 从照片生成并安装
      --alpha 0.3        图片层面混白强度 0~1（默认 0 = 纯透明，不发白）
      --blur 6           背景模糊 px（默认 0，设 0 = 原片清晰）
      --no-blur          等同 --blur 0

  python setup.py tune 0.3        # 只调白纱 alpha
  python setup.py tune --blur 8        # 只调模糊（字不清时用这个，不会发白）
  python setup.py show                # 看当前设置
  python setup.py reset               # 恢复默认 alpha 0 / blur 0
  python setup.py uninstall           # 恢复官方原版

设计原则：默认 alpha=0 / blur=0 = 原片零处理、纯透明。
字看不清请调 --blur，不要调 --alpha（加白会让画面发灰发白）。

环境变量（可选）：
  WB_PYTHON  指定解释器，默认 python
  WB_BASE    指定主题缓存目录，默认 ~/.workbuddy/appearance-resources
"""
import os, re, sys, glob, shutil, subprocess

HOME      = os.path.expanduser("~")
BASE      = os.environ.get("WB_BASE") or os.path.join(HOME, ".workbuddy", "appearance-resources")
HERE      = os.path.dirname(os.path.abspath(__file__))
WALL_DIR  = os.path.join(HERE, "assets")
WALL      = os.path.join(WALL_DIR, "wallpaper.png")
BASE_WALL = os.path.join(WALL_DIR, "wallpaper_base.png")   # 无滤镜原版，调透明度时从它重生成
STATE     = os.path.join(HERE, "state.json")
TARGET_W, TARGET_H = 2560, 1440          # 16:9，通用壁纸规格
DEF_ALPHA, DEF_BLUR = "0", "0"

VAR_DECL = """/* ── 照片背景（由 setup.py 生成，追加在官方 skin.css 末尾）─────────────
   做法：壁纸铺在根容器，所有内容层统一半透明 = 一整块背景不被切断
   透明度：--alpha 背景白纱（0=照片全显 1=全白）
   ================================================================ */
:root, body {
  --alpha: __ALPHA__;                /* 全局唯一透明参数：0=全透 1=全白 */
  --wb-wallpaper-image: url("__WALL_URL__");
}

/* ═══════════════════════════════════════════════════════════════
   核心思路（老板要求：「全部整体都是我给的背景，不存在白色对话框」）
   白纱只能有【一层】，而且必须铺在最底层。
   之前每个容器都刷一次 rgba(255,255,255,.25)，三层嵌套就叠成 60%+ 白，
   所以看起来像"蒙了层白纱"。现在：容器全透明 + 根层单层白纱。
   ═══════════════════════════════════════════════════════════════ */

/* ── ① 壁纸铺在最底层根容器（只铺一次）── */
html,
body,
body #root,
body .workbuddy-app {
  background-image: var(--wb-wallpaper-image) !important;
  background-size: cover !important;
  background-position: center center !important;
  background-repeat: no-repeat !important;
  background-attachment: fixed !important;
  background-color: transparent !important;
}

/* ── ② 白纱已烤进 wallpaper.png（图片层面只混一次），这里不需要任何覆盖层 ──
   若在这里再刷一层 rgba(255,255,255,.25)，就变成两层白纱 = 43% 白，等于蒙纱。*/

/* ── ③ 所有内容层一律完全透明（不刷任何白）── */
body .workbuddy-app,
body .workbuddy-app *,
body .teams-container,
body .teams-container *,
body .teams-content-wrapper,
body .teams-content-wrapper *,
body .teams-main-content,
body .teams-main-content *,
body .main-content--chat,
body .main-content--chat *,
body .main-content--welcome,
body .main-content--welcome *,
body .claw-workspace,
body .claw-workspace *,
body .claw-workspace__main,
body .claw-workspace__main *,
body .claw-workspace__pane,
body .claw-workspace__pane *,
body .claw-agent-chat-pane,
body .claw-agent-chat-pane *,
body .cr-agent,
body .cr-agent *,
body .cr-agent__body,
body .cr-agent__body *,
body .cr-frame,
body .cr-frame *,
body .cr-frame__content,
body .cr-frame__content *,
body .cr-message-list,
body .cr-message-list *,
body .cr-message-list-viewport,
body .cr-message-list__content,
body .cr-message-list__bottom-mask,
body [data-view-id],
body [data-view-id] * {
  background-color: transparent !important;
  background-image: none !important;
  box-shadow: none !important;
}

/* ── ④ 页面级背景变量一律 transparent（官方那522 个变量只能这样兜底）── */
:root,
body,
.cr-theme,
.cr-agent,
.cr-frame,
.cr-agent__body,
.cr-frame__content {
  --wb-home-bg-secondary: transparent !important;
  --wb-home-bg-primary: transparent !important;
  --wb-bg-primary: transparent !important;
  --wb-color-bg-primary-default: transparent !important;
  --cr-bg-canvas: transparent !important;
  --cr-bg-primary-default: transparent !important;
  --cr-bg-secondary: transparent !important;
  --cr-bg-tertiary: transparent !important;
  --cb-bg-secondary: transparent !important;
  --cb-content-background: transparent !important;
  --cb-panel-bg-primary: transparent !important;
}
"""

# ───────────────────────── 工具函数 ─────────────────────────

def load_state():
    import json
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            pass
    return {"alpha": DEF_ALPHA, "blur": DEF_BLUR}

def save_state(s):
    import json
    json.dump(s, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def find_official_base():
    """找一份未被改动的官方 skin.css 作为基底"""
    cands = []
    for f in glob.glob(os.path.join(BASE, "theme-*", "**", "skin.css"), recursive=True):
        txt = open(f, encoding="utf-8", errors="ignore").read()
        if "--wb-home-bg-primary" in txt or "--cb-bg-primary" in txt:
            cands.append((f, txt))
    if not cands:
        return None, None
    # 取最短的（未被追加过）
    cands.sort(key=lambda x: len(x[1]))
    return cands[0]

def make_wallpaper(src, alpha=0, blur=0):
    """把照片处理成最终壁纸：裁成 16:9 → （存base）→ 可选模糊 → 可选加白。
    默认 blur=0 / alpha=0 → **原片零处理**，输出与base 像素级一致。
    白纱与模糊直接烤进图片，避免多层容器各刷一次白导致越叠越白。
    ★ 不做亮度调整：老板要「原片一样清楚」，压暗会让画面发灰、看着不真实。"""
    from PIL import Image, ImageEnhance, ImageFilter
    os.makedirs(WALL_DIR, exist_ok=True)
    im = Image.open(src).convert("RGB")
    w, h = im.size
    tw, th = TARGET_W, TARGET_H
    # 目标比例更宽则裁上下，更窄则裁左右；不拉伸变形
    if w / h > tw / th:
        nw = int(h * tw / th); left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:
        nh = int(w * th / tw); top = (h - nh) // 2
        im = im.crop((0, top, w, top + nh))
    # 只在放大时用 LANCZOS（保细节）；等比或缩小时用 BICUBIC（避免 LANCZOS 振铃）
    if w >= tw:
        im = im.resize((tw, th), Image.LANCZOS)
    else:
        im = im.resize((tw, th), Image.BICUBIC)
    small = im.resize((48, 48))
    # Pillow 12 起 getdata() 弃用、14 起移除；新 API 返回同样的 RGB 元组序列
    _pixels = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
    avg = sum(sum(p) for p in _pixels) / (48 * 48 * 3)
    # 存一份无滤镜的 base，之后调透明度都从 base 重新生成，避免反复叠加
    im.save(BASE_WALL)
    # 模糊也烤进图片（CSS backdrop-filter 在多层容器下不可控）
    out = im
    b = int(float(blur))
    if b > 0:
        out = out.filter(ImageFilter.GaussianBlur(float(b)))
    # ★ 唯一一层白纱：图片层面直接混一次 alpha 的白色
    a = min(max(float(alpha), 0.0), 1.0)
    if a > 0:
        veil = Image.new("RGB", out.size, (255, 255, 255))
        out = Image.blend(out, veil, a)
    out.save(WALL)
    return avg

def regenerate_wallpaper(alpha, blur):
    """从 base 重新生成壁纸（调透明度/模糊时用，不碰原图）"""
    if not os.path.exists(BASE_WALL):
        return False
    from PIL import Image, ImageFilter
    im = Image.open(BASE_WALL).convert("RGB")
    out = im
    b = int(float(blur))
    if b > 0:
        out = out.filter(ImageFilter.GaussianBlur(float(b)))
    a = min(max(float(alpha), 0.0), 1.0)
    if a > 0:
        veil = Image.new("RGB", out.size, (255, 255, 255))
        out = Image.blend(out, veil, a)
    os.makedirs(WALL_DIR, exist_ok=True)
    out.save(WALL)          # 无损 PNG，不做 JPEG 压缩
    return True

def to_local_file_url(abs_path):
    """绝对路径 → local-file:// URL（对齐官方实现，Windows 必用）

    官方 app.asar → appearance 模块 toLocalFileUrl()：
        const encoded = absPath.replace(/\\\\/g, "/")
                              .split("/").map(p => p === "" ? "" : encodeURIComponent(p)).join("/");
        return `local-file://${encoded.startsWith("/") ? "" : "/"}${encoded}`;
    即 Windows 下 `C:\\Users\\x\\w.png` → `local-file:///C:/Users/x/w.png`
    （**三斜杠**，且分隔符必须转成正斜杠；直接塞反斜杠路径会加载失败）。
    路径里可能有中文 / 空格，逐段 encode，和官方 encodeURIComponent 语义一致
    （保留 A-Za-z0-9 与 - _ . ! ~ * ' ( )，其余转义；冒号会变成 %3A，
     官方同样如此，加载端 net.fetch 会 decode 回来）。
    """
    from urllib.parse import quote
    p = str(abs_path).replace("\\", "/")
    enc = "/".join(quote(seg, safe="-_.!~*'()") if seg else "" for seg in p.split("/"))
    return "local-file://" + ("" if enc.startswith("/") else "/") + enc

def build_patch(theme_dir, alpha, blur):
    # 模糊与白纱都已烤进 wallpaper.png，CSS 里不需要 backdrop-filter
    return (VAR_DECL
            .replace("__ALPHA__", str(alpha))
            .replace("__WALL_URL__", to_local_file_url(os.path.join(theme_dir, "assets", "wallpaper.png"))))

def install(alpha, blur):
    blur = int(float(blur))          # state.json 里可能是字符串
    if not os.path.isdir(BASE):
        print("✗ 找不到主题缓存目录：", BASE)
        print("  请先在 WorkBuddy 设置→外观 里任选一个主题（会建立缓存目录）")
        return False
    if not os.path.exists(WALL):
        print("✗ 还没有壁纸。请先运行：python3 setup.py <图片路径>")
        return False
    # 有 base 就按新alpha/blur 重新烤一次壁纸（保证调透明度是幂等的）
    if os.path.exists(BASE_WALL):
        regenerate_wallpaper(alpha, blur)
    css = (VAR_DECL
          .replace("__ALPHA__", str(alpha))
          .replace("__WALL_URL__", "__WALL__"))
    n = 0
    for d in sorted(glob.glob(os.path.join(BASE, "theme-*"))):
        for sub in ("assets",):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
        shutil.copy2(WALL, os.path.join(d, "assets", "wallpaper.png"))
        local = css.replace("__WALL__", to_local_file_url(os.path.join(d, "assets", "wallpaper.png")))
        # ★ 关键：必须以官方 skin.css 为基底追加，不能整文件替换
        dst = os.path.join(d, "skin.css")
        #基底优先级：① 根 skin.css  ② 内层 workbuddy-skin-*/skin.css 官方备份
        if not os.path.exists(dst):
            for inner in glob.glob(os.path.join(d, "workbuddy-skin-*", "skin.css")):
                shutil.copy2(inner, dst)
                break
        if os.path.exists(dst):
            base_txt = open(dst, encoding="utf-8", errors="ignore").read()
            # 若上一轮是我们写的（含标记），先剥掉旧片段，避免无限追加
            if "照片背景（由 setup.py 生成" in base_txt:
                base_txt = re.split(r"/\* ── 照片背景（由 setup\.py 生成", base_txt)[0].rstrip() + "\n"
            # 官方规则在前、我们的在后 → 靠后天然覆盖
            merged = base_txt + "\n" + local
        else:
            merged = local
        open(dst, "w", encoding="utf-8").write(merged)
        n += 1
    save_state({"alpha": alpha, "blur": blur})
    print(f"✓ 已安装到 {n} 个主题目录（透明度 {alpha}）")
    print("→ WorkBuddy 设置→外观 切走再切回，即可看到效果")
    return True

def uninstall():
    n = 0
    for d in sorted(glob.glob(os.path.join(BASE, "theme-*"))):
        f = os.path.join(d, "skin.css")
        if os.path.exists(f):
            os.remove(f); n += 1
        for w in glob.glob(os.path.join(d, "**", "wallpaper.png"), recursive=True):
            os.remove(w)
    print(f"✓ 已清理 {n} 个主题目录")
    print("→ 设置→外观 切走再切回，App 会自动重新下载官方主题")

# ───────────────────────── 命令入口 ─────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]

    if cmd == "uninstall":
        uninstall(); return

    if cmd == "reset":
        save_state({"alpha": DEF_ALPHA, "blur": DEF_BLUR})
        print(f"✓ 已恢复默认：透明度 {DEF_ALPHA} / 模糊 {DEF_BLUR}px")
        install(DEF_ALPHA, DEF_BLUR); return

    if cmd == "show":
        s = load_state()
        print(f"背景白纱 alpha  = {s['alpha']}   （0=照片全显，1=全白）")
        print(f"背景模糊 blur   = {s['blur']}px")
        print(f"壁纸            = {WALL if os.path.exists(WALL) else '未设置'}")
        return

    if cmd == "tune":
        s = load_state()
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            tok = args[i]
            if tok == "--alpha" and i + 1 < len(args):
                s["alpha"] = f"{min(max(float(args[i+1]),0),1):g}"; i += 2
            elif tok == "--blur" and i + 1 < len(args):
                s["blur"] = f"{min(max(float(args[i+1]),0),30):g}"; i += 2
            elif tok == "--no-blur":
                s["blur"] = "0"; i += 1
            else:
                try:
                    s["alpha"] = f"{min(max(float(tok),0),1):g}"
                except ValueError:
                    print(f"⚠️ 忽略无法识别的参数: {tok}")
                i += 1
        print(f"透明度 alpha = {s['alpha']}   模糊 blur = {s['blur']}px")
        install(s["alpha"], s["blur"]); return

# 默认：setup <图片> [选项]
    # 解析：选项名以 -- 开头，其后跟值；第一个"不是选项、也不是选项值"的 token 是图片路径
    # 更简单可靠：先取出所有 --xxx 及其紧随的值，剩下的第一个就是图片
    argv = sys.argv[1:]          # argv[0] 是图片路径本身（cmd 已在上面用过 sys.argv[1]）
    opts, img = [], None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("--alpha", "--blur"):
            if i + 1 < len(argv):
                opts += [tok, argv[i + 1]]; i += 2
            else:
                i += 1
        elif tok == "--no-blur":
            opts.append(tok); i += 1
        else:
            if img is None:
                img = tok
            i += 1
    if img is None:
        print("✗ 请提供图片路径"); print(__doc__); return
    src = img
    if not os.path.exists(src):
        print("✗ 找不到图片:", src); return

    alpha, blur = DEF_ALPHA, DEF_BLUR
    i = 0
    while i < len(opts):
        if opts[i] == "--alpha":   alpha = f"{min(max(float(opts[i+1]),0),1):g}"; i += 2
        elif opts[i] == "--blur":  blur = int(float(opts[i+1])); i += 2
        elif opts[i] == "--no-blur": blur = 0; i += 1
        else: i += 1

    base = find_official_base()
    if base[0] is None:
        print("⚠️ 没找到官方 skin.css 作为基底。")
        print("   请先到 WorkBuddy 设置→外观 里任选一个主题（触发下载），再运行本脚本。")
        return
    avg = make_wallpaper(src, alpha, blur)
    print(f"✓ 壁纸已生成 2560x1440（原片均亮 {avg:.0f}/255，**未做任何亮度调整**）")
    print(f"  白纱 alpha={alpha}（0=纯透明）  模糊 blur={blur}px（0=原片清晰）")
    install(alpha, blur)

if __name__ == "__main__":
    main()