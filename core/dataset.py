"""
Dataset management: motions index + takes on disk.
"""
import json
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any


class Motion:
    def __init__(self, id: str, name: str, description: str = '',
                 tags: list = None, performer: str = '', created_at: str = ''):
        self.id = id
        self.name = name
        self.description = description
        self.tags = tags or []
        self.performer = performer
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'tags': self.tags,
            'performer': self.performer,
            'created_at': self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> 'Motion':
        return Motion(
            d['id'], d['name'],
            d.get('description', ''),
            d.get('tags', []),
            d.get('performer', ''),
            d.get('created_at', ''),
        )


class Dataset:
    VERSION = '1.0'

    def __init__(self, root: str = 'dataset'):
        self.root = os.path.abspath(root)
        self._motions_file = os.path.join(self.root, 'motions.json')
        self._takes_dir = os.path.join(self.root, 'takes')
        os.makedirs(self._takes_dir, exist_ok=True)
        self._motions: List[Motion] = []
        self._load()

    # ── Motions ──────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self._motions_file):
            with open(self._motions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._motions = [Motion.from_dict(m) for m in data.get('motions', [])]
        else:
            self._motions = []

    def _save_index(self):
        data = {'version': self.VERSION, 'motions': [m.to_dict() for m in self._motions]}
        with open(self._motions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def motions(self) -> List[Motion]:
        return list(self._motions)

    def get_motion(self, motion_id: str) -> Optional[Motion]:
        return next((m for m in self._motions if m.id == motion_id), None)

    def add_motion(self, name: str, description: str = '',
                   tags: list = None, performer: str = '') -> Motion:
        m = Motion(str(uuid.uuid4()), name, description, tags or [], performer)
        self._motions.append(m)
        os.makedirs(self._take_dir(m.id), exist_ok=True)
        self._save_index()
        return m

    def rename_motion(self, motion_id: str, new_name: str):
        m = self.get_motion(motion_id)
        if m:
            m.name = new_name
            self._save_index()

    def delete_motion(self, motion_id: str):
        self._motions = [m for m in self._motions if m.id != motion_id]
        take_dir = self._take_dir(motion_id)
        if os.path.exists(take_dir):
            shutil.rmtree(take_dir)
        self._save_index()

    # ── Takes ─────────────────────────────────────────────────────────

    def _take_dir(self, motion_id: str) -> str:
        return os.path.join(self._takes_dir, motion_id)

    def _take_path(self, motion_id: str, take_index: int) -> str:
        return os.path.join(self._take_dir(motion_id), f'{take_index:03d}.json')

    def take_count(self, motion_id: str) -> int:
        d = self._take_dir(motion_id)
        if not os.path.exists(d):
            return 0
        return len([f for f in os.listdir(d) if f.endswith('.json')])

    def list_takes(self, motion_id: str) -> List[Dict[str, Any]]:
        """Return list of take metadata dicts (without frames, for speed)."""
        d = self._take_dir(motion_id)
        if not os.path.exists(d):
            return []
        takes = []
        for fname in sorted(os.listdir(d)):
            if not fname.endswith('.json'):
                continue
            path = os.path.join(d, fname)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            takes.append({
                'take_index': data['take_index'],
                'duration': data['duration'],
                'mode': data['mode'],
                'recorded_at': data['recorded_at'],
                'face_frame_count': len(data.get('face_frames', [])),
                'body_frame_count': len(data.get('body_frames', [])),
                'path': path,
            })
        return takes

    def load_take(self, motion_id: str, take_index: int) -> Optional[Dict]:
        path = self._take_path(motion_id, take_index)
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_take(self, motion_id: str, frame_data: dict, performer: str = '') -> int:
        """Save a new take. Returns the take_index."""
        motion = self.get_motion(motion_id)
        if not motion:
            raise ValueError(f'Motion {motion_id} not found')
        os.makedirs(self._take_dir(motion_id), exist_ok=True)
        # Next index
        existing = self.list_takes(motion_id)
        take_index = (max(t['take_index'] for t in existing) + 1) if existing else 1
        take = {
            'version': self.VERSION,
            'motion_id': motion_id,
            'motion_name': motion.name,
            'take_index': take_index,
            'recorded_at': datetime.now().isoformat(),
            'duration': frame_data['duration'],
            'mode': frame_data['mode'],
            'performer': performer,
            'face_frames': frame_data.get('face_frames', []),
            'body_frames': frame_data.get('body_frames', []),
        }
        with open(self._take_path(motion_id, take_index), 'w', encoding='utf-8') as f:
            json.dump(take, f, ensure_ascii=False)
        return take_index

    def delete_take(self, motion_id: str, take_index: int):
        path = self._take_path(motion_id, take_index)
        if os.path.exists(path):
            os.remove(path)

    def export_take_csv(self, motion_id: str, take_index: int, out_path: str):
        """Export face_frames as CSV."""
        import csv
        take = self.load_take(motion_id, take_index)
        if not take:
            return
        frames = take.get('face_frames', [])
        if not frames:
            return
        keys = ['t', 'pitch', 'yaw', 'roll', 'eye_l', 'eye_r',
                'brow_l', 'brow_r', 'mouth_open', 'mouth_form', 'conf']
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
            w.writeheader()
            w.writerows(frames)

    def export_take_npz(self, motion_id: str, take_index: int, out_path: str):
        """Export face_frames as .npz numpy archive."""
        import numpy as np
        take = self.load_take(motion_id, take_index)
        if not take:
            return
        frames = take.get('face_frames', [])
        if not frames:
            return
        keys = ['t', 'pitch', 'yaw', 'roll', 'eye_l', 'eye_r',
                'brow_l', 'brow_r', 'mouth_open', 'mouth_form', 'conf']
        arrays = {
            k: __import__('numpy').array([fr.get(k, 0.0) for fr in frames], dtype=__import__('numpy').float32)
            for k in keys
        }
        np.savez(out_path, **arrays)
