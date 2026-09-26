import time

import minimalmodbus
import serial


PORT = (
    "/dev/serial/by-id/"
    "usb-Prolific_Technology_Inc._USB-Serial_Controller_"
    "A_COb114J19-if00-port0"
)
SLAVE_ID = 9


gripper = minimalmodbus.Instrument(
    PORT,
    SLAVE_ID,
    mode=minimalmodbus.MODE_RTU,
)

gripper.serial.baudrate = 115200
gripper.serial.bytesize = 8
gripper.serial.parity = serial.PARITY_NONE
gripper.serial.stopbits = 1
gripper.serial.timeout = 0.3
gripper.clear_buffers_before_each_transaction = True


def read_status():
    registers = gripper.read_registers(
        0x07D0,
        4,
        functioncode=3,
    )

    status_byte = registers[0] & 0xFF
    temperature = registers[3] >> 8
    if temperature >= 128:
        temperature -= 256

    return {
        "enabled": bool(status_byte & 0x01),
        "moving": bool(status_byte & 0x08),
        "state": (status_byte >> 4) & 0x03,
        "object": (status_byte >> 6) & 0x03,
        "fault": registers[1] & 0xFF,
        "position": registers[1] >> 8,
        "speed": registers[2] & 0xFF,
        "current": registers[2] >> 8,
        "voltage": registers[3] & 0xFF,
        "temperature": temperature,
    }


def wait_until_initialized(timeout=15.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        status = read_status()
        print("初始化状态：", status)

        if status["fault"]:
            raise RuntimeError(f"初始化故障：0x{status['fault']:02X}")

        if status["enabled"] and status["state"] == 3:
            return status

        time.sleep(0.2)

    raise TimeoutError("等待夹爪初始化超时")


def initialize():
    # 先复位，再使能。使能过程会产生开合标定动作。
    gripper.write_register(0x03E8, 0x0000, functioncode=6)
    time.sleep(0.3)
    gripper.write_register(0x03E8, 0x0001, functioncode=6)
    wait_until_initialized()


def move(position, speed=32, force=32):
    if not 0 <= position <= 255:
        raise ValueError("position 必须为 0～255")
    if not 0 <= speed <= 255:
        raise ValueError("speed 必须为 0～255")
    if not 0 <= force <= 255:
        raise ValueError("force 必须为 0～255")

    # 0x03E8：使能 + 参数模式 + 前往目标位置
    control = 0x0009

    # 0x03E9 高字节为位置
    position_register = position << 8

    # 0x03EA 高字节为力，低字节为速度
    force_speed_register = (force << 8) | speed

    gripper.write_registers(
        0x03E8,
        [control, position_register, force_speed_register],
    )

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = read_status()
        print("运动状态：", status)

        if status["fault"]:
            raise RuntimeError(f"夹爪故障：0x{status['fault']:02X}")

        if status["state"] == 3 and status["object"] != 0:
            return status

        time.sleep(0.2)

    raise TimeoutError("等待夹爪运动完成超时")


print("当前状态：", read_status())

confirmation = input(
    "确认夹爪整个行程内无人、无线缆、无障碍物，输入 MOVE 继续："
)

if confirmation != "MOVE":
    raise SystemExit("已取消，未发送任何运动命令")

if not read_status()["enabled"]:
    initialize()

# 51 约为从完全张开位置闭合 20%，即约移动 10 mm。
# 使用较低速度和较低力进行第一次测试。
move(position=0, speed=32, force=32)

print("第一次测试完成：", read_status())