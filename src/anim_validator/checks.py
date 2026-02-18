# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import maya.cmds as cmds


# -----------------------------
# Simple status model (demo)
# -----------------------------

class Status:
    WAIT = "WAIT"
    OK = "OK"
    WARNING = "WARNING"
    ERROR = "ERROR"

    # UI colors (Qt stylesheet hex)
    COLORS = {
        WAIT:    "#4b5563",  # gray
        OK:      "#22c55e",  # green
        WARNING: "#f59e0b",  # orange
        ERROR:   "#ef4444",  # red
    }


@dataclass
class CheckResult:
    status: str = Status.WAIT
    message: str = ""
    errors: List[str] = field(default_factory=list)    # strings shown in details
    warnings: List[str] = field(default_factory=list)
    error_nodes: List[str] = field(default_factory=list)    # nodes for selection
    warning_nodes: List[str] = field(default_factory=list)


class Check:
    """
    Minimal base check:
    - run() -> CheckResult
    - fix() optional
    """
    name: str = "Unnamed Check"
    description: str = ""
    fixable: bool = False

    def run(self) -> CheckResult:
        return CheckResult(status=Status.OK)

    def fix(self) -> bool:
        return False


# -----------------------------
# Demo: "Reel Disaster"
# -----------------------------

def setup_reel_disaster() -> None:
    """Genera problemas técnicos reales para demostrar el validador."""
    illegal_name = "L_arm_@#_RIG_JNT"
    if not cmds.objExists(illegal_name):
        cmds.group(em=True, n=illegal_name)

    cam_name = "render_cam_SHOT_01"
    if not cmds.objExists(cam_name):
        cam_nodes = cmds.camera(n=cam_name)
        cam_shape = cam_nodes[1]
        cmds.setAttr(f"{cam_shape}.nearClipPlane", 15.0)

        ip = cmds.createNode("imagePlane", n="basura_IP")
        cmds.connectAttr(f"{ip}.message", f"{cam_shape}.imagePlane[0]", force=True)

    cmds.inViewMessage(
        amg="<hl>SCENE PREPARED:</hl> 3 Production issues created.",
        pos="midCenter",
        fade=True
    )


# -----------------------------
# Concrete checks (simple + demo)
# -----------------------------

class IllegalNamingCheck(Check):
    name = "Naming: illegal characters"
    description = "Detecta nombres con caracteres no permitidos (ej: @, #, etc.)."
    fixable = True

    _illegal = re.compile(r"[^A-Za-z0-9_:|]+")

    def run(self) -> CheckResult:
        res = CheckResult(status=Status.OK, message="OK")

        nodes = cmds.ls(long=False) or []
        bad = [n for n in nodes if self._illegal.search(n)]
        if bad:
            res.status = Status.ERROR
            res.message = f"{len(bad)} nombres inválidos"
            res.errors = [f"Invalid name: {n}" for n in bad[:200]]
            # for selection, these are nodes themselves
            res.error_nodes = bad[:200]
        return res

    def fix(self) -> bool:
        nodes = cmds.ls(long=False) or []
        bad = [n for n in nodes if self._illegal.search(n)]
        if not bad:
            return False

        fixed_any = False
        for n in bad:
            if not cmds.objExists(n):
                continue
            safe = re.sub(self._illegal, "_", n)
            safe = re.sub(r"__+", "_", safe).strip("_") or "RENAMED_NODE"

            base = safe
            idx = 1
            while cmds.objExists(safe):
                idx += 1
                safe = f"{base}_{idx}"
            try:
                cmds.rename(n, safe)
                fixed_any = True
            except Exception:
                continue

        return fixed_any


class CameraNearClipCheck(Check):
    name = "Camera: nearClip too high"
    description = "Warn si nearClipPlane es demasiado alto (puede causar clipping)."
    fixable = True

    def __init__(self, threshold: float = 1.0, fix_value: float = 0.1) -> None:
        self.threshold = float(threshold)
        self.fix_value = float(fix_value)

    def run(self) -> CheckResult:
        res = CheckResult(status=Status.OK, message="OK")
        cams = cmds.ls(type="camera") or []

        warn_shapes = []
        for cam_shape in cams:
            try:
                near = cmds.getAttr(f"{cam_shape}.nearClipPlane")
            except Exception:
                continue
            if near is None:
                continue
            if float(near) > self.threshold:
                warn_shapes.append((cam_shape, float(near)))

        if warn_shapes:
            res.status = Status.WARNING
            res.message = f"{len(warn_shapes)} camera(s) con nearClip alto"
            res.warnings = [f"{s} nearClipPlane={v}" for s, v in warn_shapes[:200]]

            # select transform when possible
            nodes = []
            for s, _v in warn_shapes[:200]:
                tr = (cmds.listRelatives(s, parent=True, fullPath=False) or [s])[0]
                nodes.append(tr)
            res.warning_nodes = nodes

        return res

    def fix(self) -> bool:
        cams = cmds.ls(type="camera") or []
        fixed_any = False
        for cam_shape in cams:
            try:
                near = cmds.getAttr(f"{cam_shape}.nearClipPlane")
            except Exception:
                continue
            if near is None:
                continue
            if float(near) > self.threshold:
                try:
                    cmds.setAttr(f"{cam_shape}.nearClipPlane", self.fix_value)
                    fixed_any = True
                except Exception:
                    continue
        return fixed_any


class ImagePlaneConnectedCheck(Check):
    name = "Camera: imagePlane connected"
    description = "Warn si hay imagePlanes conectados a cámaras (limpieza típica)."
    fixable = True

    def run(self) -> CheckResult:
        res = CheckResult(status=Status.OK, message="OK")
        cam_shapes = cmds.ls(type="camera") or []

        found = []
        for cam_shape in cam_shapes:
            ips = cmds.listConnections(f"{cam_shape}.imagePlane", s=True, d=False) or []
            for ip in ips:
                found.append((cam_shape, ip))

        if found:
            res.status = Status.WARNING
            res.message = f"{len(found)} conexión(es) de imagePlane"
            res.warnings = [f"{cam} <- {ip}" for cam, ip in found[:200]]

            nodes = []
            for cam, _ip in found[:200]:
                tr = (cmds.listRelatives(cam, parent=True, fullPath=False) or [cam])[0]
                nodes.append(tr)
            res.warning_nodes = nodes

        return res

    def fix(self) -> bool:
        cam_shapes = cmds.ls(type="camera") or []
        fixed_any = False

        for cam_shape in cam_shapes:
            ips = cmds.listConnections(f"{cam_shape}.imagePlane", s=True, d=False) or []
            if not ips:
                continue

            # Disconnect all incoming connections to camera.imagePlane[*] and delete ips
            conns = cmds.listConnections(
                f"{cam_shape}.imagePlane",
                s=True, d=False,
                plugs=True, connections=True
            ) or []

            # conns list: [srcPlug, dstPlug, srcPlug, dstPlug...]
            for i in range(0, len(conns), 2):
                src_plug = conns[i]
                dst_plug = conns[i + 1]
                try:
                    cmds.disconnectAttr(src_plug, dst_plug)
                except Exception:
                    pass

            for ip in ips:
                if cmds.objExists(ip):
                    try:
                        cmds.delete(ip)
                        fixed_any = True
                    except Exception:
                        pass

        return fixed_any


def build_default_checks() -> List[Check]:
    """
    Acá definís la lista de checks para tu demo reel.
    Agregar uno nuevo = sumar a esta lista.
    """
    return [
        IllegalNamingCheck(),
        CameraNearClipCheck(threshold=1.0, fix_value=0.1),
        ImagePlaneConnectedCheck(),
    ]
