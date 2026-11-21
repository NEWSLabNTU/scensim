"""f1tenth_system's bringup against the RoboRacer twin (scensim roadmap 091 W20).

f1tenth_stack's own nodes with its own config files (`vesc.yaml`, `mux.yaml`), unmodified:
ackermann_to_vesc, vesc_to_odom, ackermann_mux and the base_link -> laser transform. The twin
replaces the two hardware drivers, vesc_driver_node (aib's `vesc` vehicle interface) and
urg_node (the car's planar lidar on `/scan`). joy and joy_teleop are left out, since there is no
joystick. f1tenth_system ships no autonomous driver, so a stand-in, `wall_follow`, publishes on
`drive`, the mux's navigation input.

`wheelbase` is the car's. vesc.yaml sets it (0.25) under vesc_to_odom's own name, which outranks
a launch file's parameters and `-p` on the command line (both are `/**`), so the car's value
goes in a file under the same name, after vesc.yaml.
"""
import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

DRIVER_ARGS = ("speed", "max_steer", "distance", "scan_yaw")


def vesc_to_odom(context, vesc, sim):
    wb = float(LaunchConfiguration("wheelbase").perform(context))
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", prefix="roboracer_wheelbase_",
                                    delete=False)
    f.write(f"vesc_to_odom_node:\n  ros__parameters:\n    wheelbase: {wb!r}\n")
    f.close()
    return [Node(package="vesc_ackermann", executable="vesc_to_odom_node",
                 name="vesc_to_odom_node", parameters=[vesc, f.name, sim])]


def generate_launch_description():
    cfg = os.path.join(get_package_share_directory("f1tenth_stack"), "config")
    vesc = os.path.join(cfg, "vesc.yaml")
    mux = os.path.join(cfg, "mux.yaml")
    sim = {"use_sim_time": True}
    return LaunchDescription([
        DeclareLaunchArgument("wheelbase", default_value="0.33",
                              description="the car's wheel base, m (the example car's 0.33)"),
        DeclareLaunchArgument("speed", default_value="1.5", description="m/s"),
        DeclareLaunchArgument("max_steer", default_value="0.36", description="rad"),
        DeclareLaunchArgument("distance", default_value="1.5",
                              description="the right wall's distance to keep, m"),
        DeclareLaunchArgument("scan_yaw", default_value="0.0",
                              description="the scan frame's yaw in base_link, rad"),
        Node(package="vesc_ackermann", executable="ackermann_to_vesc_node",
             name="ackermann_to_vesc_node", parameters=[vesc, sim]),
        OpaqueFunction(function=vesc_to_odom, args=[vesc, sim]),
        Node(package="ackermann_mux", executable="ackermann_mux", name="ackermann_mux",
             parameters=[mux, sim], remappings=[("ackermann_cmd_out", "ackermann_drive")]),
        Node(package="tf2_ros", executable="static_transform_publisher",
             name="static_baselink_to_laser",
             arguments=["0.27", "0.0", "0.11", "0.0", "0.0", "0.0", "base_link", "laser"]),
        Node(package="roboracer_f1tenth", executable="wall_follow", name="wall_follow",
             parameters=[sim, {k: LaunchConfiguration(k) for k in DRIVER_ARGS}]),
    ])
