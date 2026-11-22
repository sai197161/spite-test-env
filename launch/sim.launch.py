import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, AppendEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    tb3_launch_dir = os.path.join(tb3_gazebo, 'launch')

    world = LaunchConfiguration('world')
    use_sim_time = LaunchConfiguration('use_sim_time')
    x_pos = LaunchConfiguration('x_pos')
    y_pos = LaunchConfiguration('y_pos')

    gzserver = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')),
            launch_arguments={
                'gz_args': ['-r -s --headless-rendering -v2 ', world],
                'on_exit_shutdown': 'true',
            }.items()
    )

    spawn_robot = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(tb3_launch_dir, 'spawn_turtlebot3.launch.py')),
            launch_arguments={
                'x_pose': x_pos,
                'y_pose': y_pos,
            }.items()
    )

    robot_state_publisher = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(tb3_launch_dir, 'robot_state_publisher.launch.py')),
            launch_arguments={
                'use_sim_time': use_sim_time,
            }.items()
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
        DeclareLaunchArgument(
            'x_pos',
            default_value='0.0',
            description='x position to spawn robot'),
        DeclareLaunchArgument(
            'y_pos',
            default_value='0.0',
            description='y position to spawn robot'),
        AppendEnvironmentVariable(
            name='GZ_SIM_RESOURCE_PATH',
            value=[os.path.join(tb3_gazebo, 'worlds'), ':', os.path.join(tb3_gazebo, 'models')]
        ),
        gzserver,
        spawn_robot,
        robot_state_publisher,
    ])
