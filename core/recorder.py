"""
Recording logic: polls FaceReceiver and BodyReceiver, accumulates frames, saves Take.
"""
import time
import threading
from typing import Optional, Callable
from core.receiver import FaceReceiver, FaceData
from core.body_receiver import BodyReceiver, BodyData


class Recorder:
    POLL_INTERVAL = 1.0 / 60.0  # 60 Hz poll rate

    def __init__(self, face_rx: FaceReceiver, body_rx: BodyReceiver):
        self._face_rx = face_rx
        self._body_rx = body_rx
        self._recording = False
        self._face_frames = []
        self._body_frames = []
        self._start_time = 0.0
        self._thread: Optional[threading.Thread] = None
        self._mode = 'both'  # 'face', 'body', 'both'
        self.on_tick: Optional[Callable[[float], None]] = None  # called with elapsed seconds

    def set_mode(self, mode: str):
        assert mode in ('face', 'body', 'both')
        self._mode = mode

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self):
        if self._recording:
            return
        self._face_frames = []
        self._body_frames = []
        self._start_time = time.time()
        self._recording = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name='Recorder')
        self._thread.start()

    def stop(self) -> dict:
        """Stop recording and return raw frame data dict."""
        self._recording = False
        if self._thread:
            self._thread.join(timeout=2.0)
        duration = time.time() - self._start_time
        return {
            'duration': round(duration, 3),
            'mode': self._mode,
            'face_frames': list(self._face_frames),
            'body_frames': list(self._body_frames),
        }

    def _loop(self):
        last_face_t = -1.0
        last_body_t = -1.0
        while self._recording:
            now = time.time()
            elapsed = now - self._start_time

            if self._mode in ('face', 'both'):
                fd: Optional[FaceData] = self._face_rx.get()
                if fd is not None and fd.timestamp != last_face_t:
                    last_face_t = fd.timestamp
                    self._face_frames.append({
                        't':          round(elapsed, 4),
                        'pitch':      round(fd.pitch, 4),
                        'yaw':        round(fd.yaw, 4),
                        'roll':       round(fd.roll, 4),
                        'eye_l':      round(fd.eye_l, 4),
                        'eye_r':      round(fd.eye_r, 4),
                        'brow_l':     round(fd.brow_l, 4),
                        'brow_r':     round(fd.brow_r, 4),
                        'mouth_open': round(fd.mouth_open, 4),
                        'mouth_form': round(fd.mouth_form, 4),
                        'conf':       round(fd.conf, 3),
                    })

            if self._mode in ('body', 'both'):
                bd: Optional[BodyData] = self._body_rx.get()
                if bd is not None and bd.timestamp != last_body_t:
                    last_body_t = bd.timestamp
                    self._body_frames.append({
                        't': round(elapsed, 4),
                        'shoulder_width_ref': bd.shoulder_width_ref,
                        'landmarks': bd.landmarks,
                    })

            if self.on_tick:
                self.on_tick(elapsed)
            time.sleep(self.POLL_INTERVAL)
