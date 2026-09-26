"""FR3 拖动示教示例。

运行前请先在 WebApp 中正确设置夹爪和所夹物体的负载重量、重心。
"""

import time

from fairino import Robot


ROBOT_IP = "192.168.57.2"


def require_ok(name, result):
    """SDK 返回非 0 时立即停止。"""
    error_code = result[0] if isinstance(result, tuple) else result
    if error_code != 0:
        raise RuntimeError(f"{name}失败，错误码：{error_code}")


def main():
    robot = Robot.RPC(ROBOT_IP)
    drag_started = False

    try:
        print("拖动前请确认：")
        print("1. 夹爪和所夹物体的负载重量、重心已经正确设置")
        print("2. 机械臂周围无人，急停在手边")
        print("3. 已经用手扶住机械臂，并避开所有关节夹缝")

        confirmation = input("全部确认后输入 DRAG：")
        if confirmation != "DRAG":
            print("已取消。")
            return

        require_ok("切换手动模式", robot.Mode(1))
        require_ok("机器人上使能", robot.RobotEnable(1))
        time.sleep(1.0)

        require_ok("进入拖动模式", robot.DragTeachSwitch(1))
        drag_started = True

        drag_state = robot.IsInDragTeach()
        require_ok("查询拖动状态", drag_state)
        if drag_state[1] != 1:
            raise RuntimeError("机器人没有进入拖动模式")

        print("已进入拖动模式，可以用手缓慢拖动机械臂。")
        input("拖动完成后按 Enter 退出：")

    finally:
        if drag_started:
            print("退出拖动模式：", robot.DragTeachSwitch(0))
        print("机器人下使能：", robot.RobotEnable(0))
        robot.closeRPC_state = True
        robot.stop_event.set()
        robot.CloseRPC()


if __name__ == "__main__":
    main()
