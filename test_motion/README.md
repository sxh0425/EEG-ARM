# FR3 状态与模式工具

所有命令都在 WSL / Ubuntu 22.04 中运行：

```bash
cd /home/xiaohehe/EEG-ARM/test_motion
```

## 查看状态（只读）

```bash
python3 show_status.py
python3 show_status.py --watch 1
```

第二条命令每 1 秒刷新一次，按 `Ctrl+C` 退出。内容包括关节角度、TCP 位姿、
自动/手动、拖动、使能、运动/程序、急停、安全停止、碰撞、故障码等状态。

## 设置模式或使能（一令一动）

```bash
# 只切换手动模式
python3 set_state.py --mode manual

# 只切换自动模式
python3 set_state.py --mode auto

# 先切换手动模式，再进入拖动示教；不改变使能状态
python3 set_state.py --mode drag

# 只上使能
python3 set_state.py --enable on

# 只下使能
python3 set_state.py --enable off
```

命令会立即执行，不要求二次确认。`--mode` 与 `--enable` 不能在同一条命令中组合，
避免一个命令改变多个独立状态。可用 `--ip` 覆盖默认地址 `192.168.57.2`。

除 `--mode drag` 会按照官方要求依次切换手动模式、进入拖动示教外，其余命令只调用
一个对应接口，不会隐含退出拖动、改变模式或改变使能。脚本不包含机械臂运动命令。
