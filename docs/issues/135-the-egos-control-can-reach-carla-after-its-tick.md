# 135: the ego's control can reach CARLA after its tick

**Status:** open, a record (2026-11-24, 243; filed by 133). **Severity:** to judge.
**Found:** 2026-11-24, while planning issue 127.

acb drives a CARLA ego on its own LibCarla client, and the calls it actuates the ego with are
asynchronous in LibCarla 0.9.16: `Vehicle::apply_control` (`ApplyControlToVehicle`, in
`acb_bridge/src/vehicle_control.rs`) and `set_target_velocity` (`SetActorTargetVelocity`, in
`vehicle_physics.rs`) are `AsyncCall`s in `carla/client/detail/Client.cpp`, as `set_transform`
is (issue 127). So the ego's control for a frame may reach the server after the world server's
tick for that frame, and the ego then drives that frame on the previous control. Not measured;
no work yet. Whether it happens, how often, and whether acb should send its control in one
synchronous batch, as issue 127 does for NPCs, is for acb's owner to look at.
