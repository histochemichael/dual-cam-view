# SO-101 Raspberry Pi Teleoperation Setup

This folder contains a Raspberry Pi teleoperation script for driving an SO-101 follower arm from an SO-101 leader arm, plus the matching calibration files for both robots.

## Included Files

- `lerobot_teleoperate_raspi.py` - Main teleoperation script.
- `so101_leader.json` - Calibration data for the leader arm.
- `so101_follower.json` - Calibration data for the follower arm.

## What the Script Does

`lerobot_teleoperate_raspi.py` is designed to run on a Raspberry Pi with LeRobot installed. It:

- loads the calibration JSON files from the same folder as the script
- expects the calibration ids `so101_leader` and `so101_follower`
- connects to the leader and follower over serial ports
- reads leader joint actions and forwards them to the follower
- supports startup-relative teleoperation so the follower moves relative to its own starting pose
- waits for the leader to move past a safety threshold before enabling follower motion
- optionally starts the follower gripper in the closed position
- patches `scservo_sdk` and `FeetechMotorsBus` compatibility at runtime

## Required File Layout

The script expects these three files to live in the same directory:

```text
lerobot_teleoperate_raspi.py
so101_leader.json
so101_follower.json
```

If either calibration file is missing, the script exits with an error.

## Example Run Command

```bash
source /home/michaelviacheslavov/venvs/lerobot/bin/activate
python lerobot_teleoperate_raspi.py \
    --leader-port /dev/ttyUSB0 \
    --follower-port /dev/ttyUSB1
```

## Command-Line Options

| Option | Default | Description |
| --- | --- | --- |
| `--leader-port` | required | Serial port for the leader arm |
| `--follower-port` | required | Serial port for the follower arm |
| `--fps` | `30` | Target control-loop frequency |
| `--max-relative-target` | `10.0` | Safety clamp for follower relative movement |
| `--duration` | none | Optional run time in seconds |
| `--relative-to-start-pose` | enabled | Uses startup poses as the shared home pose |
| `--no-relative-to-start-pose` | off | Disables startup-relative teleoperation |
| `--start-gripper-closed` | disabled | Starts the follower gripper closed |
| `--no-start-gripper-closed` | off | Leaves startup gripper behavior unchanged |
| `--activation-threshold` | `2.0` | Minimum leader movement before follower activation |
| `--log-level` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Teleoperation Behavior

At startup, the script:

1. validates that both calibration JSON files exist
2. connects the SO-101 leader and follower devices
3. captures startup joint positions when relative teleoperation is enabled
4. waits until the leader moves at least the activation threshold
5. sends mapped actions from the leader to the follower
6. disconnects both devices cleanly on exit

## Calibration Format

Each calibration JSON entry contains:

- `id` - servo id
- `drive_mode` - motor drive mode
- `homing_offset` - calibration offset
- `range_min` - minimum allowed raw position
- `range_max` - maximum allowed raw position

## Leader Calibration Summary

| Joint | ID | Homing Offset | Range Min | Range Max |
| --- | ---: | ---: | ---: | ---: |
| shoulder_pan | 1 | 1939 | 734 | 3448 |
| shoulder_lift | 2 | -2011 | 814 | 3198 |
| elbow_flex | 3 | 1042 | 876 | 3089 |
| wrist_flex | 4 | 1998 | 910 | 3190 |
| wrist_roll | 5 | -47 | 0 | 4095 |
| gripper | 6 | -1362 | 1667 | 2868 |

## Follower Calibration Summary

| Joint | ID | Homing Offset | Range Min | Range Max |
| --- | ---: | ---: | ---: | ---: |
| shoulder_pan | 1 | -1890 | 802 | 3168 |
| shoulder_lift | 2 | -722 | 843 | 3208 |
| elbow_flex | 3 | 1130 | 894 | 3098 |
| wrist_flex | 4 | -1933 | 835 | 3160 |
| wrist_roll | 5 | 2011 | 0 | 4095 |
| gripper | 6 | 1539 | 1478 | 2945 |

## Notes

- The leader and follower use different homing offsets and motion limits, so each arm needs its own calibration file.
- The script relies on the local calibration directory instead of a global calibration location.
- This setup is intended for Raspberry Pi serial devices such as `/dev/ttyUSB0` and `/dev/ttyUSB1`.
