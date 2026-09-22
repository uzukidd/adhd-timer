# Focus Flow

Focus Flow 是一个基于 PySide6 的桌面时间管理工具，用来安排按顺序循环执行的专注任务。

## 功能

- 添加多个任务，并选择高饱和度颜色。
- 任务时长可以分别设置小时、分钟和秒。
- 支持循环任务和单次任务。
- 在任务池与时刻表之间拖动任务，并调整执行顺序。
- 任务按顺序执行；单次任务完成后自动回到任务池。
- 使用始终置顶、可拖动的浮动计时条，支持暂停和跳过。
- 关闭主窗口时隐藏到 Windows 右下角托盘，计时不会停止。
- 左键点击托盘角标打开主 UI。
- 右键点击托盘角标弹出菜单，可以选择“打开主 UI”或“退出”。
- 可以在主 UI 中切换 English 和中文，默认语言为 English。
- 在 Settings 中单独开关浮窗进度条和剩余时间。
- 主 UI 隐藏时，只有最后 30 秒显示秒级倒计时。
- 自动保存任务、时刻表顺序、显示设置和语言选择。

## 环境

项目使用专用的 Miniconda 环境 `adhd-timer`。不要使用 `base` 环境或系统 Python。

```powershell
& "D:\miniconda3\Scripts\conda.exe" create -n adhd-timer python=3.12 pip -y
& "D:\miniconda3\Scripts\conda.exe" run -n adhd-timer python -m pip install pytest "PySide6-Essentials==6.8.2"
```

## 启动

PowerShell：

```powershell
.\scripts\run.bat
```

也可以直接运行：

```powershell
& "D:\miniconda3\Scripts\conda.exe" run -n adhd-timer python -m focus_flow.app
```

Git Bash 或类 Unix shell：

```sh
./scripts/run.sh
```

## 测试

PowerShell：

```powershell
.\scripts\test.bat
```

类 Unix shell：

```sh
./scripts/test.sh
```

应用数据会保存到 Qt 为当前系统提供的应用数据目录中。

英文文档请查看 [README.md](README.md)。
