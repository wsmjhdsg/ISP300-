"""步序与点击点的轻量校验层。

背景: 历史版本全程 dict 传递数据、无校验, 用户手改 JSON(README 明确支持)或旧数据
出现缺字段/类型错误时, 要等执行期才暴露, 且被单步容错吞成一行难懂日志。

本模块把"数据契约"显式化: 校验函数返回问题列表, 供执行器(跳过并计失败)与编辑器
(保存前弹窗提示)复用, 消除两处规则漂移。未知步骤类型不再静默跳过, 而是显式报错。
"""
from typing import Any, Dict, List, Optional

from core.constants import ClickPointTypes, MouseButtons, OpenFileModes, StepTypes

# 点击/控件点的合法按键方式(Step 自身也可带 button 覆盖)
_VALID_BUTTONS = MouseButtons.VALID


def _check_button(step: Dict[str, Any], key: str = "button") -> List[str]:
    btn = step.get(key)
    if btn is not None and btn not in _VALID_BUTTONS:
        return [f"字段 '{key}' 取值非法: {btn!r} (应为 {_VALID_BUTTONS})"]
    return []


def validate_step(
    step: Any, click_point_names: Optional[List[str]] = None
) -> List[str]:
    """校验单个步序对象, 返回问题列表(空列表 = 合法)。click_point_names 提供时,
    额外校验 click 步骤引用的点位是否存在。"""
    if not isinstance(step, dict):
        return [f"步骤不是对象: {step!r}"]

    errs: List[str] = []
    step_type = step.get("type")

    if step_type not in StepTypes.ALL:
        errs.append(f"未知步骤类型: {step_type!r} (应为 {StepTypes.ALL})")
        return errs

    if step_type == StepTypes.LAUNCH:
        path = step.get("path")
        if not isinstance(path, str) or not path.strip():
            errs.append("launch 步骤缺少 'path'(软件路径不能为空)")

    elif step_type == StepTypes.CLICK:
        has_point = bool(step.get("point_name"))
        has_xy = step.get("x") is not None and step.get("y") is not None
        if not has_point and not has_xy:
            errs.append("click 步骤需要 'point_name' 或 'x'/'y' 之一")
        if has_point and click_point_names is not None:
            name = step["point_name"]
            if name not in click_point_names:
                errs.append(f"click 引用不存在的位置点: {name!r}")
        errs.extend(_check_button(step))

    elif step_type == StepTypes.OPENFILE:
        mode = step.get("mode") or OpenFileModes.PATH
        if mode not in OpenFileModes.ALL:
            errs.append(
                f"openfile 的 'mode' 取值非法: {mode!r} (应为 {OpenFileModes.ALL})"
            )
        elif mode == OpenFileModes.PATH:
            path = step.get("path")
            if not isinstance(path, str) or not path.strip():
                errs.append("openfile(path 模式) 缺少 'path'(文件路径不能为空)")
        elif mode == OpenFileModes.LATEST:
            directory = step.get("dir")
            if not isinstance(directory, str) or not directory.strip():
                errs.append("openfile(latest 模式) 缺少 'dir'(目录不能为空)")

    elif step_type == StepTypes.TYPE:
        if not isinstance(step.get("text"), str) or not step.get("text"):
            errs.append("type 步骤缺少 'text'(输入文本不能为空)")

    elif step_type == StepTypes.KEY:
        if not isinstance(step.get("key"), str) or not step.get("key"):
            errs.append("key 步骤缺少 'key'(按键名不能为空)")

    elif step_type == StepTypes.WAIT:
        sec = step.get("seconds", 1.0)
        try:
            if float(sec) < 0:
                errs.append(f"wait 秒数不能为负: {sec!r}")
        except (TypeError, ValueError):
            errs.append(f"wait 的 'seconds' 必须是数字: {sec!r}")

    elif step_type == StepTypes.WAITRESULT:
        timeout = step.get("timeout")
        if timeout is not None:
            try:
                if float(timeout) < 0:
                    errs.append(f"waitresult 超时不能为负: {timeout!r}")
            except (TypeError, ValueError):
                errs.append(f"waitresult 的 'timeout' 必须是数字: {timeout!r}")

    return errs


def validate_click_point(name: str, data: Any) -> List[str]:
    """校验一个点击位置点(坐标点或控件点), 返回问题列表。"""
    if not isinstance(data, dict):
        return [f"位置点 {name!r} 不是对象: {data!r}"]

    errs: List[str] = []
    if data.get("type") == ClickPointTypes.CONTROL:
        # 控件点: 至少一个定位字段非空
        if not (data.get("control_type") or data.get("title") or data.get("auto_id")):
            errs.append(f"控件点 {name!r} 缺少定位信息(control_type/title/auto_id 至少一项)")
    else:
        # 坐标点
        for field in ("x", "y"):
            try:
                int(data.get(field))
            except (TypeError, ValueError):
                errs.append(f"坐标点 {name!r} 的 '{field}' 不是整数: {data.get(field)!r}")
    errs.extend(_check_button(data))
    return errs


def validate_click_points(points: Dict[str, Any]) -> Dict[str, List[str]]:
    """批量校验点击库, 返回 {点位名: 问题列表}(合法的点位不在结果中)。"""
    return {
        name: errs
        for name, data in points.items()
        if (errs := validate_click_point(name, data))
    }
