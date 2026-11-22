"""094 P4, ours: the lead-brake task as a ScensimEnv (stock: WheeledLab isaaclab-3.0
bench/p4_leadbrake, fef6385; its terms ported one for one, named to their stock function).

The comparable row: the Model 3 spec's articulation (its generated carla-0.9.16 body, the file
stock's car copies its numbers from) on engine B, the control component bypassed and stock's
action law on its joints exactly (CarAction): the rear wheels' drive torque up to the spin
joints' effort limit, the brake as the spin joints' implicit damping toward rest, capped at the
brake fraction of the max brake torque, the steer to both front wheels' Ackermann angles. The
episode is the compiled scenario (leadbrake.xosc), each reset's from the start pool at stock's
distribution, the lead SSv2's default vehicle braking by the storyboard.

Registered as Scensim-LeadBrake-v0 with stock's PPO settings (p4_leadbrake.agent, verbatim)."""
import torch
from isaaclab.utils import configclass

from ..env import ScensimEnv, ScensimEnvCfg
from . import leadbrake as LB


@configclass
class LeadBrakeEnvCfg(ScensimEnvCfg):
    engine: str = "B"
    bypass_component: bool = True
    implicit_effort: tuple = ("spin",)        # stock's spin joints: ImplicitActuatorCfg, 0 and 0
    ground_material: tuple = (1.0, 1.0, "average")    # stock's dry road (its plane's 1.0)
    ground_size: tuple = (4000.0, 4000.0)             # stock's
    decimation: int = 6                       # 20 Hz policy over 120 Hz physics
    episode_length_s: float = 30.0
    action_space: int = 2
    observation_space: int = 9                # ego 4, lead 3, last action 2
    state_space: int = 0
    num_envs: int = 1024
    starts_log: str = ""                      # the start pool's records log (a jsonl), or none
    pool_seed: int = -1                       # the pool's seed; -1: the run's
    # the training headway (133): "record", every episode at its record's h (the default, what
    # seats replay); "stock", stock's training distribution: an episode reset inside a step starts
    # its lead one policy step further on (v dt; Isaac Lab steps stock's lead command after its
    # resets), env.reset()'s at h exactly, as stock's evaluation. Named in P4's table.
    train_headway: str = "record"
    # stock's evaluator's --samples-out file: its episodes replayed as the records, in env order
    # (eval_leadbrake.py --conditions-from); none: the pool's draws
    conditions_from: str = ""
    # the row (133): "joints", the comparable row, stock's CarAction on the joints (the component
    # bypassed); "ecu", the car's own drive unit and ECU (sim_vehicle_ecu's `ev`: the motor's
    # envelope and lag, regen blended with the friction brakes, ABS, TC, ESC, the steer rate),
    # stock's action, [-1, 1]^2 as stock's, read as its Autoware command (ecu_command)
    row: str = "joints"

    def __post_init__(self):
        super().__post_init__()
        self.sim.dt = 1.0 / 120.0
        self.sim.render_interval = self.decimation
        self.sim.device = "cuda:0"
        self.scene.num_envs = self.num_envs
        self.scene.env_spacing = 10.0         # stock's: each env's road its own +x axis
        self.resolve()

    def resolve(self):
        """The task's paths and the pool from this checkout (as MushrDriftRLEnvCfg resolves)."""
        from sim_vehicle_spec import spec as specmod
        root = LB._spec_root()
        sp = specmod.load(root / "vehicles" / f"{LB.SPEC}.yaml")
        self.body = str(root / "generated" / LB.SPEC / LB.BODY)
        self.vehicle = specmod.effective(sp, LB.BODY_NAME).doc    # the body the file is of
        self.catalogs = {"vehicles": str(root / "catalogs" / "vehicles.xosc")}
        self.world_factory = LB.straight_world
        scen = LB.project() / "scenarios"
        self.start_pool = {"distribution": str(scen / "leadbrake_dist.xosc"), "chunk": 10000,
                           "log": self.starts_log}
        if self.pool_seed >= 0:
            self.start_pool["seed"] = int(self.pool_seed)
        if self.conditions_from:
            recs, _ = LB.records_from_samples(self.conditions_from)
            self.start_pool["records"] = recs
            self.start_pool["chunk"] = len(recs)
        LB.check_trigger_geometry(scen / "leadbrake.xosc", LB.straight_world())
        if self.train_headway not in ("record", "stock"):
            raise ValueError(f"train_headway {self.train_headway!r}: record or stock")
        if self.row not in ("joints", "ecu"):
            raise ValueError(f"row {self.row!r}: joints or ecu")
        if self.row == "ecu":
            self.component, self.bypass_component, self.implicit_effort = "ev", False, ()
        else:
            self.component, self.bypass_component, self.implicit_effort = "ideal", True, ("spin",)


class LeadBrakeEnv(ScensimEnv):
    cfg: LeadBrakeEnvCfg

    def __init__(self, cfg, render_mode=None, **kwargs):
        if hasattr(cfg, "resolve"):
            cfg.resolve()
        super().__init__(cfg, render_mode, **kwargs)
        n, dev = self.num_envs, self.device
        self.lead = self.compiled.index("lead")
        self.lead_col = self.compiled.of_role("default").index(self.lead)
        act = self._body_doc["actuation"]
        self.wheel_base, self.tread = float(act["wheel_base"]), float(act["wheel_tread"])
        self.steer_max = float(act["max_steer_angle"])
        self.brake_max = float(act["max_brake_torque"])
        self.drive_max = float(self._body_doc["joints"]["rear_left_spin"]["drive"]["effort_limit"])
        # FL FR RL RR (articulation.CORNERS): the driven axle's (stock's DRIVEN_JOINTS)
        self.driven = torch.tensor([0.0, 0.0, 1.0, 1.0], device=dev)
        # the ECU row's scales, from the spec's body (ecu_scales)
        self.a_drive, self.a_brake = LB.ecu_scales(cfg.vehicle)
        self.raw = torch.zeros(n, 2, device=dev)
        self.proc = torch.zeros(n, 2, device=dev)
        self.s_prev = torch.zeros(n, device=dev)
        self.outcome = {}
        # the lead as the last observation showed it: stock's lead is a CommandTerm, updated after
        # its terminations and rewards (ManagerBasedRLEnv.step), so those read the lead of the
        # step before while the observation reads this step's (243)
        self.lead_seen = None
        self._stepping = False

    def step(self, action):
        self._stepping = True                 # a reset now is an in-training one (train_headway)
        try:
            return super().step(action)
        finally:
            self._stepping = False

    def _draw_starts(self, env_ids, home):
        super()._draw_starts(env_ids, home)
        if self.cfg.train_headway == "stock" and self._stepping:
            c = self.compiled
            it = torch.as_tensor(list(env_ids), dtype=torch.long, device=c.x.device)
            # the straight lane along +x (check_trigger_geometry): x is the lead's s
            c.x[it, self.lead] += c.speed[it, self.lead] * self.step_dt

    # --- the action (stock's CarAction) ---------------------------------------------------------

    def _pre_physics_step(self, actions):
        self.raw = actions.clone()
        self.proc = torch.clamp(actions, -1.0, 1.0)
        if self.cfg.row == "ecu":
            _, _, _, v, _ = self._ego()
            actions = LB.ecu_command(self.proc, v, self.a_drive, self.a_brake, self.steer_max,
                                     self.step_dt)
        super()._pre_physics_step(actions)

    def joint_targets(self, actions):
        lon, steer = self.proc[:, 0], self.proc[:, 1]
        left, right = LB.ackermann(steer * self.steer_max, self.wheel_base, self.tread)
        drive = torch.clamp(lon, min=0.0) * self.drive_max
        spin = drive[:, None] * self.driven
        b = torch.clamp(-lon, min=0.0)[:, None].expand(-1, 4)
        braking = b > 0.0
        damping = torch.where(braking, LB.BRAKE_DAMPING, 0.0)
        limit = torch.where(braking, b * self.brake_max, torch.full_like(b, self.drive_max))
        return torch.stack([left, right], -1), spin, damping, limit

    # --- what the terms read (stock's ego_s_y_yaw, gap, the lead's state) -----------------------

    def _ego(self):
        a = self.scene.articulations["ego"]
        T = lambda p: p.torch if hasattr(p, "torch") else p   # noqa: E731
        d = a.data
        pos = T(d.root_pos_w) - self.scene.env_origins
        q = T(d.root_quat_w)
        x, y, z, w = q.unbind(-1)
        yaw = torch.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
        v = T(d.root_lin_vel_b)[:, 0]
        r = T(d.root_ang_vel_b)[:, 2]
        return pos[:, 0] - LB.EGO_S, pos[:, 1], yaw, v, r     # s from the ego's start, as stock

    def _lead(self):
        """The lead's rear along the route from the ego's start, its speed and acceleration (the
        step's world: BatchRun's observation after the physics)."""
        o = self.run.obs
        x = torch.as_tensor(o["x"][:, self.lead], device=self.device).float()
        v = torch.as_tensor(o["v"][:, self.lead], device=self.device).float()
        a = torch.as_tensor(self.run.vehicles.a[:, self.lead_col], device=self.device).float()
        return x - LB.REAR - LB.EGO_S, v, a

    def gap(self, lead=None):
        s, _, yaw, _, _ = self._ego()
        lead_s = (lead if lead is not None else self._lead())[0]
        return lead_s - (s + LB.FRONT * torch.cos(yaw))

    def _lead_before(self):
        """The lead as stock's terminations and rewards see it: the last observation's."""
        return self.lead_seen if self.lead_seen is not None else self._lead()

    # --- observations (stock's obs_ego, obs_lead, last_action) ----------------------------------

    def _get_observations(self):
        _, y, yaw, v, r = self._ego()
        lead = self._lead()
        _, lv, la = lead
        obs = torch.cat([torch.stack([v, r, y, yaw], 1),
                         torch.stack([self.gap(lead), v - lv, la], 1), self.raw], -1).float()
        self.lead_seen = tuple(t.clone() for t in lead)
        self.extras["scensim"] = self.run.obs
        return {"policy": obs}

    # --- terminations (stock's collided, off_road, route_done, time_out) ------------------------

    def _get_dones(self):
        super()._get_dones()                   # the step's world (BatchRun.after_physics)
        s, y, _, v, _ = self._ego()
        lead = self._lead_before()
        g = self.gap(lead)
        self.gap_before = g
        self.collided = g <= 0.0
        self.off_road = y.abs() > LB.OFF_ROAD
        route_done = s >= LB.ROUTE
        time_out = self.episode_length_buf >= self.max_episode_length    # stock's time_out
        lv = lead[1]
        self.safe = (lv <= 0.0) & (v.abs() < 0.1) & (g >= LB.SAFE_GAP[0]) & (g <= LB.SAFE_GAP[1])
        self.time_out = time_out
        # the evaluator's record of the episodes ending now, before their reset (record_outcome)
        self.outcome = {"safe": self.safe.clone(), "s": s.clone(), "y": y.clone(),
                        "gap": g.clone(), "collided": self.collided.clone(),
                        "off_road": self.off_road.clone(), "route_done": route_done.clone()}
        return self.collided | self.off_road | route_done, time_out

    # --- rewards (stock's carl_reward, infraction, safe_stop: each w f dt) ----------------------

    def _get_rewards(self):
        s, y, _, v, _ = self._ego()
        progress = (s - self.s_prev) / LB.ROUTE
        self.s_prev = s.clone()
        m_speed = 1.0 - torch.clamp((v - LB.SPEED_LIMIT).clamp(min=0.0) / LB.SPEED_LIMIT,
                                    max=1.0)
        m_lane = 1.0 - torch.clamp(y.abs() / LB.LANE_HALF, max=1.0)
        carl = torch.where(self.collided, torch.zeros_like(progress), progress * m_speed * m_lane)
        infraction = (self.collided | self.off_road).float()
        safe_stop = (self.time_out & self.safe).float()
        dt = self.step_dt
        return (1.0 * carl - 1.0 * infraction + 1.0 * safe_stop) * dt

    # --- reset (stock's reset_episode: the pool's record instead of its draws) ------------------

    def _reset_idx(self, env_ids):
        super()._reset_idx(env_ids)
        self.raw[env_ids] = 0.0
        self.proc[env_ids] = 0.0
        self.s_prev[env_ids] = 0.0
