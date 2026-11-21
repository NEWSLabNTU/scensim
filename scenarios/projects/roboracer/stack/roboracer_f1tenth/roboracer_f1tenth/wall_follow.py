"""A wall follower for scensim roadmap 091 W20, after F1TENTH's own lab exercise. It stands in for a
user's navigation and publishes AckermannDriveStamped on `drive` (ackermann_mux's navigation
input) from `scan`. It is not part of f1tenth_system: the chain after `drive` is f1tenth_system's
own.

It keeps the right wall at `distance` (m), so the car laps a room counter-clockwise. Two beams on
the right, at -90 deg and at -90 + `theta` deg, give the wall's angle alpha and the car's distance
to it, projected `lookahead` m ahead; a PD on that distance's error steers. When the way ahead is
closer than `turn_at` (m), a corner is coming, and the car turns left at full lock and half speed.
"""
import math

import numpy as np
import rclpy
import rclpy.executors
from ackermann_msgs.msg import AckermannDriveStamped
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class WallFollow(Node):
    def __init__(self):
        super().__init__("wall_follow")
        p = lambda name, default: self.declare_parameter(name, default).value  # noqa: E731
        self.speed = p("speed", 1.5)
        self.max_steer = p("max_steer", 0.36)
        self.distance = p("distance", 1.5)
        self.lookahead = p("lookahead", 0.8)
        self.theta = math.radians(p("theta_deg", 50.0))
        self.kp, self.kd = p("kp", 0.5), p("kd", 0.1)
        self.max_err = p("max_err", 0.5)      # m: far from the wall, approach it, do not spin
        self.turn_at = p("turn_at", 2.0)
        self.scan_yaw = p("scan_yaw", 0.0)
        self.prev = None
        self.pub = self.create_publisher(AckermannDriveStamped, "drive", 10)
        self.create_subscription(LaserScan, "scan", self.on_scan, 10)

    def beam(self, m, angle):
        """The median range of the five beams nearest `angle` (rad, the car's frame)."""
        i = int(round((angle - self.scan_yaw - m.angle_min) / m.angle_increment))
        r = np.asarray(m.ranges[max(0, i - 2):i + 3], dtype=float)
        r = r[np.isfinite(r) & (r >= m.range_min)]
        return float(np.median(r)) if len(r) else m.range_max

    def on_scan(self, m):
        t = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
        b = self.beam(m, -math.pi / 2)
        a = self.beam(m, -math.pi / 2 + self.theta)
        alpha = math.atan2(a * math.cos(self.theta) - b, a * math.sin(self.theta))
        ahead = b * math.cos(alpha) + self.lookahead * math.sin(alpha)
        err = self.distance - ahead          # > 0: too close to the right wall, steer left
        err = max(-self.max_err, min(self.max_err, err))
        d = 0.0 if self.prev is None or t <= self.prev[0] else (err - self.prev[1]) / (t - self.prev[0])
        self.prev = (t, err)
        steer = self.kp * err + self.kd * d
        speed = self.speed
        if self.beam(m, 0.0) < self.turn_at:
            steer, speed = self.max_steer, 0.5 * self.speed
        out = AckermannDriveStamped()
        out.header.stamp = m.header.stamp
        out.drive.steering_angle = float(max(-self.max_steer, min(self.max_steer, steer)))
        out.drive.speed = float(speed)
        self.pub.publish(out)


def main():
    rclpy.init()
    try:
        rclpy.spin(WallFollow())
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass  # the launch's SIGINT at the end of a run: a clean exit, not a crash
    except Exception:  # noqa: BLE001 - Humble's rclpy, its context shut down mid-spin
        if rclpy.ok():
            raise
