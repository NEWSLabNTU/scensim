"""Issue 135 step 1's alignment check (prediction in docs/issues/135, written first): which
control a tick's snapshot holds, for a control applied just before the tick by a synchronous
batch and by apply_control (async). A CARLA of its own, synchronous at 20 Hz, one vehicle."""
import json
import sys

import carla

PORT, N = int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 400
c = carla.Client("127.0.0.1", PORT)
c.set_timeout(60.0)
w = c.get_world()
old = w.get_settings()
s = w.get_settings()
s.synchronous_mode, s.fixed_delta_seconds = True, 0.05
w.apply_settings(s)
v = None
try:
    bp = w.get_blueprint_library().find("vehicle.tesla.model3")
    v = w.spawn_actor(bp, w.get_map().get_spawn_points()[0])
    w.tick()

    def run(mode):
        out = []
        for k in range(N):
            ctl = carla.VehicleControl(throttle=0.05 + 0.4 * k / N, steer=0.3 if k % 2 else -0.3)
            if mode == "batch":
                r = c.apply_batch_sync([carla.command.ApplyVehicleControl(v.id, ctl)], False)
                assert not r[0].error, r[0].error
            else:
                v.apply_control(ctl)
            frame = w.tick()
            snap = w.get_snapshot()
            got = v.get_control()
            out.append({"k": k, "tick_frame": frame, "snapshot_frame": snap.frame,
                        "sent": [ctl.throttle, ctl.steer], "got": [got.throttle, got.steer]})
        return out

    def same(a, b):
        return all(abs(x - y) < 1e-5 for x, y in zip(a, b))

    report = {}
    for mode in ("batch", "async"):
        rows = run(mode)
        now = sum(same(r["sent"], r["got"]) for r in rows)
        prev = sum(k > 0 and not same(r["sent"], r["got"]) and same(rows[k - 1]["sent"], r["got"])
                   for k, r in enumerate(rows))
        report[mode] = {"ticks": len(rows),
                        "frames_aligned": sum(r["tick_frame"] == r["snapshot_frame"] for r in rows),
                        "holds_this_ticks_control": now, "holds_the_previous": prev,
                        "other": len(rows) - now - prev,
                        "first_mismatches": [r for r in rows if not same(r["sent"], r["got"])][:5]}
    print(json.dumps(report, indent=1))
finally:
    if v is not None:
        v.destroy()
    w.apply_settings(old)
