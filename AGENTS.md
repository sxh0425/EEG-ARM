# Workspace rules

- The real project workspace is the WSL directory `/home/xiaohehe/EEG-ARM`, exposed to Windows as `\\wsl.localhost\Ubuntu-22.04\home\xiaohehe\EEG-ARM`.
- Do not treat `D:\A_EEG_ARM` or another Windows-local directory as this project.
- Run project shell commands through Ubuntu 22.04, for example: `wsl.exe -d Ubuntu-22.04 -- bash -lc "cd /home/xiaohehe/EEG-ARM && <command>"`.
- Interpret paths, permissions, executables, Python environments, and dependencies as Linux/WSL resources unless the user explicitly says otherwise.
- Use `apply_patch` for edits to project files.
- Never execute robot-motion or actuator-changing code. Read-only inspection, parsing, network checks, and robot status queries are allowed. Do not call motion, enable, mode-change, reset-error, or similar state-changing robot APIs unless the user explicitly changes this rule.
- Do not run long-running terminal commands, persistent processes, monitoring loops, training jobs, or robot programs. The user runs those commands personally. Only short, non-invasive query and validation commands may be run by the assistant.
- For FAIRINO behavior and API details, consult the official Chinese documentation at `https://fairino-doc-zhs.readthedocs.io/latest/` instead of guessing.
