"""Issue 195: the ROS port asks Autoware to initialize its localization with no pose, so the
pose initializer takes the GNSS pose and NDT's align, as on a real car."""

import inspect

import pytest

pytest.importorskip("rclpy")
pytest.importorskip("autoware_adapi_v1_msgs")

from scensim_agent.adapters import autoware_ros  # noqa: E402


def test_the_initialize_request_carries_no_pose():
    request = autoware_ros.initialize_request()
    assert list(request.pose) == []


def test_the_port_cannot_be_given_a_pose():
    params = list(inspect.signature(autoware_ros.AutowarePort.initialize).parameters)
    assert params == ["self", "stamp"]
