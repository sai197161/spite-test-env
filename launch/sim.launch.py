"""
Headless Gazebo sim with spite_burger (TurtleBot3 Burger + RGB-D camera).

Usage (inside the container):
  ros2 launch /spitesim_ws/src/launch/sim.launch.py
  ros2 launch /spitesim_ws/src/launch/sim.launch.py world:=<path/to/world.sdf> x_pos:=-2.0 y_pos:=-0.5 yaw:=0.0

Record a demo video (world must have a camera publishing video_topic, e.g. the overhead demo_cam):
  ros2 launch /spitesim_ws/src/launch/sim.launch.py world:=/spitesim_ws/src/worlds/perpendicular_hallways.sdf \
      x_pos:=-4.5 record:=true duration:=60
  -> results/<world name>/<timestamp>/demo.mp4 in the repo; the sim shuts down when recording ends.
"""
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, IncludeLaunchDescription, AppendEnvironmentVariable,
                            ExecuteProcess, RegisterEventHandler, EmitEvent)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # repo root = one level up from launch/, wherever the repo is mounted
    repo_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    models_dir = os.path.join(repo_root, 'models')
    worlds_dir = os.path.join(repo_root, 'worlds')
    robot_sdf = os.path.join(models_dir, 'spite_burger', 'model.sdf')
    bridge_config = os.path.join(repo_root, 'config', 'spite_burger_bridge.yaml')
    recorder_script = os.path.join(repo_root, 'scripts', 'record_video.py')

    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')

    # spite_burger reuses the stock burger URDF for TF (base_footprint, base_link, base_scan, imu, wheels).
    # The camera frames are added below with static transforms.
    with open(os.path.join(tb3_gazebo, 'urdf', 'turtlebot3_burger.urdf'), 'r') as f:
        robot_description = f.read()

    world = LaunchConfiguration('world')
    use_sim_time = LaunchConfiguration('use_sim_time')
    x_pos = LaunchConfiguration('x_pos')
    y_pos = LaunchConfiguration('y_pos')
    yaw = LaunchConfiguration('yaw')
    record = LaunchConfiguration('record')
    duration = LaunchConfiguration('duration')
    video_topic = LaunchConfiguration('video_topic')
    output_dir = LaunchConfiguration('output_dir')

    # gazebo server only (no GUI), headless rendering so sensors work over ssh
    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            # trailing space matters: the list is joined into one string
            'gz_args': ['-r -s --headless-rendering -v2 ', world],
            'on_exit_shutdown': 'true',
        }.items(),
    )

    # spawn spite_burger from the repo's model file
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-name', 'spite_burger',
            '-file', robot_sdf,
            '-x', x_pos,
            '-y', y_pos,
            '-z', '0.01',
            '-Y', yaw,
        ],
    )

    # ros <-> gz topics: clock, odom, tf, imu, scan, cmd_vel, joint_states, rgbd_camera/*
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge_config,
            'use_sim_time': use_sim_time,
        }],
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
        }],
    )

    # base_link -> camera_link: matches camera_link pose in model.sdf (0.045, 0, 0.12 from the model origin;
    # base_link sits 0.01 above the origin, so z = 0.11 here)
    camera_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_link_tf',
        arguments=[
            '--x', '0.045', '--y', '0', '--z', '0.11',
            '--roll', '0', '--pitch', '0', '--yaw', '0',
            '--frame-id', 'base_link', '--child-frame-id', 'camera_link',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # camera_link (x forward, z up) -> camera_optical_frame (z forward, x right, y down), the
    # convention image/pixel-projection code expects. Gazebo stamps camera msgs with camera_link.
    camera_optical_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='camera_optical_tf',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0',
            '--roll', '-1.5708', '--pitch', '0', '--yaw', '-1.5708',
            '--frame-id', 'camera_link', '--child-frame-id', 'camera_optical_frame',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # demo video: records `duration` sim-seconds of video_topic to an mp4, then exits
    recorder = ExecuteProcess(
        cmd=['python3', recorder_script,
             '--topic', video_topic,
             '--world', world,
             '--output-dir', output_dir,
             '--duration', duration],
        output='screen',
        condition=IfCondition(record),
    )

    # when the recorder exits (recording done), shut the whole sim down
    stop_when_recorded = RegisterEventHandler(
        OnProcessExit(
            target_action=recorder,
            on_exit=[EmitEvent(event=Shutdown(reason='demo recording finished'))],
        ),
        condition=IfCondition(record),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(tb3_gazebo, 'worlds', 'empty_world.world'),
            description='SDF world file'),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'),
        DeclareLaunchArgument('x_pos', default_value='0.0', description='spawn x (m)'),
        DeclareLaunchArgument('y_pos', default_value='0.0', description='spawn y (m)'),
        DeclareLaunchArgument('yaw', default_value='0.0', description='spawn heading (rad)'),
        DeclareLaunchArgument('record', default_value='false', description='record a demo video if true'),
        DeclareLaunchArgument('duration', default_value='60.0', description='sim-seconds of video to record'),
        DeclareLaunchArgument('video_topic', default_value='/demo_cam/image', description='image topic to record'),
        DeclareLaunchArgument('output_dir', default_value=os.path.join(repo_root, 'results'),
                              description='where videos are saved (results/<world name>/<timestamp>/)'),

        # where gazebo looks up model:// URIs (spite_burger, turtlebot3_common meshes, world assets)
        AppendEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=os.pathsep.join([
                models_dir,
                worlds_dir,
                os.path.join(tb3_gazebo, 'models'),
                os.path.join(tb3_gazebo, 'worlds'),
            ]),
        ),

        gzserver,
        spawn_robot,
        bridge,
        robot_state_publisher,
        camera_tf,
        camera_optical_tf,
        recorder,
        stop_when_recorded,
    ])
