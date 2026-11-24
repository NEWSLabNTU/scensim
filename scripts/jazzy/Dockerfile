# The Jazzy developer host (092 K6): Ubuntu 24.04 with ROS 2 Jazzy, as a developer starts it,
# before `just setup`. Only what a 24.04 host has before setup: setup itself installs Rust, the
# colcon plugin and rosdep's keys, which is what this image tests. libclang 14 is a host
# prerequisite on 24.04 (082 step 7: carla-sys's bindings drop `const` with 18).
FROM ros:jazzy
ARG UID=1000
ARG GID=1000
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends \
      sudo git curl ca-certificates just python3-pip python3-venv build-essential \
      libclang-14-dev clang-14 pkg-config libssl-dev zstd
# apt's package lists stay, as on a host (rosdep's apt lines need them; images usually drop them)
# a user with the host's ids, passwordless sudo for rosdep's apt line (setup asks for it as a
# user's host does)
RUN (getent group $GID || groupadd -g $GID dev) \
 && (id -u $UID >/dev/null 2>&1 && userdel -r $(id -nu $UID) || true) \
 && useradd -m -u $UID -g $GID -s /bin/bash dev \
 && echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev
USER dev
WORKDIR /home/dev
