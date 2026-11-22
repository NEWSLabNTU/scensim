"""094 P2's run config for WheeledLab's train_rl.py: stock's RSS_DRIFT_CONFIG with only the task
ours (Scensim-MushrDriftRL-v0). Import after Isaac's app has launched (WheeledLab's configs
import Isaac Lab); scripts/train_drift.py does."""
from isaaclab.utils import configclass
from wheeledlab_rl.configs import EnvSetup
from wheeledlab_rl.configs.runs import RSS_DRIFT_CONFIG


@configclass
class SCENSIM_DRIFT_CONFIG(RSS_DRIFT_CONFIG):
    env_setup = EnvSetup(num_envs=1024, task_name="Scensim-MushrDriftRL-v0")
