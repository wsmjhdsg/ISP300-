# AutoISP300 代码优化方案

> 版本：v1.0（2026-09-08）· 状态：**P0~P3 全部建议已落地**（v3 版，2026-09-08 随 UI 工业风重做一并实施），本文件保留作实施依据与决策记录。
> 范围：以「性能、可读性、结构、可维护性」为目标，对 main.py / core/ / ui/ 全量评审后的改进建议。

**落地对照**：P0-1 原子写 ✅ · P0-2 结构化统计 ✅ · P0-3 会话化+finally ✅ · P0-4 校验层 ✅ · P1-1 死代码清理 ✅（models.py 采用方案 B 删除，schema 收敛进 constants/validation）· P1-2 mtime 缓存 ✅（领域类不拆分，见下注）· P1-3 主窗口拆分 ✅ · P1-4 显式类型映射 ✅（动态表单未整体 schema 化，见下注）· P1-5 控件缓存 ✅ · P2-1~2-4 全部 ✅ · P3-1~3-3 ✅（22 个测试用例）。

> 实施中的两处工程取舍（写在此供后人参考，避免重复提议）：
> 1. **ConfigManager 不拆领域类**：机种/累进 CRUD 与步序文件联动天然耦合（改名要同步 rename 步骤文件），拆 store 只会引入循环引用/引用链；保留单门面 + 类内分区 + mtime 缓存即可，可测试性由 `reset_instance()+app_base_dir monkeypatch` 解决。
> 2. **步序编辑器动态表单未整体 schema 化**：5 类步骤已稳定、表单交互差异大（文件浏览/坐标二选一/快捷钮），重写成 schema 驱动收益低于回归风险；已把「类型展示↔key」的脆弱 split 解析改为 constants 显式映射，新增类型时仅需在 `STEP_SHORT_LABELS/STEP_DISPLAY_VALUES` 补一项。

---

## 0. 现状评估（先说结论）

### 做得好的地方（应保留）
1. **分层清晰**：`core/`（纯逻辑）与 `ui/`（界面）解耦，`ui` 不反向依赖业务细节；
2. **常量收敛**：配色、字体、执行参数全部集中到 `core/constants.py`，改一处全局生效；
3. **职责单一拆分**：主窗口与三个编辑器各自成文件，样式抽到 `styles.py`；
4. **绿色便携设计**：`paths.app_base_dir()` 同时处理源码/frozen 两种形态，config/logs 随 exe 走；
5. **按需导入意识**：`isp_controls.py` 函数内导入 pywinauto，避免无关场景加载重依赖。

### 主要短板（本方案要解决的）
| 类别 | 问题摘要 |
|------|---------|
| 正确性 | 配置 JSON 非原子写，崩溃/断电可能损坏数据；执行统计"success"失实；Simulator 全局静态状态存在残留泄漏风险 |
| 结构 | models.py / editor_dialogs.py / burner 存取为死代码或半死代码；ConfigManager 300 行大而全；steps 内存缓存不感知外部手改 |
| 可读性 | Simulator 全静态方法 + 类变量状态；main_window 大方法嵌套闭包；step_editor 动态表单样板重复、类型 key 靠字符串解析 |
| 性能 | 控件点击每次全树递归查找；日志框无限增长；pyautogui 顶层导入拖慢冷启动 |
| 工程化 | 零测试；无依赖锁定文件；无 lint/类型检查 |

建议分 4 个优先级落地，每项均按「问题 → 优化思路 → 预期收益 → 实施步骤」说明。

---

## P0 正确性与健壮性（建议最先做，UI 无感）

### P0-1 配置 JSON 改为原子写（防数据损坏）

**现状问题**
`config_manager._save_json()` 直接 `open(file, "w")` 覆写目标文件。若在写入中途崩溃/断电/被杀进程，JSON 文件会损坏，下次启动 `_load_json()` 失败后**静默回退默认值**——机种/累进/坐标数据丢失且无任何提示。README 又支持用户手动编辑 JSON，损坏窗口期客观存在。

**优化思路**
写入走「临时文件 + `os.replace` 原子替换」；读取损坏时保留坏文件副本供人工恢复，并明确告警而非静默。

**预期收益**
杜绝「数据静默丢失」这一最大风险；损坏时可追溯、可恢复。

**实施步骤**
1. 新增 `_atomic_write_json(path, data)`：写 `path.with_suffix(".tmp")` → `os.replace(tmp, path)`；
2. `_save_json()` 全部改走原子写（涉及 machines / click_points / burner / steps 四处调用点，改动集中在一个私有方法）；
3. `_load_json()` 捕获 `json.JSONDecodeError` 时：将坏文件改名留存（如 `machines.json.corrupt-<时间戳>`）→ 返回 default → 日志 ERROR；
4. 手测：正常增删改机种/累进/点击点/步序后重开程序，数据完好。

---

### P0-2 修复执行统计口径，`execute_step` 返回结构化结果

**现状问题**
- `simulator.execute_steps()` 中 `success_count` 对**执行过的每一步**无条件 +1：启动失败、控件未找到、点击失败等全部被计为"成功"，汇总「成功: N」误导用户；
- `execute_step()` 只返回人类可读文本，无结构化成败标志 → 无法精确统计、无法做单元测试、无法按类型聚合失败原因。

**优化思路**
`execute_step` 改为返回 `(ok: bool, message: str)`（或 `StepResult` 对象）；`execute_steps` 按 `ok` 计数；「未知步骤类型」由静默跳过改为显式失败并记录。

**预期收益**
汇总数字真实可信；执行失败原因可被测试与日志聚合；UI 文案无需改动（仍消费 message 文本）。

**实施步骤**
1. `execute_step()` 每个分支返回二元组，成功 `(True, msg)`、失败/告警 `(False, msg)`；
2. `execute_steps()` 中 `success_count` 只在 `ok` 时累加，汇总日志增加「成功 X / 失败 Y」；
3. `wait/type` 等当前无异常路径的步骤保持返回 True；
4. 顺带新增 `core/validation.py` 的雏形见 P0-4，两处配合。

---

### P0-3 Simulator 全局静态状态 → 会话化，资源清理进 try/finally

**现状问题**
`Simulator` 全部是 `@staticmethod`，执行状态（`_original_hkl`、`_mouse_interrupted`、`_monitoring`、`_monitor_thread`、`_monitor_lock`）挂在**类变量**上：
- 全局共享 → 两个执行并发（未来双窗口/多实例）会互相踩踏；
- `_restore_ime()` 的不清空注释说明存在微妙残留逻辑：若一次执行中途抛出未捕获异常，鼠标监控线程与英文输入法**都不会被清理**，污染下一次执行（用户后续打字可能仍在英文状态）；
- `_switch_to_english_ime` 用 `__import__("ctypes")` 小动作，可读性差。

**优化思路**
将「一次执行」的会话状态封装为对象（`Simulator` 改可实例化，或抽出 `ExecutionSession`）；`execute_steps` 用 `try/finally` 保证「停监控 + 恢复输入法」必然执行。

**预期收益**
消除跨执行状态污染与 IME/监控线程泄漏；为将来并发执行留路；状态不再依赖全局，便于测试。

**实施步骤**
1. 把 IME 相关类变量与鼠标监控相关类变量收进会话对象；方法改为实例方法或显式传入 session；
2. `execute_steps` 结构改为：
   ```python
   monitor.start(); switched = ime.switch_to_english()
   try:
       for ... : 执行步骤
   finally:
       monitor.stop(); 
       if switched: ime.restore()
   ```
3. 用「本次是否由我们切换」的布尔值替代「靠残留句柄恢复」的隐式约定；
4. 顶部直接 `import ctypes`（Windows 下无害，可读性更好）。

---

### P0-4 新增数据校验层（dict schema 校验）

**现状问题**
全程以 dict 传数据，字段名靠手写字符串。5 类步骤 / 2 类点击点**没有任何校验**：用户手改 JSON（README Q6 明确支持）或旧数据出现缺字段、类型错误时，执行期才暴露且被 try/except 吞掉变成一行难懂日志。`models.Step` 把所有类型字段平铺，也无法表达"click 必须有 point_name 或 x&y"这类约束。

**优化思路**
新增轻量 `core/validation.py`：`validate_step(step) -> list[str]`、`validate_click_point(data) -> list[str]`，按 `StepTypes` 分别约束必填与类型；执行前与编辑器保存前都调用。

**预期收益**
错误在「编辑/加载」时暴露而非「执行中吞掉」；执行器与编辑器共用同一套规则，消除两处规则漂移。

**实施步骤**
1. 规则表：launch→`path` 非空；click→`point_name` 命中点击库 或 `x&y` 为 int；type→`text` 存在；key→`key` 非空；wait→`seconds` ≥ 0 数字；未知 type 记为错误；
2. `Simulator.execute_steps()` 开头逐条校验：非法步骤计 fail 并记录「跳过原因」，**维持现有"单步失败不中断"的容错哲学**；
3. `StepEditorDialog._save()`、`ClickPointEditorDialog` 保存前调用校验，问题直接弹窗指出；
4. 长期可把 `Step` 升级为按 type 区分的 dataclass（见 P1-1 models 决策）。

---

## P1 结构与可维护性

### P1-1 清理死代码与半死代码

**现状问题**（均已验证无外部引用）
- `ui/editor_dialogs.py`：兼容转发层，全项目无任何 import；
- `core/models.py`：`ClickPoint/Step/ExecutionSummary/BurnerConfig/AppConfig` 五个 dataclass **没有任何模块引用**（README 自述"作为结构约定"，实际是半成品死代码）；
- `config_manager` 中 `get_burner_path/set_burner_path` + `burner.json` 加载：无 UI、无执行器调用（历史保留）；
- 根目录 `_inspect_isp300.py`、`_patch_mjh_skill.py`：开发期一次性脚本（README 亦注明可删）；
- `Step` 的 `wait` 遗留字段与 `seconds` 并存，UI 步序表格"事后等待"列读取逻辑易误导。

**优化思路**
纯删 + 二选一决策：`editor_dialogs`、临时脚本直接删；`models`、`burner`、`wait` 给出取舍建议并同步 README。

**预期收益**
减少约 10–15% 维护面；消除「看起来在用其实没用」的误导；字段语义单一化。

**实施步骤**
1. 删除 `ui/editor_dialogs.py`、根目录两个 `_*.py`（若需留档先移出仓库）；
2. burner：删除 ConfigManager 中 burner 加载与两个方法，保留 `burner.json` 文件不读不写（兼容外部脚本），README 更新；
3. models 取舍（建议 **方案 A 轻量**）：
   - A（推荐）：保留并按 type 拆分 Step（`LaunchStep/ClickStep/TypeStep/KeyStep/WaitStep` + 序列化入口），作为 P0-4 校验规则的载体；`ClickPoint` 同步补 `control_type/title/auto_id` 字段（当前模型只有坐标字段，与点击库的两种形态不符，需先补字段再用）；
   - B（最小）：整文件删除，校验职责全放 `validation.py`；
4. `wait` 字段：UI 不再读取、执行器继续忽略（现状已忽略），并在 README「设计演进」注明弃用；如需彻底化，加一次性迁移把「步骤内 wait」转成独立 wait 步骤。

---

### P1-2 ConfigManager 拆分 + 步骤缓存感知外部修改

**现状问题**
- `config_manager.py` 约 300 行单类承载：路径初始化、machines/rates CRUD（含文件联动改名）、click_points CRUD（坐标+控件两种形态）、steps 文件读写缓存、旧格式迁移——改动互相影响；
- `_steps_cache` 是纯内存缓存，**不感知外部手动编辑**：README Q6 鼓励手改 JSON，但程序已缓存旧步骤，界面与实际文件不一致，重启才恢复。

**优化思路**
两层方案：
- 轻量（改动最小）：`get_steps()` 比对文件 `mtime`，变了就重读，缓存带时间戳；
- 结构性：抽 `FileStore`（原子读/写）+ 三个领域 store（Machines/ClickPoints/Steps），`ConfigManager` 退化为**门面**保留原方法签名——UI 层全部走 `config_manager.xxx`，门面模式可让 UI 零改动。

**预期收益**
单一职责、每个 store 可独立单测；手改 JSON 立即生效；为 P3-1 测试打基础。

**实施步骤**
1. 先做缓存 mtime 失效（改动约 10 行，收益立竿见影）；
2. 再评估是否拆 store（改动面中等：内部重组、对外签名不变）；
3. 补 `tmp_path` 单测覆盖 CRUD / 重命名联动文件 / mtime 重载。

---

### P1-3 主窗口大方法拆分与线程调度收敛

**现状问题**
- `main_window._start_burn()` 约 90 行，内嵌 `run_thread` 与三层 lambda 闭包；成功/中断/异常三条结束路径的 UI 恢复分散在各处，靠 `finally` 兜底但不直观；
- 跨线程回主线程统一用 `after(0, lambda ...)`，散落且匿名，未来若调整刷新策略（如节流）需要处处改。

**优化思路**
- `_start_burn` 拆为：`_prepare_run()`（校验+置 running 态）→ `_run_in_background()`（线程入口）→ `_finish_run(summary, error)`（统一收尾：进度/状态/弹窗/按钮复位）；
- 新增统一刷新助手 `_ui(fn)` 内部 `self.after(0, fn)`，所有跨线程刷新走它。

**预期收益**
主流程可读性显著提升；三条结束路径收敛到一处，避免状态遗漏；刷新策略可集中调整。

**实施步骤**
1. 抽出 `_append_log/_set_status/_set_progress` 三个私有方法替换内联 lambda；
2. `run_thread` 内容按阶段命名化拆分；结束处理合并为单一 `_finish_run`；
3. 手测：正常完成 / 鼠标中断 / 抛异常三条路径的按钮、状态、进度均正确复位。

---

### P1-4 步序编辑器表单 schema 化（消除样板与脆弱解析）

**现状问题**
- `step_editor.py` 609 行，5 个 `_build_*_ui` 结构高度雷同（标签 + 输入 + pack 校验闭包），新增步骤类型需整段复制模板；
- `get_type_key()` 用 `label.split()[0]` 从显示名反推类型——显示名「点击 - 调用已记录坐标」取出的「点击」与真正的 key `click` 是两套词，**仅靠 STEP_TYPES 表顺序一致才勉强工作**，属隐性脆弱点；
- 类型显示名与字段约束分散在多个方法，规则难统一。

**优化思路**
把步骤类型升级为 **schema**：`{type: {display, fields: [{name, label, kind, required, quick_options...}]}}`，由 schema 驱动动态表单渲染与数据收集，删掉 5 个 `_build_*_ui` 的大部分样板；`kind` 支持 file/click_point/coords/text/key/wait 等特殊控件工厂。

**预期收益**
新增步骤类型 ≈ 增加一条 schema；显示名↔key 的脆弱 split 逻辑消失；编辑器与校验器共用字段定义。

**实施步骤**
1. 将 `STEP_TYPES` 扩展为含字段定义的 schema（建议放 `core/constants.py` 或独立 `ui/step_schemas.py`）；
2. 重写 `_open_step_dialog` 动态区：遍历 schema 渲染控件 + 统一收集/校验；
3. 逐类型回归：5 类步骤的 新增/修改/保存 路径全量手测；
4. **最小可行先行**：若暂不大改，至少把 `get_type_key` 的 split 解析换成显式字典映射（当前靠表序一致，属迟早踩坑的写法）。

---

### P1-5 控件查找缓存与保护（执行节拍）

**现状问题**
`isp_controls.py`：每次控件点击都 `find_isp_window()`（全桌面枚举窗口）+ `find_control()` **全树深度递归**遍历所有子元素。一步控件点击可达数百 ms ~ 2s；一条步序多个控件点会明显拖慢产线节拍。另 `find_isp_window` 按标题关键字取第一个，多窗口同名时可能点错。

**优化思路**
会话级窗口句柄缓存（点击前用 `exists()/is_active()` 校验，失效再重找）；递归加深度上限与总耗时保护；预留精确标题参数。

**预期收益**
控件步骤点击延迟显著下降（实测对比），错误目标风险降低。

**实施步骤**
1. `isp_controls` 增加"最近窗口"缓存：首次 find 后缓存，下次先验活再复用；
2. `find_control`/`enumerate_controls` 加最大深度（如 15 层）与迭代预算（如 3s 超时）；
3. 对同一控件连续点击 20 次做耗时基准，对比优化前后。

---

## P2 性能与体验

### P2-1 日志框截断（长时间执行防卡顿）

**现状问题**
`_log()` 向 `ScrolledText` 无限 insert，无行数上限。步骤多或重复执行时，Tk 文本控件行数膨胀后插入/滚动显著变慢、内存上升。

**优化思路**
设行数上限（建议 1500 行），超出即删除头部行；超长单行在 UI 展示层截断（完整日志本就落在 `logs/auto_isp.log`，不损失）。

**预期收益**
长时间/多次执行界面始终流畅。

**实施步骤**
1. `_log` 内 insert 后统计行数，超限 `delete("1.0", f"{count - 1500}.0")`；
2. 对比 5000 行日志下的滚动流畅度。

### P2-2 延迟导入重依赖（冷启动 + 解耦）

**现状问题**
`simulator.py` 模块顶层 `import pyautogui`，而 `main_window` 顶层 `from core.simulator import Simulator` → **程序一启动就加载 pyautogui**。与 `isp_controls` 的函数内导入 pywinauto 风格不一致；无烧录动作的编辑场景也白白加载。

**优化思路**
pyautogui 改为在 `click/type_text/press_key/_monitor_loop` 等函数内导入；`main.py` 入口对缺失依赖给出友好提示（对应 README Q8），而非堆栈崩溃。

**预期收益**
冷启动略快；依赖缺失时提示友好；风格统一。

**实施步骤**
1. 删除模块顶部 `import pyautogui`，在用到处函数内导入；
2. `main.py` 包一个启动异常保护，`ImportError` 时弹窗提示 `pip install pyautogui pynput pywinauto`。

### P2-3 长文本输入提速（可选增强）

**现状问题**
`type_text` 用 `pyautogui.typewrite` 逐字符、`TYPE_INTERVAL=0.05s`：30 字符 ≈ 1.5s+ 且逐字符模拟开销更高；长文本含特殊字符时有转义风险。

**优化思路**
固定长文本改「剪贴板 + Ctrl+V」：一次粘贴即完成，速度数量级提升；可按长度自动选择（如 > 40 字符走剪贴板），或 UI 提供开关。注意：粘贴后清空剪贴板，避免污染用户剪贴板；复用 IME 英文切换。

**预期收益**
长文本步骤耗时从秒级降到毫秒级。

**实施步骤**
1. 新增 `paste_text(text)`：切英文 IME → 写剪贴板 → `hotkey("ctrl", "v")` → 清剪贴板；
2. type 表单增加「快速粘贴」选项，默认长度阈值自动；
3. 回归大小写、特殊字符、中文输入法共存场景。

### P2-4 提供主动「停止」能力（安全与体验）

**现状问题**
- 中断只靠「鼠标偏离容差」一种触发；`wait` 用 `time.sleep`，长等待时无法即时响应中断；
- 执行中关闭主窗口，daemon 线程仍会继续模拟输入若干秒（直到进程退出），存在「关窗后电脑还在被操控」的风险窗口。

**优化思路**
会话内引入 `threading.Event` 作为停止信号：主循环每步前检查；`wait` 改 `event.wait(seconds)` 可即时唤醒；主按钮执行中变「停止」；`WM_DELETE_WINDOW` 协议在执行中弹确认。

**预期收益**
紧急情况下可立即停手；消除关窗后的残留操控窗口。

**实施步骤**
1. 随 P0-3 会话化一起落地 stop_event（两改动天然契合）；
2. 主窗口 running 态按钮文案「执行中...→ 停止」并绑定置位；
3. `on_close`：执行中先 askyesno 确认。

---

## P3 工程化与质量

### P3-1 测试体系（核心层优先）
**现状**：全项目零测试；而 `config_manager`（CRUD/迁移/联动改名）、步骤校验、执行循环统计、录制器双击判定都是高价值可测纯逻辑。
**思路**：pytest + `tmp_path` 测 config；mock pyautogui 测执行循环的统计/中断/finally 清理；把 recorder 双击判定抽成纯函数（时间序列 → left/double/right）便于注入假时钟。
**收益**：P0/P1 重构有安全网；回归成本大降。
**步骤**：见 P3-2 的 pyproject 初始化后，依次建 `tests/test_config_manager.py`、`test_validation.py`、`test_simulator.py`；新逻辑（validation、session）**边写边测**。

### P3-2 依赖与构建声明
**现状**：无 `requirements.txt`/`pyproject.toml`；README 裸 `pip install pyautogui pynput pywinauto` 无版本；`AutoISP300.spec` 手写依赖收集。
**思路**：新增 `pyproject.toml`：项目元数据、`requires-python >= 3.10`（与文档对齐，避开 3.8 下新版依赖兼容坑，或反向把 README 改成 3.10+）、dependencies 三个库（写实测锁定版本）、ruff + pytest 配置。
**收益**：环境/构建可复现，别人一条命令可跑；为 CI 或 pre-commit 铺路。
**步骤**：建 pyproject → 在打包机 `pip install -e .` 验证 → `build.bat` 前自动确认依赖版本一致。

### P3-3 文档一致性收尾
**现状**：README 部分表述与实际有出入：core 模块数表述、models「作为结构约定」与现实（未使用）、wait 字段语义、Python 版本声明。
**思路**：P0/P1 落地后同步 README；在 README「设计演进」记录 models/burner/wait/editor_dialogs 的取舍，避免后来者困惑。
**收益**：文档即真相，降低接手成本。

---

## 实施路线图（建议顺序）

| 阶段 | 内容 | 收尾动作 |
|------|------|---------|
| 1 正确性 | P0-1 原子写 → P0-2 统计口径 → P0-3 会话化+finally → P0-4 校验层 | 回归手测 + `build.bat` 出包验证 |
| 2 可维护性 | P1-1 死代码清理 → P1-2 缓存 mtime（+可选门面拆分）→ P1-3 主窗口拆分 → P1-4 表单 schema（或先修 split）→ P1-5 控件缓存 | 手测三个编辑器全路径 |
| 3 性能体验 | P2-1 日志截断 → P2-2 延迟导入 → P2-4 停止按钮（并入阶段 1 更顺）→ P2-3 剪贴板（可选） | 执行体验回归 |
| 4 工程化 | P3-1 测试（可与阶段 1 并行启动）→ P3-2 pyproject → P3-3 README | `pytest` 全绿 + 出包 |

> 每个阶段保持「可独立交付、可独立回滚」；阶段 1 全部改动对外 UI 行为不变，风险最低，优先投入。

## 预期收益总览

| 维度 | 收益 |
|------|------|
| 可靠性 | 配置不再因异常写入损坏；执行统计真实；IME/监控不再泄漏到下次执行 |
| 可维护性 | 消除约 15% 死代码；Simulator/ConfigManager/主窗口大方法职责收敛；校验规则单一来源 |
| 性能 | 控件步骤点击延迟下降、长日志不卡、冷启动略快、长文本输入毫秒级完成 |
| 工程质量 | 核心逻辑有单测覆盖；依赖可复现；新步骤类型扩展成本降为「加一条 schema」 |
