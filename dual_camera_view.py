from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


WINDOW_NAME = "Dual Camera Viewer"
COMMON_RESOLUTIONS: list[tuple[int, int]] = [
    (3840, 2160),
    (2560, 1440),
    (1920, 1080),
    (1600, 1200),
    (1280, 1024),
    (1280, 720),
    (1024, 768),
    (800, 600),
    (640, 480),
]


@dataclass(frozen=True)
class BackendOption:
    value: int
    name: str


@dataclass(frozen=True)
class CameraRequest:
    index: int
    width: int
    height: int
    fps: int
    backend: BackendOption
    fourcc: str | None


@dataclass(frozen=True)
class CameraSelection:
    request: CameraRequest
    actual_width: int
    actual_height: int
    actual_fps: float


class RecordingSession:
    def __init__(self, folder: Path, left_shape: tuple[int, int], right_shape: tuple[int, int], fps: int) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.folder = folder
        self.started_at = time.time()
        safe_fps = max(float(fps), 1.0)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.left_writer = cv2.VideoWriter(
            str(folder / "camera_a.mp4"), fourcc, safe_fps, (left_shape[0], left_shape[1])
        )
        self.right_writer = cv2.VideoWriter(
            str(folder / "camera_b.mp4"), fourcc, safe_fps, (right_shape[0], right_shape[1])
        )
        self.csv_file = (folder / "timestamps.csv").open("w", newline="", encoding="utf-8")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["elapsed_s", "camera_a_frame", "camera_b_frame"])
        self.frame_index = 0

    def write(self, left_frame: np.ndarray, right_frame: np.ndarray) -> None:
        self.left_writer.write(left_frame)
        self.right_writer.write(right_frame)
        self.csv_writer.writerow([f"{time.time() - self.started_at:.6f}", self.frame_index, self.frame_index])
        self.frame_index += 1

    def close(self) -> None:
        self.left_writer.release()
        self.right_writer.release()
        self.csv_file.close()


def backend_candidates() -> list[BackendOption]:
    candidates: list[BackendOption] = []
    if sys.platform.startswith("win"):
        for name in ("CAP_DSHOW", "CAP_MSMF"):
            value = getattr(cv2, name, None)
            if value is not None:
                candidates.append(BackendOption(value=value, name=name.replace("CAP_", "")))
    candidates.append(BackendOption(value=cv2.CAP_ANY, name="ANY"))
    return candidates



def preferred_fourccs(preferred: str | None) -> list[str | None]:
    ordered: list[str | None] = []
    for value in (preferred, "MJPG", "YUY2", None):
        if value not in ordered:
            ordered.append(value)
    return ordered



def warmup_capture(capture: cv2.VideoCapture, frames: int = 5) -> tuple[bool, np.ndarray | None]:
    frame: np.ndarray | None = None
    for _ in range(frames):
        ok, frame = capture.read()
        if ok:
            return True, frame
        time.sleep(0.05)
    return False, frame



def apply_capture_request(capture: cv2.VideoCapture, request: CameraRequest) -> None:
    if request.fourcc:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*request.fourcc))
    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, request.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, request.height)
    capture.set(cv2.CAP_PROP_FPS, request.fps)



def open_capture(request: CameraRequest) -> tuple[cv2.VideoCapture | None, CameraSelection | None]:
    capture = cv2.VideoCapture(request.index, request.backend.value)
    if not capture.isOpened():
        capture.release()
        return None, None

    apply_capture_request(capture, request)
    ok, _ = warmup_capture(capture)
    if not ok:
        capture.release()
        return None, None

    actual_width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
    actual_height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    actual_fps = float(capture.get(cv2.CAP_PROP_FPS) or request.fps)
    selection = CameraSelection(
        request=request,
        actual_width=max(actual_width, 1),
        actual_height=max(actual_height, 1),
        actual_fps=max(actual_fps, 1.0),
    )
    return capture, selection



def score_selection(selection: CameraSelection) -> tuple[int, float, int, int]:
    backend_bonus = 2 if selection.request.backend.name == "DSHOW" else 1 if selection.request.backend.name == "MSMF" else 0
    fourcc_bonus = 1 if selection.request.fourcc == "MJPG" else 0
    area = selection.actual_width * selection.actual_height
    return area, selection.actual_fps, backend_bonus, fourcc_bonus



def probe_camera(index: int, fps: int, preferred_fourcc: str | None) -> list[CameraSelection]:
    results: list[CameraSelection] = []
    seen: set[tuple[int, int, int, str, str | None]] = set()
    for backend in backend_candidates():
        for fourcc in preferred_fourccs(preferred_fourcc):
            for width, height in COMMON_RESOLUTIONS:
                request = CameraRequest(index=index, width=width, height=height, fps=fps, backend=backend, fourcc=fourcc)
                capture, selection = open_capture(request)
                if capture is None or selection is None:
                    continue
                capture.release()
                key = (
                    selection.actual_width,
                    selection.actual_height,
                    int(round(selection.actual_fps)),
                    selection.request.backend.name,
                    selection.request.fourcc,
                )
                if key not in seen:
                    seen.add(key)
                    results.append(selection)
    results.sort(key=score_selection, reverse=True)
    return results



def select_camera(
    index: int,
    width: int | None,
    height: int | None,
    fps: int,
    preferred_fourcc: str | None,
    announce: bool = True,
) -> CameraSelection | None:
    if width is not None and height is not None:
        if announce:
            print(f"Camera {index}: trying requested mode {width}x{height}@{fps}.", flush=True)
        for backend in backend_candidates():
            for fourcc in preferred_fourccs(preferred_fourcc):
                request = CameraRequest(index=index, width=width, height=height, fps=fps, backend=backend, fourcc=fourcc)
                capture, selection = open_capture(request)
                if capture is None or selection is None:
                    continue
                capture.release()
                if announce:
                    print(f"Camera {index}: selected {format_selection(selection)}", flush=True)
                return selection
        if announce:
            print(f"Camera {index}: requested mode did not open.", flush=True)
        return None

    if announce:
        print(f"Camera {index}: probing highest working resolution.", flush=True)
    for width, height in COMMON_RESOLUTIONS:
        for backend in backend_candidates():
            for fourcc in preferred_fourccs(preferred_fourcc):
                request = CameraRequest(index=index, width=width, height=height, fps=fps, backend=backend, fourcc=fourcc)
                capture, selection = open_capture(request)
                if capture is None or selection is None:
                    continue
                capture.release()
                if announce:
                    print(f"Camera {index}: selected {format_selection(selection)}", flush=True)
                return selection
    if announce:
        print(f"Camera {index}: no working mode found.", flush=True)
    return None



def find_cameras(indices: Iterable[int], fps: int, preferred_fourcc: str | None) -> list[int]:
    found: list[int] = []
    for index in indices:
        selection = select_camera(index=index, width=640, height=480, fps=fps, preferred_fourcc=preferred_fourcc, announce=False)
        if selection is not None:
            found.append(index)
    return found



def format_selection(selection: CameraSelection) -> str:
    fourcc = selection.request.fourcc or "default"
    return (
        f"camera={selection.request.index} backend={selection.request.backend.name} fourcc={fourcc} "
        f"actual={selection.actual_width}x{selection.actual_height}@{selection.actual_fps:.1f}"
    )



def lerobot_camera_entry(name: str, selection: CameraSelection) -> str:
    return (
        f"{name}: {{type: opencv, index_or_path: {selection.request.index}, "
        f"width: {selection.actual_width}, height: {selection.actual_height}, fps: {int(round(selection.actual_fps))}}}"
    )



def letterbox(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    if frame.size == 0:
        return np.zeros((height, width, 3), dtype=np.uint8)

    src_h, src_w = frame.shape[:2]
    scale = min(width / src_w, height / src_h)
    resized = cv2.resize(frame, (max(1, int(src_w * scale)), max(1, int(src_h * scale))))
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    y = (height - resized.shape[0]) // 2
    x = (width - resized.shape[1]) // 2
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return canvas



def draw_label(frame: np.ndarray, label: str) -> np.ndarray:
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 70), (0, 0, 0), -1)
    lines = label.split("\n")
    for row, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (12, 24 + row * 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 0),
            2,
            cv2.LINE_AA,
        )
    return frame



def placeholder(width: int, height: int, label: str) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(frame, label, (20, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)
    return frame



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Preview two cameras, probe their highest working resolution, and print a LeRobot camera config. "
            "Use lerobot-record for ACT datasets with joint positions."
        )
    )
    parser.add_argument("--camera-a", type=int, help="Index for camera A.")
    parser.add_argument("--camera-b", type=int, help="Index for camera B.")
    parser.add_argument("--camera-a-name", default="wrist", help="LeRobot name for camera A.")
    parser.add_argument("--camera-b-name", default="top", help="LeRobot name for camera B.")
    parser.add_argument("--probe", type=int, default=8, help="How many camera indices to probe when auto-detecting.")
    parser.add_argument("--width", type=int, help="Requested width for both cameras. Leave unset to auto-pick the highest working mode.")
    parser.add_argument("--height", type=int, help="Requested height for both cameras. Leave unset to auto-pick the highest working mode.")
    parser.add_argument("--fps", type=int, default=30, help="Requested FPS for each camera.")
    parser.add_argument("--fourcc", default="MJPG", help="Preferred camera pixel format, for example MJPG or YUY2.")
    parser.add_argument("--list-modes", action="store_true", help="Print all working modes found for the selected cameras and exit.")
    parser.add_argument("--print-lerobot", action="store_true", help="Print a ready-to-paste value for --robot.cameras.")
    parser.add_argument("--no-preview", action="store_true", help="Do not open the side-by-side preview window.")
    parser.add_argument(
        "--record-dir",
        type=Path,
        help="Optional folder for a quick dual-MP4 smoke test. This is not a LeRobot dataset.",
    )
    parser.add_argument(
        "--record-seconds",
        type=float,
        default=0,
        help="Stop the smoke-test recording after this many seconds. Use 0 to run until q or Esc.",
    )
    return parser.parse_args()



def resolve_camera_indices(args: argparse.Namespace) -> tuple[int, int] | None:
    selected = [args.camera_a, args.camera_b]
    if any(index is None for index in selected):
        print(f"Looking for two cameras in indices 0..{args.probe - 1}.", flush=True)
        detected = find_cameras(range(args.probe), args.fps, args.fourcc)
        if len(detected) < 2:
            print(f"Found {len(detected)} camera(s): {detected}. Need two cameras connected.", flush=True)
            return None
        if args.camera_a is None:
            args.camera_a = detected[0]
        if args.camera_b is None:
            args.camera_b = detected[1]
        print(f"Auto-selected cameras {args.camera_a} and {args.camera_b}.", flush=True)
    return args.camera_a, args.camera_b



def print_mode_report(index: int, fps: int, preferred_fourcc: str | None) -> None:
    print(f"\nCamera {index} working modes:", flush=True)
    results = probe_camera(index=index, fps=fps, preferred_fourcc=preferred_fourcc)
    if not results:
        print("  no working mode found", flush=True)
        return
    for selection in results:
        print(f"  {format_selection(selection)}", flush=True)



def main() -> int:
    args = parse_args()
    indices = resolve_camera_indices(args)
    if indices is None:
        return 1

    if args.list_modes:
        print_mode_report(args.camera_a, args.fps, args.fourcc)
        print_mode_report(args.camera_b, args.fps, args.fourcc)
        return 0

    if (args.width is None) != (args.height is None):
        print("Provide both --width and --height together, or leave both unset for automatic max-resolution probing.", flush=True)
        return 1

    left_selection = select_camera(args.camera_a, args.width, args.height, args.fps, args.fourcc)
    right_selection = select_camera(args.camera_b, args.width, args.height, args.fps, args.fourcc)
    if left_selection is None or right_selection is None:
        print(f"Unable to configure both cameras. Left={args.camera_a}, Right={args.camera_b}", flush=True)
        return 1

    print(f"Camera A: {format_selection(left_selection)}", flush=True)
    print(f"Camera B: {format_selection(right_selection)}", flush=True)

    lerobot_value = (
        "{"
        + lerobot_camera_entry(args.camera_a_name, left_selection)
        + ", "
        + lerobot_camera_entry(args.camera_b_name, right_selection)
        + "}"
    )
    if args.print_lerobot or args.no_preview:
        print("\nPaste this into lerobot-record as --robot.cameras:", flush=True)
        print(lerobot_value, flush=True)
        if args.no_preview and args.record_dir is None:
            return 0

    print("Opening live preview.", flush=True)
    left_capture, left_live = open_capture(left_selection.request)
    right_capture, right_live = open_capture(right_selection.request)
    if left_capture is None or left_live is None or right_capture is None or right_live is None:
        print("The cameras probed successfully but could not be reopened for preview/recording.", flush=True)
        if left_capture is not None:
            left_capture.release()
        if right_capture is not None:
            right_capture.release()
        return 1

    panel_w = 960
    panel_h = 540
    recording: RecordingSession | None = None
    record_started_at = 0.0

    if args.record_dir is not None:
        recording = RecordingSession(
            folder=args.record_dir,
            left_shape=(left_live.actual_width, left_live.actual_height),
            right_shape=(right_live.actual_width, right_live.actual_height),
            fps=min(int(round(left_live.actual_fps)), int(round(right_live.actual_fps))),
        )
        record_started_at = time.time()
        print(f"Smoke-test recording to: {args.record_dir}", flush=True)

    if not args.no_preview:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        print("Preview is live. Press q or Esc to quit.", flush=True)

    try:
        while True:
            left_ok, left_frame = left_capture.read()
            right_ok, right_frame = right_capture.read()

            if not left_ok or left_frame is None:
                left_frame = placeholder(left_live.actual_width, left_live.actual_height, f"Camera {args.camera_a} read failed")
            if not right_ok or right_frame is None:
                right_frame = placeholder(right_live.actual_width, right_live.actual_height, f"Camera {args.camera_b} read failed")

            if recording is not None:
                recording.write(left_frame, right_frame)
                if args.record_seconds > 0 and time.time() - record_started_at >= args.record_seconds:
                    break

            if args.no_preview:
                time.sleep(0.01)
                continue

            left_label = (
                f"{args.camera_a_name}: cam {args.camera_a}\n"
                f"{left_live.actual_width}x{left_live.actual_height} @ {left_live.actual_fps:.1f} fps"
            )
            right_label = (
                f"{args.camera_b_name}: cam {args.camera_b}\n"
                f"{right_live.actual_width}x{right_live.actual_height} @ {right_live.actual_fps:.1f} fps"
            )
            left_panel = draw_label(letterbox(left_frame, panel_w, panel_h), left_label)
            right_panel = draw_label(letterbox(right_frame, panel_w, panel_h), right_label)
            combined = np.hstack((left_panel, right_panel))

            footer = "q / Esc: quit"
            if recording is not None:
                footer += f" | recording to {recording.folder}"
            cv2.putText(
                combined,
                footer,
                (20, combined.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow(WINDOW_NAME, combined)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    finally:
        if recording is not None:
            recording.close()
        left_capture.release()
        right_capture.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
