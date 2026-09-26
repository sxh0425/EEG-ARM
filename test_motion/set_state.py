#!/usr/bin/env python3
"""按单条命令切换法奥 FR3 的模式或使能状态。"""

from __future__ import annotations

import argparse
import time

from fr3_common import (
    DEFAULT_ROBOT_IP,
    MODE_NAMES,
    close_robot,
    connect,
    require_ok,
    result_value,
    value_name,
    wait_for_realtime_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="单独设置 FR3 模式或使能状态（不发送运动指令）",
        epilog=(
            "示例：%(prog)s --mode manual；"
            "%(prog)s --mode drag；"
            "%(prog)s --enable off"
        ),
    )
    parser.add_argument("--ip", default=DEFAULT_ROBOT_IP, help="机器人控制器 IP")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--mode",
        choices=("manual", "auto", "drag"),
        help="目标模式：manual=手动，auto=自动，drag=拖动示教",
    )
    action.add_argument(
        "--enable",
        choices=("on", "off"),
        help="on=上使能，off=下使能",
    )
    return parser.parse_args()


def current_summary(robot) -> tuple[int, int, int]:
    state = wait_for_realtime_state(robot)
    drag = int(result_value("查询拖动状态", robot.IsInDragTeach()))
    return int(state.robot_mode), drag, int(state.rbtEnableState)


def describe(mode: int, drag: int, enabled: int) -> str:
    mode_text = "拖动示教" if drag else value_name(mode, MODE_NAMES)
    enable_text = "上使能" if enabled else "下使能"
    return f"模式={mode_text}，使能={enable_text}"


def apply_state(robot, args: argparse.Namespace) -> None:
    """除 drag 的必要前置手动模式外，不做任何隐含状态切换。"""
    if args.mode == "manual":
        require_ok("切换手动模式", robot.Mode(1))
    elif args.mode == "auto":
        require_ok("切换自动模式", robot.Mode(0))
    elif args.mode == "drag":
        # 官方接口要求：拖动示教前先切换到手动模式。
        require_ok("切换手动模式", robot.Mode(1))
        require_ok("进入拖动示教", robot.DragTeachSwitch(1))
    elif args.enable == "on":
        require_ok("机器人上使能", robot.RobotEnable(1))
    elif args.enable == "off":
        require_ok("机器人下使能", robot.RobotEnable(0))


def expected_matches(args: argparse.Namespace, mode: int, drag: int, enabled: int) -> bool:
    mode_ok = (
        args.mode is None
        or (args.mode == "manual" and mode == 1)
        or (args.mode == "auto" and mode == 0)
        or (args.mode == "drag" and mode == 1 and drag == 1)
    )
    enable_ok = (
        args.enable is None
        or (args.enable == "on" and enabled == 1)
        or (args.enable == "off" and enabled == 0)
    )
    return mode_ok and enable_ok


def main() -> int:
    args = parse_args()
    robot = None
    try:
        robot = connect(args.ip)
        mode, drag, enabled = current_summary(robot)
        print(f"设置前状态：{describe(mode, drag, enabled)}")
        apply_state(robot, args)
        time.sleep(0.5)
        mode, drag, enabled = current_summary(robot)
        after = describe(mode, drag, enabled)
        print(f"设置后状态：{after}")
        if not expected_matches(args, mode, drag, enabled):
            raise RuntimeError("反馈状态与请求不一致，请检查控制器/WebApp 提示")
        print("设置成功。")
        return 0
    except KeyboardInterrupt:
        print("已取消。")
        return 130
    except Exception as exc:
        print(f"错误：{exc}")
        return 1
    finally:
        close_robot(robot)


if __name__ == "__main__":
    raise SystemExit(main())
