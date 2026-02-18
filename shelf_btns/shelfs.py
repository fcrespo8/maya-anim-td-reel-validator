# Set up de la escena con una esfera y una cámara independiente (90-150)

import maya.cmds as cmds

def reel_setup_scene(min_frame=90, max_frame=150):
    cmds.file(new=True, force=True) # Limpia la escena
    cmds.playbackOptions(min=min_frame, max=max_frame, ast=min_frame, aet=max_frame)
    cmds.currentTime(101)

    # Control de la Esfera
    ctrl = "sphere_CTRL"
    if not cmds.objExists(ctrl):
        ctrl = cmds.spaceLocator(name=ctrl)[0]
        cmds.setAttr(ctrl + ".translateY", 10)

    # Geometría
    geo = "sphere_GEO"
    if not cmds.objExists(geo):
        geo = cmds.polySphere(name=geo, r=1.5)[0]
        cmds.parent(geo, ctrl)
        cmds.setAttr(geo + ".translate", 0, 0, 0)

    # Cámara Independiente
    cam_t = "reel_cam"
    if not cmds.objExists(cam_t):
        cam_t, cam_s = cmds.camera(name=cam_t)
        cmds.setAttr(cam_t + ".translate", 25, 15, 25)
        cmds.setAttr(cam_t + ".rotate", -20, 45, 0)

    cmds.select(ctrl)
    cmds.inViewMessage(amg="Step 1: Setup Ready (No Constraints)", pos="midCenter", fade=True)

reel_setup_scene()

# Botón 2: Esfera con "Arco" y Rotación (96-136)

import maya.cmds as cmds

def anim_sphere_pro():
    node = "sphere_CTRL"
    if not cmds.objExists(node): return

    # Frames: Pre-roll(96), Start(101), Mid(116), End(131), Post-roll(136)
    frames = [96, 101, 116, 131, 136]

    # Posiciones con un arco en el eje Y (subida y bajada)
    pos = [(-5, 8, -5), (0, 10, 0), (12, 18, 10), (25, 12, 20), (30, 10, 23)]
    # Rotaciones para que el Motion Blur sea radial también
    rot = [(-20, -20, -20), (0, 0, 0), (180, 360, 90), (360, 720, 180), (400, 800, 200)]

    for i in range(len(frames)):
        f = frames[i]
        # Set Translate
        for axis, val in zip(['X', 'Y', 'Z'], pos[i]):
            cmds.setKeyframe(node, t=f, at=f"translate{axis}", v=val)
        # Set Rotate
        for axis, val in zip(['X', 'Y', 'Z'], rot[i]):
            cmds.setKeyframe(node, t=f, at=f"rotate{axis}", v=val)

        cmds.keyTangent(node, t=(f, f), itt="auto", ott="auto") # Tangentes suaves para el arco

    cmds.inViewMessage(amg="Step 2: Pro Sphere Anim (Arc + Rotation)", pos="midCenter", fade=True)

anim_sphere_pro()

# btn 3 Animación de cámara con look automático a un target (TD Trick)

import maya.cmds as cmds

def anim_camera_pro_fixed_look():
    cam = "reel_cam1"
    target = "sphere_CTRL"

    if not cmds.objExists(cam) or not cmds.objExists(target):
        cmds.warning("Falta la cámara o la esfera. Corre los botones anteriores.")
        return

    # Limpiamos animación previa de la cámara
    cmds.cutKey(cam, s=True)

    # Definimos posiciones de cámara (Cerca para que se vea bien)
    # Frame 101: Un poco a la derecha y abajo
    # Frame 131: Se mueve a la izquierda y sube
    frames = [101, 131]
    posiciones = [(12, 11, 14), (-6, 16, 16)]

    for i, f in enumerate(frames):
        cmds.currentTime(f)

        # 1. Posicionar cámara
        cmds.setAttr(f"{cam}.translate", *posiciones[i])

        # 2. Truco de TD: Apuntar a la esfera automáticamente
        cmds.viewLookAt(cam, pos=cmds.xform(target, q=True, ws=True, t=True))

        # 3. Setear Keys en Translate y Rotate
        cmds.setKeyframe(cam, at="translate")
        cmds.setKeyframe(cam, at="rotate")

    # Forzamos que sea lineal para que se note el "golpe" de inicio/fin
    cmds.keyTangent(cam, itt="linear", ott="linear")

    # IMPORTANTE: Nos aseguramos de que NO haya nada antes ni después
    cmds.setInfinity(cam, pri="constant", poi="constant")

    cmds.inViewMessage(amg="<hl>Step 3:</hl> Dynamic Framing (Static at borders)", pos="midCenter", fade=True)

anim_camera_pro_fixed_look()

# 4: FIX CAMERA FINAL

import maya.cmds as cmds

def fix_camera_final():
    cam = "reel_cam"
    if not cmds.objExists(cam):
        cmds.warning("No se encontró la cámara.")
        return

    # Atributos a reparar (movimiento y rotación)
    attrs = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]
    padding = 5  # Empatamos con los 5 frames de la esfera

    for attr in attrs:
        full_attr = f"{cam}.{attr}"

        # --- PRE-ROLL (Hacia atrás del frame 101) ---
        v101 = cmds.getAttr(full_attr, time=101)
        v102 = cmds.getAttr(full_attr, time=102)
        vel_start = v102 - v101 # Diferencia por 1 frame

        pre_val = v101 - (vel_start * padding)
        cmds.setKeyframe(cam, at=attr, t=101 - padding, v=pre_val)

        # --- POST-ROLL (Hacia adelante del frame 131) ---
        v131 = cmds.getAttr(full_attr, time=131)
        v130 = cmds.getAttr(full_attr, time=130)
        vel_end = v131 - v130 # Diferencia por 1 frame

        post_val = v131 + (vel_end * padding)
        cmds.setKeyframe(cam, at=attr, t=131 + padding, v=post_val)

    # Seteamos las tangentes a LINEAL para que la velocidad sea constante
    # en la entrada y salida, que es lo que el motor de render ama.
    cmds.keyTangent(cam, itt="linear", ott="linear")

    # Bonus: Extendemos el timeline para que se vea el fix
    cmds.playbackOptions(min=101 - padding, max=131 + padding)

    cmds.inViewMessage(amg="<hl>Step 4: FIX SUCCESSFUL</hl><br>Camera inertia restored for Motion Blur", pos="midCenter", fade=True)

fix_camera_final()

# Botón 6: Presenter Mode (Slow Playback)

import maya.cmds as cmds
import time

def slow_presenter_move(start=101, end=131, delay=0.1):
    """
    Mueve el timeline frame por frame con una pausa para que se vea pro.
    delay: tiempo en segundos entre cada frame (0.1 o 0.2 es ideal).
    """
    for f in range(start, end + 1):
        cmds.currentTime(f, edit=True)
        # Forzar refresco de la vista para que el Motion Blur se calcule
        cmds.refresh(force=True)
        time.sleep(delay)

# Ejecuta esto para grabar tu video:
slow_presenter_move(start=96, end=136, delay=0.15)


# Botón 7: Hot-Reload del Validator (para desarrollo)
import sys
import importlib

# Cambia esta ruta a tu carpeta local
REPO_SRC = "/Users/franciscocrespo/dev/github/maya-anim-td-reel-validator/src"
if REPO_SRC not in sys.path:
    sys.path.insert(0, REPO_SRC)

import anim_validator.checks
import anim_validator.app
importlib.reload(anim_validator.checks)
importlib.reload(anim_validator.app)

from anim_validator.app import show
show()

# Botón 8: Crear Issues de Demo (para desarrollo)

import maya.cmds as cmds
"""
def setup_production_disaster():
    
    # 1. Nombres con caracteres ilegales (muy común en importaciones de FBX)
    if not cmds.objExists("L_arm_Rig_@#_JNT"):
        cmds.joint(name="L_arm_Rig_@#_JNT")

    # 2. Camera clipping roto y ImagePlanes basura
    cam_name = "render_cam_01"
    if not cmds.objExists(cam_name):
        cam = cmds.camera(n=cam_name)[1]
        cmds.setAttr(f"{cam}.nearClipPlane", 25.0) # Esto hará que no se vea nada cerca
        ip = cmds.createNode("imagePlane")
        cmds.connectAttr(f"{ip}.message", f"{cam}.imagePlane[0]")

    # 3. Nodos con namespaces vacíos o raros
    if not cmds.objExists("temp:garbage_node"):
        try:
            cmds.namespace(add="temp")
            cmds.group(em=True, n="temp:garbage_node")
        except: pass

    cmds.inViewMessage(amg="<hl>Scene 'Corrupted' for Demo: 3 production issues added.</hl>", pos="midCenter", fade=True)

setup_production_disaster()

"""
import maya.cmds as cmds

def setup_reel_disaster():
    """Genera problemas técnicos reales para demostrar el validador."""
    # Para demo: fijamos un playback range "normal"
    cmds.playbackOptions(min=1, max=100)

    # 1) ERROR NAMING: Caracteres prohibidos
    illegal_name = "L_arm_@#_RIG_JNT"
    if not cmds.objExists(illegal_name):
        cmds.group(em=True, n=illegal_name)

    # 2) WARNING CAMERA: nearClipPlane demasiado alto
    cam_name = "render_cam_SHOT_01"
    if not cmds.objExists(cam_name):
        cam_nodes = cmds.camera(n=cam_name)
        cam_shape = cam_nodes[1]
    else:
        cam_shape = (cmds.listRelatives(cam_name, shapes=True, type="camera") or [None])[0]

    if cam_shape and cmds.objExists(cam_shape):
        cmds.setAttr(f"{cam_shape}.nearClipPlane", 15.0)

        # 3) WARNING IMAGEPLANE: conectado a la cámara
        ip = "basura_IP"
        if not cmds.objExists(ip):
            ip = cmds.createNode("imagePlane", n=ip)

        try:
            cmds.connectAttr(f"{ip}.message", f"{cam_shape}.imagePlane[0]", force=True)
        except Exception:
            pass

    # 4) WARNING ANIM: time unit incorrecto (para que el check lo detecte)
    # (si tu check espera "pal", esto lo rompe a propósito)
    try:
        cmds.currentUnit(time="ntsc")  # 30fps
    except Exception:
        pass

    # 5) WARNING ANIM: keys fuera del playback range
    ctrl = "demo_CTRL"
    if not cmds.objExists(ctrl):
        ctrl = cmds.spaceLocator(n=ctrl)[0]

    # Keys fuera del rango [1, 100]
    # Usamos translateX para que sea obvio y seleccionable
    cmds.setAttr(f"{ctrl}.translateX", 0)
    cmds.setKeyframe(ctrl, at="translateX", t=-10, v=0)
    cmds.setKeyframe(ctrl, at="translateX", t=10, v=5)
    cmds.setKeyframe(ctrl, at="translateX", t=200, v=0)

    cmds.inViewMessage(
        amg="<hl>SCENE PREPARED:</hl> 5 demo issues created.",
        pos="midCenter",
        fade=True
    )

setup_reel_disaster()
