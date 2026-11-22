"""The batch as an Isaac Lab environment (roadmap 092 K2.2; batch-executor.md section 1): a
DirectRLEnv over N slots of one compiled scenario, each slot one of its sample records, the
ego through its vectorised control component on an engine backend, SSv2's default vehicles
around it. Rewards and terminations are the user's: subclass and override `_get_rewards` and
`_get_dones`; the observation and `extras["scensim"]` carry what they need.

    cfg = ScensimEnvCfg(scenario="cs2.xosc", records=records, world_factory=..., rig=rig,
                        component="roboracer_vesc", ...)
    env = ScensimEnv(cfg)

Isaac Lab owns the physics loop: before each physics step `_apply_action` reads the cars of the
step before (`sample`) and actuates them through the component (`BatchRun.before_physics`);
after the last, `_get_observations` reads them and moves the NPCs (`after_physics`). Isaac Lab
v3.0.0-EA (scripts/isaaclab_overlay.sh). Not exercised yet on 139's GPU: K2.2's smoke.
"""
import torch

from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils import configclass

from . import compile as compilemod
from . import core

B_SPAWN_Z = 0.02    # m: engine B's cars spawn this far up and settle on their springs
# the action, per command type, as the component reads it (S3's batch commands)
ACTIONS = {"autoware": ("acceleration", "velocity", "tire_angle"),
           "ackermann": ("speed", "acceleration", "steering_angle"),
           "vesc": ("value", "servo")}


@configclass
class ScensimEnvCfg(DirectRLEnvCfg):
    scenario: str = ""
    records: list = []
    world_factory: object = None     # callable() -> the world adapter (lane_pose, route, speed_limit)
    rig: object = None               # aib's rig: the car
    component: str = "ideal"         # sim_vehicle_ecu component name (vectorised, S3)
    component_params: object = None  # one dict, or a list of N (per slot)
    vehicle: dict = {}               # the spec document the component is built for
    provides: tuple = ()             # the verdict's conditions this env meets
    vesc_mode: str = "speed"         # a vesc component's motor command mode
    allow_loop: bool = False         # accept a LoopBatch component (checks only, never a bench)
    start_frames: int = 0            # a seats run's S, for its scenario time (K2.4's replay)
    # the ego's actions before the scenario's time (each [N, len(ACTIONS[kind])], one env
    # step each, physics substeps and all), run at every reset of all slots before the first
    # observation, SSv2's vehicles held and the storyboard idle: a seats ego's frames before
    # startNpcLogic (092 K2.4). For agreement runs only: a partial reset (a training env's
    # per-slot time-out or termination) cannot pre-roll, and is refused while this is set
    ego_preroll: list = None
    # samples of SSv2's spline per default vehicle's 300 m route (BatchRun's `points`)
    route_points: int = 121           # 2.5 m apart: K2.4's lead within 3 cm (61: 9 cm, 301: no better)
    # the engine (batch-executor.md section 5): "A", aib's PhysX vehicle (PhysX's CPU pipeline,
    # the sim device "cpu"); "B", the articulation car from `body` (sim_vehicle_spec's
    # articulation_<body>.yaml), which runs on either pipeline
    engine: str = "A"
    body: str = ""
    # where a body's asset lives (a spec's body.asset, 094 P2): its usd is under this root, and
    # engine B loads it (its sha256 checked) instead of the generated body. A host setting
    asset_root: str = ""
    # every episode's start a sample record of its own (094 P2; start_pool.StartPool): a dict
    # {distribution: <ParameterValueDistribution xosc>, seed: int, chunk: int (records a refill
    # draws), log: <jsonl path or "">}. The records then come from the pool (`records` is
    # ignored), each reset takes the next unused ones, and the log names each (slot, episode,
    # record id). Only Init is drawn again: a storyboard reading a sampled parameter is refused
    start_pool: dict = {}            # (empty: none; a None default would not survive hydra)
    # the action straight to the joints, the control component bypassed (094 P2's row b, as
    # stock): a subclass's joint_targets(actions) gives (steer [N, 2], spin [N, 4]); engine B
    bypass_component: bool = False
    # the ground's material: (static, dynamic, combine) or None (Isaac Lab's default plane)
    ground_material: tuple = ()
    # B on a GPU sim: BatchRun, the car model and the component on that device, nothing copied
    # to the host per step (092 K2.2c); the component must have a torch form (array_api)
    device_resident: bool = False
    decimation: int = 4
    episode_length_s: float = 30.0
    # backend A's PhysX vehicles need PhysX's CPU pipeline: the direct-GPU one refuses their
    # constraints and the CPU velocity setters (as aib's runner, which uses the CPU). Scene
    # queries on: a PhysX vehicle finds the ground by raycasting each wheel, and Isaac Lab turns
    # them off by default; without them every wheel was off the ground (K2.2's env smoke: the
    # steer and the wheel spin reached PhysX, the tire force stayed 0, every ego coasted to
    # rest on its body). Fabric stays Isaac Lab's default: on and off measured the same.
    sim: SimulationCfg = SimulationCfg(dt=1 / 240, device="cpu",
                                       enable_scene_query_support=True)
    scene: InteractiveSceneCfg = InteractiveSceneCfg(num_envs=1, env_spacing=200.0,
                                                     replicate_physics=False)
    action_space: int = 3
    observation_space: int = 8


class ScensimEnv(DirectRLEnv):
    cfg: ScensimEnvCfg

    def __init__(self, cfg: ScensimEnvCfg, render_mode=None, **kwargs):
        n = len(cfg.records) if not cfg.start_pool else cfg.scene.num_envs
        if n != cfg.scene.num_envs:
            raise ValueError(f"{n} records for {cfg.scene.num_envs} environments: one per slot")
        if cfg.engine == "B":
            # Isaac Lab 3.0 builds and clones a scene's assets from its config: the body's
            # articulation is declared there before the scene exists
            import os
            import tempfile

            from . import articulation as art
            self._body_doc = art.load_body(cfg.body)
            if self._body_doc.get("asset"):
                usd = art.asset_usd(self._body_doc, cfg.asset_root)
            else:
                usd = os.path.join(tempfile.mkdtemp(prefix="scensim_body_"),
                                   f"{self._body_doc['name']}.usda")
                art.write_usd(self._body_doc, usd)
            cfg.scene.ego = art.articulation_cfg(self._body_doc, usd, z=self._spawn_z())
        super().__init__(cfg, render_mode, **kwargs)

    # --- the scene ----------------------------------------------------------------------------

    def _setup_scene(self):
        import omni.physx
        import omni.usd
        from isaaclab.sim.spawners.from_files import GroundPlaneCfg, spawn_ground_plane
        from sim_vehicle_ecu import batch as ecu_batch

        from .physx_vehicle import PhysxVehicleBackend

        cfg = self.cfg
        g = GroundPlaneCfg()
        if cfg.ground_material:
            import isaaclab.sim as sim_utils
            st, dy, comb = cfg.ground_material
            g = GroundPlaneCfg(physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=st, dynamic_friction=dy, friction_combine_mode=comb,
                restitution_combine_mode=comb))
        spawn_ground_plane("/World/ground", g)
        world = cfg.world_factory()
        self.pool, self._episodes, self._start_log = None, None, None
        if cfg.start_pool:
            from .start_pool import StartPool
            sp = dict(cfg.start_pool)
            dev = cfg.sim.device if cfg.device_resident else "cpu"
            # a run-level draw (sp["run_knobs"], "module:function" of the run's seed): world
            # knobs every record of the run reads, as stock's drift run fixes its 20 points
            seed = int(sp["seed"]) if "seed" in sp else int(cfg.seed or 0)   # the run's, else
            knobs = {}
            if sp.get("run_knobs"):
                import importlib
                mod, fn = sp["run_knobs"].split(":")
                knobs = getattr(importlib.import_module(mod), fn)(seed)
            self.pool = StartPool(sp["distribution"], world, seed=seed,
                                  chunk=int(sp.get("chunk", 10000)), device=dev,
                                  provides=cfg.provides, knobs=knobs)
            n = cfg.scene.num_envs
            while len(self.pool.records) < n:
                self.pool.refill()
            # the first reset takes rows 0..n-1: the scenario compiles on those records
            cfg.records = [dict(r) for r in self.pool.records[:n]]
            self.cfg.scenario = str(self.pool.scenario)
            self._episodes = [0] * n
            path = sp.get("log") or ""
            self._start_log = open(path, "a") if path else None
            self.start_log = []
            import json
            run = {"run": {"seed": seed, "knobs": knobs,
                           "distribution": str(sp["distribution"]),
                           "run_knobs": sp.get("run_knobs") or None}}
            self.start_log.append(run)
            if self._start_log is not None:
                self._start_log.write(json.dumps(run) + "\n")
        if cfg.engine not in ("A", "B"):
            raise ValueError(f"engine {cfg.engine!r}: A or B")
        dev = None
        if cfg.device_resident:
            if cfg.engine != "B" or str(cfg.sim.device) == "cpu":
                raise ValueError("device_resident needs engine B on a GPU sim (sim.device "
                                 "cuda): engine A runs on PhysX's CPU pipeline")
            dev = torch.device(cfg.sim.device)
        with core._OnDevice(dev):
            self.compiled = compilemod.compile_scenario(cfg.scenario, cfg.records, world,
                                                        provides=cfg.provides,
                                                        device=dev or "cpu")
        n = self.compiled.n
        seeds = [int(s or 0) for s in self.compiled.seeds]
        component = ecu_batch.load_batch(cfg.component, cfg.vehicle, cfg.component_params, seeds,
                                         array_api="torch" if dev is not None else "numpy",
                                         device=dev)
        self.kind = component.commands
        self.resident = dev
        if cfg.engine == "A":
            self.backend = PhysxVehicleBackend(None, omni.usd.get_context().get_stage(),
                                               omni.physx.get_physx_interface(), cfg.rig, n,
                                               origins=self.scene.env_origins.cpu().numpy())
        else:
            self.backend = self._engine_b(n, dev is not None)
        self.run = core.BatchRun(self.compiled, world, self.backend, component,
                                 points=cfg.route_points,
                                 # bypassed, the component never steps: its form is moot
                                 allow_loop=cfg.allow_loop or cfg.bypass_component,
                                 start_frames=cfg.start_frames,
                                 step_time=self.step_dt if cfg.start_frames else None,
                                 device=dev)
        self.commands = None
        self.stepped = False
        self.obs = None

    def _engine_b(self, n, resident):
        """Engine B: the body's articulation (the scene's `ego`, one per env); its backend
        built on first use, once the sim has started and the joints exist."""
        from . import articulation as art
        asset = self.scene.articulations["ego"]
        doc = self._body_doc
        return _LazyB(lambda: art.ArticulationBackend(asset, doc, self.scene.env_origins,
                                                      sim=None, z=self._spawn_z(),
                                                      resident=resident))

    def _spawn_z(self):
        # an asset spawns where its author put it (stock's MuSHR: at 0); a generated body a
        # little up, to settle on its springs
        return 0.0 if self._body_doc.get("asset") else B_SPAWN_Z

    # --- the step -----------------------------------------------------------------------------

    def _pre_physics_step(self, actions: torch.Tensor):
        """The policy's actions as the component's commands (ACTIONS[kind], in order): host
        arrays, or on a device-resident env tensors on its device."""
        if self.cfg.bypass_component:
            self.joint_targets_now = self.joint_targets(actions)
            return
        if self.resident is not None:
            self.commands = self._commands_on_device(actions)
            return
        a = actions.detach().to("cpu", torch.float64).numpy()
        n = a.shape[0]
        import numpy as np
        fields = ACTIONS[self.kind]
        c = {f: a[:, i].copy() for i, f in enumerate(fields)}
        c["valid"] = np.ones(n, bool)
        if self.kind == "autoware":
            c["gear"] = np.full(n, 2, dtype=np.int64)   # drive
        elif self.kind == "ackermann":
            for f in ("jerk", "steering_angle_velocity", "age"):
                c[f] = np.zeros(n)
        elif self.kind == "vesc":
            from sim_vehicle_ecu.signals import MOTOR_MODES
            c["motor"] = np.full(n, MOTOR_MODES.index(self.cfg.vesc_mode), dtype=np.int64)
            c["age"] = np.zeros(n)
        self.commands = c

    def joint_targets(self, actions):
        """The bypassed action (bypass_component): (steer [N, 2] rad, spin [N, 4]) targets."""
        raise NotImplementedError(f"{type(self).__name__}: bypass_component needs "
                                  "joint_targets(actions)")

    def _commands_on_device(self, actions):
        dev = self.resident
        a = actions.detach().to(dev, torch.float64)
        n = a.shape[0]
        c = {f: a[:, i].clone() for i, f in enumerate(ACTIONS[self.kind])}
        c["valid"] = torch.ones(n, dtype=torch.bool, device=dev)
        if self.kind == "autoware":
            c["gear"] = torch.full((n,), 2, dtype=torch.int64, device=dev)   # drive
        elif self.kind == "ackermann":
            for f in ("jerk", "steering_angle_velocity", "age"):
                c[f] = torch.zeros(n, dtype=torch.float64, device=dev)
        elif self.kind == "vesc":
            from sim_vehicle_ecu.signals import MOTOR_MODES
            c["motor"] = torch.full((n,), MOTOR_MODES.index(self.cfg.vesc_mode),
                                    dtype=torch.int64, device=dev)
            c["age"] = torch.zeros(n, dtype=torch.float64, device=dev)
        return c

    def _apply_action(self):
        dt = self.physics_dt
        if self.stepped:          # the substep before this one: the cars read back
            self.backend.sample(dt)
        if self.cfg.bypass_component:
            self.backend.apply_joints(*self.joint_targets_now)
        else:
            self.run.before_physics(self.commands, dt)
        self.backend.actuate(dt)
        self.stepped = True

    # Isaac Lab's step after the physics (DirectRLEnv.step, v2 and v3.0.0-EA alike):
    # _get_dones, _get_rewards, _reset_idx(the done slots), _get_observations. The step's
    # world (the last substep read back, SSv2's default vehicles moved, the storyboard ticked)
    # is made in the first of them, so dones, rewards and observations all read this step,
    # and a reset slot's observation is its reset's (BatchRun.reset), the others untouched
    # (243's review of K2.2: they were a step late, and reset slots ran a step ahead).

    def _get_dones(self):
        if self.stepped:
            self.backend.sample(self.physics_dt)
            self.stepped = False
        self.obs = self.run.after_physics(self.step_dt)
        self.extras["scensim"] = self.obs
        return self.dones()

    def _get_rewards(self):
        return self.rewards()

    def _get_observations(self):
        self.obs = self.run.obs
        self.extras["scensim"] = self.obs
        ego = self.obs["ego"]
        o = torch.stack([ego["v"], ego["yaw_rate"], ego["accel_x"], ego["accel_y"],
                         ego["x"], ego["y"], torch.cos(ego["yaw"]), torch.sin(ego["yaw"])], -1)
        return {"policy": o.to(self.device, torch.float32)}

    def _reset_idx(self, env_ids):
        super()._reset_idx(env_ids)
        home = self.resident if self.resident is not None else torch.device("cpu")
        mask = torch.zeros(self.num_envs, dtype=torch.bool, device=home)
        mask[torch.as_tensor(env_ids, dtype=torch.long).to(home)] = True
        pre = None
        if self.cfg.ego_preroll:
            if not bool(mask.all()):
                raise RuntimeError(
                    f"ego_preroll is set but slots {torch.nonzero(mask).flatten().tolist()} "
                    "reset alone: a pre-roll steps every slot's physics, so only an agreement "
                    "run (every slot reset together) takes one")
            pre = self._preroll
        if self.pool is not None:
            self._draw_starts(env_ids, home)
        self.run.reset(mask, preroll=pre)   # merges: the other slots' observation stays this step's

    def _draw_starts(self, env_ids, home):
        """The reset slots' Init from the pool's next records, logged (094 P2)."""
        import json
        ids = [int(i) for i in torch.as_tensor(env_ids).flatten().tolist()]
        rows = self.pool.take(len(ids))
        x, y, yaw, v = self.pool.init(rows)
        c, e = self.compiled, self.run.ego
        it = torch.as_tensor(ids, dtype=torch.long, device=c.x.device)
        for t, val in ((c.x, x), (c.y, y), (c.yaw, yaw), (c.speed, v)):
            t[it, e] = val.to(t.device, t.dtype)
        for slot, row in zip(ids, rows):
            r = self.pool.record(row)
            line = {"slot": slot, "episode": self._episodes[slot], "record": r["id"],
                    "row": row, "chunk": r.get("pool_chunk")}
            self._episodes[slot] += 1
            self.start_log.append(line)
            if self._start_log is not None:
                self._start_log.write(json.dumps(line) + "\n")
        if self._start_log is not None:
            self._start_log.flush()

    def _preroll(self, run):
        """cfg.ego_preroll, as env steps of the ego alone: each action's commands, then the
        decimation's physics substeps as _apply_action and the sim run them."""
        # DirectRLEnv.step's physics loop (Isaac Lab 3.0), without its render and counters:
        # the pre-roll is not an episode step (243)
        steps_per_call = self.cfg.decimation if self._physics_handles_decimation else 1
        for a in self.cfg.ego_preroll:
            self._pre_physics_step(torch.as_tensor(a, dtype=torch.float64))
            for _ in range(self.cfg.decimation // steps_per_call):
                self._apply_action()
                self.scene.write_data_to_sim()
                self.sim.step(render=False)
                self.scene.update(dt=self.physics_dt * steps_per_call)
        if self.stepped:
            self.backend.sample(self.physics_dt)
            self.stepped = False

    # --- the user's: override these (self.obs is this step's) ----------------------------------

    def rewards(self):
        return torch.zeros(self.num_envs, device=self.device)

    def dones(self):
        """Terminated: the storyboard's exitSuccess or exitFailure (self.obs['outcome']: 1
        success, 2 failure); truncated: the episode length, which is SSv2's test runner
        timeout's role. A slot whose storyboard completed or stopped without an exit runs on
        to it, as on seats."""
        timeout = self.episode_length_buf >= self.max_episode_length - 1
        out = self.obs.get("outcome") if self.obs is not None else None
        term = (out != 0).to(timeout.device) if out is not None else torch.zeros_like(timeout)
        return term, timeout


class _LazyB:
    """Engine B's backend, built at its first use: the articulation's joints exist only once
    the sim has started (Isaac Lab's reset), after _setup_scene."""

    def __init__(self, make):
        self._make, self._b = make, None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if self._b is None:
            self._b = self._make()
        return getattr(self._b, name)
