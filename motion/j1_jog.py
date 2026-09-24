import socket
import time

from fairino import Robot


# ============================================================
# 固定配置
# ============================================================

ROBOT_IP = "192.168.57.2"

# J1方向：
# 1 = 正方向
# 0 = 负方向
J1_DIRECTION = 1

# 第一次测试最大只允许J1运动0.2°
J1_MAX_DISTANCE_DEG = 0.2

# 第一次测试使用极低速度和加速度
J1_SPEED_PERCENT = 1.0
J1_ACCELERATION_PERCENT = 5.0

# 监控时间。到达时间后会额外发送StopJOG
MONITOR_SECONDS = 2.0

# J2～J6允许的反馈波动
OTHER_JOINT_TOLERANCE_DEG = 0.1


# ============================================================
# 辅助函数
# ============================================================

def check_port(ip, port):
    """启动SDK前检查端口，避免连接失败时旧SDK后台线程异常。"""
    try:
        with socket.create_connection((ip, port), timeout=3):
            print(f"端口 {port}：正常")
    except OSError as error:
        raise RuntimeError(
            f"无法连接机器人 {ip}:{port}，错误：{error}"
        )


def require_zero(name, result):
    """检查只返回错误码的SDK函数。"""
    if result != 0:
        raise RuntimeError(
            f"{name}失败，错误码：{result}"
        )


def read_status(name, result):
    """读取形如 (错误码, 数据) 的SDK返回值。"""
    if not isinstance(result, tuple) or len(result) < 2:
        raise RuntimeError(
            f"{name}返回格式异常：{result}"
        )

    error_code = result[0]

    if error_code != 0:
        raise RuntimeError(
            f"{name}失败，错误码：{error_code}"
        )

    return result[1]


def validate_configuration():
    """限制本程序只能进行低速、极小角度的J1测试。"""
    if J1_DIRECTION not in (0, 1):
        raise RuntimeError(
            "J1_DIRECTION只能设置为0或1"
        )

    if not (0.0 < J1_MAX_DISTANCE_DEG <= 0.2):
        raise RuntimeError(
            "首次测试的J1_MAX_DISTANCE_DEG必须在0～0.2°之间"
        )

    if not (0.0 < J1_SPEED_PERCENT <= 1.0):
        raise RuntimeError(
            "首次测试的J1_SPEED_PERCENT必须在0～1%之间"
        )

    if not (0.0 < J1_ACCELERATION_PERCENT <= 5.0):
        raise RuntimeError(
            "首次测试的J1_ACCELERATION_PERCENT必须在0～5%之间"
        )


def read_and_check_robot_state(robot):
    """读取并检查运动前的机器人状态。"""
    robot_errors = read_status(
        "读取机器人错误",
        robot.GetRobotErrorCode(),
    )

    emergency_stop = read_status(
        "读取急停状态",
        robot.GetRobotEmergencyStopState(),
    )

    safety_stop = read_status(
        "读取安全停止状态",
        robot.GetSafetyStopState(),
    )

    motion_state = read_status(
        "读取机器人运动状态",
        robot.GetProgramState(),
    )

    queue_length = read_status(
        "读取运动队列长度",
        robot.GetMotionQueueLength(),
    )

    joints = read_status(
        "读取当前关节角度",
        robot.GetActualJointPosDegree(0),
    )

    print("机器人错误：", robot_errors)
    print("急停状态：", emergency_stop)
    print("安全停止状态：", safety_stop)
    print("机器人运动状态：", motion_state)
    print("运动队列长度：", queue_length)
    print("当前关节角度：", joints)

    if len(joints) != 6:
        raise RuntimeError(
            f"关节数据长度异常：{joints}"
        )

    if any(int(value) != 0 for value in robot_errors):
        raise RuntimeError(
            f"机器人存在错误：{robot_errors}"
        )

    if int(emergency_stop) != 0:
        raise RuntimeError(
            "急停处于触发状态"
        )

    if any(int(value) != 0 for value in safety_stop):
        raise RuntimeError(
            f"安全停止信号有效：{safety_stop}"
        )

    # 这个版本中状态1表示机器人停止
    if int(motion_state) != 1:
        raise RuntimeError(
            f"机器人当前不是停止状态，状态值：{motion_state}"
        )

    if int(queue_length) != 0:
        raise RuntimeError(
            f"机器人运动队列不为空，长度：{queue_length}"
        )

    return [float(value) for value in joints]


# ============================================================
# 主程序
# ============================================================

robot = None
jog_active = False
enabled_by_script = False
mode_changed = False

try:
    validate_configuration()

    # 只预检查控制端口。20004是实时数据流端口，留给SDK独占连接。
    check_port(ROBOT_IP, 20003)

    print(f"正在连接机器人：{ROBOT_IP}")
    robot = Robot.RPC(ROBOT_IP)

    # 给实时状态线程一点接收数据的时间
    time.sleep(1.0)

    if not getattr(robot, "sock_cli_state_state", False):
        raise RuntimeError(
            "SDK没有成功连接实时状态端口20004，拒绝运动"
        )

    # --------------------------------------------------------
    # 版本检查
    # --------------------------------------------------------

    sdk_result = robot.GetSDKVersion()
    print("SDK版本：", sdk_result)

    if not isinstance(sdk_result, tuple) or len(sdk_result) < 2:
        raise RuntimeError(
            f"无法读取SDK版本：{sdk_result}"
        )

    if sdk_result[0] != 0:
        raise RuntimeError(
            f"读取SDK版本失败，错误码：{sdk_result[0]}"
        )

    sdk_versions = sdk_result[1]

    if "SDK:V2.0.8" not in sdk_versions:
        raise RuntimeError(
            f"SDK版本不是V2.0.8：{sdk_versions}"
        )

    if "Robot:V3.7.8" not in sdk_versions:
        raise RuntimeError(
            f"SDK目标控制器版本不是V3.7.8：{sdk_versions}"
        )

    software_result = robot.GetSoftwareVersion()
    print("机器人软件版本：", software_result)

    if (
        not isinstance(software_result, tuple)
        or len(software_result) < 4
        or software_result[0] != 0
    ):
        raise RuntimeError(
            f"读取机器人软件版本失败：{software_result}"
        )

    robot_model = str(software_result[1])
    web_version = str(software_result[2])
    controller_version = str(software_result[3])

    if "FR3" not in robot_model.upper():
        raise RuntimeError(
            f"机器人型号不是FR3：{robot_model}"
        )

    if controller_version.upper() != "V3.7.8":
        raise RuntimeError(
            f"控制器版本不是V3.7.8：{controller_version}"
        )

    print("机器人型号：", robot_model)
    print("Web版本：", web_version)
    print("控制器版本：", controller_version)

    # --------------------------------------------------------
    # 第一次安全状态检查
    # --------------------------------------------------------

    joints_before = read_and_check_robot_state(robot)

    print()
    print("准备执行的唯一运动命令：")
    print("  关节：J1")
    print(
        "  方向：",
        "正方向" if J1_DIRECTION == 1 else "负方向",
    )
    print(f"  最大角度：{J1_MAX_DISTANCE_DEG}°")
    print(f"  速度：{J1_SPEED_PERCENT}%")
    print(f"  加速度：{J1_ACCELERATION_PERCENT}%")
    print()
    print("J1旋转会带动上方整条机械臂在空间中旋转。")
    print("J2～J6不会收到运动指令，但会跟随J1整体改变空间位置。")
    print()

    confirmation = input(
        "确认机器人已经固定、整个回转区域无人、"
        "物理急停在手边后，输入 MOVE_J1："
    )

    if confirmation != "MOVE_J1":
        print("未输入MOVE_J1，取消运行。")
        raise SystemExit(0)

    # --------------------------------------------------------
    # 切换模式、设置低速并使能
    # --------------------------------------------------------

    require_zero(
        "切换自动模式",
        robot.Mode(0),
    )
    mode_changed = True

    require_zero(
        "设置全局速度",
        robot.SetSpeed(1),
    )

    require_zero(
        "机器人使能",
        robot.RobotEnable(1),
    )
    enabled_by_script = True

    time.sleep(1.0)

    # 使能后再次检查状态，并使用最新关节角度作为基准
    joints_before = read_and_check_robot_state(robot)

    print("即将发送J1点动命令。")

    # --------------------------------------------------------
    # 唯一的运动指令：J1点动
    # --------------------------------------------------------

    jog_result = robot.StartJOG(
        ref=0,                          # 关节坐标系
        nb=1,                           # 固定为J1
        dir=J1_DIRECTION,               # 0负方向，1正方向
        max_dis=J1_MAX_DISTANCE_DEG,    # 最大0.2°
        vel=J1_SPEED_PERCENT,           # 速度1%
        acc=J1_ACCELERATION_PERCENT,    # 加速度5%
    )

    require_zero(
        "启动J1点动",
        jog_result,
    )

    jog_active = True

    # --------------------------------------------------------
    # 运动期间监控J2～J6
    # --------------------------------------------------------

    monitor_deadline = time.monotonic() + MONITOR_SECONDS

    while time.monotonic() < monitor_deadline:
        current_joints = read_status(
            "监控当前关节角度",
            robot.GetActualJointPosDegree(0),
        )

        current_joints = [
            float(value)
            for value in current_joints
        ]

        joint_changes = [
            current - initial
            for initial, current in zip(
                joints_before,
                current_joints,
            )
        ]

        # 下标1～5对应J2～J6
        unexpected_changes = [
            abs(change)
            for change in joint_changes[1:]
        ]

        if any(
            change > OTHER_JOINT_TOLERANCE_DEG
            for change in unexpected_changes
        ):
            immediate_result = robot.ImmStopJOG()
            jog_active = False

            raise RuntimeError(
                "检测到J2～J6角度变化超过允许值，"
                f"已发送立即停止。变化量：{joint_changes}，"
                f"停止返回值：{immediate_result}"
            )

        time.sleep(0.05)

    # 额外发送一次关节点动减速停止
    stop_result = robot.StopJOG(1)

    if stop_result != 0:
        immediate_result = robot.ImmStopJOG()
        jog_active = False

        raise RuntimeError(
            f"StopJOG失败，错误码：{stop_result}；"
            f"ImmStopJOG返回值：{immediate_result}"
        )

    jog_active = False

    time.sleep(0.5)

    # --------------------------------------------------------
    # 显示最终角度变化
    # --------------------------------------------------------

    joints_after = read_status(
        "读取运动后关节角度",
        robot.GetActualJointPosDegree(0),
    )

    joints_after = [
        float(value)
        for value in joints_after
    ]

    joint_changes = [
        round(after - before, 4)
        for before, after in zip(
            joints_before,
            joints_after,
        )
    ]

    print()
    print("运动前关节角度：", joints_before)
    print("运动后关节角度：", joints_after)
    print("各关节角度变化：", joint_changes)

    if any(
        abs(change) > OTHER_JOINT_TOLERANCE_DEG
        for change in joint_changes[1:]
    ):
        print("警告：J2～J6存在超过允许值的角度变化。")
    else:
        print("J2～J6未检测到明显角度变化。")

    print("J1低速点动测试完成。")

except KeyboardInterrupt:
    print("\n检测到Ctrl+C，发送JOG立即停止命令。")

    if robot is not None:
        try:
            print(
                "ImmStopJOG返回值：",
                robot.ImmStopJOG(),
            )
        except Exception as stop_error:
            print("软件停止失败：", stop_error)
            print("请立即使用物理急停。")

except SystemExit:
    pass

except Exception as error:
    print("程序停止：", error)

    if robot is not None and jog_active:
        try:
            print(
                "ImmStopJOG返回值：",
                robot.ImmStopJOG(),
            )
        except Exception:
            print("软件停止失败，请使用物理急停。")

finally:
    if robot is not None:
        if jog_active:
            try:
                robot.ImmStopJOG()
            except Exception:
                pass

        if enabled_by_script:
            try:
                print(
                    "机器人下使能：",
                    robot.RobotEnable(0),
                )
            except Exception as disable_error:
                print("机器人下使能异常：", disable_error)

        if mode_changed:
            try:
                print(
                    "切回手动模式：",
                    robot.Mode(1),
                )
            except Exception as mode_error:
                print("切回手动模式异常：", mode_error)

        try:
            # v2.0.8必须先设置退出标志，再关闭实时状态套接字，
            # 否则后台线程可能反复读取已经关闭的文件描述符。
            robot.closeRPC_state = True
            robot.stop_event.set()
            robot.CloseRPC()
        except Exception as close_error:
            print("关闭RPC异常：", close_error)
