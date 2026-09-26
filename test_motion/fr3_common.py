"""FR3 状态/模式工具共用代码。"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SDK_PATH = PROJECT_ROOT / "third_party" / "fairino-python-sdk" / "linux"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from fairino import Robot  # noqa: E402


DEFAULT_ROBOT_IP = "192.168.57.2"
MODE_NAMES = {0: "自动", 1: "手动"}
ROBOT_STATE_NAMES = {1: "停止", 2: "运行", 3: "暂停", 4: "拖动"}
PROGRAM_STATE_NAMES = {1: "停止/无程序", 2: "运行", 3: "暂停"}


def value_name(value: int, names: dict[int, str]) -> str:
    return f"{names.get(value, '未知')} ({value})"


def result_value(name: str, result: Any) -> Any:
    """解析 SDK 常见的 ``(错误码, 数据)`` 返回值。"""
    if not isinstance(result, tuple) or len(result) < 2:
        raise RuntimeError(f"{name}返回格式异常：{result!r}")
    if result[0] != 0:
        raise RuntimeError(f"{name}失败，错误码：{result[0]}")
    return result[1]


def require_ok(name: str, result: Any) -> None:
    """检查只返回错误码的 SDK 调用。"""
    error_code = result[0] if isinstance(result, tuple) else result
    if error_code != 0:
        raise RuntimeError(f"{name}失败，错误码：{error_code}")


def connect(ip: str):
    print(f"正在连接 FR3：{ip}")
    return Robot.RPC(ip)


def wait_for_realtime_state(robot: Any, timeout: float = 5.0) -> Any:
    """等待 SDK 收到一帧有效实时状态，避免显示初始化零值。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = getattr(robot, "robot_state_pkg", None)
        timestamp = getattr(robot, "robot_state_pkg_timestamp", None)
        if state is not None and not isinstance(state, type) and timestamp is not None:
            if time.monotonic() - timestamp <= 1.0:
                return state
        time.sleep(0.05)
    raise RuntimeError(f"{timeout:.1f} 秒内未收到机器人有效实时状态")


def close_robot(robot: Any) -> None:
    """兼容当前项目内 SDK 的安全关闭方式。"""
    if robot is None:
        return
    robot.closeRPC_state = True
    robot.stop_event.set()
    robot.CloseRPC()

