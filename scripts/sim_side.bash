# The simulation side: its packages, and the Autoware message packages it builds against
# without an Autoware (roadmaps 082, 092 K6).
#
# Sourced by the justfile and scripts/release/build_sim.sh, never run. On Humble a developer
# builds every package against Autoware 1.5.0. On a distro Autoware 1.5.0 does not support
# (Jazzy), `just setup` and `just build` build the simulation side only, as the release's
# Jazzy tarball does: these packages, over third_party/sim_vendor, the message packages
# sim.repos pins, built once into their own workspace and sourced where Humble sources
# /opt/autoware, so the install layout stays the same.

# The packages of the simulation side (082's table) and everything they build against; the
# vehicle side is left out even where a simulation package names it (082 fix 3).
SCENSIM_SIM_PACKAGES=(scenario_world_bridge scenario_agent_relay scensim scensim_launch
    scensim_interfaces scensim_examples scensim_carla_world scensim_isaac_world
    scensim_world_check scenario_test_runner
    colcon-scensim  # colcon's scensim_testbench build type (081): no ROS package depends on it
    coop_pilots     # scripts/coop as data, for the coop study testbenches (081 step 4, group C)
    scensim_study_scenarios  # the studies' shared bench/ and gap/ scenarios (081 step 4, group B)
    # SSv2 loads its entity behaviours with pluginlib at run time; nothing depends on them
    behavior_tree_plugin do_nothing_plugin
    # the vehicle side every non-Autoware pilot on CARLA starts (133, 2026-11-18): acb's
    # bridge (with the blueprint pedal maps) and the car's descriptions
    acb_bridge tesla_model3_description tesla_model3_sensor_kit_description)
SCENSIM_VEHICLE_SIDE=(acb_launch aib_launch autoware_sim_profile individual_params
    tesla_model3_launch tesla_model3_sensor_kit_launch)

# carla-sys 0.15.1 (carla-rust) generates its C++ bindings with autocxx, which reads the
# headers through libclang. With libclang 18 (Ubuntu 24.04's default) the generated wrappers
# drop `const` and fail to compile ("invalid conversion from 'const ...*'"); libclang 14
# (Ubuntu 22.04's default, and apt's libclang-14-dev on 24.04) works. Prints the directory to
# use (LIBCLANG_PATH if set, else llvm-14's when present), nothing when there is neither.
scensim_libclang_path() {
    if [ -n "${LIBCLANG_PATH:-}" ]; then
        printf '%s\n' "$LIBCLANG_PATH"
    elif [ -d /usr/lib/llvm-14/lib ]; then
        printf '%s\n' /usr/lib/llvm-14/lib
    fi
}

# scensim_sim_vendor_build <dir> <ros setup.bash> <sim.repos>: fetch sim.repos' pinned
# versions into <dir>/src and build them into <dir>/install against ROS alone, from a clean
# environment (no Autoware, no other workspace). Re-run after sim.repos changes.
scensim_sim_vendor_build() {
    local dir=$1 ros_setup=$2 repos=$3
    command -v vcs >/dev/null || { echo "sim_vendor: vcs not on PATH (apt install python3-vcstool)" >&2; return 2; }
    [ -f "$ros_setup" ] || { echo "sim_vendor: no $ros_setup" >&2; return 2; }
    mkdir -p "$dir/src"
    vcs import --shallow --force --input "$repos" "$dir/src" >/dev/null
    (cd "$dir" && env -i HOME="$HOME" USER="${USER:-}" TERM=dumb LANG=C.UTF-8 \
        PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
        bash -c 'source "$1" && exec colcon build --base-paths src --cmake-args -DBUILD_TESTING=OFF \
            --event-handlers console_cohesion- summary+ status-' _ "$ros_setup")
}
