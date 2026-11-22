"""Tasks on K2's environment (094): DriftEnv, WheeledLab's MuSHR drift, registered as
Scensim-MushrDriftRL-v0 with stock's own rsl_rl PPO settings (wheeledlab_tasks' drifting
MushrPPORunnerCfg), so WheeledLab's train_rl.py trains it unchanged
(`env_setup.task_name=Scensim-MushrDriftRL-v0`)."""
try:
    import gymnasium as gym
except ImportError:      # outside Isaac Lab's Python
    gym = None

if gym is not None and "Scensim-MushrDriftRL-v0" not in gym.registry:
    gym.register(
        id="Scensim-MushrDriftRL-v0",
        entry_point="scensim_batch.tasks.drift:DriftEnv",
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": "scensim_batch.tasks.drift:MushrDriftRLEnvCfg",
            "rsl_rl_cfg_entry_point":
                "wheeledlab_tasks.drifting.config.agents.mushr.rsl_rl_ppo_cfg:MushrPPORunnerCfg",
        },
    )
