# src/anim_validator/checks.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import maya.cmds as cmds


@dataclass
class Issue:
    check_id: str
    title: str
    severity: str  # "OK" | "WARN" | "ERROR"
    message: str
    nodes: List[str]
    fixable: bool = False


class BaseCheck:
    check_id: str = "base"
    title: str = "Base Check"
    severity: str = "WARN"

    def run(self) -> Issue:
        raise NotImplementedError

    def fix(self, issue: Issue) -> bool:
        return False


# -----------------------------
# Helpers
# -----------------------------
def _camera_shape_from_transform(cam_tr: str) -> Optional[str]:
    shapes = cmds.listRelatives(cam_tr, shapes=True, fullPath=True) or []
    for s in shapes:
        if cmds.nodeType(s) == "camera":
            return s
    return None


def _is_default_maya_camera(cam_tr: str) -> bool:
    short = cam_tr.split("|")[-1]
    return short in {"persp", "top", "front", "side"}


def _has_animcurve(node: str, attr: str) -> bool:
    plug = f"{node}.{attr}"
    anim = cmds.listConnections(plug, s=True, d=False, type="animCurve") or []
    return bool(anim)


def _list_key_times(node: str, attrs: Tuple[str, ...]) -> List[float]:
    times = set()
    for a in attrs:
        try:
            ks = cmds.keyframe(node, at=a, q=True, tc=True) or []
            for t in ks:
                times.add(float(t))
        except Exception:
            continue
    return sorted(times)


# -----------------------------
# Checks
# -----------------------------
class CameraImagePlaneCheck(BaseCheck):
    check_id = "camera_imageplane"
    title = "Camera ImagePlanes"
    severity = "ERROR"

    def run(self) -> Issue:
        camera_shapes = cmds.ls(type="camera", long=True) or []
        bad_cam_transforms = []

        for cam_shape in camera_shapes:
            parents = cmds.listRelatives(cam_shape, parent=True, fullPath=True) or []
            cam_tr = parents[0] if parents else cam_shape
            if _is_default_maya_camera(cam_tr):
                continue

            planes = cmds.listConnections(f"{cam_shape}.imagePlane", source=True, destination=False) or []
            if planes:
                bad_cam_transforms.append(cam_tr)

        if bad_cam_transforms:
            return Issue(
                check_id=self.check_id,
                title=self.title,
                severity=self.severity,
                message="Some cameras have ImagePlanes connected.",
                nodes=sorted(list(set(bad_cam_transforms))),
                fixable=True,
            )

        return Issue(self.check_id, self.title, "OK", "OK", [], fixable=True)

    def fix(self, issue: Issue) -> bool:
        changed = False
        for cam_tr in issue.nodes:
            cam_shape = _camera_shape_from_transform(cam_tr)
            if not cam_shape:
                continue
            planes = cmds.listConnections(f"{cam_shape}.imagePlane", source=True, destination=False) or []
            for p in planes:
                try:
                    cmds.delete(p)
                    changed = True
                except Exception:
                    pass
        return changed


class InvalidNamingCharactersCheck(BaseCheck):
    check_id = "invalid_naming"
    title = "Invalid Naming Characters"
    severity = "WARN"
    _pattern = re.compile(r"^[a-z0-9_|:]+$", re.IGNORECASE)

    def run(self) -> Issue:
        nodes = cmds.ls(long=True) or []
        bad = []
        for n in nodes:
            short = n.split("|")[-1]
            if self._pattern.search(short):
                continue
            try:
                if cmds.nodeType(n) == "imagePlane":
                    continue
            except Exception:
                pass
            bad.append(n)

        if bad:
            return Issue(
                self.check_id,
                self.title,
                self.severity,
                "Found nodes with invalid characters in their names.",
                sorted(bad),
                fixable=False,
            )

        return Issue(self.check_id, self.title, "OK", "OK", [], fixable=False)


class MayaVersionCheck(BaseCheck):
    check_id = "maya_version"
    title = "Maya Version Compliance"
    severity = "WARN"

    def __init__(self, required_major: int = 2025) -> None:
        self.required_major = required_major

    def run(self) -> Issue:
        v = cmds.about(version=True)
        try:
            major = int(str(v).split()[0])
        except Exception:
            major = None

        if major != self.required_major:
            return Issue(
                self.check_id,
                self.title,
                self.severity,
                f"Running Maya {v}. Recommended: Maya {self.required_major}.",
                [],
                fixable=False,
            )
        return Issue(self.check_id, self.title, "OK", "OK", [], fixable=False)


class FrameRangeHandlesCheck(BaseCheck):
    """
    Anim-focused:
    - Verifica que el playback range sea (shot_start-handle .. shot_end+handle)
    - Verifica que el/los controles seleccionados (o cámaras) tengan keys en los handles.
    """
    check_id = "frame_range_handles"
    title = "Frame Range & Handles"
    severity = "WARN"

    def __init__(self, shot_start: int = 101, shot_end: int = 131, handle: int = 5) -> None:
        self.shot_start = int(shot_start)
        self.shot_end = int(shot_end)
        self.handle = int(handle)

    def run(self) -> Issue:
        exp_min = self.shot_start - self.handle
        exp_max = self.shot_end + self.handle

        pb_min = int(cmds.playbackOptions(q=True, min=True))
        pb_max = int(cmds.playbackOptions(q=True, max=True))

        problems = []
        if pb_min != exp_min or pb_max != exp_max:
            problems.append(f"Playback range is {pb_min}-{pb_max} (expected {exp_min}-{exp_max}).")

        # Targets: selección si hay, si no: cámaras no-default
        targets = cmds.ls(sl=True, long=True) or []
        if not targets:
            cams = []
            for cam_shape in (cmds.ls(type="camera", long=True) or []):
                parent = (cmds.listRelatives(cam_shape, parent=True, fullPath=True) or [cam_shape])[0]
                if not _is_default_maya_camera(parent):
                    cams.append(parent)
            targets = cams

        attrs = ("translateX","translateY","translateZ","rotateX","rotateY","rotateZ")

        missing_nodes = []
        for n in targets:
            if not cmds.objExists(n):
                continue
            times = _list_key_times(n, attrs)
            if not times:
                # Puede estar animado por constraint; para el reel igual nos sirve marcar
                missing_nodes.append(n)
                continue

            # Queremos al menos una key en exp_min y exp_max (o muy cerca)
            has_pre = any(abs(t - exp_min) < 0.001 for t in times)
            has_post = any(abs(t - exp_max) < 0.001 for t in times)
            if not (has_pre and has_post):
                missing_nodes.append(n)

        if problems or missing_nodes:
            msg = " / ".join(problems) if problems else "Missing handle keys on targets."
            nodes = sorted(list(set(missing_nodes)))
            return Issue(
                self.check_id,
                self.title,
                self.severity,
                msg if msg else "Handle keys missing.",
                nodes,
                fixable=False,
            )

        return Issue(self.check_id, self.title, "OK", "OK", [], fixable=False)


class CameraClippingPlanesCheck(BaseCheck):
    check_id = "camera_clipping"
    title = "Camera Clipping Planes"
    severity = "WARN"

    def __init__(self, near_max: float = 1.0, far_min: float = 5000.0) -> None:
        self.near_max = float(near_max)
        self.far_min = float(far_min)

    def run(self) -> Issue:
        bad = []
        camera_shapes = cmds.ls(type="camera", long=True) or []
        for cam_shape in camera_shapes:
            parents = cmds.listRelatives(cam_shape, parent=True, fullPath=True) or []
            cam_tr = parents[0] if parents else cam_shape
            if _is_default_maya_camera(cam_tr):
                continue

            try:
                near = cmds.getAttr(cam_shape + ".nearClipPlane")
                far = cmds.getAttr(cam_shape + ".farClipPlane")
            except Exception:
                continue

            if near > self.near_max or far < self.far_min:
                bad.append(cam_tr)

        if bad:
            return Issue(
                self.check_id,
                self.title,
                self.severity,
                f"Some cameras have risky clipping planes (near > {self.near_max} or far < {self.far_min}).",
                sorted(list(set(bad))),
                fixable=False,
            )

        return Issue(self.check_id, self.title, "OK", "OK", [], fixable=False)


def default_checks() -> List[BaseCheck]:
    return [
        CameraImagePlaneCheck(),
        InvalidNamingCharactersCheck(),
        MayaVersionCheck(required_major=2025),
        FrameRangeHandlesCheck(shot_start=101, shot_end=131, handle=5),
        CameraClippingPlanesCheck(near_max=1.0, far_min=5000.0),
    ]
