"""The Plinko board.

PlinkoBook only tells the client where the five slots are; everything the arcade shows - the pins,
the side walls, the prize zones and every single frame of a ball's fall - is drawn from what the
server sends (ui.plinko.PlinkoObject reads it), so the board itself lives here.  The client plays
back the points one per frame and lights the slot the ball carries in PLINKO_ID.
"""
import math
import random

from ..es5.esobject import EsObject
from .keys import K

# ui.plinko.PlinkoObject
TYPE_BALL = 0
TYPE_COLLISION = 1
TYPE_PIN = 2
TYPE_REWARD = 3

WIDTH = 480.0
HEIGHT = 560.0
SLOTS = 5                       # PlinkoWindow.showHit only knows 0..4
PIN_ROWS = 7
FIRST_ROW_Y = 90.0
ROW_SPACING = 52.0
PIN_RADIUS = 6.0
BALL_RADIUS = 10.0
STEP = 6.0                      # how far a ball falls per animation frame
SLOT_WEIGHTS = (15, 25, 20, 25, 15)


def pick_slot():
    return random.choices(range(SLOTS), weights=SLOT_WEIGHTS)[0]


def pin_rows():
    """(y, [x...]) for each row of pins, staggered the way a plinko board is."""
    rows = []
    for row in range(PIN_ROWS):
        count = SLOTS + 1 if row % 2 == 0 else SLOTS
        gap = WIDTH / count
        rows.append((FIRST_ROW_Y + row * ROW_SPACING, [gap / 2 + index * gap for index in range(count)]))
    return rows


def board():
    """The pins, the side walls and the five prize zones, exactly as the client draws them."""
    objects = [_shape(TYPE_COLLISION, 0.0, 0.0, [(0.0, 0.0), (0.0, HEIGHT)]),
               _shape(TYPE_COLLISION, WIDTH, 0.0, [(0.0, 0.0), (0.0, HEIGHT)])]
    for row_y, positions in pin_rows():
        objects += [_circle(TYPE_PIN, x, row_y, PIN_RADIUS) for x in positions]
    width = WIDTH / SLOTS
    for slot in range(SLOTS):
        objects.append(_shape(TYPE_REWARD, (slot + 0.5) * width, HEIGHT - 30.0,
                              [(0.0, 0.0), (width - 4.0, 0.0), (0.0, 60.0), (width - 4.0, 60.0)]))
    return objects


def drop(slot):
    """One ball's whole fall: a point, a rotation and a contact flag for every frame."""
    rows = pin_rows()
    target = (slot + 0.5) * (WIDTH / SLOTS)
    start = WIDTH / 2 + random.uniform(-12.0, 12.0)
    xs, ys, rotations, contacts = [], [], [], []
    y, rotation = 20.0, 0
    while y < HEIGHT - 40.0:
        travelled = min(1.0, (y - 20.0) / (HEIGHT - 60.0))
        wobble = math.sin(travelled * math.pi * 3.5) * 22.0 * (1.0 - travelled)
        x = start + (target - start) * travelled + wobble
        hit = any(abs(y - row_y) < STEP / 2 for row_y, _ in rows)
        xs.append(int(round(max(BALL_RADIUS, min(WIDTH - BALL_RADIUS, x)))))
        ys.append(int(round(y)))
        rotation = (rotation + (18 if hit else 9)) % 360
        rotations.append(rotation)
        contacts.append(bool(hit))
        y += STEP
    return (_circle(TYPE_BALL, float(xs[0]), float(ys[0]), BALL_RADIUS)
            .set_integer_array(K.PLINKO_BALL_X_POINTS, xs)
            .set_integer_array(K.PLINKO_BALL_Y_POINTS, ys)
            .set_integer_array(K.PLINKO_BALL_ROTATIONS, rotations)
            .set_boolean_array(K.PLINKO_BALL_CONTACTS, contacts)
            .set_integer(K.PLINKO_ID, slot))


def _circle(kind, x, y, radius):
    return (EsObject().set_integer(K.PLINKO_OBJECT_TYPE, kind).set_float(K.PLINKO_OBJECT_X_POS, x)
            .set_float(K.PLINKO_OBJECT_Y_POS, y).set_float(K.PLINKO_OBJECT_RADIUS, radius))


def _shape(kind, x, y, vertices):
    """Two vertices draw a line, four draw a rectangle (PlinkoObject.fromEsObject)."""
    eso = (EsObject().set_integer(K.PLINKO_OBJECT_TYPE, kind).set_float(K.PLINKO_OBJECT_X_POS, x)
           .set_float(K.PLINKO_OBJECT_Y_POS, y))
    return eso.set_esobject_array(K.PLINKO_OBJECT_VERTICIES, [
        EsObject().set_float(K.PLINKO_OBJECT_X_VER, vx).set_float(K.PLINKO_OBJECT_Y_VER, vy)
        for vx, vy in vertices])
