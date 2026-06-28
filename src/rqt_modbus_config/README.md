# rqt_modbus_config

rqt 插件，以表格形式展示 MODBUS 寄存器标签配置，支持连接 PLC 并实时读取寄存器原始值与解析值。

## 功能概述

- **配置表格** — 从 `modbus_config.toml` 加载所有寄存器标签，以表格展示分组、名称、地址、数据类型等信息
- **PLC 连接** — 基于 MODBUS TCP 连接 PLC，实时读取寄存器数据
- **连接超时检测** — 8 秒看门狗，连接无响应时弹窗提示
- **连接状态更新** — 意外断连自动检测并更新界面状态，不影响自动轮询
- **当前值解析** — 根据标签的 `data_type` 将原始寄存器值解析为实际物理值，支持 10 种数据类型
- **scale 缩放** — 对 `int32` 等类型自动应用缩放因子（如角度值 × 0.01）
- **寄存器原始值** — 显示寄存器的原始值（多字节按**小端**方式组合，以十六进制显示）
- **筛选搜索** — 支持按分组下拉筛选、关键字搜索、显示/隐藏禁用标签
- **自动刷新** — 可配置定时自动轮询 PLC 数据（200 ms ~ 60 s）

## 依赖

| 依赖 | 说明 |
|------|------|
| `rqt_gui` / `rqt_gui_py` | rqt 框架 |
| `modbus_pkg` | MODBUS 配置解析与 PLC 通信 |
| `ament_index_python` | 查找已安装包路径 |

## 安装

### 1. 确保 ROS2 Jazzy 环境已加载

```bash
source /opt/ros/jazzy/setup.bash
```

### 2. 编译工作区

```bash
cd ~/projects/ros2ws
colcon build --packages-select rqt_modbus_config modbus_pkg
```

### 3. 加载工作区环境

```bash
source install/setup.bash
```

## 运行方式

### 方式一：独立 rqt 窗口（推荐）

直接以独立插件模式启动 rqt：

```bash
rqt --standalone-rqt-plugin rqt_modbus_config.modbus_config_plugin.ModbusConfigPlugin
```

### 方式二：从 rqt 主窗口加载

1. 启动 rqt：
   ```bash
   rqt
   ```
2. 菜单栏选择 **Plugins** → **Modbus Config Table**

### 方式三：通过 rqt 命令行指定插件

```bash
rqt -s rqt_modbus_config
```

## 使用流程

1. **加载配置** — 启动后自动加载默认配置文件（`modbus_pkg/config/modbus_config.toml`），也可通过工具栏「打开…」按钮手动选择
2. **连接 PLC** — 点击「连接 PLC」按钮建立 MODBUS TCP 连接
   - 连接成功：状态指示器变绿，自动读取一次数据
   - 连接失败（8 秒内无响应或拒绝）：弹出错误对话框，提示检查 PLC 电源、IP、网线
3. **读取数据** — 连接成功后自动读取一次，也可手动点击「读取数据」
4. **自动刷新** — 勾选「自动刷新」并设置间隔，定时轮询 PLC 数据
5. **断开连接** — 点击「断开」按钮，状态指示器恢复灰色
   - PLC 意外断连时自动检测并更新状态，**不会弹出对话框**（避免自动轮询时反复弹窗）

## 表格列说明

| 列名 | 说明 |
|------|------|
| 分组 | 标签所属分组 |
| 标签名 | 标签唯一名称 |
| 描述 | 标签描述信息 |
| 寄存器类型 | 如 Holding Register |
| 起始地址 | MODBUS 寄存器起始地址 |
| 长度 | 寄存器数量 |
| KEP地址 | KEPWare 风格地址（如 `%MW07910`） |
| 数据类型 | 见下方数据类型支持表 |
| 读写权限 | 只读 / 读写 / 只写 |
| 扫描周期(ms) | 配置的扫描周期 |
| 当前值 | **根据 data_type 解析后的实际物理值**（见下方） |
| 寄存器原始值 | 原始寄存器值，多字节按**小端**组合，十六进制显示 |
| 启用 | 标签是否启用 |

### 当前值解析 — 数据类型支持

| data_type | 寄存器数 | 解析方式 | 显示示例 |
|-----------|---------|---------|---------|
| `Boolean` | 1 | 按位提取 0/1 | `0` 或 `1` |
| `Word` | 1 | 16 位无符号整数 | `65535` |
| `Short` | 1 | 16 位有符号整数 | `-1` |
| `int32` | 2 | 小端组合 → 有符号 32 位 × scale | `123` 或 `1.23` (scale=0.01) |
| `DWord` | 2 | 小端组合 → 无符号 32 位 | `131071` |
| `uint32` | 2 | 小端组合 → 无符号 32 位 | `131071` |
| `Float` | 2 | 小端组合 → IEEE 754 float32 | `3.14159` |
| `Float Array` | 2N | 每 2 寄存器一组 → float32 | `1.0, 2.0, 3.0` |
| `Long Array` | 2N | 每 2 寄存器一组 → int32 | `100, -50, 200` |
| `String` | N | ASCII 解码（去尾部 null） | `ABCD` |

- **scale**：配置文件中 `scale` 字段，默认值为 `1`。`int32` 和 `Short` 类型会乘以 scale 后再显示
- 悬停提示显示原始十六进制值（如 `0x00000FA0`）和缩放计算过程
- 未知类型回退到原始数值显示

### 寄存器原始值说明

- **单寄存器**（length=1）：直接显示为 `0x03F2`，悬停提示显示十进制值
- **多寄存器**（length>1）：按小端方式组合 —— `values[0]` 为低字（LSW），`values[1]` 为高字
  - 例如 values = `[0x0001, 0x0002]` → 显示 `0x00020001`
  - 悬停提示显示各寄存器明细：`寄存器: 0x0001, 0x0002 → 小端组合: 131073`

## 连接状态说明

| 状态指示器 | 颜色 | 含义 |
|-----------|------|------|
| `● 未连接` | 灰色 | 未建立连接或已断开 |
| `● 连接中…` | 黄色 | 正在尝试连接 |
| `● 已连接` | 绿色 | 连接正常 |
| `● 错误` | 红色 | 连接失败（弹窗提示） |

- **连接超时**：点击连接后 8 秒内无响应，弹出超时警告并显示错误状态
- **意外断连**：自动轮询检测到连接丢失时，静默更新为"未连接"，不弹窗
- **主动断开**：点击断开按钮，状态变为灰色"未连接"

## 配置文件说明

插件按以下优先级查找配置文件：

1. ament_index 中 `modbus_pkg` 包下的 `config/modbus_config.toml`
2. 开发工作区中的 `src/modbus_pkg/config/modbus_config.toml`
3. 环境变量 `MODBUS_CONFIG_PATH` 指定路径

也可通过工具栏「打开…」手动选择任意 `.toml` 文件。

配置文件格式详见 `modbus_pkg/CLAUDE.md`。每个标签的关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `group` | string | 分组名 |
| `name` | string | 标签唯一名称 |
| `start_address` | int | MODBUS 起始地址 |
| `length` | int | 寄存器数量 |
| `data_type` | string | 数据类型（见上方支持表） |
| `scale` | float | 缩放因子，默认 `1` |
| `enable` | bool | 是否启用 |

## 包结构

```
rqt_modbus_config/
├── package.xml                          # 包元数据（依赖 rqt_gui, modbus_pkg）
├── setup.py                             # ament_python 安装脚本
├── plugin.xml                           # rqt 插件注册（入口点声明）
├── resource/
│   └── rqt_modbus_config                # ament resource marker
├── rqt_modbus_config/
│   ├── __init__.py                      # 包初始化
│   ├── modbus_config_plugin.py          # 主插件：表格界面、筛选、连接操作
│   └── plc_worker.py                    # 后台线程：asyncio 事件循环、PLC 异步读写
├── config/                              # 配置目录
├── test/                                # 测试目录
├── logs/                                # 日志目录
└── README.md
```
