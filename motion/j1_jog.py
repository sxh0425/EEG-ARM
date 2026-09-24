import argparse
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

# 按已确认方案，J1正方向最多运动15°
J1_MAX_DISTANCE_DEG = 15.0

# 采用师兄方案的角度和速度，保留较低加速度
J1_SPEED_PERCENT = 20.0
J1_ACCELERATION_PERCENT = 5.0

# 最长监控时间；正常情况下到达目标角度后会提前停止
MONITOR_SECONDS = 20.0
TARGET_REACHED_RATIO = 0.95
J1_REVERSE_TOLERANCE_DEG = 0.2
J1_OVERSHOOT_TOLERANCE_DEG = 0.5

# J2～J6允许的反馈波动
OTHER_JOINT_TOLERANCE_DEG = 0.1


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "FR3 J1首次低速点动测试。默认只检查状态；"
            "只有添加--execute才可能发送运动命令。"
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="允许在人工确认后执行J1正方向15°点动",
    )
    return parser.parse_args()


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
    """限制本程序只能进行已确认参数范围内的J1测试。"""
    if J1_DIRECTION not in (0, 1):
        raise RuntimeError(
            "J1_DIRECTION只能设置为0或1"
        )

    if not (0.0 < J1_MAX_DISTANCE_DEG <= 15.0):
        raise RuntimeError(
            "J1_MAX_DISTANCE_DEG必须在0～15°之间"
        )

    if not (0.0 < J1_SPEED_PERCENT <= 20.0):
        raise RuntimeError(
            "J1_SPEED_PERCENT必须在0～20%之间"
        )

    if not (0.0 < J1_ACCELERATION_PERCENT <= 5.0):
        raise RuntimeError(
            "首次测试的J1_ACCELERATION_PERCENT必须在0～5%之间"
        )


def read_and_check_realtime_state(
    robot,
    expected_mode,
):
    """检查实时状态帧中的模式和运动安全状态。"""
    state = robot.robot_state_pkg

    if isinstance(state, type):
        raise RuntimeError(
            "尚未收到有效的机器人实时状态帧"
        )

    state_timestamp = getattr(
        robot,
        "robot_state_pkg_timestamp",
        None,
    )

    if state_timestamp is None:
        raise RuntimeError(
            "实时状态帧没有有效时间戳"
        )

    state_age_seconds = time.monotonic() - state_timestamp

    realtime = {
        "robot_mode": int(state.robot_mode),
        "enable_state": "当前773字节状态帧不提供",
        "motion_done": int(state.motion_done),
        "collision_state": int(state.collisionState),
        "state_age_seconds": round(state_age_seconds, 3),
        "valid_frames": int(robot.robot_state_valid_count),
        "invalid_frames": int(robot.robot_state_invalid_count),
    }

    print("实时安全状态：", realtime)

    if realtime["robot_mode"] != expected_mode:
        raise RuntimeError(
            "机器人模式不符合预期："
            f"期望{expected_mode}，实际{realtime['robot_mode']}"
        )

    if realtime["motion_done"] != 1:
        raise RuntimeError(
            "实时状态显示机器人尚未停止"
        )

    if realtime["collision_state"] != 0:
        raise RuntimeError(
            "实时状态显示机器人存在碰撞信号"
        )

    if state_age_seconds > 0.5:
        raise RuntimeError(
            "实时状态已经超过0.5秒没有更新，拒绝继续"
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

arguments = parse_arguments()

robot = None
jog_stop_required = False
enable_was_requested = False

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
    read_and_check_realtime_state(
        robot,
        expected_mode=1,
    )

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

    if not arguments.execute:
        print("只读检查通过。")
        print("本次未提供--execute，不会切换模式、使能或运动。")
        print(
            "完成现场安全确认后，才可由操作者本人使用"
            "--execute重新运行。"
        )
        raise SystemExit(0)

    confirmation = input(
        "确认机器人已经固定、整个回转区域无人、"
        "物理急停在手边后，输入 MOVE_J1："
    )

    if confirmation != "MOVE_J1":
        print("未输入MOVE_J1，取消运行。")
        raise SystemExit(0)

    # --------------------------------------------------------
    # 保持手动模式并使能
    # --------------------------------------------------------

    # 只要发送过使能请求，finally就会尝试下使能。
    enable_was_requested = True
    require_zero(
        "机器人使能",
        robot.RobotEnable(1),
    )

    # V3.7.x官方示例在上使能后等待3秒。
    time.sleep(3.0)

    # 使能命令返回成功后，再确认无报警、仍为手动模式且静止。
    # 这台控制器的773字节状态帧不包含独立使能反馈字段。
    joints_before = read_and_check_robot_state(robot)
    read_and_check_realtime_state(
        robot,
        expected_mode=1,
    )

    require_zero(
        "设置全局速度",
        robot.SetSpeed(J1_SPEED_PERCENT),
    )

    print("即将发送J1点动命令。")

    # --------------------------------------------------------
    # 唯一的运动指令：J1点动
    # --------------------------------------------------------

    # 在调用前设置停止标志，避免命令已经到达但响应丢失时漏发停止。
    jog_stop_required = True
    jog_result = robot.StartJOG(
        ref=0,                          # 关节坐标系
        nb=1,                           # 固定为J1
        dir=J1_DIRECTION,               # 0负方向，1正方向
        max_dis=J1_MAX_DISTANCE_DEG,    # 最大15°
        vel=J1_SPEED_PERCENT,           # 速度20%
        acc=J1_ACCELERATION_PERCENT,    # 加速度5%
    )

    require_zero(
        "启动J1点动",
        jog_result,
    )

    # --------------------------------------------------------
    # 运动期间监控J1目标以及J2～J6
    # --------------------------------------------------------

    monitor_deadline = time.monotonic() + MONITOR_SECONDS
    next_progress_time = time.monotonic()
    target_reached = False

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

        directed_j1_change = (
            joint_changes[0]
            if J1_DIRECTION == 1
            else -joint_changes[0]
        )

        if directed_j1_change < -J1_REVERSE_TOLERANCE_DEG:
            immediate_result = robot.ImmStopJOG()
            jog_stop_required = False

            raise RuntimeError(
                "检测到J1向错误方向运动，"
                f"已发送立即停止。变化量：{joint_changes[0]:.4f}°，"
                f"停止返回值：{immediate_result}"
            )

        if (
            directed_j1_change
            > J1_MAX_DISTANCE_DEG + J1_OVERSHOOT_TOLERANCE_DEG
        ):
            immediate_result = robot.ImmStopJOG()
            jog_stop_required = False

            raise RuntimeError(
                "检测到J1超过允许角度，"
                f"已发送立即停止。变化量：{joint_changes[0]:.4f}°，"
                f"停止返回值：{immediate_result}"
            )

        if any(
            change > OTHER_JOINT_TOLERANCE_DEG
            for change in unexpected_changes
        ):
            immediate_result = robot.ImmStopJOG()
            jog_stop_required = False

            raise RuntimeError(
                "检测到J2～J6角度变化超过允许值，"
                f"已发送立即停止。变化量：{joint_changes}，"
                f"停止返回值：{immediate_result}"
            )

        current_time = time.monotonic()
        if current_time >= next_progress_time:
            print(
                "J1当前变化："
                f"{joint_changes[0]:.4f}° / "
                f"目标{J1_MAX_DISTANCE_DEG:.1f}°"
            )
            next_progress_time = current_time + 0.5

        if (
            directed_j1_change
            >= J1_MAX_DISTANCE_DEG * TARGET_REACHED_RATIO
        ):
            target_reached = True
            print("J1已接近目标角度，准备减速停止。")
            break

        time.sleep(0.05)

    # 额外发送一次关节点动减速停止
    stop_result = robot.StopJOG(1)

    if stop_result != 0:
        immediate_result = robot.ImmStopJOG()
        jog_stop_required = False

        raise RuntimeError(
            f"StopJOG失败，错误码：{stop_result}；"
            f"ImmStopJOG返回值：{immediate_result}"
        )

    jog_stop_required = False

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

    if not target_reached:
        raise RuntimeError(
            f"J1在{MONITOR_SECONDS:.1f}秒内未达到目标角度，"
            "已停止本次测试"
        )

    print("J1低速点动测试完成。")

except KeyboardInterrupt:
    print("\n检测到Ctrl+C，发送JOG立即停止命令。")

    if robot is not None and jog_stop_required:
        try:
            print(
                "ImmStopJOG返回值：",
                robot.ImmStopJOG(),
            )
            jog_stop_required = False
        except Exception as stop_error:
            print("软件停止失败：", stop_error)
            print("请立即使用物理急停。")

except SystemExit:
    pass

except Exception as error:
    print("程序停止：", error)

    if robot is not None and jog_stop_required:
        try:
            print(
                "ImmStopJOG返回值：",
                robot.ImmStopJOG(),
            )
            jog_stop_required = False
        except Exception:
            print("软件停止失败，请使用物理急停。")

finally:
    if robot is not None:
        if jog_stop_required:
            try:
                robot.ImmStopJOG()
            except Exception:
                pass

        if enable_was_requested:
            try:
                print(
                    "机器人下使能：",
                    robot.RobotEnable(0),
                )
            except Exception as disable_error:
                print("机器人下使能异常：", disable_error)

        try:
            # v2.0.8必须先设置退出标志，再关闭实时状态套接字，
            # 否则后台线程可能反复读取已经关闭的文件描述符。
            robot.closeRPC_state = True
            robot.stop_event.set()
            robot.CloseRPC()
        except Exception as close_error:
            print("关闭RPC异常：", close_error)
