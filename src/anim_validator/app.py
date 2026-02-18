# src/anim_validator/app.py
from __future__ import annotations

from typing import Dict, List, Optional

import maya.cmds as cmds

try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except Exception:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets  # type: ignore
    from shiboken2 import wrapInstance  # type: ignore

import maya.OpenMayaUI as omui

from .checks import Issue, BaseCheck, default_checks


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget) if ptr else None


# ---------- Demo helper ----------
def create_demo_issues():
    """
    Crea problemas demo para filmar el reel:
    - nodo con nombre inválido
    - imagePlane conectado a una cámara no-default (si existe)
    - clipping near alto en una cámara
    """
    # invalid name node
    if not cmds.objExists("bad#name@NODE"):
        cube = cmds.polyCube(name="bad#name@NODE")[0]
        cmds.setAttr(cube + ".translateY", 2)

    # find a non-default camera transform (or create one)
    cam_tr = None
    for cam_shape in (cmds.ls(type="camera", long=True) or []):
        parent = (cmds.listRelatives(cam_shape, parent=True, fullPath=True) or [cam_shape])[0]
        short = parent.split("|")[-1]
        if short not in {"persp", "top", "front", "side"}:
            cam_tr = parent
            break

    if not cam_tr:
        cam_tr, cam_shape = cmds.camera(name="validator_demo_cam")
        cmds.setAttr(cam_tr + ".translate", 15, 10, 15, type="double3")
        cmds.setAttr(cam_tr + ".rotate", -20, 45, 0, type="double3")

    cam_shape = None
    shapes = cmds.listRelatives(cam_tr, shapes=True, fullPath=True) or []
    for s in shapes:
        if cmds.nodeType(s) == "camera":
            cam_shape = s
            break

    # add imagePlane to camera
    if cam_shape:
        # Create imagePlane and connect to cam
        # Avoid duplicates: check existing connections
        existing = cmds.listConnections(f"{cam_shape}.imagePlane", source=True, destination=False) or []
        if not existing:
            ip_shape = cmds.createNode("imagePlane", name="validator_demo_imagePlaneShape")
            ip_tr = (cmds.listRelatives(ip_shape, parent=True, fullPath=True) or [None])[0]
            if not ip_tr:
                ip_tr = cmds.createNode("transform", name="validator_demo_imagePlane")
                cmds.parent(ip_shape, ip_tr, shape=True, relative=True)

            try:
                cmds.connectAttr(f"{ip_shape}.message", f"{cam_shape}.imagePlane[0]", force=True)
            except Exception:
                pass

    # clipping issue
    if cam_shape:
        try:
            cmds.setAttr(cam_shape + ".nearClipPlane", 5.0)  # too high on purpose
        except Exception:
            pass

    cmds.inViewMessage(amg="<hl>Demo issues created</hl>", pos="midCenter", fade=True)


# ---------- UI ----------
class ValidatorWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or maya_main_window())
        self.setWindowTitle("Animation Scene Validator")
        self.setObjectName("anim_scene_validator_window")
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(820, 520)

        self.checks: List[BaseCheck] = default_checks()
        self.issues: Dict[str, Issue] = {}

        self._build_ui()
        self._connect()
        self._refresh_header()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()

        self.title_lbl = QtWidgets.QLabel("Animation Scene Validator")
        f = self.title_lbl.font()
        f.setPointSize(f.pointSize() + 5)
        f.setBold(True)
        self.title_lbl.setFont(f)

        self.sub_lbl = QtWidgets.QLabel("Preflight checks for Animation / shot workflows")
        self.sub_lbl.setStyleSheet("color: #9aa0a6;")

        self.status_lbl = QtWidgets.QLabel("—")
        self.status_lbl.setStyleSheet("color: #9aa0a6;")

        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.sub_lbl)
        title_box.addWidget(self.status_lbl)

        header.addLayout(title_box)
        header.addStretch(1)

        self.demo_btn = QtWidgets.QPushButton("Create Demo Issues")
        self.run_all_btn = QtWidgets.QPushButton("Run All")
        self.run_sel_btn = QtWidgets.QPushButton("Run Selected")
        self.fix_sel_btn = QtWidgets.QPushButton("Fix Selected")
        self.select_nodes_btn = QtWidgets.QPushButton("Select Nodes")

        self.fix_sel_btn.setEnabled(False)
        self.select_nodes_btn.setEnabled(False)

        header.addWidget(self.demo_btn)
        header.addWidget(self.run_all_btn)
        header.addWidget(self.run_sel_btn)
        header.addWidget(self.fix_sel_btn)
        header.addWidget(self.select_nodes_btn)

        root.addLayout(header)

        # Main split
        split = QtWidgets.QSplitter()
        split.setOrientation(QtCore.Qt.Horizontal)

        # Left: Table of checks
        left = QtWidgets.QWidget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)

        self.table = QtWidgets.QTreeWidget()
        self.table.setHeaderLabels(["Check", "Status", "Count", "Fix"])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

        self._populate_table()

        left_l.addWidget(QtWidgets.QLabel("Checks"))
        left_l.addWidget(self.table)

        # Right: Details
        right = QtWidgets.QWidget()
        right_l = QtWidgets.QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)

        self.detail_title = QtWidgets.QLabel("Details")
        df = self.detail_title.font()
        df.setBold(True)
        self.detail_title.setFont(df)

        self.detail_msg = QtWidgets.QLabel("Select a check and run it.")
        self.detail_msg.setWordWrap(True)

        self.nodes = QtWidgets.QListWidget()
        self.nodes.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        right_l.addWidget(self.detail_title)
        right_l.addWidget(self.detail_msg)
        right_l.addWidget(QtWidgets.QLabel("Nodes"))
        right_l.addWidget(self.nodes)

        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([520, 300])

        root.addWidget(split)

        # Log
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(400)
        self.log.setFixedHeight(140)

        root.addWidget(QtWidgets.QLabel("Log"))
        root.addWidget(self.log)

    def _populate_table(self):
        self.table.clear()
        for c in self.checks:
            item = QtWidgets.QTreeWidgetItem([c.title, "—", "—", "—"])
            item.setData(0, QtCore.Qt.UserRole, c.check_id)
            self.table.addTopLevelItem(item)
        if self.table.topLevelItemCount() > 0:
            self.table.setCurrentItem(self.table.topLevelItem(0))

    def _connect(self):
        self.demo_btn.clicked.connect(self._on_demo)
        self.run_all_btn.clicked.connect(self._on_run_all)
        self.run_sel_btn.clicked.connect(self._on_run_selected)
        self.fix_sel_btn.clicked.connect(self._on_fix_selected)
        self.select_nodes_btn.clicked.connect(self._on_select_nodes)

        self.table.currentItemChanged.connect(self._on_table_selection_changed)

    def _log(self, txt: str):
        self.log.appendPlainText(txt)

    def _current_check_id(self) -> Optional[str]:
        item = self.table.currentItem()
        if not item:
            return None
        return item.data(0, QtCore.Qt.UserRole)

    def _get_check(self, check_id: str) -> Optional[BaseCheck]:
        for c in self.checks:
            if c.check_id == check_id:
                return c
        return None

    def _refresh_header(self):
        # counts based on last run
        err = sum(1 for i in self.issues.values() if i.severity == "ERROR")
        warn = sum(1 for i in self.issues.values() if i.severity == "WARN")
        ok = sum(1 for i in self.issues.values() if i.severity == "OK")

        if self.issues:
            self.status_lbl.setText(f"{len(self.issues)} checks · {err} error · {warn} warning · {ok} ok")
        else:
            self.status_lbl.setText(f"{len(self.checks)} checks · Ready")

    def _set_row_for_issue(self, issue: Issue):
        # find table item
        for idx in range(self.table.topLevelItemCount()):
            it = self.table.topLevelItem(idx)
            if it.data(0, QtCore.Qt.UserRole) != issue.check_id:
                continue

            if issue.severity == "OK":
                it.setText(1, "OK")
                it.setText(2, "0")
            else:
                it.setText(1, issue.severity)
                it.setText(2, str(len(issue.nodes)))

            it.setText(3, "Yes" if issue.fixable else "—")
            break

    def _render_details(self, issue: Optional[Issue]):
        self.nodes.clear()

        if not issue:
            self.detail_msg.setText("Select a check and run it.")
            self.fix_sel_btn.setEnabled(False)
            self.select_nodes_btn.setEnabled(False)
            return

        if issue.severity == "OK":
            self.detail_msg.setText("✅ OK")
            self.fix_sel_btn.setEnabled(False)
            self.select_nodes_btn.setEnabled(False)
            return

        icon = "⛔" if issue.severity == "ERROR" else "⚠️"
        self.detail_msg.setText(f"{icon} {issue.severity}: {issue.message}")

        for n in issue.nodes:
            self.nodes.addItem(n)

        self.select_nodes_btn.setEnabled(bool(issue.nodes))
        self.fix_sel_btn.setEnabled(bool(issue.fixable and issue.nodes))

    def _on_table_selection_changed(self, *_):
        check_id = self._current_check_id()
        if not check_id:
            self._render_details(None)
            return
        self._render_details(self.issues.get(check_id))

    def _run_check(self, check: BaseCheck) -> Issue:
        try:
            issue = check.run()
        except Exception as e:
            issue = Issue(check.check_id, check.title, "ERROR", f"Check failed: {e}", [], fixable=False)
        self.issues[check.check_id] = issue
        self._set_row_for_issue(issue)
        return issue

    def _on_demo(self):
        create_demo_issues()
        self._log("Created demo issues.\n")

    def _on_run_all(self):
        self._log("Running all checks…")
        for c in self.checks:
            issue = self._run_check(c)
            if issue.severity == "OK":
                self._log(f"✅ {c.title}: OK")
            else:
                self._log(f"{issue.severity}: {c.title} — {len(issue.nodes)} item(s)")
        self._log("Done.\n")
        self._refresh_header()
        self._on_table_selection_changed()

    def _on_run_selected(self):
        check_id = self._current_check_id()
        if not check_id:
            return
        check = self._get_check(check_id)
        if not check:
            return

        self._log(f"Running: {check.title} …")
        issue = self._run_check(check)
        if issue.severity == "OK":
            self._log("✅ OK\n")
        else:
            self._log(f"{issue.severity}: {len(issue.nodes)} item(s)\n")
        self._refresh_header()
        self._render_details(issue)

    def _on_fix_selected(self):
        check_id = self._current_check_id()
        if not check_id:
            return
        check = self._get_check(check_id)
        issue = self.issues.get(check_id)
        if not check or not issue or not issue.fixable or not issue.nodes:
            return

        self._log(f"Fixing: {check.title} …")
        try:
            changed = check.fix(issue)
        except Exception as e:
            self._log(f"ERROR during fix: {e}\n")
            return

        self._log("Fix applied.\n" if changed else "No changes made.\n")

        # Re-run selected
        new_issue = self._run_check(check)
        self._refresh_header()
        self._render_details(new_issue)

    def _on_select_nodes(self):
        # selected in UI list; if none selected -> all
        selected = [i.text() for i in self.nodes.selectedItems()]
        if not selected:
            selected = [self.nodes.item(i).text() for i in range(self.nodes.count())]
        if not selected:
            return
        existing = [n for n in selected if cmds.objExists(n)]
        if existing:
            cmds.select(existing, r=True)
            self._log(f"Selected {len(existing)} node(s) in Maya.\n")
        else:
            self._log("Nothing to select.\n")


_window: Optional[ValidatorWindow] = None


def show():
    global _window
    if _window and _window.isVisible():
        _window.raise_()
        _window.activateWindow()
        return _window

    # close stale instances
    try:
        for w in QtWidgets.QApplication.allWidgets():
            if w.objectName() == "anim_scene_validator_window":
                w.close()
    except Exception:
        pass

    _window = ValidatorWindow()
    _window.show()
    return _window
