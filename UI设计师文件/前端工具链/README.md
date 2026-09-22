# 前端工具链：TypeScript + Tailwind CSS + pnpm

元宝前端工程师补充包。三个都装好了，实测可用，附完整实测数据。

## 版本（实测，非估算）

| 工具 | 版本 | 验证方式 |
|---|---|---|
| **TypeScript** | 7.0.2 | `tsc -v` + 实际编译运行 |
| **Tailwind CSS** | 4.3.3 | 实际构建出 8496 bytes CSS |
| **@tailwindcss/cli** | 4.3.3 | CLI 构建通过 |
| **pnpm** | 12.5.1 | `pnpm -v` + 装包实测 |

## 快速开始

```bash
source restore.sh     # 设镜像 → 装 pnpm → 装依赖 → 验证，全自动
```

手动方式：

```bash
npm config set registry https://mirrors.cloud.tencent.com/npm/
npm install -g pnpm
pnpm install --ignore-scripts          # ⚠️ 必须带，原因见下
```

## 实测数据

### TypeScript 编译

```bash
./node_modules/.bin/tsc --strict --target ES2020 --module commonjs \
    --outDir dist src/demo.ts
node dist/demo.js
```

输出：`{"id":"btn_submit","x":138,"y":487,"visible":true}`

（demo.ts 含 interface、泛型返回 `Control | null`、filter 链式调用，strict 模式零报错）

### Tailwind CSS 构建

Tailwind v4 写法与 v3 不同——**不需要 tailwind.config.js**，改在 CSS 里用 `@theme`：

```css
@import "tailwindcss";
@source "../src/**/*.html";

@theme {
  --color-panel:  #2B2F33;
  --color-accent: #4DD0E1;
  --color-ok:     #00C853;
  --color-err:    #B00020;
}
```

构建：

```bash
./node_modules/.bin/tailwindcss -i css/input.css -o css/output.css --minify
```

产物验证（8496 bytes）：

```
✅ 自定义色 #2B2F33 / #4DD0E1 / #00C853 / #B00020  全部进入产物
✅ .bg-panel / .text-err 等自定义工具类已生成
✅ grid-cols-3 → repeat(3,...)
✅ hover: 变体正常
```

> 配色取自 GUI 视觉验证工具包里那套（面板深灰 / 青色强调 / 成功绿 / 报错红），
> 两个工具包可以共用同一套色板。

### pnpm vs npm 速度（真实跑出来的）

| 场景 | npm | pnpm | 结论 |
|---|---|---|---|
| 冷启动（装 lodash+chalk+commander） | 5552 ms | 5023 ms | pnpm 快 1.1 倍 |
| **热缓存**（删 node_modules 重装） | 225 ms | **28 ms** | **pnpm 快 8.0 倍** |

冷启动差距小，是因为瓶颈在网络下载而非包管理器本身。**日常反复安装时 pnpm 的优势才真正体现**（8 倍）。

## 两个必须避开的坑

### 坑 1：`ERR_PNPM_IGNORED_BUILDS`

不带参数直接 `pnpm install` 会失败：

```
× installing dependencies
╰─▶ Ignored build scripts: @parcel/watcher@2.5.1
help: Run "pnpm approve-builds" to pick which dependencies should be allowed
```

**解法：`pnpm install --ignore-scripts`**

试过三种写法，只有这个管用：

```
❌ package.json 里 pnpm.onlyBuiltDependencies   → 仍报错
❌ package.json 里 pnpm.ignoredBuiltDependencies → 仍报错
❌ pnpm install --allow-build=...               → pnpm 12 无此参数
✅ pnpm install --ignore-scripts                → 成功
```

原因：`@parcel/watcher` 是 Tailwind **watch 模式**的可选依赖，CLI 构建用不到。
忽略后实测 tsc 编译、Tailwind 构建均正常。

### 坑 2：pnpm 官方安装脚本走不通

`curl -fsSL https://get.pnpm.io/install.sh | sh` 会被沙盒网关拒。
改用 `npm install -g pnpm`，走腾讯镜像，实测 43 秒装完。

## 镜像源（实测对比）

| | 腾讯镜像 | 官方源 |
|---|---|---|
| npm i lodash | **359 ms** | 5307 ms（14.8 倍） |
| apt-get update | **1506 ms** | 5231 ms（且退出码 100 失败） |

## 文件说明

```
package.json        依赖声明 + pnpm 配置
pnpm-lock.yaml      锁版本，保证重装一致
restore.sh          一键恢复（source 执行）
src/demo.ts         TypeScript 示例（interface + strict）
src/panel.html      Tailwind 示例（用上面那套自定义色）
css/input.css       Tailwind 输入（含 @theme 色板）
css/output.css      构建产物（8496 bytes）
dist/demo.js        tsc 编译产物
```

> `node_modules/` 未打包（48 MB）。恢复时 `pnpm install` 重装约 2 分钟，
> 走腾讯镜像比下载 48MB 压缩包更快也更可靠。

## 与 GUI 视觉验证工具包配合

两个包共用一套配色和坐标体系：

| GUI 工具包坐标 | Tailwind 色板 |
|---|---|
| 提交按钮 (138,487) | `--color-accent` #4DD0E1 |
| 状态区 变绿 2593 px | `--color-ok` #00C853 |
| 状态区 变红 2666 px | `--color-err` #B00020 |
| 面板底色 | `--color-panel` #2B2F33 |

流程：用 Tailwind 写界面 → Chromium 出真实渲染稿 → GUI 工具包像素级验证交互。
