"""WheeledLab's MuSHR drift task through K2's environment (roadmap 094 P2): stock's
observations, rewards, curriculum, terminations and events (wheeledlab_tasks' drifting/
mushr_drift_env_cfg.py, fork isaaclab-3.0 a35060c, BSD-3-Clause, The Wheeled Lab Project
Developers), ported term by term, on scensim's side of the comparison: the car is the MuSHR
spec on engine B (its body stock's asset, body.asset), the episode is a compiled scenario
(mushr_drift.xosc) whose start is a sample record per episode (the start pool), and the action
goes through the car's control component or, bypassed, straight to the joints as stock's
RCCarRWDAction does (`bypass_component`).

What differs from stock, by name (094 P2's differences table):
- the start: a record per episode, drawn uniform along the oval (stock: 20 reference points
  per run, one picked per reset), with stock's noise;
- the events: Isaac Lab's own terms with stock's parameters on the asset's names, through
  DirectRLEnvCfg.events (stock: ManagerBasedRLEnvCfg.events); the reset event is the pool;
- the ground: Isaac Lab's ground plane with stock's material (stock: a TerrainImporter plane);
- the rewards and terminations: the same functions on the same quantities, summed with the
  step's dt as Isaac Lab's RewardManager does.
"""

import torch

from isaaclab.utils import configclass

from ..env import ScensimEnv, ScensimEnvCfg

# stock's constants (mushr_drift_env_cfg.py)
CORNER_IN_RADIUS = 0.3
CORNER_OUT_RADIUS = 2.0
LINE_RADIUS = 0.8
STRAIGHT = 0.8
SLIP_THRESHOLD = 0.55
MAX_SPEED = 3.0
# stock's action (MushrRWDActionCfg): its own geometry, not the car's (133: kept on this path)
ACTION_SCALE = (3.0, 0.488)
ACTION_WHEEL_RADIUS = 0.05
# stock's observation noise (BlindObsCfg, enable_corruption on in training): std per term
OBS_NOISE = {"pos": 0.1, "euler": 0.1, "lin_vel": 0.5, "ang_vel": 0.4}
# stock's rewards: name -> (initial weight); the curriculum raises three of them
WEIGHTS = {"side_slip": 10.0, "vel": -5.0, "progress": 40.0, "tlgr": 0.0, "turn_energy": 20.0,
           "cross_track": -50.0, "term_pens": -5000.0}
CURRICULUM = {"side_slip": (20.0, 20, 10), "tlgr": (10.0, 20, 5), "term_pens": (-1000.0, 50, 5)}


import isaaclab.envs.mdp as mdp  # noqa: E402
from isaaclab.managers import EventTermCfg as EventTerm  # noqa: E402
from isaaclab.managers import SceneEntityCfg  # noqa: E402


@configclass
class DriftEvents:
    """Stock's DriftEventsRandomCfg without its reset term (the start pool draws the start), on
    the asset's own body and joint names (the asset is stock's USD; our scene calls it ego)."""
    change_wheel_friction = EventTerm(
        func=mdp.randomize_rigid_body_material, mode="startup",
        params={"static_friction_range": (0.3, 0.5), "dynamic_friction_range": (0.3, 0.5),
                "restitution_range": (0.0, 0.0), "num_buckets": 20,
                "asset_cfg": SceneEntityCfg("ego", body_names=".*wheel_link"),
                "make_consistent": True})
    randomize_gains = EventTerm(
        func=mdp.randomize_actuator_gains, mode="startup",
        params={"asset_cfg": SceneEntityCfg("ego", joint_names=[".*back.*throttle"]),
                "damping_distribution_params": (10.0, 50.0), "operation": "abs"})
    push_robots_hf = EventTerm(
        func=mdp.push_by_setting_velocity, mode="interval", interval_range_s=(0.1, 0.4),
        params={"velocity_range": {"x": (-0.1, 0.1), "y": (-0.03, 0.03), "yaw": (-0.3, 0.3)},
                "asset_cfg": SceneEntityCfg("ego")})
    push_robots_lf = EventTerm(
        func=mdp.push_by_setting_velocity, mode="interval", interval_range_s=(0.8, 1.2),
        params={"velocity_range": {"yaw": (-0.6, 0.6)}, "asset_cfg": SceneEntityCfg("ego")})
    add_base_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass, mode="startup",
        params={"asset_cfg": SceneEntityCfg("ego", body_names=["base_link"]),
                "mass_distribution_params": (0.3, 0.5), "operation": "add",
                "distribution": "uniform"})


@configclass
class DriftEnvCfg(ScensimEnvCfg):
    engine: str = "B"
    bypass_component: bool = True
    ground_material: tuple = (1.1, 1.0, "multiply")
    decimation: int = 4
    episode_length_s: float = 5.0
    action_space: int = 2
    observation_space: int = 14
    state_space: int = 0             # none (None does not survive WheeledLab's hydra round trip)
    obs_corruption: bool = True
    randomize: bool = True           # stock's DriftEventsRandomCfg (startup and interval terms)
    # the pass bar's run (scripts/eval_drift.py, as stock's bench/p1/eval_drift.py): off track
    # is counted there, not a termination; no penalty that reads it; fixed reward weights
    terminate_off_track: bool = True
    curriculum: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.sim.dt = 0.005
        self.sim.render_interval = 20
        self.scene.env_spacing = 0.0
        if self.randomize:
            self.events = DriftEvents()


class DriftEnv(ScensimEnv):
    cfg: DriftEnvCfg

    def __init__(self, cfg, render_mode=None, **kwargs):
        from isaaclab.envs.utils.spaces import deserialize_space
        for k in ("observation_space", "action_space", "state_space"):
            v = getattr(cfg, k)
            if isinstance(v, str):            # MushrDriftRLEnvCfg's (WheeledLab's hydra flow)
                setattr(cfg, k, deserialize_space(v))
        if hasattr(cfg, "resolve"):           # the arguments the trainer set (MushrDriftRLEnvCfg)
            cfg.resolve()
        super().__init__(cfg, render_mode, **kwargs)
        if not cfg.bypass_component and getattr(cfg, "vesc_gain_range", ()):
            self._randomize_vesc_gains(cfg.vesc_gain_range)
        self.weights = dict(WEIGHTS)
        self.raw_actions = torch.zeros(self.num_envs, 2, device=self.device)
        self.processed = torch.zeros(self.num_envs, 2, device=self.device)
        self.episode_sums = {k: torch.zeros(self.num_envs, device=self.device) for k in WEIGHTS}
        self.out_of_bounds = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)

    # --- the action (stock's RCCarRWDAction: clip, scale, no reverse) --------------------------

    def _pre_physics_step(self, actions):
        self.raw_actions = actions.clone()
        a = torch.clip(actions, -1.0, 1.0) * torch.tensor(ACTION_SCALE, device=actions.device)
        a[:, 0] = torch.clamp(a[:, 0], min=0.0)
        self.processed = a
        if not self.cfg.bypass_component:
            actions = self._vesc_commands(a)
        super()._pre_physics_step(actions)

    def _randomize_vesc_gains(self, rng_range):
        """Row (a)'s replacement for stock's randomize_gains (a startup term there): each env's
        VESC speed loop kp and ki times one factor U[lo, hi], drawn once from the run's seed."""
        lo, hi = rng_range
        comp = self.run.component
        g = torch.Generator().manual_seed(int(self.cfg.seed or 0))
        f = lo + (hi - lo) * torch.rand(self.num_envs, generator=g, dtype=torch.float64)
        for k in ("speed_kp", "speed_ki"):
            p = comp.p[k]
            comp.p[k] = p * comp.xp.asarray(f.numpy(), comp.xp.float64)
        self.vesc_gain_factor = f

    def _vesc_commands(self, a):
        """Row (a): the action as MuSHR's driver sends it to its VESC (vesc_ackermann's
        ackermann_to_vesc): ERPM = gain v (capped at its speed_max only with vesc_speed_cap),
        servo = gain d + offset within [servo_min, servo_max]. [N, 2] (value, servo)."""
        d = self.cfg.vesc_driver
        erpm = a[:, 0] * d["erpm_per_mps"]
        if self.cfg.vesc_speed_cap:
            erpm = torch.clamp(erpm, -d["speed_max_erpm"], d["speed_max_erpm"])
        servo = torch.clamp(a[:, 1] * d["servo_gain"] + d["servo_offset"], d["servo_min"],
                            d["servo_max"])
        return torch.stack([erpm, servo], -1)

    def joint_targets(self, actions):
        v, d = self.processed[:, 0].double(), self.processed[:, 1].double()
        t = torch.tan(d)
        steer = torch.stack([t, t], -1)
        w = v / ACTION_WHEEL_RADIUS
        z = torch.zeros_like(w)
        spin = torch.stack([z, z, w, w], -1)           # front_left, front_right, rear_l, rear_r
        return steer, spin

    # --- what the terms read (the asset's root, as stock's mdp functions do) -------------------

    def _root(self):
        a = self.scene.articulations["ego"]
        T = lambda p: p.torch if hasattr(p, "torch") else p   # noqa: E731
        d = a.data
        pos = T(d.root_link_pos_w) - self.scene.env_origins
        quat = T(d.root_link_quat_w)
        lin_b = T(d.root_lin_vel_b) if hasattr(d, "root_lin_vel_b") else None
        ang_b = T(d.root_ang_vel_b) if hasattr(d, "root_ang_vel_b") else None
        ang_w = T(d.root_link_ang_vel_w)
        steer = T(d.joint_pos)[:, self.backend.steer_ids]
        return pos, quat, lin_b, ang_b, ang_w, steer

    def _get_observations(self):
        from isaaclab.utils.math import euler_xyz_from_quat
        pos, quat, lin_b, ang_b, _, _ = self._root()
        r, p, y = euler_xyz_from_quat(quat)
        euler = torch.stack([r, p, y], -1)
        terms = [("pos", pos), ("euler", euler), ("lin_vel", lin_b), ("ang_vel", ang_b)]
        out = []
        for name, t in terms:
            t = t.float()
            if self.cfg.obs_corruption:
                t = t + torch.randn_like(t) * OBS_NOISE[name]
            out.append(t)
        out.append(torch.clip(self.raw_actions, -1.0, 1.0).float())
        self.run_obs = self.run.obs
        self.extras["scensim"] = self.run.obs
        return {"policy": torch.cat(out, -1)}

    # --- stock's rewards ----------------------------------------------------------------------

    def _terms(self):
        pos, quat, lin_b, ang_b, ang_w, steer = self._root()
        x, y = pos[:, 0], pos[:, 1]
        speed = torch.norm(lin_b[:, :2], dim=-1)
        on_straights = y.abs() < STRAIGHT
        # cross_track_dist(straight=STRAIGHT, track_radius=LINE_RADIUS, offset=-1, p=1)
        sq = torch.where(on_straights,
                         torch.where(x > 0, (x - LINE_RADIUS) ** 2, (x + LINE_RADIUS) ** 2),
                         torch.where(y > 0,
                                     (torch.sqrt((y - STRAIGHT) ** 2 + x ** 2) - LINE_RADIUS) ** 2,
                                     (torch.sqrt((y + STRAIGHT) ** 2 + x ** 2) - LINE_RADIUS) ** 2))
        cross_track = torch.sqrt(sq) - 1.0
        # side_slip(min 0.25, max SLIP_THRESHOLD, min_vel_x 1.0)
        slip = torch.abs(torch.atan2(lin_b[:, 1], lin_b[:, 0]))
        slip = torch.where((lin_b[:, 0].abs() < 1.0) | (slip > SLIP_THRESHOLD), 0.0, slip)
        slip = torch.where(slip < 0.25, 0.0, slip)
        # turn_left_go_right(ang_vel_thresh 1.0)
        av = torch.clamp(ang_b[:, 2], -1.0, 1.0)
        tlgr = torch.clamp(steer.mean(-1) * av * -1.0, min=0.0)
        return {
            "side_slip": slip,
            "vel": (speed - MAX_SPEED) ** 2 - MAX_SPEED ** 2,
            "progress": ang_w[:, 2],
            "tlgr": tlgr,
            "turn_energy": torch.where(y.abs() > STRAIGHT, speed ** 2, 0.0),
            "cross_track": cross_track,
            "term_pens": self.out_of_bounds.float(),
        }

    def _get_rewards(self):
        terms = self._terms()
        total = torch.zeros(self.num_envs, device=self.device)
        for k, v in terms.items():
            r = self.weights[k] * v.float() * self.step_dt      # as RewardManager: w f dt
            self.episode_sums[k] += r
            total = total + r
        return total

    # --- stock's terminations --------------------------------------------------------------------

    def _get_dones(self):
        super()._get_dones()                   # the step's world (BatchRun.after_physics)
        self.out_of_bounds = self.off_track()
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        if not self.cfg.terminate_off_track:
            return torch.zeros_like(self.out_of_bounds), time_out
        return self.out_of_bounds, time_out

    def off_track(self):
        """Stock's cart_off_track: outside the outer corners' radius or inside the inner's."""
        pos = self._root()[0]
        x, y = pos[:, 0], pos[:, 1]
        st = y.abs() < STRAIGHT

        def outside(r, inner):
            d2 = torch.where(y > 0, (y - STRAIGHT) ** 2 + x ** 2, (y + STRAIGHT) ** 2 + x ** 2)
            return torch.where(st, (x.abs() < r) if inner else (x.abs() > r),
                               (d2 < r * r) if inner else (d2 > r * r))
        return outside(CORNER_OUT_RADIUS, False) | outside(CORNER_IN_RADIUS, True)

    # --- stock's curriculum (increase_reward_weight_over_time, at a reset) -----------------------

    def _reset_idx(self, env_ids):
        super()._reset_idx(env_ids)
        n_ep = self.common_step_counter // self.max_episode_length
        if self.cfg.curriculum and self.common_step_counter % self.max_episode_length == 0:
            for k, (inc, per, most) in CURRICULUM.items():
                if n_ep // per > most:
                    continue
                if (n_ep + 1) % per == 0:
                    self.weights[k] += inc
        self.raw_actions[env_ids] = 0.0
        self.processed[env_ids] = 0.0
        for k in self.episode_sums:
            self.episode_sums[k][env_ids] = 0.0


@configclass
class MushrDriftRLEnvCfg(DriftEnvCfg):
    """The drift task as P2 trains it: this checkout's MuSHR spec (its body WheeledLab's asset,
    under SCENSIM_ASSET_ROOT, a host setting: WheeledLab's source/ directory), its episode and
    start distribution, 1024 envs (stock's). The project settings are this config's fields,
    so train_rl.py takes them as arguments (`env.starts=uniform`):

    - starts: "stock" (20 points a run, then an index and noise per episode) or "uniform"
      (the variant row: the point uniform along the track per episode);
    - starts_log: a jsonl the episodes' records go to ("": none);
    - pool_seed: the start pool's seed (-1: the run's, cfg.seed, the trainer's agent seed);
    - drift_component: "" bypasses the control component (row b), else its name or
      "module:Class" (row a: roboracer_vesc.component:RoboRacerVesc at MuSHR's values,
      vesc_params);
    - vesc_speed_cap: MuSHR's driver speed cap (0.93 m/s) on row (a)'s action: off, named."""
    num_envs: int = 1024
    starts: str = "stock"
    starts_log: str = ""
    pool_seed: int = -1
    drift_component: str = ""
    # row (a)'s: the component's parameter file (relative: the project's), and whether MuSHR's
    # driver speed cap (its speed_max ERPM) applies to the action
    vesc_params: str = "component/mushr_vesc.yaml"
    vesc_speed_cap: bool = False
    # stock's randomize_gains' replacement on row (a): the speed loop's kp and ki times one
    # factor per env, uniform in this range: stock's damping U[10, 50] as a factor of its mean
    # (the same shape, max / min 5); empty: none (randomize off)
    vesc_gain_range: tuple = ()

    def __post_init__(self):
        import os
        import tempfile
        from pathlib import Path

        super().__post_init__()
        from sim_vehicle_spec import articulation as gen, spec as specmod
        sp = specmod.load(Path(__file__).resolve().parents[3] / "sim_vehicle_spec" / "vehicles" /
                          "mushr_nano.yaml")       # the car's one source (sim_vehicle_spec)
        body = Path(tempfile.mkdtemp(prefix="scensim_mushr_")) / "articulation.yaml"
        body.write_text(gen.files(sp, "MushrDriftRLEnvCfg")["articulation.yaml"])
        self.body = str(body)
        self.vehicle = sp.doc
        self.catalogs = {"vehicles": str(sp.path.parent.parent / "catalogs" / "vehicles.xosc")}
        self.asset_root = os.environ.get("SCENSIM_ASSET_ROOT", "")
        self.world_factory = _oval_world
        self.scene.num_envs = self.num_envs
        self.sim.device = "cuda:0"
        self.resolve()
        # WheeledLab's hydra flow updates this config from one whose spaces it serialized, and
        # deserializes them after (replace_strings_with_env_cfg_spaces): ours start serialized
        from isaaclab.envs.utils.spaces import serialize_space
        for k in ("observation_space", "action_space", "state_space"):
            v = getattr(self, k)
            if not isinstance(v, str):
                setattr(self, k, serialize_space(v))

    def resolve(self):
        """The fields into the env's own settings; again at the env's start, after the
        trainer's arguments have set the fields."""
        import os
        for name, arg in RETIRED_ENV.items():
            if name in os.environ:
                raise ValueError(f"{name} is retired: a project setting, pass {arg} to "
                                 "train_rl.py instead")
        scen = _project() / "scenarios"
        if self.starts == "stock":
            self.start_pool = {"distribution": str(scen / "mushr_drift_dist.xosc"),
                               "run_knobs": "scensim_batch.tasks.drift_start:reference_points"}
        elif self.starts == "uniform":
            self.start_pool = {"distribution": str(scen / "mushr_drift_uniform_dist.xosc")}
        else:
            raise ValueError(f"starts={self.starts!r}: stock or uniform")
        self.start_pool.update(chunk=10000, log=self.starts_log)
        if self.pool_seed >= 0:
            self.start_pool["seed"] = int(self.pool_seed)
        self.bypass_component = not self.drift_component
        self.component = self.drift_component or "ideal"
        if ":" in self.component:             # "module:Class": a component not installed as an
            import importlib                  # entry point (the roboracer project's VESC)
            mod, cls = self.component.split(":")
            self.component = getattr(importlib.import_module(mod), cls)
        self.vesc_driver = {}
        if self.drift_component:
            import yaml
            path = _project() / self.vesc_params
            doc = yaml.safe_load(path.read_text())
            self.component_params = dict(doc["params"])
            self.vesc_driver = dict(doc["driver"])
            self.vesc_mode = "speed"
            self.device_resident = True       # the component's torch form, nothing on the host
            # stock's randomize_gains draws its DC motor's gain (damping U[10, 50]); here the
            # VESC is the motor and the joint an effort drive, so its replacement draws the
            # VESC's speed loop gain the same way (DriftEnv._randomize_vesc_gains; 133)
            if getattr(self.events, "randomize_gains", None) is not None:
                self.events.randomize_gains = None
                self.vesc_gain_range = (1.0 / 3.0, 5.0 / 3.0)


RETIRED_ENV = {"SCENSIM_DRIFT_STARTS_UNIFORM": "env.starts=uniform",
               "SCENSIM_DRIFT_STARTS": "env.starts_log=<jsonl>",
               "SCENSIM_DRIFT_POOL_SEED": "env.pool_seed=<n>",
               "SCENSIM_DRIFT_COMPONENT": "env.drift_component=<name>"}


def _project():
    from pathlib import Path
    return Path(__file__).resolve().parents[4] / "scenarios" / "projects" / "mushr_drift"


def _oval_world():
    from ..world_lanelet import LaneletWorld
    return LaneletWorld.from_polylines({1: [[0.8, -0.8], [0.8, 0.8]]}, width=4.0)
