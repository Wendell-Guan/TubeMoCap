"""
Face receiver — supports two backends:

1. **UDP** (legacy): listens for OpenSeeFace packets on port 11573.
2. **Camera** (built-in): opens a camera via MediaPipe FaceLandmarker,
   extracts blendshapes + head rotation, and produces the same FaceData.

The active backend is selected by calling start_udp() or start_camera().
"""
import math
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# ── OpenSeeFace binary format constants ──────────────────────────────
_FMT  = '<d i 4f B f 4f 3f 3f 68f 136f 210f 14f'
_SIZE = struct.calcsize(_FMT)   # 1785

_O_RIGHT_EYE = 4
_O_LEFT_EYE  = 5
_O_SUCCESS   = 6
_O_EULER     = 12
_O_FEAT      = 432
_F_EYE_L, _F_EYE_R = 0, 1
_F_BROW_UD_L, _F_BROW_UD_R = 3, 6
_F_MOUTH_OPEN, _F_MOUTH_WIDE = 12, 13
_F_CORNER_UD_L, _F_CORNER_UD_R = 8, 10


@dataclass
class FaceData:
    pitch: float = 0.0
    yaw:   float = 0.0
    roll:  float = 0.0
    eye_l: float = 1.0
    eye_r: float = 1.0
    brow_l: float = 0.0
    brow_r: float = 0.0
    mouth_open: float = 0.0
    mouth_form: float = 0.0
    conf:  float = 0.0
    success: bool = True
    timestamp: float = field(default_factory=time.time)


class FaceReceiver:
    DEFAULT_HOST = '127.0.0.1'
    DEFAULT_PORT = 11573
    STALE_TIMEOUT_S = 0.5

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self._host, self._port = host, port
        self._latest: Optional[FaceData] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._camera_index: int = 0
        self._error: Optional[str] = None
        self._mode: str = 'udp'  # 'udp' or 'camera'

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def mode(self) -> str:
        return self._mode

    def start(self):
        """Start with the current mode (default: udp)."""
        if self._running:
            return
        self._running = True
        self._error = None
        if self._mode == 'camera':
            self._thread = threading.Thread(target=self._camera_loop, daemon=True, name='FaceCam')
        else:
            self._thread = threading.Thread(target=self._recv_loop, daemon=True, name='FaceUDP')
        self._thread.start()

    def start_camera(self, camera_index: int = 0):
        """Stop any running backend and switch to built-in camera mode."""
        self.stop()
        time.sleep(0.3)
        self._camera_index = camera_index
        self._mode = 'camera'
        # Probe camera from calling thread to trigger macOS permission dialog
        try:
            import cv2
            _probe = cv2.VideoCapture(camera_index)
            _probe.release()
        except Exception:
            pass
        self.start()

    def start_udp(self):
        """Stop any running backend and switch to UDP (OpenSeeFace) mode."""
        self.stop()
        time.sleep(0.3)
        self._mode = 'udp'
        self.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def get(self) -> Optional[FaceData]:
        with self._lock:
            d = self._latest
        if d is None:
            return None
        if time.time() - d.timestamp > self.STALE_TIMEOUT_S:
            return None
        return d

    def inject(self, data: FaceData):
        with self._lock:
            self._latest = data

    def is_active(self) -> bool:
        return self.get() is not None

    # ── UDP backend (OpenSeeFace) ────────────────────────────────────

    def _recv_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self._host, self._port))
            sock.settimeout(1.0)
            while self._running:
                try:
                    raw, _ = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                if len(raw) < _SIZE:
                    continue
                face = _parse_packet(raw)
                if face is not None:
                    with self._lock:
                        self._latest = face
        except OSError:
            pass
        finally:
            sock.close()

    # ── Camera backend (MediaPipe FaceLandmarker) ────────────────────

    def _camera_loop(self):
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:
            self._error = f"Missing dependency: {e}"
            self._running = False
            return

        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'models', 'face_landmarker.task'
        )
        if not os.path.exists(model_path):
            self._error = f"Face model not found: {model_path}"
            self._running = False
            return

        base_options = mp_python.BaseOptions(
            model_asset_path=model_path,
            delegate=mp_python.BaseOptions.Delegate.CPU,
        )
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self._error = f"Cannot open camera {self._camera_index}"
            self._running = False
            return

        try:
            with mp_vision.FaceLandmarker.create_from_options(options) as landmarker:
                while self._running:
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(0.01)
                        continue
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    timestamp_ms = int(time.time() * 1000)
                    result = landmarker.detect_for_video(mp_image, timestamp_ms)

                    if not result.face_blendshapes or not result.facial_transformation_matrixes:
                        continue

                    face = _parse_mediapipe_result(result)
                    if face:
                        with self._lock:
                            self._latest = face
        except Exception as e:
            self._error = str(e)
        finally:
            cap.release()
            self._running = False


def _parse_mediapipe_result(result) -> Optional[FaceData]:
    """Convert MediaPipe FaceLandmarker output to FaceData."""
    bs_list = result.face_blendshapes[0]
    bs = {b.category_name: b.score for b in bs_list}

    # Head rotation from the 4x4 transformation matrix
    mat = result.facial_transformation_matrixes[0]
    pitch, yaw, roll = _rotation_matrix_to_euler(mat)

    eye_l = 1.0 - bs.get('eyeBlinkLeft', 0.0)
    eye_r = 1.0 - bs.get('eyeBlinkRight', 0.0)

    brow_l = (bs.get('browOuterUpLeft', 0.0) + bs.get('browInnerUp', 0.0) * 0.5
              - bs.get('browDownLeft', 0.0))
    brow_r = (bs.get('browOuterUpRight', 0.0) + bs.get('browInnerUp', 0.0) * 0.5
              - bs.get('browDownRight', 0.0))
    brow_l = max(-1.0, min(1.0, brow_l))
    brow_r = max(-1.0, min(1.0, brow_r))

    mouth_open = bs.get('jawOpen', 0.0)

    smile = (bs.get('mouthSmileLeft', 0.0) + bs.get('mouthSmileRight', 0.0)) * 0.5
    frown = (bs.get('mouthFrownLeft', 0.0) + bs.get('mouthFrownRight', 0.0)) * 0.5
    mouth_form = max(-1.0, min(1.0, (smile - frown) * 2.0))

    return FaceData(
        pitch=pitch, yaw=yaw, roll=roll,
        eye_l=max(0.0, min(1.0, eye_l)),
        eye_r=max(0.0, min(1.0, eye_r)),
        brow_l=brow_l, brow_r=brow_r,
        mouth_open=max(0.0, min(1.0, mouth_open)),
        mouth_form=mouth_form,
        conf=0.9,
        success=True,
        timestamp=time.time(),
    )


def _rotation_matrix_to_euler(mat) -> tuple:
    """Extract pitch, yaw, roll (degrees) from a 4x4 transformation matrix."""
    import numpy as np
    m = np.array(mat).reshape(4, 4) if not hasattr(mat, 'shape') else mat
    r = m[:3, :3]

    sy = math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)
    if sy > 1e-6:
        pitch = math.atan2(r[2, 1], r[2, 2])
        yaw   = math.atan2(-r[2, 0], sy)
        roll  = math.atan2(r[1, 0], r[0, 0])
    else:
        pitch = math.atan2(-r[1, 2], r[1, 1])
        yaw   = math.atan2(-r[2, 0], sy)
        roll  = 0.0

    return (math.degrees(pitch), math.degrees(yaw), math.degrees(roll))


# ── OpenSeeFace packet parser (unchanged) ────────────────────────────

def _parse_packet(data: bytes) -> Optional[FaceData]:
    try:
        v = struct.unpack_from(_FMT, data)
    except struct.error:
        return None
    success = bool(v[_O_SUCCESS])
    if not success:
        return FaceData(success=False)
    raw_pitch, raw_yaw, raw_roll = v[_O_EULER], v[_O_EULER + 1], v[_O_EULER + 2]
    pitch, yaw, roll = -raw_pitch, raw_yaw, -raw_roll
    eye_r = float(v[_O_RIGHT_EYE])
    eye_l = float(v[_O_LEFT_EYE])
    feat_eye_l  = v[_O_FEAT + _F_EYE_L]
    feat_eye_r  = v[_O_FEAT + _F_EYE_R]
    feat_brow_l = v[_O_FEAT + _F_BROW_UD_L]
    feat_brow_r = v[_O_FEAT + _F_BROW_UD_R]
    feat_mouth_open = v[_O_FEAT + _F_MOUTH_OPEN]
    corner_l = v[_O_FEAT + _F_CORNER_UD_L]
    corner_r = v[_O_FEAT + _F_CORNER_UD_R]
    eye_l_final = feat_eye_l if feat_eye_l > 0.05 else eye_l
    eye_r_final = feat_eye_r if feat_eye_r > 0.05 else eye_r
    mouth_form = max(-1.0, min(1.0, (corner_l + corner_r) * 0.5 * 3.0))
    brow_l = max(-1.0, min(1.0, feat_brow_l * 2.0))
    brow_r = max(-1.0, min(1.0, feat_brow_r * 2.0))
    return FaceData(
        pitch=pitch, yaw=yaw, roll=roll,
        eye_l=eye_l_final, eye_r=eye_r_final,
        brow_l=brow_l, brow_r=brow_r,
        mouth_open=max(0.0, min(1.0, feat_mouth_open)),
        mouth_form=mouth_form,
        conf=0.9,
        success=True,
        timestamp=time.time(),
    )
