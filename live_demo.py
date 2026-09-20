"""Run several Step-1 test cases in one window and animate them together.

Each panel shows the room, static crowd, estimated boundary, deployment
curve, targets, guide agents, and live trajectories as the controller steps.

Examples
--------
python live_demo.py
python live_demo.py --all
python live_demo.py --cases square,ellipse,off_center
python live_demo.py --all --gif results/live_demo_all.gif

The live window opens maximized on the monitor under the cursor.
F11 toggles fullscreen; Esc leaves fullscreen. Space pauses. Q closes.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from controller import ABCGController
from controller.safety import Safety, is_safe, path_clearances
from environment import Environment
from run import load_config


ROOT = Path(__file__).resolve().parent

BG = '#07111f'
CARD = '#0c1c2c'
PLOT = '#081624'
ROOM_FILL = '#0a1824'
INK = '#e8f4fb'
MUTED = '#7fa3b5'
LINE = '#1e3a4c'
ACCENT = '#3ad4c5'
CROWD = '#f08b55'
BOUNDARY = '#c4a484'
DEPLOY = '#3ad4c5'
GUIDE = '#58acff'
RESERVE = '#2d4d66'

STATUS_COLOR = {
    'PLANNING': '#7fa3b5',
    'TRACKING': '#3ad4c5',
    'SETTLED': '#7ee0a3',
    'TIMEOUT': '#e7c06a',
    'PAUSED': '#e7c06a',
    'SAFETY_VIOLATION': '#f07167',
    'INITIALIZATION_INVALID': '#f07167',
    'REPLAN_EXHAUSTED': '#f07167',
    'CAPACITY_SHORTFALL': '#e7c06a',
    'OFFSET_INVALID': '#e7c06a',
    'PLAN_SEARCH_EXHAUSTED': '#e7c06a',
    'PATH_UNREACHABLE': '#f07167',
}

CASES = {
    'square': {
        'title': 'Square',
        'config': ROOT / 'configs/step1/square.yaml',
        'method': 'average_cvt',
    },
    'rectangle': {
        'title': 'Rectangle',
        'config': ROOT / 'configs/step1/rectangle.yaml',
        'method': 'equal_arc',
    },
    'ellipse': {
        'title': 'Ellipse',
        'config': ROOT / 'configs/step1/scenarios/ellipse.yaml',
        'method': 'mass_cvt',
    },
    'off_center': {
        'title': 'Off-center',
        'config': ROOT / 'configs/step1/scenarios/off_center.yaml',
        'method': 'distmesh',
    },
    'elongated': {
        'title': 'Elongated',
        'config': ROOT / 'configs/step1/scenarios/elongated.yaml',
        'method': 'average_cvt',
    },
    'high_demand': {
        'title': 'High demand',
        'config': ROOT / 'configs/step1/scenarios/high_demand_side.yaml',
        'method': 'equal_arc',
    },
}
DEFAULT_CASES = ['square', 'rectangle', 'ellipse', 'off_center']
ALL_CASES = list(CASES)


@dataclass
class LiveCase:
    name: str
    title: str
    config_path: Path
    method: str
    protocol: str = 'adaptive_resource'
    fixed_n: int | None = None
    max_steps: int | None = None
    env: Environment | None = None
    controller: ABCGController | None = None
    safety: Safety | None = None
    observation: object | None = None
    positions: np.ndarray | None = None
    history: list = field(default_factory=list)
    status: str = 'PLANNING'
    hold: int = 0
    progress: list = field(default_factory=list)
    step_index: int = 0
    done: bool = False
    artists: dict = field(default_factory=dict)

    def setup(self):
        config = load_config(self.config_path)
        config['controller']['method'] = self.method
        if self.max_steps is not None:
            config['simulation']['max_steps'] = self.max_steps
        self.config = config
        self.env = Environment(config)
        self.observation = self.env.observe()
        initial = self.env.initialize_guides(config['guides'])
        guide, control = config['guides'], config['controller']
        self.safety = Safety(
            2 * guide['radius'] + control['clearance'],
            guide['radius'] + float(self.observation.radii.max()) + control['clearance'],
            guide['radius'] + control['clearance'], guide['max_speed'],
            control['safety_numeric_tolerance'],
        )
        if not is_safe(path_clearances(
            initial, initial, self.observation.positions, self.env.scene.size
        ), self.safety):
            self.status = 'INITIALIZATION_INVALID'
            self.positions = initial
            self.history = [initial.copy()]
            self.done = True
            return
        self.positions = initial
        self.history = [initial.copy()]
        self.controller = ABCGController(
            control, self.safety, self.env.scene.size, self.protocol, self.fixed_n
        )
        self.controller.prepare(self.observation, initial)
        self.progress = [float(self.controller.remaining_path_lengths(initial).mean())]
        self.status = 'TRACKING'

    def advance(self):
        if self.done or self.controller is None:
            return
        config = self.config
        control, sim = config['controller'], config['simulation']
        _requested, result = self.controller.step(
            self.env.observe(), self.positions, sim['dt']
        )
        next_position = self.positions + sim['dt'] * result.velocity
        clearances = path_clearances(
            self.positions, next_position, self.observation.positions, self.env.scene.size
        )
        if not is_safe(clearances, self.safety):
            self.status = 'SAFETY_VIOLATION'
            self.done = True
            return
        self.env.advance(sim['dt'])
        self.positions = next_position
        self.history.append(next_position.copy())
        self.step_index += 1
        errors = self.controller.errors(next_position)
        self.progress.append(float(self.controller.remaining_path_lengths(next_position).mean()))
        settled = (
            np.all(errors <= control['position_tolerance'])
            and np.max(np.linalg.norm(result.velocity, axis=1)) <= control['speed_tolerance']
        )
        self.hold = self.hold + 1 if settled else 0
        if self.hold >= control['hold_steps']:
            self.status = 'SETTLED'
            self.done = True
            return
        window = control['stall_window']
        active_speed = np.linalg.norm(
            result.velocity[self.controller.assignment >= 0], axis=1
        )
        stalled = (
            len(self.progress) >= window + 1
            and self.progress[-window - 1] - self.progress[-1] < control['position_tolerance']
            and errors.max(initial=0.) > control['position_tolerance']
            and active_speed.mean() <= control['speed_tolerance']
        )
        if stalled:
            strategy = self.controller.recover(self.env.observe(), next_position)
            if strategy is None:
                self.status = 'REPLAN_EXHAUSTED'
                self.done = True
                return
            self.progress = [float(self.controller.remaining_path_lengths(next_position).mean())]
            self.status = f'RECOVER:{strategy}'
            return
        if self.step_index >= sim['max_steps']:
            self.status = 'TIMEOUT'
            self.done = True
            return
        self.status = 'TRACKING'

    def status_family(self):
        return self.status.split(':', 1)[0]

    def status_color(self):
        return STATUS_COLOR.get(self.status_family(), MUTED)

    def counts(self):
        if self.controller is None or self.controller.assignment is None:
            n = 0 if self.positions is None else len(self.positions)
            return 0, n
        active = int((self.controller.assignment >= 0).sum())
        return active, len(self.controller.assignment) - active

    def remaining(self):
        return None if not self.progress else float(self.progress[-1])


def _grid(n):
    if n <= 2:
        return 1, n
    if n <= 4:
        return 2, 2
    return 2, 3


def _blank(ax, facecolor=None):
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if facecolor is not None:
        ax.set_facecolor(facecolor)


def _apply_theme():
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Segoe UI', 'Calibri', 'DejaVu Sans', 'Arial'],
        'axes.unicode_minus': False,
        'figure.facecolor': BG,
        'savefig.facecolor': BG,
        'axes.facecolor': PLOT,
        'text.color': INK,
    })


def _status_label(status):
    family, _, detail = status.partition(':')
    if detail:
        return f'{family} · {detail.replace("_", " ")}'
    return family.replace('_', ' ')


def _draw_scene(ax, case: LiveCase):
    from matplotlib.patches import Circle, Polygon as MplPolygon

    env, crowd = case.env, case.observation
    width, height = env.scene.width, env.scene.height
    room = np.asarray(env.scene.polygon.exterior.coords)
    ax.add_patch(MplPolygon(
        room[:-1], closed=True, facecolor=ROOM_FILL, edgecolor='#4b88b5', lw=1.5, zorder=0,
    ))
    ax.set_xlim(-0.55, width + 0.55)
    ax.set_ylim(-0.55, height + 0.55)
    ax.set_aspect('equal')
    ax.set_facecolor(PLOT)
    ax.tick_params(colors=MUTED, labelsize=7, length=2.5, pad=2)
    ax.tick_params(which='both', direction='in')
    for spine in ax.spines.values():
        spine.set_color(LINE)
        spine.set_linewidth(0.8)
    ax.grid(color='#1a3344', alpha=0.55, lw=0.6)
    ax.set_axisbelow(True)

    for point, radius in zip(crowd.positions, crowd.radii):
        ax.add_patch(Circle(point, radius, color=CROWD, alpha=0.30, lw=0, zorder=2))
    ax.scatter(*crowd.positions.T, c=crowd.demand, cmap='YlOrRd', s=8, zorder=3, linewidths=0)
    controller = case.controller
    if controller is not None and controller.boundary is not None:
        ax.plot(*np.vstack([controller.boundary.crowd, controller.boundary.crowd[0]]).T,
                color=BOUNDARY, ls='--', lw=1.15, zorder=4)
        ax.plot(*np.vstack([controller.boundary.deployment, controller.boundary.deployment[0]]).T,
                color=DEPLOY, ls='--', lw=1.35, zorder=4)
    if controller is not None and controller.plan is not None:
        ax.scatter(*controller.plan.positions.T, marker='+', color=DEPLOY, s=32, zorder=5, lw=1.1)

    n_guides = 0 if case.positions is None else len(case.positions)
    traj = [ax.plot([], [], color=GUIDE, alpha=0.28, lw=0.9, zorder=3)[0] for _ in range(n_guides)]
    active = ax.scatter([], [], s=28, color=GUIDE, edgecolors='#d5edff', linewidths=0.6, zorder=6)
    reserve = ax.scatter([], [], s=18, color=RESERVE, edgecolors='#7fa3b5', linewidths=0.4, zorder=5)
    ax.text(0.02, 0.03, 'm', transform=ax.transAxes, color=MUTED, fontsize=7, ha='left', va='bottom')
    case.artists.update({'ax': ax, 'traj': traj, 'active': active, 'reserve': reserve})


def _draw_card(fig, spec, case: LiveCase):
    from matplotlib.patches import FancyBboxPatch

    host = fig.add_subplot(spec)
    host.set_facecolor(CARD)
    host.set_xticks([])
    host.set_yticks([])
    for spine in host.spines.values():
        spine.set_color('#163044')
        spine.set_linewidth(1.15)
    host.add_patch(FancyBboxPatch(
        (0, 0.97), 1, 0.03, transform=host.transAxes, boxstyle='square,pad=0',
        facecolor=ACCENT, edgecolor='none', clip_on=False,
    ))

    head = host.inset_axes([0.04, 0.888, 0.92, 0.082])
    _blank(head, CARD)
    head.set_xlim(0, 1)
    head.set_ylim(0, 1)
    head.text(0.0, 0.70, case.title, color=INK, fontsize=12, fontweight='bold', va='center', ha='left')
    head.text(0.0, 0.12, case.method.replace('_', ' '), color=MUTED, fontsize=8, va='center', ha='left')
    chip_text = head.text(
        1.0, 0.48, '', color=ACCENT, fontsize=7.5, fontweight='bold',
        ha='right', va='center', transform=head.transAxes,
        bbox=dict(boxstyle='round,pad=0.35', facecolor='#102838', edgecolor=ACCENT, lw=0.9),
    )

    plot = host.inset_axes([0.065, 0.105, 0.87, 0.755])
    _draw_scene(plot, case)

    foot = host.inset_axes([0.045, 0.015, 0.91, 0.07])
    _blank(foot, CARD)
    foot.set_xlim(0, 1)
    foot.set_ylim(0, 1)
    meta = foot.text(0.0, 0.45, '', color=MUTED, fontsize=8, va='center', ha='left')
    clock = foot.text(1.0, 0.45, '', color=INK, fontsize=8, va='center', ha='right')
    case.artists.update({
        'host': host, 'chip_text': chip_text, 'meta': meta, 'clock': clock,
    })
    _refresh_card(case)


def _refresh_card(case: LiveCase, paused=False):
    artists = case.artists
    if case.positions is not None and 'traj' in artists:
        trail = np.stack(case.history)
        for i, line in enumerate(artists['traj']):
            line.set_data(trail[:, i, 0], trail[:, i, 1])
        if case.controller is not None and case.controller.assignment is not None:
            mask = case.controller.assignment >= 0
        else:
            mask = np.zeros(len(case.positions), dtype=bool)
        active = case.positions[mask]
        reserve = case.positions[~mask]
        artists['active'].set_offsets(active if len(active) else np.empty((0, 2)))
        artists['reserve'].set_offsets(reserve if len(reserve) else np.empty((0, 2)))

    status = 'PAUSED' if paused and not case.done else case.status
    color = STATUS_COLOR['PAUSED'] if status == 'PAUSED' else case.status_color()
    artists['chip_text'].set_text(_status_label(status).upper())
    artists['chip_text'].set_color(color)
    artists['chip_text'].set_bbox(dict(
        boxstyle='round,pad=0.35', facecolor='#102838', edgecolor=color, lw=0.9,
    ))

    active_n, reserve_n = case.counts()
    remain = case.remaining()
    remain_text = '—' if remain is None else f'{remain:.2f} m remain'
    artists['meta'].set_text(f'{active_n} active   {reserve_n} reserve   {remain_text}')
    dt = case.config['simulation']['dt'] if hasattr(case, 'config') else 0.1
    artists['clock'].set_text(f't = {case.step_index * dt:5.1f} s    step {case.step_index}')


def _parse_cases(names):
    unknown = [name for name in names if name not in CASES]
    if unknown:
        raise SystemExit(f'Unknown cases {unknown}. Choose from: {", ".join(ALL_CASES)}')
    return names


def build_cases(names, max_steps):
    cases = []
    for name in names:
        spec = CASES[name]
        case = LiveCase(
            name=name, title=spec['title'], config_path=spec['config'],
            method=spec['method'], max_steps=max_steps,
        )
        print(f'Planning {case.title} / {case.method} ...', flush=True)
        try:
            case.setup()
            print(f'  {case.status}', flush=True)
        except ValueError as error:
            case.status = str(error).split(':', 1)[0]
            case.done = True
            print(f'  {case.status}: {error}', flush=True)
            if case.env is None:
                raise
        cases.append(case)
    return cases


def _qt_modules():
    try:
        from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
        return QtCore, QtGui, QtWidgets
    except Exception:
        return None, None, None


def _screen_work_area():
    """Work area of the screen under the cursor. Never the combined virtual desktop."""
    QtCore, QtGui, QtWidgets = _qt_modules()
    if QtWidgets is not None:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
            if screen is None:
                screen = app.primaryScreen()
            if screen is not None:
                geo = screen.availableGeometry()
                return geo.x(), geo.y(), geo.width(), geo.height()
    return _win32_work_area()


def _win32_work_area():
    if sys.platform != 'win32':
        return None
    try:
        import ctypes
    except ImportError:
        return None

    class POINT(ctypes.Structure):
        _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ('left', ctypes.c_long), ('top', ctypes.c_long),
            ('right', ctypes.c_long), ('bottom', ctypes.c_long),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ('cbSize', ctypes.c_ulong),
            ('rcMonitor', RECT),
            ('rcWork', RECT),
            ('dwFlags', ctypes.c_ulong),
        ]

    user32 = ctypes.windll.user32
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = ctypes.c_int
    user32.MonitorFromPoint.argtypes = [POINT, ctypes.c_uint]
    user32.MonitorFromPoint.restype = ctypes.c_void_p
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = ctypes.c_int

    cursor = POINT()
    if not user32.GetCursorPos(ctypes.byref(cursor)):
        cursor.x, cursor.y = 0, 0
    monitor = user32.MonitorFromPoint(cursor, 2)
    if not monitor:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    return work.left, work.top, work.right - work.left, work.bottom - work.top


def _window_from_figure(fig):
    manager = getattr(fig.canvas, 'manager', None)
    if manager is None:
        return None
    return getattr(manager, 'window', None)


def _qt_flag(qt, *names):
    current = qt
    for name in names:
        current = getattr(current, name, None)
        if current is None:
            return None
    return current


def _qt_target_screen(window=None):
    QtCore, QtGui, QtWidgets = _qt_modules()
    if QtWidgets is None:
        return None
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None
    app.processEvents()
    screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
    if screen is None and window is not None:
        screen = window.screen()
    if screen is None:
        area = _win32_work_area()
        if area is not None:
            center = QtCore.QPoint(area[0] + area[2] // 2, area[1] + area[3] // 2)
            screen = QtWidgets.QApplication.screenAt(center)
            if screen is None:
                for candidate in app.screens():
                    geo = candidate.availableGeometry()
                    if geo.contains(center):
                        screen = candidate
                        break
    return screen or app.primaryScreen()


def _maximize_on_current_screen(fig):
    """Open maximized on the monitor under the cursor, with a working maximize box."""
    window = _window_from_figure(fig)
    if window is None:
        return
    QtCore, QtGui, QtWidgets = _qt_modules()

    if QtWidgets is not None and isinstance(window, QtWidgets.QWidget):
        window.setMinimumSize(960, 600)
        maximize_hint = _qt_flag(QtCore.Qt, 'WindowMaximizeButtonHint')
        if maximize_hint is None:
            maximize_hint = _qt_flag(QtCore.Qt, 'WindowType', 'WindowMaximizeButtonHint')
        if maximize_hint is not None:
            window.setWindowFlag(maximize_hint, True)
        screen = _qt_target_screen(window)
        if screen is not None:
            handle = window.windowHandle()
            if handle is not None:
                handle.setScreen(screen)
            geo = screen.availableGeometry()
            window.setGeometry(geo)
        window.show()
        QtWidgets.QApplication.instance().processEvents()
        window.showMaximized()
        maximized = _qt_flag(QtCore.Qt, 'WindowMaximized')
        if maximized is None:
            maximized = _qt_flag(QtCore.Qt, 'WindowState', 'WindowMaximized')
        if maximized is not None:
            window.setWindowState(window.windowState() | maximized)
        window.raise_()
        window.activateWindow()
        return

    area = _screen_work_area()
    if hasattr(window, 'geometry') and hasattr(window, 'state'):
        window.resizable(True, True)
        try:
            window.minsize(960, 600)
        except Exception:
            pass
        if area is not None:
            left, top, width, height = area
            seed_w = max(960, min(1280, width - 80))
            seed_h = max(600, min(720, height - 80))
            window.geometry(f'{seed_w}x{seed_h}+{left + 24}+{top + 24}')
        try:
            window.update_idletasks()
        except Exception:
            pass

        def zoom():
            try:
                window.state('zoomed')
            except Exception:
                try:
                    window.attributes('-zoomed', True)
                except Exception:
                    if area is not None:
                        left, top, width, height = area
                        window.geometry(f'{width}x{height}+{left}+{top}')

        if hasattr(window, 'after'):
            window.after(1, zoom)
        else:
            zoom()
        return

    frame = getattr(getattr(fig.canvas, 'manager', None), 'frame', None)
    if frame is not None and hasattr(frame, 'Maximize'):
        frame.Maximize(True)


def _toggle_fullscreen(fig, state):
    window = _window_from_figure(fig)
    if window is None:
        return False
    QtCore, QtGui, QtWidgets = _qt_modules()
    if QtWidgets is not None and isinstance(window, QtWidgets.QWidget):
        if window.isFullScreen():
            window.showMaximized()
            state['fullscreen'] = False
        else:
            window.showFullScreen()
            state['fullscreen'] = True
        return True
    next_value = not state['fullscreen']
    if hasattr(window, 'attributes'):
        window.attributes('-fullscreen', next_value)
        if not next_value:
            try:
                window.state('zoomed')
            except Exception:
                pass
        state['fullscreen'] = next_value
        return True
    return False


def _figure(cases, for_screen=True):
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec
    from matplotlib.lines import Line2D

    _apply_theme()
    rows, cols = _grid(len(cases))
    if for_screen:
        area = _screen_work_area()
        dpi = 100
        if area is None:
            width_in, height_in = min(8.4 * cols, 16.0), min(5.2 * rows + 1.3, 9.0)
        else:
            _left, _top, px_w, px_h = area
            width_in = max(10.0, (px_w - 24) / dpi)
            height_in = max(6.0, (px_h - 88) / dpi)
        fig = plt.figure(figsize=(width_in, height_in), dpi=dpi)
    else:
        fig = plt.figure(figsize=(5.4 * cols, 3.55 * rows + 1.15), dpi=100)
    fig.patch.set_facecolor(BG)
    outer = GridSpec(
        3, 1, figure=fig, height_ratios=[0.072, 1.0, 0.058],
        hspace=0.035, left=0.022, right=0.988, top=0.975, bottom=0.028,
    )

    header = fig.add_subplot(outer[0])
    _blank(header, BG)
    header.set_xlim(0, 1)
    header.set_ylim(0, 1)
    header.text(
        0.0, 0.48, '  STEP 1  ', color=ACCENT, fontsize=8, fontweight='bold',
        ha='left', va='center',
        bbox=dict(boxstyle='round,pad=0.32', facecolor='#102838', edgecolor=ACCENT, lw=0.9),
    )
    header.annotate(
        'ABCG Controller', xy=(0.0, 0.48), xycoords=header.transAxes,
        xytext=(78, 0), textcoords='offset points',
        ha='left', va='center', color=INK, fontsize=15, fontweight='bold',
    )
    header.annotate(
        '·  simultaneous live tests', xy=(0.0, 0.48), xycoords=header.transAxes,
        xytext=(228, 0), textcoords='offset points',
        ha='left', va='center', color=MUTED, fontsize=9.5,
    )
    live = header.annotate(
        ' LIVE ', xy=(1.0, 0.48), xycoords=header.transAxes,
        xytext=(-138, 0), textcoords='offset points',
        ha='right', va='center', color=ACCENT, fontsize=8.5, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.32', facecolor='#102838', edgecolor=ACCENT, lw=0.9),
    )
    summary = header.text(1.0, 0.48, '', color=MUTED, fontsize=9, ha='right', va='center')

    body = outer[1].subgridspec(rows, cols, wspace=0.028, hspace=0.045)
    for index, case in enumerate(cases):
        _draw_card(fig, body[index // cols, index % cols], case)

    footer = fig.add_subplot(outer[2])
    _blank(footer, BG)
    footer.set_xlim(0, 1)
    footer.set_ylim(0, 1)
    handles = [
        Line2D([0], [0], color='#4b88b5', lw=1.6, label='Room'),
        Line2D([0], [0], color=CROWD, marker='o', ls='', ms=6, label='Crowd'),
        Line2D([0], [0], color=BOUNDARY, ls='--', lw=1.3, label='Estimated boundary'),
        Line2D([0], [0], color=DEPLOY, ls='--', lw=1.3, label='Deployment curve'),
        Line2D([0], [0], color=DEPLOY, marker='+', ls='', ms=8, label='Targets'),
        Line2D([0], [0], color=GUIDE, marker='o', ls='', ms=6, markeredgecolor='#d5edff', label='Active guides'),
        Line2D([0], [0], color=RESERVE, marker='o', ls='', ms=5, markeredgecolor='#7fa3b5', label='Reserve'),
    ]
    legend = footer.legend(
        handles=handles, loc='center', ncol=7, frameon=False, fontsize=8,
        labelcolor=MUTED, handlelength=1.6, borderaxespad=0.2,
    )
    for text in legend.get_texts():
        text.set_color(MUTED)
    footer.text(
        1.0, 0.5, 'Space pause    F11 fullscreen    Q close',
        color=MUTED, fontsize=8, ha='right', va='center',
    )
    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title('ABCG Controller  ·  Live tests')
    return fig, {'live': live, 'summary': summary, 'hint': None}


def _refresh_chrome(cases, chrome, paused):
    settled = sum(case.status == 'SETTLED' for case in cases)
    running = sum(not case.done for case in cases)
    if paused:
        label, color = ' PAUSED ', STATUS_COLOR['PAUSED']
    elif running:
        label, color = ' LIVE ', ACCENT
    else:
        label, color = ' DONE ', STATUS_COLOR['SETTLED']
    chrome['live'].set_text(label)
    chrome['live'].set_color(color)
    chrome['live'].set_bbox(dict(
        boxstyle='round,pad=0.32', facecolor='#102838', edgecolor=color, lw=0.9,
    ))
    chrome['summary'].set_text(f'{settled}/{len(cases)} settled   ·   {running} running')


def _frame_image(fig):
    from PIL import Image

    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    return Image.fromarray(rgba[:, :, :3].copy())


def _write_gif(path, frames, duration_ms=80):
    from PIL import Image

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    palette = frames[len(frames) // 2].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    quantized = [frame.quantize(palette=palette) for frame in frames]
    quantized[0].save(
        path, save_all=True, append_images=quantized[1:],
        duration=duration_ms, loop=0, disposal=2, optimize=False,
    )
    return path


def animate(cases, interval, stride, snapshot, gif=None):
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    export = snapshot is not None or gif is not None
    fig, chrome = _figure(cases, for_screen=not export)
    paused = {'value': False}
    display = {'fullscreen': False}
    if not export:
        _maximize_on_current_screen(fig)

    def on_key(event):
        if event.key == ' ':
            paused['value'] = not paused['value']
            _refresh_chrome(cases, chrome, paused['value'])
            for case in cases:
                _refresh_card(case, paused['value'])
            fig.canvas.draw_idle()
        elif event.key == 'f11':
            _toggle_fullscreen(fig, display)
        elif event.key == 'escape' and display['fullscreen']:
            _toggle_fullscreen(fig, display)
        elif event.key in {'q', 'escape'}:
            plt.close(fig)

    fig.canvas.mpl_connect('key_press_event', on_key)
    _refresh_chrome(cases, chrome, False)

    def tick(_frame):
        if paused['value']:
            return []
        if all(case.done for case in cases):
            _refresh_chrome(cases, chrome, False)
            return []
        for _ in range(stride):
            for case in cases:
                case.advance()
        for case in cases:
            _refresh_card(case)
        _refresh_chrome(cases, chrome, False)
        return []

    if gif:
        frames = [_frame_image(fig)]
        while any(not case.done for case in cases):
            tick(0)
            frames.append(_frame_image(fig))
        frames.extend([frames[-1]] * 12)
        saved = _write_gif(gif, frames, duration_ms=max(40, interval))
        plt.close(fig)
        print(f'Saved {saved}  ({len(frames)} frames)')
        return
    if snapshot:
        while any(not case.done for case in cases):
            tick(0)
        Path(snapshot).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(snapshot, dpi=140)
        plt.close(fig)
        print(f'Saved {snapshot}')
        return
    animation = FuncAnimation(
        fig, tick, interval=interval, blit=False, cache_frame_data=False,
    )
    plt.show()
    del animation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', default=','.join(DEFAULT_CASES),
                        help='Comma-separated case names')
    parser.add_argument('--all', action='store_true', help='Run all six built-in cases')
    parser.add_argument('--max-steps', type=int, help='Override simulation.max_steps')
    parser.add_argument('--interval', type=int, default=30, help='Animation delay in ms')
    parser.add_argument('--stride', type=int, default=2, help='Simulation steps per frame')
    parser.add_argument('--snapshot', type=Path, help='Run headless and save one comparison PNG')
    parser.add_argument('--gif', type=Path, help='Run headless and save an animated GIF')
    args = parser.parse_args()
    names = ALL_CASES if args.all else [item.strip() for item in args.cases.split(',') if item.strip()]
    names = _parse_cases(names)
    if args.snapshot or args.gif:
        import matplotlib
        matplotlib.use('Agg')
    cases = build_cases(names, args.max_steps)
    animate(cases, args.interval, max(1, args.stride), args.snapshot, args.gif)


if __name__ == '__main__':
    main()
