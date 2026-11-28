"""A stand-in RoboRacer drive unit: a VESC driving a sensored brushless motor through the
Slash 4x4's spur, centre and axle gears, and a steering servo (scensim roadmap 091 W23).

It is an example of a user's control component (sim_vehicle_ecu's component interface), made so
that the synthetic stand-in for real logs (W23) has parameters to perturb and the fitting tool
(W10) has parameters to recover. It is not a model of any particular car, and scensim does not
ship it: 091 leaves the car's model to its user. Pure: no simulator, no I/O.

It is written once, in array form over N cars (`RoboRacerVescBatch`, the batched form of
sim_vehicle_ecu.batch, scensim 092 S3), and `RoboRacerVesc` is that at one car
(`batch.ScalarOf`): the scalar and the batched car are one code. The arithmetic is elementwise
+ - * /, abs, min/max and where, in the order the scalar form had, so N cars equal N single
cars bit for bit; the wheels' mean is written out, ((w0 + w1) + w2) + w3, not `sum()` (Python
3.12's float `sum()` is compensated; roboracer-indoor-twin.md 2.6).

Commands are the ``vesc`` ones (``VescCommand``):
- `speed` (ERPM): the VESC's speed loop. It is a PI on the ERPM error, its output a motor
  current within the limits.
- `current` (A): the motor current, within the limits.
- `brake` (A): a braking current, as a brake torque on every wheel.
- `duty` (-1 to 1): the motor's voltage over the battery's, against its back-EMF through its
  resistance.
- `position`: not modelled; it gives no current.

A motor command older than `timeout` releases the motor (a real VESC's timeout). The servo
position becomes the bicycle tire angle through the driver's gain and offset (f1tenth's
`steering_angle_to_servo_gain`, `_offset`), and the servo moves at most `servo_rate` rad/s.
Commands take effect `latency` seconds after they arrive. `latency_jitter` (s, the standard
deviation) draws each command's own extra delay from the seed. That is a perturbation the
fitting tool's model holds as a single latency, so W23 can see how a fit degrades on it.

Each car keeps its own queue of pending commands (a ring buffer per car, drained in arrival
order) and its own `random.Random(seed)`, drawn in the same order as a single car draws, so car
i of a batch is the single car with seed i.

The motor's speed is the wheels' mean, as a sensored VESC sees it through the differentials.
The telemetry is what `sensors/core` carries: `erpm`, `current_motor`, `duty`, `voltage_input`
and `tachometer`. The reported `erpm` is the motor's times `erpm_sign`: how the motor is wired
to the VESC, which decides the sign the VESC reports while commanded positive ERPM drives the
car forward. f1tenth_system's `humble-devel` reads a VESC that reports forward as negative (its
vesc_to_odom negates `state.speed`), `jazzy-devel` one that reports it as positive (scensim
issue 098); the commands' sign never changes.
"""
import random

import numpy as np

from sim_vehicle_ecu import batch as ecu_batch
from sim_vehicle_ecu import xp as xpmod
from sim_vehicle_ecu.signals import MOTOR_MODES

# The defaults: a 1/10 car on f1tenth_system's humble-devel `vesc.yaml` and a 3500 kV motor
DEFAULTS = {
    "erpm_per_mps": 4614.0,         # f1tenth's speed_to_erpm_gain: ERPM per m/s at the wheels
    "erpm_per_motor_rad_s": 9.549,  # ERPM per rad/s of the motor: pole pairs x 60 / (2 pi), 1 pair
    "kt": 0.00273,                  # N m per A at the motor: 60 / (2 pi kV), kV 3500
    "current_max": 40.0,            # A, the motor current's limit, both ways
    "brake_max": 40.0,              # A, the braking current's limit
    "speed_kp": 0.0045,             # A per ERPM of error
    "speed_ki": 0.012,              # A per ERPM s
    "resistance": 0.03,             # ohm, for duty commands
    "servo_gain": -1.2135,          # servo position per rad of tire angle
    "servo_offset": 0.5304,         # servo position at a straight tire
    "servo_rate": 5.0,              # rad/s at the wheels
    "erpm_sign": 1.0,               # the reported ERPM's sign: the motor's wiring (+1 or -1)
    "latency": 0.02,                # s, from the command's arrival to its effect
    "latency_jitter": 0.0,          # s, standard deviation of each command's extra delay
    "timeout": 0.5,                 # s, a motor command older than this releases the motor
}
QUEUE = 256   # pending commands per car: latency / dt of them, with room
SPEED, CURRENT, BRAKE, DUTY = (MOTOR_MODES.index(m) for m in ("speed", "current", "brake", "duty"))
NONE = -1


class RoboRacerVescBatch:
    """The batch, written once over an array namespace (`xp`, sim_vehicle_ecu.xp: numpy, the
    reference, or torch on any device; scensim 092 K2.2c): the same elementwise arithmetic in
    the same order in both, so a torch batch on a GPU equals the numpy one bit for bit, and its
    per-step path brings nothing to the host (no `any`, no index lists): the pending commands
    drain in one pass (`_due`), and a queue overflow, which numpy raises at once, is a flag on
    a device (`check`, run at each reset). The latency jitter's draws are each car's own
    `random.Random`, on the host, as the single car's; only a car with jitter draws."""
    commands = "vesc"
    driven = (True,) * 4  # the Slash 4x4's; an instance's from its spec's drive_axle
    truth = ()
    # the battery's voltage, measured before the run: the session's, not a param (scensim 091
    # W12), given at construction as session={"battery_v": [N]}
    session = ("battery_v",)
    array_api, dtype = ("numpy", "torch"), np.float64
    per_slot_params = True   # every param an array [N]: a fit's candidates, a varied car

    def __init__(self, vehicle: dict, params: dict, seeds, xp=None, session=None):
        if "battery" in params:
            raise ValueError("roboracer_vesc: param battery is retired: the battery's voltage is "
                             "the session's (scensim 091 W12), session.battery.voltage_v in the "
                             "run's session record")
        if not session or "battery_v" not in session:
            raise ValueError("roboracer_vesc: no battery_v: construct it with "
                             "session={'battery_v': V} (sim_vehicle_ecu load and load_batch do, "
                             "from the run's session record)")
        unknown = set(params) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown params {sorted(unknown)}; known: {sorted(DEFAULTS)}")
        xp = self.xp = xp or xpmod.namespace("numpy")
        n = len(seeds)
        # each param per car, [N]: a number (one car's, or every car's) or an array [N]
        host = {k: np.broadcast_to(np.asarray(params.get(k, d), dtype=np.float64), (n,)).copy()
                for k, d in DEFAULTS.items()}
        host["battery"] = np.broadcast_to(np.asarray(session["battery_v"], dtype=np.float64),
                                          (n,)).copy()   # V, per car: its run's session's
        self.p = {k: xp.asarray(v, xp.float64) for k, v in host.items()}
        self.jitter = host["latency_jitter"] > 0          # host: which cars draw
        g = vehicle["geometry"]
        self.r = float(g["wheel_radius"])
        # the wheels the motor drives: the spec's powertrain.drive_axle (the Slash 4x4: all; a
        # 2WD car, the MuSHR of scensim 094 P2: rear); the motor sees their mean, its torque
        # splits over them
        axle = (vehicle.get("powertrain") or {}).get("drive_axle", "all")
        if axle not in ("all", "rear", "front"):
            raise ValueError(f"roboracer_vesc: powertrain.drive_axle {axle!r}: all, rear or front")
        self.axle = axle
        self.driven = {"all": (True,) * 4, "rear": (False, False, True, True),
                       "front": (True, True, False, False)}[axle]
        self.max_steer = float(g["max_steer_angle"])
        # the gearing: wheel rad/s per motor rad/s, from the ERPM per m/s
        motor_rad_s_per_mps = self.p["erpm_per_mps"] / self.p["erpm_per_motor_rad_s"]
        self.gear = motor_rad_s_per_mps * self.r  # motor rad/s per wheel rad/s
        self.seeds = [int(s) for s in seeds]
        n, q = len(self.seeds), QUEUE
        self.n = n
        self.rngs = [random.Random(s) for s in self.seeds]
        self.rows = xp.arange(n)
        self.ring = xp.arange(q)
        # the queue: (effective time, arrival, command) per car, as a ring buffer
        self.q_eff, self.q_arr = xp.zeros((n, q)), xp.zeros((n, q))
        self.q_motor = xp.full((n, q), NONE, xp.int64)
        self.q_value, self.q_servo = xp.zeros((n, q)), xp.full((n, q), xp.nan)
        self.head, self.size = xp.zeros(n, xp.int64), xp.zeros(n, xp.int64)
        self.motor, self.last_motor = xp.full(n, NONE, xp.int64), xp.full(n, NONE, xp.int64)
        self.has_last = xp.zeros(n, xp.bool)
        self.overflow = xp.zeros(n, xp.bool)
        for name in ("t", "integral", "tire_angle", "tachometer", "current", "value",
                     "last_value", "last_age"):
            setattr(self, name, xp.zeros(n))
        for name in ("servo", "arrived", "last_servo"):
            setattr(self, name, xp.full(n, xp.nan))
        self.debug = {}

    def check(self):
        """Raise for a car whose queue overflowed (a torch batch keeps it as a flag)."""
        if self.xp.any(self.overflow):
            raise RuntimeError(f"roboracer_vesc: more than {QUEUE} commands pending in a car")

    def reset_batch(self, mask):
        xp = self.xp
        self.check()
        m = xp.asarray(mask, xp.bool)
        for name in ("t", "integral", "tire_angle", "tachometer", "current", "value",
                     "last_value", "last_age"):
            setattr(self, name, xp.where(m, 0.0, getattr(self, name)))
        for name in ("servo", "arrived", "last_servo"):
            setattr(self, name, xp.where(m, xp.nan, getattr(self, name)))
        self.motor = xp.where(m, NONE, self.motor)
        self.last_motor = xp.where(m, NONE, self.last_motor)
        self.has_last = xp.where(m, False, self.has_last)
        self.head, self.size = xp.where(m, 0, self.head), xp.where(m, 0, self.size)
        for i in np.flatnonzero(np.asarray(xp.to_host(m), bool)):
            self.rngs[i] = random.Random(self.seeds[i])

    # --- commands ------------------------------------------------------------------------

    def _arrive(self, c):
        """Commands the vehicle interface hands over, queued until their latency has passed. A
        command is a new one when its motor command or servo position changed, or its age fell
        (a new message with the same values)."""
        xp = self.xp
        valid = c.get("valid")
        valid = xp.ones(self.n, xp.bool) if valid is None else xp.asarray(valid, xp.bool)
        motor, value = xp.asarray(c["motor"], xp.int64), xp.asarray(c["value"], xp.float64)
        servo, age = xp.asarray(c["servo"], xp.float64), xp.asarray(c["age"], xp.float64)
        same_servo = (servo == self.last_servo) | (xp.isnan(servo) & xp.isnan(self.last_servo))
        same = (self.has_last & (motor == self.last_motor) & (value == self.last_value)
                & same_servo & (age >= self.last_age))
        self.last_motor = xp.where(valid, motor, self.last_motor)
        self.last_value = xp.where(valid, value, self.last_value)
        self.last_servo = xp.where(valid, servo, self.last_servo)
        self.last_age = xp.where(valid, age, self.last_age)
        self.has_last = self.has_last | valid
        new = valid & ~same
        arrived = self.t - xp.where(xp.isinf(age), 0.0, age)
        delay = xp.copy(self.p["latency"])
        if self.jitter.any():   # each car's own generator, in its order (host: its draws)
            new_h = np.asarray(xp.to_host(new), bool)
            lat = np.asarray(xp.to_host(self.p["latency"]))
            jit = np.asarray(xp.to_host(self.p["latency_jitter"]))
            d = np.asarray(xp.to_host(delay)).copy()
            for i in np.flatnonzero(new_h & self.jitter):
                d[i] = max(0.0, float(lat[i]) + self.rngs[i].gauss(0.0, float(jit[i])))
            delay = xp.asarray(d, xp.float64)
        over = new & (self.size >= QUEUE)
        if xp.name == "numpy":
            if xp.any(over):
                raise RuntimeError(f"roboracer_vesc: more than {QUEUE} commands pending in a car")
        else:
            self.overflow = self.overflow | over
        new = new & ~over
        slot = (self.head + self.size) % QUEUE
        rows = self.rows
        for q, v in ((self.q_eff, arrived + delay), (self.q_arr, arrived),
                     (self.q_motor, motor), (self.q_value, value), (self.q_servo, servo)):
            q[rows, slot] = xp.where(new, v, q[rows, slot])
        self.size = self.size + xp.astype(new, xp.int64)

    def _due(self):
        """The pending commands whose time has come, in arrival order: a car's ring from its
        head, the prefix of due ones taken at once (each overrides the one before, so the last
        due is the car's command), in one pass with no host round trip."""
        xp = self.xp
        order = (self.head[:, None] + self.ring[None, :]) % QUEUE              # [N, Q]
        pending = self.ring[None, :] < self.size[:, None]
        rows = self.rows[:, None]
        due = pending & (self.q_eff[rows, order] <= self.t[:, None] + 1e-12)
        k = _prefix_count(xp, due)                                             # [N]
        some = k > 0
        last = (self.head + xp.maximum(k - 1, 0)) % QUEUE
        r = self.rows
        self.arrived = xp.where(some, self.q_arr[r, last], self.arrived)
        self.motor = xp.where(some, self.q_motor[r, last], self.motor)
        self.value = xp.where(some, self.q_value[r, last], self.value)
        self.servo = xp.where(some, self.q_servo[r, last], self.servo)
        self.head = (self.head + k) % QUEUE
        self.size = self.size - k

    # --- the step ------------------------------------------------------------------------

    def step_batch(self, commands, sensors, dt):
        xp, p = self.xp, self.p
        self.t = self.t + dt
        self._arrive(commands)
        self._due()
        valid = xp.asarray(sensors["valid"], xp.bool)
        w = xp.where(valid[:, None], xp.asarray(sensors["wheel_speeds"], xp.float64), 0.0)
        if self.axle == "all":
            wheel = (((w[:, 0] + w[:, 1]) + w[:, 2]) + w[:, 3]) / 4.0  # rad/s, written out (2.6)
        elif self.axle == "rear":
            wheel = (w[:, 2] + w[:, 3]) / 2.0
        else:
            wheel = (w[:, 0] + w[:, 1]) / 2.0
        motor = wheel * self.gear  # rad/s
        erpm = motor * p["erpm_per_motor_rad_s"]
        mode = self.motor
        age = xp.where(mode != NONE, self.t - self.arrived, xp.inf)
        released = (mode == NONE) | (age > p["timeout"])
        zero = xp.zeros(self.n)
        # the speed loop
        err = self.value - erpm
        speed = ~released & (mode == SPEED)
        integral = xp.where(speed, self.integral + err * dt, self.integral)
        # anti-windup: the integral holds what keeps the output within the limit
        imax = p["current_max"] / xp.maximum(p["speed_ki"], 1e-12)
        integral = xp.where(speed, xp.maximum(-imax, xp.minimum(imax, integral)), integral)
        self.integral = xp.where(released, 0.0, integral)
        emf = motor * p["kt"]  # V: the back-EMF, kt w
        current = xp.where(speed, p["speed_kp"] * err + p["speed_ki"] * self.integral, zero)
        current = xp.where(~released & (mode == CURRENT), self.value, current)
        current = xp.where(~released & (mode == DUTY),
                           (self.value * p["battery"] - emf) / p["resistance"], current)
        brake_current = xp.where(~released & (mode == BRAKE),
                                 xp.minimum(xp.abs(self.value), p["brake_max"]), zero)
        current = xp.maximum(-p["current_max"], xp.minimum(p["current_max"], current))
        self.current = current
        torque = current * p["kt"] * self.gear  # N m at the wheels, all four
        brake_torque = brake_current * p["kt"] * self.gear
        if self.axle == "all":
            drive = xp.repeat_cols(torque / 4.0, 4)
            brake = xp.repeat_cols(brake_torque / 4.0, 4)
        else:   # the motor's torque, and its braking, on the driven axle's two wheels only
            on = xp.asarray([1.0 if d else 0.0 for d in self.driven], xp.float64)[None, :]
            drive = xp.repeat_cols(torque / 2.0, 4) * on
            brake = xp.repeat_cols(brake_torque / 2.0, 4) * on
        # the servo
        has = ~xp.isnan(self.servo)
        target = (self.servo - p["servo_offset"]) / p["servo_gain"]
        target = xp.maximum(-self.max_steer, xp.minimum(self.max_steer, target))
        step = p["servo_rate"] * dt
        move = xp.maximum(-step, xp.minimum(step, target - self.tire_angle))
        self.tire_angle = xp.where(has, self.tire_angle + move, self.tire_angle)
        self.tachometer = self.tachometer + xp.abs(erpm) * dt / 60.0
        duty = (motor * p["kt"] + current * p["resistance"]) / p["battery"]
        telemetry = {"erpm": p["erpm_sign"] * erpm, "current_motor": current,
                     "duty": xp.maximum(-1.0, xp.minimum(1.0, duty)),
                     "voltage_input": xp.copy(p["battery"]),
                     "tachometer": xp.astype(xp.floor(self.tachometer), xp.int64)}
        self.debug = {"erpm": erpm, "current": current, "brake_current": brake_current,
                      "mode": mode}
        return {"drive": drive, "brake": brake, "tire_angle": xp.copy(self.tire_angle),
                "telemetry": telemetry}


def _prefix_count(xp, due):
    """Per row, how many leading entries are true: the cumulative product's sum, in integers
    (exact)."""
    if xp.name == "numpy":
        return np.cumprod(due.astype(np.int64), axis=1).sum(axis=1)
    return xp.torch.cumprod(due.to(xp.int64), dim=1).sum(dim=1)


class RoboRacerVesc(ecu_batch.ScalarOf):
    """The single car: the batch at one slot. The constructor is (car, params, seed), as
    before; `p`, `gear`, `r` and `debug` read the one car's, as floats."""
    batch = RoboRacerVescBatch

    @property
    def p(self):
        return {k: float(v[0]) for k, v in self._b.p.items()}

    @property
    def gear(self):
        return float(self._b.gear[0])

    @property
    def r(self):
        return self._b.r

    @property
    def debug(self):
        d = self._b.debug
        if not d:
            return {}
        m = int(d["mode"][0])
        return {"erpm": float(d["erpm"][0]), "current": float(d["current"][0]),
                "brake_current": float(d["brake_current"][0]),
                "mode": None if m == NONE else MOTOR_MODES[m]}
