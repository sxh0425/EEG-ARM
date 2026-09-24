import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fairino import Robot
import time

ROBOT_IP = "192.168.57.2"

# 参数区
JOG_AXIS = 1          # 1 = J1
JOG_DIR = 0           # 1 = 正方向，0 = 反方向
TARGET_DELTA = 15.0   # 目标移动角度：10度
VEL = 20.0            # 速度百分比
ACC = 30.0            # 加速度百分比

robot = Robot.RPC(ROBOT_IP)

try:
    print("SDK版本:", robot.GetSDKVersion())
    print("复位错误:", robot.ResetAllError())

    # JOG点动用手动模式
    print("切手动模式:", robot.Mode(1))
    time.sleep(1)

    print("上使能:", robot.RobotEnable(1))
    time.sleep(1)

    print("设置全局速度:", robot.SetSpeed(VEL))

    print("急停状态:", robot.GetRobotEmergencyStopState())
    print("安全停止状态:", robot.GetSafetyStopState())
    print("错误码:", robot.GetRobotErrorCode())

    ret, joint_before = robot.GetActualJointPosDegree()
    if ret != 0:
        print("读取关节角失败，停止")
        robot.CloseRPC()
        exit()

    print("运动前关节角:", joint_before)
    print(f"开始 J{JOG_AXIS} 点动，方向={JOG_DIR}，目标约 {TARGET_DELTA}°，速度={VEL}%")

    # StartJOG(ref, nb, dir, max_dis, vel, acc)
    # ref=0 表示关节点动
    ret = robot.StartJOG(0, JOG_AXIS, JOG_DIR, TARGET_DELTA, vel=VEL, acc=ACC)
    print("StartJOG返回:", ret)

    if ret != 0:
        print("StartJOG失败，停止")
        robot.CloseRPC()
        exit()

    for i in range(100):
        time.sleep(0.2)

        ret_joint, joint_now = robot.GetActualJointPosDegree()
        if ret_joint != 0:
            print("读取当前关节失败")
            break

        delta = joint_now[JOG_AXIS - 1] - joint_before[JOG_AXIS - 1]

        print(f"[{i}] J1={joint_now[0]:.4f}, delta={delta:.4f}°")

        # 接近目标角度就停止
        if abs(delta) >= TARGET_DELTA * 0.95:
            print("接近目标角度，准备停止")
            break

except KeyboardInterrupt:
    print("\n检测到 Ctrl+C，立即停止点动")

finally:
    try:
        print("StopJOG:", robot.StopJOG(1))
    except Exception as e:
        print("StopJOG失败:", e)
        try:
            print("ImmStopJOG:", robot.ImmStopJOG())
        except Exception as e2:
            print("ImmStopJOG也失败:", e2)

    time.sleep(0.5)

    print("运动后关节角:", robot.GetActualJointPosDegree())
    print("最终错误码:", robot.GetRobotErrorCode())

    robot.CloseRPC()
    print("结束")