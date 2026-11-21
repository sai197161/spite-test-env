# choose base image
FROM osrf/ros:jazzy-desktop

# so installs dont need input
ARG DEBIAN_FRONTEND=noninteractive

# install dependencies
RUN apt-get update && apt-get install -y \
    ros-jazzy-ros-gz \
    ros-jazzy-rqt-image-view \
    ros-jazzy-turtlebot3-gazebo \
    ros-jazzy-turtlebot3-description \
    ffmpeg \
    xvfb \
    python3-colcon-common-extensions \
    python3-rosdep \
    git \
    mesa-utils \
    && rm -rf /var/lib/apt/lists/*

# set working dir
WORKDIR /spitesim_ws
RUN mkdir -p src

# enable any hardware acceleration for sim purposes
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute

# resource path
ENV GZ_SIM_RESOURCE_PATH="/spitesim_ws/src/models:/spitesim_ws/src/worlds:/opt/ros/jazzy/share/turtlebot3_gazebo/models"
ENV TURTLEBOT3_MODL=burger

# automatic source ros
RUN echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc \
    && echo "if [ -f /spitesim_ws/install/setup.bash ]; then source /spitesim_ws/install/setup.bash; fi" >> ~/.bashrc

CMD ["bash"]

# docker container setup instructions:
    # uses ros jazzy and gazebo harmonic
    # build command: docker build -t spite-sim .
    # run command: docker run --rm -it -v ~/<path to spite-test-env>:/spitesim_ws/src spite-sim
    



