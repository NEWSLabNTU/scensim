# 202: the overlay's NDT stops a stock-profile pilot at start

**Status:** open; plan only (241, 2026-11-28, for 133). **Severity:** high: every
`autoware_profile: stock` pilot with the Autoware overlay on (the default) has had no NDT since
scensim cf931f5c; its pose initializer waits for ever. **Found:** 2026-11-28, 118, in L3's
Tsukuba lap b (`scensim-logs/tsukuba_b/stacks/2026-11-28T10-16-06_seat0/proc/pilot-ego/console.log`
on 118; the runs: NAS `autoveh/logs/2026 SSv2 on CARLA/2026-11-28 Tsukuba lap a and b
(118)/runs/TSK_b-*`).

## What happens

```
terminate called after throwing an instance of
  'rclcpp::exceptions::UninitializedStaticallyTypedParameterException'
  what():  Statically typed parameter
  'initial_pose_estimation.yaw_prior_variance_threshold' must be initialized.
```

ndt_scan_matcher exits -6 about 2 ms after it starts.

- The overlay's ndt_scan_matcher (NEWSLabNTU autoware_core `csb/ndt-step-reversal-1.5.0` at
  61f9c96e, issue 195's yaw prior) declares `initial_pose_estimation.yaw_prior_variance_threshold`
  statically typed with no default (`hyper_parameters.hpp`,
  `declare_parameter<double>(name)`).
- The scensim profile's param file sets it (asv 9d4bc31, 0.01), and so does the package's own
  yaml (0.0).
- autoware_launch's stock `ndt_scan_matcher.param.yaml`, which a stock-profile pilot runs as it
  is, does not.

Issue 195 said the stock profile "ignores" the key (7c3f1528). That was wrong: the stock param
file lacks the key, so the overlay's node refuses to start.

## The plan (133 approved, 2026-11-28; 243 recommended the same)

1. A test first, failing today: the node starts from the package's param file with the key
   removed (what a stock param file gives it), and the threshold reads 0.0.
2. The fork: declare the threshold with default 0.0. A variance is never below 0, so the yaw
   is drawn over the circle: upstream's behaviour, for a param file that predates the key. The
   schema no longer lists it as required. The scensim profile keeps 0.01.
3. The overlay pin, in the same scensim commit and gate as issue 201's pins.

Stock param files stay stock. Until the pin lands, a stock-profile pilot runs with
`autoware_overlay:=false`, labelled as such (133); that also drops the overlay's other fixes
(issues 002 and 027).
