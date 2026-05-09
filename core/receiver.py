"""
OpenSeeFace UDP face receiver.
OpenSeeFace sends one UDP datagram per tracked face per frame on port 11573 (default).

Packet layout (little-endian, 1785 bytes):
  d        timestamp            (8 B)
  i        face_id              (4 B)
  4f       width, height, eye_blink_right, eye_blink_left
  B        success              (1 B)
  f        pnp_error            (4 B)
  4f       quaternion  x,y,z,w
  3f       euler  pitch,yaw,roll  (degrees)
  3f       translation  x,y,z
  68f      per-landmark confidence
  136f     2-D landmarks  (y,x) x 68
  210f     3-D points     (x,-y,-z) x 70
  14f      features: eye_l, eye_r, brow_steep_l, brow_ud_l, brow_quirk_l,
                     brow_steep_r, brow_ud_r, brow_quirk_r,
                     mouth_corner_ud_l, mouth_corner_io_l,
                     mouth_corner_ud_r, mouth_corner_io_r,
                     mouth_open, mouth_wide
"""
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

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

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True, name='FaceReceiver')
        self._thread.start()

    def stop(self):
        self._running = False

    def get(self) -> Optional[FaceData]:
        with self._lock:
            d = self._latest
        if d is None:
            return None
        if time.time() - d.timestamp > self.STALE_TIMEOUT_S:
            return None
        return d

    def is_active(self) -> bool:
        return self.get() is not None

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
        conf=0.9,  # OpenSeeFace doesn't expose per-frame conf easily; use placeholder
        success=True,
        timestamp=time.time(),
    )
