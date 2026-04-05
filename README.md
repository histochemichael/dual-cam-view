# Dual Camera Viewer

`dual_camera_view.py` is a small OpenCV utility for working with two USB cameras at once. It can:

- detect two available cameras automatically
- try the highest working resolution for each camera, or use a requested width/height
- open a live side-by-side preview window
- print a ready-to-paste `--robot.cameras` value for LeRobot
- optionally save a quick smoke-test recording as two MP4 files plus a timestamp CSV

## Requirements

- Python 3.10+
- `opencv-python`
- `numpy`

Install dependencies with:

```bash
pip install opencv-python numpy
```

## What The Script Does

When you run the script, it looks for two working cameras, configures them, and then:

1. prints the selected camera modes
2. builds a LeRobot camera configuration snippet
3. opens a live preview unless you disable preview
4. optionally records both cameras to disk

On Windows, it prefers the OpenCV `DSHOW` and `MSMF` backends when available, then falls back to `ANY`.

## Basic Usage

Run with automatic camera detection:

```bash
python dual_camera_view.py
```

Use specific camera indices:

```bash
python dual_camera_view.py --camera-a 0 --camera-b 1
```

Request a fixed resolution and FPS:

```bash
python dual_camera_view.py --camera-a 0 --camera-b 1 --width 1280 --height 720 --fps 30
```

Print the LeRobot camera config without opening the preview:

```bash
python dual_camera_view.py --camera-a 0 --camera-b 1 --print-lerobot --no-preview
```

List all working modes found for both cameras:

```bash
python dual_camera_view.py --camera-a 0 --camera-b 1 --list-modes
```

Run a short smoke-test recording for 10 seconds:

```bash
python dual_camera_view.py --camera-a 0 --camera-b 1 --record-dir test_capture --record-seconds 10
```

## Main Options

- `--camera-a`, `--camera-b`: camera indices to use
- `--camera-a-name`, `--camera-b-name`: names used in the LeRobot output
- `--probe`: how many indices to scan when auto-detecting cameras
- `--width`, `--height`: requested resolution for both cameras
- `--fps`: requested frame rate
- `--fourcc`: preferred pixel format such as `MJPG` or `YUY2`
- `--list-modes`: print all working modes and exit
- `--print-lerobot`: print the `--robot.cameras` value
- `--no-preview`: skip the live preview window
- `--record-dir`: folder for a quick dual-camera recording
- `--record-seconds`: recording length in seconds; `0` means run until you quit

## Preview Controls

If preview is enabled, press `q` or `Esc` to quit.

## Recording Output

If you pass `--record-dir`, the script creates:

- `camera_a.mp4`
- `camera_b.mp4`
- `timestamps.csv`

This recording mode is only a quick validation/smoke test. It is not a full LeRobot dataset recorder.

## LeRobot Output

The script prints a value shaped like this:

```text
{wrist: {type: opencv, index_or_path: 0, width: 1280, height: 720, fps: 30}, top: {type: opencv, index_or_path: 1, width: 1280, height: 720, fps: 30}}
```

You can paste that into `lerobot-record` as the value for `--robot.cameras`.

## Notes

- If only one of `--width` or `--height` is provided, the script exits with an error. Provide both or neither.
- If preview is disabled and no recording directory is given, the script prints the LeRobot config and exits.
- If a camera frame read fails during preview, the script shows a placeholder frame instead of crashing immediately.
