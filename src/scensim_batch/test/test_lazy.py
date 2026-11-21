"""K2.2c: the lazy ticks (BatchRun's steps between its host checks, where a device run skips no
branch and defers its checks) give the eager ones' results: test_storyboard's and test_core's
cases run again with every BatchRun lazy on the CPU (core.CPU_SYNC_EVERY 16). A case that
expects a check to raise at once is left to the eager run (LAZY_SKIP)."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import test_core  # noqa: E402
import test_storyboard  # noqa: E402

LAZY_SKIP = set()


def _lazy(cls):
    from scensim_batch import core

    def setUpClass(k):
        k._was = core.CPU_SYNC_EVERY
        core.CPU_SYNC_EVERY = 16
        super(lazy_cls, k).setUpClass()

    def tearDownClass(k):
        core.CPU_SYNC_EVERY = k._was
        super(lazy_cls, k).tearDownClass()

    lazy_cls = type(f"Lazy{cls.__name__}", (cls,), {
        "setUpClass": classmethod(setUpClass), "tearDownClass": classmethod(tearDownClass),
        "__module__": __name__})
    for name in LAZY_SKIP:
        if hasattr(lazy_cls, name):
            setattr(lazy_cls, name, unittest.skip("checks at once (eager only)")(
                getattr(lazy_cls, name)))
    return lazy_cls


for _mod in (test_storyboard, test_core):
    for _name, _obj in list(vars(_mod).items()):
        if (isinstance(_obj, type) and issubclass(_obj, unittest.TestCase)
                and _obj.__module__ == _mod.__name__):
            globals()[f"Lazy{_name}"] = _lazy(_obj)

if __name__ == "__main__":
    unittest.main()
