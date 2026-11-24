# 156: a pytest that has initialised rclpy survives SIGTERM

**Status:** open, a record (241; filed by 133); not fixed. **Severity:** low: test runs only. After a
test has called `rclpy.init()` in the pytest process, a SIGTERM to that process does not end it,
so a gate or script that stops its tests by SIGTERM leaves the pytest running, orphaned once its
parent has gone, until it is killed with SIGKILL.
**Found:** 2026-11-25, scensim 241, stopping a gate of issue 153 by its process group's SIGTERM:
the pytest of the `scensim_agent` and relay group stayed, its parent gone; a side run of the same
group did the same.

## What happens

`rclpy.init()` installs rclpy's own handlers for SIGINT and SIGTERM unless told not to
(`signal_handler_options`). Its SIGTERM handler shuts the rclpy context down and does not end the
process. It is installed below Python: `signal.getsignal(signal.SIGTERM)` still says `SIG_DFL`,
while `/proc/<pid>/status` shows SIGTERM caught (`SigCgt` includes signal 15; `SigIgn` only 13
and 25 for the stopped gate's pytest).

`test_simple_pilot_ros.py`, `test_ros_adapter.py` and `test_autoware_rtc_api.py` call
`rclpy.init()` in the pytest process. From then on, the run survives SIGTERM.

Shown on 241 (Humble, `ROS_LOCALHOST_ONLY=1`):

```
python3 -c 'import os, signal, time, rclpy
rclpy.init()
os.kill(os.getpid(), signal.SIGTERM); time.sleep(1)
print("alive 1 s after SIGTERM; context ok:", rclpy.ok())'
```

prints `alive 1 s after SIGTERM; context ok: False` and exits 0. The same with
`rclpy.init(signal_handler_options=SignalHandlerOptions.NO)` is ended by the SIGTERM (exit 143).
`scensim_agent`'s vehicle agent already passes `SignalHandlerOptions.NO` for this reason
(`adapters/vehicle_agent.py`).

## What a fix would be (not done)

The tests pass `signal_handler_options=SignalHandlerOptions.NO` to `rclpy.init()`, so a SIGTERM
ends the run as it ends any other test. Until then, a script that stops a test run follows its
SIGTERM with SIGKILL after a grace, as `stack.stop_processes` and t3's `stop_group` do.
