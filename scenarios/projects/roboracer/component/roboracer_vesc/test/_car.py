"""The roboracer test car's geometry, in a plain module: scensim_batch's test_device takes it
without importing test_batch, which imports pytest (issue 186: Isaac's Python has none)."""

CAR = {"geometry": {"wheel_radius": 0.055, "max_steer_angle": 0.36}}
