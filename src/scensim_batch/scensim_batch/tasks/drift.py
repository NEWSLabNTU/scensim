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


def _events(asset="ego"):
    """Stock's DriftEventsRandomCfg without its reset term (the start pool draws the start),
    on the asset's own body and joint names (the asset is stock's USD)."""
    import isaaclab.envs.mdp as mdp
    from isaaclab.managers import EventTermCfg as EventTerm
    from isaaclab.managers import SceneEntityCfg

    @configclass
    class DriftEvents:
        change_wheel_friction = EventTerm(
            func=mdp.randomize_rigid_body_material, mode="startup",
            params={"static_friction_range": (0.3, 0.5), "dynamic_friction_range": (0.3, 0.5),
                    "restitution_range": (0.0, 0.0), "num_buckets": 20,
                    "asset_cfg": SceneEntityCfg(asset, body_names=".*wheel_link"),
                    "make_consistent": True})
        randomize_gains = EventTerm(
            func=mdp.randomize_actuator_gains, mode="startup",
            params={"asset_cfg": SceneEntityCfg(asset, joint_names=[".*back.*throttle"]),
                    "damping_distribution_params": (10.0, 50.0), "operation": "abs"})
        push_robots_hf = EventTerm(
            func=mdp.push_by_setting_velocity, mode="interval", interval_range_s=(0.1, 0.4),
            params={"velocity_range": {"x": (-0.1, 0.1), "y": (-0.03, 0.03),
                                       "yaw": (-0.3, 0.3)},
                    "asset_cfg": SceneEntityCfg(asset)})
        push_robots_lf = EventTerm(
            func=mdp.push_by_setting_velocity, mode="interval", interval_range_s=(0.8, 1.2),
            params={"velocity_range": {"yaw": (-0.6, 0.6)}, "asset_cfg": SceneEntityCfg(asset)})
        add_base_mass = EventTerm(
            func=mdp.randomize_rigid_body_mass, mode="startup",
            params={"asset_cfg": SceneEntityCfg(asset, body_names=["base_link"]),
                    "mass_distribution_params": (0.3, 0.5), "operation": "add",
                    "distribution": "uniform"})
    return DriftEvents()


@configclass
class DriftEnvCfg(ScensimEnvCfg):
    engine: str = "B"
    bypass_component: bool = True
    ground_material: tuple = (1.1, 1.0, "multiply")
    decimation: int = 4
    episode_length_s: float = 5.0
    action_space: int = 2
    observation_space: int = 14
    obs_corruption: bool = True
    randomize: bool = True           # stock's DriftEventsRandomCfg (startup and interval terms)

    def __post_init__(self):
        super().__post_init__()
        self.sim.dt = 0.005
        self.sim.render_interval = 20
        self.scene.env_spacing = 0.0
        if self.randomize:
            self.events = _events()


class DriftEnv(ScensimEnv):
    cfg: DriftEnvCfg

    def __init__(self, cfg, render_mode=None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)
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
        super()._pre_physics_step(actions)

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
        pos = self._root()[0]
        x, y = pos[:, 0], pos[:, 1]
        st = y.abs() < STRAIGHT

        def outside(r, inner):
            d2 = torch.where(y > 0, (y - STRAIGHT) ** 2 + x ** 2, (y + STRAIGHT) ** 2 + x ** 2)
            return torch.where(st, (x.abs() < r) if inner else (x.abs() > r),
                               (d2 < r * r) if inner else (d2 > r * r))
        self.out_of_bounds = outside(CORNER_OUT_RADIUS, False) | outside(CORNER_IN_RADIUS, True)
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        return self.out_of_bounds, time_out

    # --- stock's curriculum (increase_reward_weight_over_time, at a reset) -----------------------

    def _reset_idx(self, env_ids):
        super()._reset_idx(env_ids)
        n_ep = self.common_step_counter // self.max_episode_length
        if self.common_step_counter % self.max_episode_length == 0:
            for k, (inc, per, most) in CURRICULUM.items():
                if n_ep // per > most:
                    continue
                if (n_ep + 1) % per == 0:
                    self.weights[k] += inc
        self.raw_actions[env_ids] = 0.0
        self.processed[env_ids] = 0.0
        for k in self.episode_sums:
            self.episode_sums[k][env_ids] = 0.0
