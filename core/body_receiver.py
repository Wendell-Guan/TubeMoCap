"""
MediaPipe Pose body receiver.
Opens a camera and runs MediaPipe Pose in a background thread.
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

LANDMARK_NAMES = [
    'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
    'right_eye_inner', 'right_eye', 'right_eye_outer',
    'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
    'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
    'left_wrist', 'right_wrist', 'left_pinky', 'right_pinky',
    'left_index', 'right_index', 'left_thumb', 'right_thumb',
    'left_hip', 'right_hip', 'left_knee', 'right_knee',
    'left_ankle', 'right_ankle', 'left_heel', 'right_heel',
    'left_foot_index', 'right_foot_index',
]

RECORD_LANDMARKS = [
    'nose', 'left_shoulder', 'right_shoulder',
    'left_elbow', 'right_elbow', 'left_wrist', 'right_wrist',
    'left_hip', 'right_hip', 'left_knee', 'right_knee',
    'left_ankle', 'right_ankle',
]


@dataclass
class BodyData:
    landmarks: Dict[str, List[float]] = field(default_factory=dict)  # name -> [x,y,z,vis]
    shoulder_width_ref: float = 0.0
    timestamp: float = field(default_factory=time.time)


class BodyReceiver:
    STALE_TIMEOUT_S = 0.5

    def __init__(self, camera_index: int = 1):
        self._camera_index = camera_index
        self._latest: Optional[BodyData] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._error: Optional[str] = None

    @property
    def error(self) -> Optional[str]:
        return self._error

    def start(self):
        if self._running:
            return
        # macOS: probe from the calling (Qt UI) thread WITHOUT
        # OPENCV_AVFOUNDATION_SKIP_AUTH so the system permission dialog fires
        # on first use.  After the probe returns (dialog resolved), set the env
        # var so the background thread skips the auth spin-loop attempt.
        import os
        if 'OPENCV_AVFOUNDATION_SKIP_AUTH' in os.environ:
            del os.environ['OPENCV_AVFOUNDATION_SKIP_AUTH']
        try:
            import cv2
            _probe = cv2.VideoCapture(self._camera_index)
            _probe.release()
        except Exception:
            pass
        os.environ['OPENCV_AVFOUNDATION_SKIP_AUTH'] = '1'
        self._running = True
        self._error = None
        self._thread = threading.Thread(target=self._recv_loop, daemon=True, name='BodyReceiver')
        self._thread.start()

    def stop(self):
        self._running = False

    def get(self) -> Optional[BodyData]:
        with self._lock:
            d = self._latest
        if d is None:
            return None
        if time.time() - d.timestamp > self.STALE_TIMEOUT_S:
            return None
        return d

    @property
    def is_running(self) -> bool:
        """True if the capture thread is alive (even before first frame arrives)."""
        return self._running

    def is_active(self) -> bool:
        """True only when recent pose data is available."""
        return self.get() is not None

    def set_camera(self, index: int):
        was_running = self._running
        if was_running:
            self.stop()
            time.sleep(0.3)
        self._camera_index = index
        if was_running:
            self.start()

    def _recv_loop(self):
        import os
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:
            self._error = f"Missing dependency: {e}. Run: pip install mediapipe opencv-python"
            self._running = False
            return

        # Model file lives next to this package in models/
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'models', 'pose_landmarker_full.task'
        )
        if not os.path.exists(model_path):
            self._error = f"Pose model not found: {model_path}"
            self._running = False
            return

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self._error = f"Cannot open camera {self._camera_index}"
            self._running = False
            return

        try:
            with mp_vision.PoseLandmarker.create_from_options(options) as landmarker:
                while self._running:
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.01)
                        continue
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    timestamp_ms = int(time.time() * 1000)
                    result = landmarker.detect_for_video(mp_image, timestamp_ms)

                    if result.pose_landmarks:
                        lms = result.pose_landmarks[0]
                        landmarks = {}
                        for name in RECORD_LANDMARKS:
                            idx = LANDMARK_NAMES.index(name)
                            lm = lms[idx]
                            landmarks[name] = [
                                round(lm.x, 4), round(lm.y, 4),
                                round(lm.z, 4), round(lm.visibility, 3)
                            ]
                        # Shoulder width as reference scale
                        ls = lms[LANDMARK_NAMES.index('left_shoulder')]
                        rs = lms[LANDMARK_NAMES.index('right_shoulder')]
                        sw = abs(ls.x - rs.x)
                        data = BodyData(
                            landmarks=landmarks,
                            shoulder_width_ref=round(sw, 4),
                            timestamp=time.time(),
                        )
                        with self._lock:
                            self._latest = data
        finally:
            cap.release()
