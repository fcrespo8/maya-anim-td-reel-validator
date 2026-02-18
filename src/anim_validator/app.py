# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    import shiboken6 as shiboken
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
    import shiboken2 as shiboken  # type: ignore

from .checks import (
    Status, Check, CheckResult,
    build_default_checks,
    setup_reel_disaster,
)


# -------------------------
# Maya helpers
# -------------------------

def maya_main_window() -> QtWidgets.QWidget:
    ptr = omui.MQtUtil.mainWindow()
    return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)


def delete_workspace_control(name: str) -> None:
    if cmds.workspaceControl(name, q=True, exists=True):
        cmds.deleteUI(name)


# -------------------------
# Small UI pieces
# -------------------------

class StatusPill(QtWidgets.QLabel):
    def __init__(self) -> None:
        super().__init__("WAIT")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedWidth(80)
        self.setFixedHeight(22)
        self.set_status(Status.WAIT)

    def set_status(self, status: str) -> None:
        color = Status.COLORS.get(status, Status.COLORS[Status.WAIT])
        self.setText(status)
        self.setStyleSheet(
            f"QLabel {{ background: {color}; color: #0b0f14; "
            "border-radius: 10px; font-weight: 700; }}"
        )


class CheckRowWidget(QtWidgets.QWidget):
    run_clicked = QtCore.Signal(str)
    fix_clicked = QtCore.Signal(str)

    def __init__(self, check_id: str, check: Check) -> None:
        super().__init__()
        self.check_id = check_id
        self.check = check

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        self.name_lbl = QtWidgets.QLabel(check.name)
        self.name_lbl.setToolTip(check.description or check.name)
        self.name_lbl.setMinimumWidth(260)

        self.pill = StatusPill()

        self.run_btn = QtWidgets.QPushButton("Run")
        self.run_btn.setFixedWidth(70)
        self.run_btn.clicked.connect(lambda: self.run_clicked.emit(self.check_id))

        self.fix_btn = QtWidgets.QPushButton("Fix")
        self.fix_btn.setFixedWidth(70)
        self.fix_btn.setEnabled(bool(getattr(check, "fixable", False)))
        self.fix_btn.clicked.connect(lambda: self.fix_clicked.emit(self.check_id))

        lay.addWidget(self.name_lbl, 1)
        lay.addWidget(self.pill, 0)
        lay.addWidget(self.run_btn, 0)
        lay.addWidget(self.fix_btn, 0)

    def set_status(self, status: str) -> None:
        self.pill.set_status(status)


# -------------------------
# Main Window
# -------------------------

class ValidatorWindow(QtWidgets.QDialog):
    WORKSPACE_NAME = "AnimValidatorDemoWorkspaceControl"

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent or maya_main_window())
        self.setObjectName("AnimValidatorDemoWindow")
        self.setWindowTitle("Anim Validator (Demo)")
        self.setMinimumSize(900, 560)

        # state
        self.checks: List[Check] = build_default_checks()
        self.check_ids: List[str] = [f"check_{i}" for i in range(len(self.checks))]
        self.results_by_id: Dict[str, CheckResult] = {cid: CheckResult() for cid in self.check_ids}

        # UI refs
        self.row_by_id: Dict[str, CheckRowWidget] = {}

        self._build_ui()
        self._apply_style()
        self._rebuild_list()

    # -------- UI build --------

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # Top
        top = QtWidgets.QHBoxLayout()
        self.search_le = QtWidgets.QLineEdit()
        self.search_le.setPlaceholderText("Search check…")
        self.search_le.textChanged.connect(self._rebuild_list)

        self.btn_disaster = QtWidgets.QPushButton("Setup Reel Disaster")
        self.btn_disaster.clicked.connect(self._on_disaster)

        top.addWidget(self.search_le, 1)
        top.addWidget(self.btn_disaster)
        root.addLayout(top)

        # Split
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root.addWidget(split, 1)

        # Left: list
        left = QtWidgets.QWidget()
        left_lay = QtWidgets.QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)

        self.listw = QtWidgets.QListWidget()
        self.listw.setAlternatingRowColors(True)
        self.listw.currentItemChanged.connect(self._on_current_changed)

        left_lay.addWidget(self.listw, 1)

        # Right: details
        right = QtWidgets.QWidget()
        right_lay = QtWidgets.QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)

        self.details_title = QtWidgets.QLabel("Details")
        self.details_title.setStyleSheet("font-weight: 700;")

        self.details_list = QtWidgets.QListWidget()
        self.details_list.itemDoubleClicked.connect(self._on_detail_double_clicked)

        self.status_bar = QtWidgets.QLabel("Listo.")
        self.status_bar.setObjectName("StatusBar")

        right_lay.addWidget(self.details_title)
        right_lay.addWidget(self.details_list, 1)
        right_lay.addWidget(self.status_bar, 0)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 4)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
        QDialog#AnimValidatorDemoWindow { background: #1f1f1f; }
        QLineEdit {
            background: #2a2a2a; border: 1px solid #3a3a3a;
            padding: 7px 10px; border-radius: 8px;
        }
        QPushButton {
            background: #2f2f2f; border: 1px solid #3d3d3d;
            padding: 7px 10px; border-radius: 10px;
        }
        QPushButton:hover { border: 1px solid #6a6a6a; }
        QPushButton:pressed { background: #262626; }
        QListWidget {
            background: #232323; border: 1px solid #353535; border-radius: 10px;
        }
        QLabel#StatusBar {
            background: #232323; border: 1px solid #353535;
            padding: 6px 10px; border-radius: 10px;
        }
        """)

    # -------- List logic --------

    def _rebuild_list(self) -> None:
        text = (self.search_le.text() or "").strip().lower()

        self.listw.blockSignals(True)
        self.listw.clear()
        self.row_by_id.clear()

        for cid, chk in zip(self.check_ids, self.checks):
            hay = f"{chk.name} {chk.description}".lower()
            if text and text not in hay:
                continue

            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, cid)
            item.setSizeHint(QtCore.QSize(10, 44))

            row = CheckRowWidget(cid, chk)
            row.run_clicked.connect(self._on_run_check)
            row.fix_clicked.connect(self._on_fix_check)
            row.set_status(self.results_by_id[cid].status)

            self.listw.addItem(item)
            self.listw.setItemWidget(item, row)
            self.row_by_id[cid] = row

        self.listw.blockSignals(False)

        if self.listw.count() > 0 and self.listw.currentRow() == -1:
            self.listw.setCurrentRow(0)

    def _current_check_id(self) -> Optional[str]:
        it = self.listw.currentItem()
        if not it:
            return None
        return it.data(QtCore.Qt.UserRole)

    # -------- Run / Fix --------

    def _on_run_check(self, check_id: str) -> None:
        chk = self._get_check_by_id(check_id)
        if not chk:
            return

        try:
            res = chk.run()
        except Exception as exc:
            res = CheckResult(
                status=Status.ERROR,
                message=f"Exception: {exc}",
                errors=[f"Check crashed: {exc}"],
            )

        self.results_by_id[check_id] = res
        self._refresh_row(check_id)
        self._show_details_if_current(check_id)

        self._set_status(f"{chk.name}: {res.status} — {res.message or ''}".strip())

    def _on_fix_check(self, check_id: str) -> None:
        chk = self._get_check_by_id(check_id)
        if not chk or not getattr(chk, "fixable", False):
            return

        ok = False
        try:
            ok = bool(chk.fix())
        except Exception as exc:
            self._set_status(f"{chk.name}: Fix exception: {exc}")
            ok = False

        # After fix, auto re-run to update status (demo-friendly)
        self._on_run_check(check_id)

        if ok:
            cmds.inViewMessage(amg=f"<hl>Fix applied:</hl> {chk.name}", pos="topCenter", fade=True)

    def _refresh_row(self, check_id: str) -> None:
        row = self.row_by_id.get(check_id)
        if not row:
            return
        row.set_status(self.results_by_id[check_id].status)

    def _get_check_by_id(self, check_id: str) -> Optional[Check]:
        try:
            idx = self.check_ids.index(check_id)
        except ValueError:
            return None
        return self.checks[idx]

    # -------- Details panel --------

    def _on_current_changed(self, *_args) -> None:
        cid = self._current_check_id()
        if not cid:
            return
        self._populate_details(cid)

    def _show_details_if_current(self, check_id: str) -> None:
        if self._current_check_id() == check_id:
            self._populate_details(check_id)

    def _populate_details(self, check_id: str) -> None:
        chk = self._get_check_by_id(check_id)
        res = self.results_by_id.get(check_id, CheckResult())

        title = chk.name if chk else "Details"
        self.details_title.setText(f"Details — {title}  ({res.status})")

        self.details_list.clear()

        # Errors first (red), then warnings (orange), then message (gray)
        def add_items(lines: List[str], nodes: List[str], severity: str) -> None:
            color = QtGui.QColor(Status.COLORS[severity])
            for i, line in enumerate(lines):
                it = QtWidgets.QListWidgetItem(line)
                it.setForeground(QtGui.QBrush(color))
                # store node for selection, if available
                node = nodes[i] if i < len(nodes) else ""
                it.setData(QtCore.Qt.UserRole, node)
                self.details_list.addItem(it)

        if res.errors:
            add_items(res.errors, res.error_nodes, Status.ERROR)
        if res.warnings:
            add_items(res.warnings, res.warning_nodes, Status.WARNING)

        if not res.errors and not res.warnings:
            it = QtWidgets.QListWidgetItem(res.message or "No issues.")
            it.setForeground(QtGui.QBrush(QtGui.QColor("#9ca3af")))
            it.setData(QtCore.Qt.UserRole, "")
            self.details_list.addItem(it)

    def _on_detail_double_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        node = item.data(QtCore.Qt.UserRole) or ""
        if node and cmds.objExists(node):
            try:
                cmds.select(node, r=True)
                cmds.inViewMessage(amg=f"<hl>Selected:</hl> {node}", pos="topCenter", fade=True)
            except Exception:
                pass

    # -------- Misc --------

    def _on_disaster(self) -> None:
        setup_reel_disaster()
        self._set_status("Reel Disaster aplicado. Ahora corré los checks.")

    def _set_status(self, msg: str) -> None:
        self.status_bar.setText(msg)

    # -------- Dock --------

    def show_docked(self) -> None:
        delete_workspace_control(self.WORKSPACE_NAME)

        ctrl = cmds.workspaceControl(
            self.WORKSPACE_NAME,
            label="Anim Validator (Demo)",
            dockToMainWindow=("right", 1),
            retain=False
        )
        qt_ctrl_ptr = omui.MQtUtil.findControl(ctrl)
        qt_ctrl = shiboken.wrapInstance(int(qt_ctrl_ptr), QtWidgets.QWidget)

        layout = QtWidgets.QVBoxLayout(qt_ctrl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self)

        self.show()
