# KaBoom Trainer X v9.5 —— 架构逆向分析

> 目标：搞清楚这个 GTA5 修改器**是怎么做的**，供自建模组参考
> 方法：静态分析（PE 结构 / 导入表 / 字符串 / 配置文件），不运行、不破解
> 日期：2026-09-14

---

## 一、总体架构

```
KaBoomInjector.exe  ──注入──>  GTA5.exe 进程
                                   │
                                   ├─ 加载 KaBoomTrainerX.dll (3.87MB)
                                   │
                                   └─ DLL 内部：
                                       ├─ 自建 TrainerItem 菜单框架
                                       ├─ 直接调 native 函数
                                       ├─ 读 settings.json (配置)
                                       ├─ 读 models.csv / peds.csv (数据表)
                                       └─ 读 xcustoms8/9 (RSC7 资源)
```

**关键判断：它不用 ScriptHookV。**

导入表里只有 `KERNEL32 / USER32 / OLEAUT32 / WINMM / MSVCP140 /
VCRUNTIME140 / CRT` —— 全是系统库。**没有 ScriptHookV.dll**。

这意味着：它是**自成体系的独立注入式修改器**，自己实现了
native 调用、菜单渲染、输入处理。这是它和常规 ASI 插件最大的区别。

---

## 二、注入机制（Injector）

### 2.1 经典 DLL 注入五件套

从 `KaBoomInjector.exe`（218KB）导入表提取到：

```
OpenProcess          打开目标进程
VirtualAllocEx       在目标进程分配内存
WriteProcessMemory   写入 DLL 路径
CreateRemoteThread   创建远程线程
LoadLibraryW         线程入口 → 加载 DLL
```

这是教科书式的 **`CreateRemoteThread + LoadLibrary`** 注入。

### 2.2 为什么单独一个 injector

说明里写了："如游戏尚未启动，修改器会等待游戏启动后再进行注入"。

所以 injector 的职责：
1. 轮询/等待 `GTA5.exe` 进程出现
2. 注入 DLL
3. 退出或常驻

**好处**：用户不用管 ScriptHookV 装没装、版本对不对。
**代价**：容易被杀软拦截（说明第 8 条专门提了这个）。

---

## 三、核心 DLL 的 C++ 类体系（最有参考价值的部分）

从 RTTI 字符串提取到的完整类继承结构：

```
TrainerUIItem (基类)
├── TrainerItem
├── TrainerItemGap                   空白间隔
├── TrainerItemSwitch                开关
├── TrainerItemFunction              功能项（点击执行）
│   └── TrainerItemFunctionValued    带值功能
├── TrainerItemSubmenu               子菜单
│   └── TrainerItemSubmenuValued     带值子菜单
├── TrainerItemStaticMenu            静态菜单
├── TrainerItemDynamicMenu           动态菜单（数据驱动）
│   └── TrainerItemDynamicMenuValued
├── TrainerItemNewPage               翻页
├── TrainerItemParam                 参数
│   ├── TrainerItemStdParam          标准参数
│   ├── TrainerItemSegmentedParam    分段选择
│   └── TrainerItemPlacement         位置类
├── TrainerItemColor                 颜色选择
└── TrainerItemValue                 数值

TrainerMenu          菜单容器
TrainerMenuStack     菜单栈（支持返回上一层）
```

### 3.1 这个设计的精髓

**一切皆 Item。** 开关、按钮、子菜单、参数、颜色，
全部继承同一个基类，放进同一个容器。

带来的能力：
- 菜单结构可**递归嵌套**（Submenu 里套 Submenu）
- 用 `MenuStack` 实现"返回"
- 动态菜单从数据文件生成（比如 633 个载具自动生成列表）
- 参数项统一支持"进入编辑 → 微调/粗调 → 保存/放弃"

### 3.2 参数编辑交互（说明第 5 条）

```
点击选择键  → 进入编辑模式
  左右键（小键盘 4/6）→ 微调 ±1
  上下键（小键盘 8/2）→ 粗调 ±10
  再按选择键 → 保存
  按返回键   → 放弃，恢复原值
```

这个交互对应 `TrainerItemStdParam` / `TrainerItemValue`，
是 trainer 类模组的标配。

---

## 四、数据驱动设计（第二个精髓）

### 4.1 功能规模

| 项 | 数量 |
|---|---:|
| 中文菜单文本 | 947 条 |
| settings 配置项 | 316 |
| 按键绑定 | 50 |
| 传送点 | 21 |
| 载具列表 (models.csv) | 633 |
| 人物列表 (peds.csv) | 650 |
| 动画列表 (animations.json) | 6645 |

### 4.2 CSV 数据表格式

`models.csv`：
```
C_1,,,,FMMC_PLIB_0,,,
C_2,,,,FMMC_PLIB_1,,,
```
`peds.csv`：
```
0,Player_Zero,麦克
0,Player_One,富兰克林
0,Player_Two,崔佛
```

**简单到刻意**——列含义靠代码位置约定，不写表头。
好处是解析快、体积小；代价是可读性差。

### 4.3 settings.json 结构

16 个顶层键：

```json
{
  "controls": {50 个按键绑定，值是虚拟键码},
  "locations": [[名称, x, y, z, heading?], ...],
  "colorScheme": {8 个菜单配色},
  "settings": {316 项功能开关/数值},
  "yachts": [], "races": [], "gasStations": [],
  "smokeTrails": [[r,g,b,a,...]],
  "vehicle favorites": [[hash, 组名, [[modelHash, 名称, 改装详情]]]],
  "rioterWeapons": [], "copWeapons": [],
  "enemyWeapons": [], "playerWeapons": [],
  "savedBodyguards": [],
  "autoModItems": {primaryColor, secondaryColor, neon, tire, ...},
  "weaponInfoList": []
}
```

### 4.4 收藏载具的完整数据结构（值得抄）

```json
[4294967295, "BMW", [
  [3055060144, "BMW X7 2026", {
    "priColor": 131, "secColor": 0, "pearlColor": 0,
    "wheelColor": 156, "dialsColor": 27, "trimColor": 111,
    "customPriColor": 0, "customSecColor": 0,
    "tireSmoke": 16777215, "neon": 16711935, "neonState": 0,
    "livery": -1, "windowTint": -1, "wheelType": 3,
    "lowGripTyres": 0, "plateIndex": 3, "plate": "68KBM458",
    "mods": {"8":0, "11":3, "12":2, "13":2, "16":4, "18":0, "22":1},
    "extras": {"10":0, "11":0, "12":0}
  }]
]]
```

**这实际上就是 GTA5 载具改装 API 的完整参数映射**：
- `mods` 的 key 是 mod type（8=引擎? 11/12/13=变速箱/刹车/涡轮，22=大灯）
- `extras` 是 extra 部件开关
- 颜色用游戏内色号，霓虹用 RGB 打包成 int

做自己的载具模组时，**这个结构可以直接复用**。

---

## 五、自定义资源（xcustoms8 / xcustoms9）

```
文件头: 52 53 43 37  = "RSC7"
大小:   各 9.5 MB
```

**RSC7 是 RAGE 引擎的资源容器格式**，GTA5 的 RPF 归档内部就用它。

说明这个文件里打包的是**自定义载具/模型资源**，运行时由 DLL
解析并注入到游戏。

这是我们之前 GTA5 研究里反复提到的那个格式——
现在有真实样本了。

---

## 六、它 vs 我们的方案（对比）

| 维度 | KaBoom X | 我们之前的 ASI 方案 |
|---|---|---|
| 加载方式 | Injector 注入 | ScriptHookV 加载 .asi |
| 依赖 | **无**（仅系统库） | 需 ScriptHookV |
| 菜单框架 | 自建 C++ 类体系 | 无（需自己写） |
| 配置 | settings.json 外置 | 硬编码 |
| 数据表 | CSV/JSON | 无 |
| native 调用 | 自己实现 | ScriptHookV 提供 |
| 体积 | 3.87 MB | 433 KB |
| 复杂度 | 极高 | 入门级 |

**核心差距不在工具，在架构。**
我们有 MinGW 能编译出结构正确的 DLL，但缺：
1. 菜单框架（TrainerItem 类体系）
2. native 调用层（自己实现内存偏移/哈希）
3. 数据驱动层

---

## 七、如果要照这个思路做，最小可行路径

### 阶段 1：保留 ScriptHookV（省掉注入器）

不自己写 injector，用现成的 ScriptHookV 加载。
这样避开杀软拦截、进程注入等一堆坑。

### 阶段 2：实现菜单框架（照抄类设计）

```cpp
class TrainerUIItem {
public:
    virtual void Draw(int y, bool selected) = 0;
    virtual void OnSelect() = 0;
    virtual void OnLeft() {}   // 微调 -1
    virtual void OnRight() {}  // 微调 +1
    virtual void OnUp() {}     // 粗调 -10
    virtual void OnDown() {}   // 粗调 +10
};

class TrainerItemSwitch : public TrainerUIItem { bool value; };
class TrainerItemSubmenu : public TrainerUIItem { Menu* sub; };
class TrainerItemStdParam : public TrainerUIItem { int value, min, max; };

class TrainerMenu {
    std::vector<TrainerUIItem*> items;
    int currentIndex;
};

class TrainerMenuStack {
    std::vector<TrainerMenu*> stack;  // 支持返回
};
```

### 阶段 3：外置配置（settings.json）

启动时读 JSON，退出时写回。
用户改按键不用重编译。

### 阶段 4：数据表（CSV）

载具、人物、传送点全部走 CSV，
加个载具只改文本，不动代码。

### 阶段 5：native 调用层

这个最难——需要维护游戏版本的函数哈希表。
**建议直接用 ScriptHookV 的 `nativeInit/nativePush/nativeCall`**，
别自己造。

---

## 八、关键启发（总结）

1. **一切皆 Item 的菜单框架**是 trainer 的核心骨架
2. **数据驱动**让 947 个功能不用写 947 段代码
3. **外置配置**让用户能自定义按键/配色/收藏
4. **不依赖 ScriptHookV** 换来独立性，但代价巨大
   （要自己维护 native 表、处理版本兼容、对抗杀软拦截）
5. **RSC7 资源**是自定义载具的打包格式

---

## 九、合规提醒

- 本分析仅做**架构学习**，未破解、未提取算法、未绕过任何保护
- 原作者说明第 9 条：不得未经允许篡改或重新打包分发
- 参考**设计思路**是允许的；直接复制代码/资源不行
- 单机修改器边界内使用，勿用于 GTA Online

---

## 附：分析所用命令

```bash
# PE 结构
python3 -c "import struct; ..."          # 机器码/可选头/节区
# 导入表（看依赖）
x86_64-w64-mingw32-objdump -p x.dll | grep "DLL Name"
# RTTI 类名（看架构）
strings -n 8 x.dll | grep -oE "\?AV[A-Za-z_]{4,30}@@"
# 中文菜单文本
python3 re.findall(rb'[\xe4-\xe9][\x80-\xbf]{2}...', open('x.dll','rb').read())
# 资源格式
xxd xcustoms8 | head -1        # RSC7 魔数
```
