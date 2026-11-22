#!/usr/bin/env python3
"""
Record a ROS image topic to an mp4 with ffmpeg, then exit.

Stops after `--duration` seconds of *sim time* (measured from image header stamps), so the
video length is right even if the sim runs slower than real time. Exiting is what lets
sim.launch.py shut the whole sim down when recording is finished.

Output: <output_dir>/<scenario>/<YYYYmmdd-HHMMSS>/demo.mp4
The output folders are chowned to the owner of <output_dir>'s parent (the mounted repo),
so files written by the root container user can be deleted from the host without sudo.

Usage:
  python3 record_video.py --topic /demo_cam/image --world worlds/perpendicular_hallways.sdf \
      --output-dir /spitesim_ws/src/results --duration 60 --fps 15
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

PIX_FMTS = {'rgb8': 'rgb24', 'bgr8': 'bgr24', 'mono8': 'gray'}
BYTES_PER_PIXEL = {'rgb8': 3, 'bgr8': 3, 'mono8': 1}


def chown_like(path, ref):
    """Give `path` the same owner as `ref` (no-op if not root or on failure)."""
    try:
        st = os.stat(ref)
        os.chown(path, st.st_uid, st.st_gid)
    except (PermissionError, OSError):
        pass


class VideoRecorder(Node):
    def __init__(self, args):
        super().__init__('demo_video_recorder')
        self.args = args
        self.ffmpeg = None
        self.first_stamp = None
        self.frames = 0
        self.done = False

        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.out_dir = os.path.join(args.output_dir, args.scenario, stamp)
        self.out_file = os.path.join(self.out_dir, 'demo.mp4')

        self.create_subscription(Image, args.topic, self.on_image, 10)
        self.get_logger().info(
            f'waiting for images on {args.topic}; recording {args.duration:.0f} s of sim time '
            f'to {self.out_file}')

    def start_ffmpeg(self, msg):
        if msg.encoding not in PIX_FMTS:
            self.get_logger().error(f'unsupported image encoding "{msg.encoding}"')
            self.done = True
            return
        os.makedirs(self.out_dir, exist_ok=True)
        cmd = [
            'ffmpeg', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pix_fmt', PIX_FMTS[msg.encoding],
            '-s', f'{msg.width}x{msg.height}', '-framerate', str(self.args.fps),
            '-i', '-',
            '-c:v', 'libx264', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
            self.out_file,
        ]
        self.ffmpeg = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.row_bytes = msg.width * BYTES_PER_PIXEL[msg.encoding]
        self.get_logger().info(f'recording {msg.width}x{msg.height} {msg.encoding} @ {self.args.fps} fps')

    def on_image(self, msg):
        if self.done:
            return
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.ffmpeg is None:
            self.first_stamp = t
            self.start_ffmpeg(msg)
            if self.done:
                return

        data = bytes(msg.data)
        if msg.step != self.row_bytes:  # strip row padding if any
            data = b''.join(data[r * msg.step:r * msg.step + self.row_bytes] for r in range(msg.height))
        try:
            self.ffmpeg.stdin.write(data)
        except BrokenPipeError:
            self.get_logger().error('ffmpeg exited early')
            self.done = True
            return
        self.frames += 1

        if t - self.first_stamp >= self.args.duration:
            self.done = True

    def finish(self):
        if self.ffmpeg is None:
            self.get_logger().warn('no frames received, nothing written')
            return False
        self.ffmpeg.stdin.close()
        self.ffmpeg.wait()
        ref = os.path.dirname(os.path.abspath(self.args.output_dir))
        for p in (self.args.output_dir, os.path.join(self.args.output_dir, self.args.scenario),
                  self.out_dir, self.out_file):
            chown_like(p, ref)
        self.get_logger().info(f'wrote {self.frames} frames to {self.out_file}')
        return self.ffmpeg.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--topic', default='/demo_cam/image')
    parser.add_argument('--scenario', help='results subfolder name (default: world file name)')
    parser.add_argument('--world', help='world file path, used to name the scenario')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--duration', type=float, default=60.0, help='sim-time seconds to record')
    parser.add_argument('--fps', type=float, default=15.0, help='must match the camera update_rate')
    args, ros_args = parser.parse_known_args()
    if not args.scenario:
        args.scenario = os.path.splitext(os.path.basename(args.world))[0] if args.world else 'unnamed'

    rclpy.init(args=ros_args)
    node = VideoRecorder(args)
    ok = False
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        ok = node.finish()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
