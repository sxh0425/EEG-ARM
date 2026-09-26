#!/usr/bin/env python3
"""只读显示法奥 FR3 当前状态，不发送模式、使能或运动命令。"""

from __future__ import annotations

import argparse
import time

from fr3_common import (
    DEFAULT_ROBOT_IP,
    MODE_NAMES,
    PROGRAM_STATE_NAMES,
    ROBOT_STATE_NAMES,
    close_robot,
    connect,
    result_value,
    value_name,
    wait_for_realtime_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读显示 FR3 当前状态")
    parser.add_argument("--ip", default=DEFAULT_ROBOT_IP, help="机器人控制器 IP")
    parser.add_argument(
        "--watch",
        type=float,
        metavar="秒",
        help="按指定间隔持续刷新；省略时只显示一次",
    )
    args = parser.parse_args()
    if args.watch is not None and args.watch < 0.1:
        parser.error("--watch 间隔不能小于 0.1 秒")
    return args


def yes_no(value: int, yes: str, no: str) -> str:
    return f"{yes if value else no} ({value})"


def print_status(robot) -> None:
    state = wait_for_realtime_state(robot)
    drag = int(result_value("查询拖动状态", robot.IsInDragTeach()))
    joints = [float(v) for v in result_value(
        "查询关节角度", robot.GetActualJointPosDegree(1)
    )]
    tcp = [float(v) for v in result_value(
        "查询 TCP 位姿", robot.GetActualTCPPose(1)
    )]

    mode = int(state.robot_mode)
    robot_state = int(state.robot_state)
    program_state = int(state.program_state)
    enabled = int(state.rbtEnableState)
    stamp_age = time.monotonic() - robot.robot_state_pkg_timestamp

    print("\n========== FR3 当前状态 ==========")
    print(f"手/自动模式 : {value_name(mode, MODE_NAMES)}")
    print(f"拖动示教   : {yes_no(drag, '是', '否')}")
    print(f"机器人使能 : {yes_no(enabled, '上使能', '下使能')}")
    print(f"运动状态   : {value_name(robot_state, ROBOT_STATE_NAMES)}")
    print(f"程序状态   : {value_name(program_state, PROGRAM_STATE_NAMES)}")
    print(f"运动到位   : {yes_no(int(state.motion_done), '是', '否')}")
    print(f"急停       : {yes_no(int(state.EmergencyStop), '已触发', '未触发')}")
    print(
        "安全停止   : "
        f"SI0={int(state.safety_stop0_state)}, "
        f"SI1={int(state.safety_stop1_state)}"
    )
    print(f"碰撞信号   : {yes_no(int(state.collisionState), '有', '无')}")
    print(f"故障码     : 主码={int(state.main_code)}, 子码={int(state.sub_code)}")
    print(f"运动队列   : {int(state.mc_queue_len)}")
    print("关节角度°  : " + ", ".join(
        f"J{i}={angle:.3f}" for i, angle in enumerate(joints, 1)
    ))
    print(
        "TCP 位姿    : "
        f"X={tcp[0]:.3f}, Y={tcp[1]:.3f}, Z={tcp[2]:.3f} mm; "
        f"RX={tcp[3]:.3f}, RY={tcp[4]:.3f}, RZ={tcp[5]:.3f}°"
    )
    print(f"工具/工件号: {int(state.tool)} / {int(state.user)}")
    print(f"状态帧延迟 : {stamp_age * 1000:.1f} ms")


def main() -> int:
    args = parse_args()
    robot = None
    try:
        robot = connect(args.ip)
        while True:
            print_status(robot)
            if args.watch is None:
                return 0
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\n已停止状态刷新。")
        return 0
    except Exception as exc:
        print(f"错误：{exc}")
        return 1
    finally:
        close_robot(robot)


if __name__ == "__main__":
    raise SystemExit(main())

