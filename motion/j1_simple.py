"""FR3 J1 点动教学示例。

这是便于学习 SDK 调用顺序的精简版，不代替生产环境安全程序。
"""

import time

from fairino import Robot


ROBOT_IP = "192.168.57.2"
J1_DIRECTION = 1
J1_DISTANCE_DEG = 15.0
J1_SPEED_PERCENT = 20.0
J1_ACCELERATION_PERCENT = 5.0
MAX_WAIT_SECONDS = 20.0


def require_ok(name, error_code):
    if error_code != 0:
        raise RuntimeError(f"{name}失败，错误码：{error_code}")


def get_joints(robot):
    error_code, joints = robot.GetActualJointPosDegree(0)
    require_ok("读取关节角度", error_code)
    return [float(value) for value in joints]


def main():
    robot = Robot.RPC(ROBOT_IP)
    jog_started = False

    try:
        print("SDK版本：", robot.GetSDKVersion())
        print("当前关节角度：", get_joints(robot))

        confirmation = input(
            "确认J1正方向15°范围安全，输入 MOVE_J1："
        )
        if confirmation != "MOVE_J1":
            print("已取消。")
            return

        # 1. 保持手动模式并上使能
        require_ok("切换手动模式", robot.Mode(1))
        require_ok("机器人上使能", robot.RobotEnable(1))
        time.sleep(3.0)

        # 2. 设置全局速度
        require_ok(
            "设置全局速度",
            robot.SetSpeed(J1_SPEED_PERCENT),
        )

        # 3. 记录起始角度并启动J1点动
        joints_before = get_joints(robot)
        jog_started = True
        require_ok(
            "启动J1点动",
            robot.StartJOG(
                ref=0,
                nb=1,
                dir=J1_DIRECTION,
                max_dis=J1_DISTANCE_DEG,
                vel=J1_SPEED_PERCENT,
                acc=J1_ACCELERATION_PERCENT,
            ),
        )

        # 4. 等待J1接近目标角度
        deadline = time.monotonic() + MAX_WAIT_SECONDS
        reached_target = False

        while time.monotonic() < deadline:
            joints_now = get_joints(robot)
            j1_change = joints_now[0] - joints_before[0]
            directed_change = (
                j1_change
                if J1_DIRECTION == 1
                else -j1_change
            )

            print(f"J1变化：{j1_change:.3f}°")

            if directed_change >= J1_DISTANCE_DEG * 0.95:
                reached_target = True
                break

            time.sleep(0.2)

        # 5. 停止点动
        require_ok("停止J1点动", robot.StopJOG(1))
        jog_started = False
        time.sleep(0.5)

        joints_after = get_joints(robot)
        print("运动前：", joints_before)
        print("运动后：", joints_after)
        print(
            "J1总变化："
            f"{joints_after[0] - joints_before[0]:.3f}°"
        )

        if not reached_target:
            print("提示：20秒内未达到目标角度，程序已停止。")

    finally:
        try:
            if jog_started:
                robot.ImmStopJOG()
        finally:
            try:
                robot.RobotEnable(0)
            finally:
                robot.closeRPC_state = True
                robot.stop_event.set()
                robot.CloseRPC()


if __name__ == "__main__":
    main()
