import argparse
import glob
import json
import math
import os
import random
from array import array
import pygame

from settings import (
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    FPS,
    TITLE,
    SHIP_THRUST,
    SHIP_ROTATION_SPEED,
    SHIP_RADIUS,
    SHIP_DAMPING,
    BULLET_SPEED,
    BULLET_RANGE,
    BULLETS_DESTROY_SHIP,
    SHIP_BOUNCES_INSTEAD_OF_DYING,
    TURRET_BULLET_SPEED,
    TURRET_FIRE_COOLDOWN,
    SHIP_MAX_FUEL,
    SHIP_START_FUEL,
    FUEL_POD_AMOUNT,
    TRACTOR_FUEL_BURN_RATE,
    SCORE_ROCK,
    SCORE_PLINTH,
    SCORE_TURRET,
    SCORE_TANK,
    SCORE_REACTOR,
    EXTRA_LIFE_SCORE,
    TURRET_ACCURATE_CHANCE,
    TURRET_INACCURATE_SPREAD_MIN,
    TURRET_INACCURATE_SPREAD_MAX,
    TANK_AIM_SPREAD_MIN,
    TANK_AIM_SPREAD_MAX,
    ORBIT_SCROLL_SPACE,
    ORBIT_ESCAPE_MARGIN,
    REACTOR_ESCAPE_TIME,
    SHIP_NOSE_LEN_MULT,
    SHIP_BASE_BACK_MULT,
    SHIP_BASE_HALF_MULT,
    BULLET_SPAWN_OFFSET,
    TRACTOR_BEAM_LENGTH,
    TRACTOR_BEAM_HALF_WIDTH,
    TRACTOR_PULL_SPEED,
    TRACTOR_TARGET_OFFSET,
    ORB_PULSE_DURATION,
    ORB_PULSE_FAST_RATE,
    ORB_PULSE_SLOW_RATE,
    ORB_FALL_MAX_SPEED,
    ORB_FALL_DAMPING,
    THRUST_PARTICLES_PER_FRAME,
    THRUST_SPREAD_DEGREES,
    THRUST_SPEED_MIN,
    THRUST_SPEED_MAX,
    THRUST_PARTICLE_LIFE,
    TURRET_HIT_POINTS,
    TURRET_RADIUS,
    TURRET_EXPLOSION_PARTICLES,
    TURRET_SPARK_SPEED_MIN,
    TURRET_SPARK_SPEED_MAX,
    TURRET_SPARK_LIFE_MIN,
    TURRET_SPARK_LIFE_MAX,
    TANK_RADIUS,
    TANK_HALF_WIDTH,
    TANK_HALF_HEIGHT,
    TANK_SPEED,
    TANK_FIRE_RANGE,
    TANK_FIRE_COOLDOWN,
    TANK_BULLET_SPEED,
    TANKS_PER_LEVEL_MAX,
    ROCK_GRAVITY_SCALE,
    ROCK_AIR_DAMPING,
    ROCK_GROUND_DAMPING,
    ROCK_SLIDE_ACCEL,
    ROCK_MAX_FALL_SPEED,
    ROCK_TERRAIN_FRICTION,
    ROCK_STOP_SPEED,
    ROCK_PILE_MAX_COUNT,
    FUEL_PARTICLE_VALUE,
    FUEL_PARTICLE_SPAWN_INTERVAL,
    FUEL_PARTICLE_PULL_SPEED,
    FUEL_PARTICLE_FADE_TIME,
    REACTOR_HIT_POINTS,
    REACTOR_EXPLOSION_PARTICLES,
    REACTOR_HIT_SPARKS,
    REACTOR_DEBRIS_PARTICLES,
    LEVEL_SELF_DESTRUCT_DURATION,
    LEVEL_DESTRUCT_SPARK_BURST,
    LEVEL_DESTRUCT_FLAME_BURST,
    LEVEL_DESTRUCT_SPARKS_PER_FRAME,
    LEVEL_DESTRUCT_FLAMES_PER_FRAME,
    SHIP_DESTRUCTION_DURATION,
    SHIP_DESTRUCTION_SPARKS,
    SHIP_DESTRUCTION_FLAMES,
    SHIP_DEBRIS_PARTICLES,
    SHIP_BOUNCE_FLASH_DURATION,
    SHIP_BOUNCE_RESTITUTION,
    FORCE_FIELD_RADIUS,
    FORCE_FIELD_GLOW_RADIUS,
    SHIP_TRANSPORTER_MATERIALIZE_DURATION,
    SHIP_TRANSPORTER_DEMATERIALIZE_DURATION,
    SHIP_TRANSPORTER_BEAM_WIDTH,
    STARFIELD_FADE_START,
    STARFIELD_FADE_DISTANCE,
    STARFIELD_STAR_COUNT,
)

SOLID_SPATIAL_CELL_SIZE = 160.0
TRACTOR_BLOCKER_QUERY_PADDING = 120.0
SHIP_SOLID_KINDS = ("turret", "tank", "rock", "gate", "switch", "fuel_pod", "reactor")
BULLET_SOLID_KINDS = ("gate", "switch", "rock", "turret", "tank", "reactor")
TRACTOR_BLOCKER_KINDS = ("rock", "gate", "switch")

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def load_json(path):
    """Load and return JSON data from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_playable_level_data(level_data):
    cave_lines = level_data.get("cave_lines")
    return isinstance(cave_lines, list) and len(cave_lines) > 0


def point_to_segment_distance(px, py, ax, ay, bx, by):
    """Return the shortest distance from point P to line segment AB."""
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = (apx * abx + apy * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    closest_x = ax + t * abx
    closest_y = ay + t * aby
    return math.hypot(px - closest_x, py - closest_y)


def closest_point_on_segment(px, py, ax, ay, bx, by):
    """Return the closest point on line segment AB to point P."""
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return ax, ay

    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))
    return ax + t * abx, ay + t * aby


def rotate_point(px, py, cx, cy, angle_radians):
    dx = px - cx
    dy = py - cy
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return (
        cx + dx * cos_a - dy * sin_a,
        cy + dx * sin_a + dy * cos_a,
    )


def line_circle_collision(line, cx, cy, radius):
    """True if the circle touches the line segment."""
    (ax, ay), (bx, by) = line
    return point_to_segment_distance(cx, cy, ax, ay, bx, by) <= radius


def circle_rect_collision(cx, cy, radius, rx, ry, half_w, half_h):
    nearest_x = max(rx - half_w, min(cx, rx + half_w))
    nearest_y = max(ry - half_h, min(cy, ry + half_h))
    return math.hypot(cx - nearest_x, cy - nearest_y) <= radius


def orientation(ax, ay, bx, by, cx, cy):
    value = (by - ay) * (cx - bx) - (bx - ax) * (cy - by)
    if abs(value) < 1e-6:
        return 0
    return 1 if value > 0.0 else 2


def on_segment(ax, ay, bx, by, cx, cy):
    return (
        min(ax, cx) - 1e-6 <= bx <= max(ax, cx) + 1e-6
        and min(ay, cy) - 1e-6 <= by <= max(ay, cy) + 1e-6
    )


def segments_intersect(a_start, a_end, b_start, b_end):
    """Return True if line segments AB and CD intersect."""
    ax, ay = a_start
    bx, by = a_end
    cx, cy = b_start
    dx, dy = b_end

    o1 = orientation(ax, ay, bx, by, cx, cy)
    o2 = orientation(ax, ay, bx, by, dx, dy)
    o3 = orientation(cx, cy, dx, dy, ax, ay)
    o4 = orientation(cx, cy, dx, dy, bx, by)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(ax, ay, cx, cy, bx, by):
        return True
    if o2 == 0 and on_segment(ax, ay, dx, dy, bx, by):
        return True
    if o3 == 0 and on_segment(cx, cy, ax, ay, dx, dy):
        return True
    if o4 == 0 and on_segment(cx, cy, bx, by, dx, dy):
        return True
    return False


def segment_intersection_distance(a_start, a_end, b_start, b_end):
    """Return the distance from A start to the segment intersection, or None."""
    ax, ay = a_start
    bx, by = a_end
    cx, cy = b_start
    dx, dy = b_end

    r_x = bx - ax
    r_y = by - ay
    s_x = dx - cx
    s_y = dy - cy
    denom = r_x * s_y - r_y * s_x

    if abs(denom) < 1e-6:
        return None

    diff_x = cx - ax
    diff_y = cy - ay
    t = (diff_x * s_y - diff_y * s_x) / denom
    u = (diff_x * r_y - diff_y * r_x) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return math.hypot(r_x, r_y) * t
    return None


def chaikin_smooth_points(points, iterations=2):
    """Round a polyline into a softer curve using Chaikin corner cutting."""
    if len(points) < 3:
        return list(points)

    smoothed = [tuple(points[0]), tuple(points[-1])]
    current = [tuple(point) for point in points]

    for _ in range(iterations):
        next_points = [current[0]]
        for index in range(len(current) - 1):
            ax, ay = current[index]
            bx, by = current[index + 1]
            q = (ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25)
            r = (ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75)
            next_points.extend((q, r))
        next_points.append(current[-1])
        current = next_points

    return current


def smooth_cave_lines(lines, iterations=2):
    """Smooth connected non-horizontal terrain chains while preserving flat platforms."""
    if not lines:
        return []

    chains = []
    current_chain = [lines[0]]
    for line in lines[1:]:
        if current_chain[-1][1] == line[0]:
            current_chain.append(line)
        else:
            chains.append(current_chain)
            current_chain = [line]
    chains.append(current_chain)

    smoothed_lines = []
    for chain in chains:
        if len(chain) == 1 or all(abs(segment[0][1] - segment[1][1]) < 0.01 for segment in chain):
            smoothed_lines.extend(chain)
            continue

        points = [chain[0][0]]
        points.extend(segment[1] for segment in chain)
        smoothed_points = chaikin_smooth_points(points, iterations=iterations)
        for start, end in zip(smoothed_points, smoothed_points[1:]):
            smoothed_lines.append((start, end))

    return smoothed_lines


def smooth_cave_line_records(records, iterations=2):
    if not records:
        return []

    chains = []
    current_chain = [records[0]]
    for record in records[1:]:
        if current_chain[-1]["points"][1] == record["points"][0] and current_chain[-1]["colour"] == record["colour"]:
            current_chain.append(record)
        else:
            chains.append(current_chain)
            current_chain = [record]
    chains.append(current_chain)

    smoothed_records = []
    for chain in chains:
        segments = [tuple(record["points"]) for record in chain]
        colour = chain[0]["colour"]
        if len(segments) == 1 or all(abs(segment[0][1] - segment[1][1]) < 0.01 for segment in segments):
            smoothed_records.extend({"points": [segment[0], segment[1]], "colour": colour} for segment in segments)
            continue

        points = [segments[0][0]]
        points.extend(segment[1] for segment in segments)
        smoothed_points = chaikin_smooth_points(points, iterations=iterations)
        for start, end in zip(smoothed_points, smoothed_points[1:]):
            smoothed_records.append({"points": [start, end], "colour": colour})

    return smoothed_records


def roughen_floor_lines(lines, world_max_y, seed_key):
    """Add downward bumps to the lowest horizontal floor segments."""
    if not lines:
        return []

    rng = random.Random(f"{seed_key}-floor-roughness")
    roughened = []
    floor_threshold = world_max_y - 80.0

    for line in lines:
        (ax, ay), (bx, by) = line
        if abs(ay - by) >= 0.01 or ay < floor_threshold:
            roughened.append(line)
            continue

        line_length = abs(bx - ax)
        if line_length < 120.0:
            roughened.append(line)
            continue

        direction = 1.0 if bx >= ax else -1.0
        span = line_length
        step = 36.0
        point_count = max(4, int(span / step))
        points = []
        for index in range(point_count + 1):
            t = index / point_count
            x = ax + direction * span * t
            envelope = math.sin(math.pi * t)
            bump = (
                math.sin(t * math.tau * rng.randint(2, 4) + rng.uniform(0.0, math.tau)) * 7.0
                + math.sin(t * math.tau * rng.randint(4, 7) + rng.uniform(0.0, math.tau)) * 3.5
                + rng.uniform(-2.5, 2.5)
            )
            y = ay + max(0.0, bump * envelope + envelope * rng.uniform(5.0, 11.0))
            points.append((x, y))

        smoothed_points = chaikin_smooth_points(points, iterations=2)
        for start, end in zip(smoothed_points, smoothed_points[1:]):
            roughened.append((start, end))

    return roughened


def roughen_floor_line_records(records, world_max_y, seed_key):
    if not records:
        return []

    rng = random.Random(f"{seed_key}-floor-roughness")
    roughened = []
    floor_threshold = world_max_y - 80.0

    for record in records:
        (ax, ay), (bx, by) = record["points"]
        colour = record["colour"]
        if abs(ay - by) >= 0.01 or ay < floor_threshold:
            roughened.append({"points": [(ax, ay), (bx, by)], "colour": colour})
            continue

        line_length = abs(bx - ax)
        if line_length < 120.0:
            roughened.append({"points": [(ax, ay), (bx, by)], "colour": colour})
            continue

        direction = 1.0 if bx >= ax else -1.0
        span = line_length
        step = 36.0
        point_count = max(4, int(span / step))
        points = []
        for index in range(point_count + 1):
            t = index / point_count
            x = ax + direction * span * t
            envelope = math.sin(math.pi * t)
            bump = (
                math.sin(t * math.tau * rng.randint(2, 4) + rng.uniform(0.0, math.tau)) * 7.0
                + math.sin(t * math.tau * rng.randint(4, 7) + rng.uniform(0.0, math.tau)) * 3.5
                + rng.uniform(-2.5, 2.5)
            )
            y = ay + max(0.0, bump * envelope + envelope * rng.uniform(5.0, 11.0))
            points.append((x, y))

        smoothed_points = chaikin_smooth_points(points, iterations=2)
        for start, end in zip(smoothed_points, smoothed_points[1:]):
            roughened.append({"points": [start, end], "colour": colour})

    return roughened


def load_controls(path="controls.json"):
    """
    Load control bindings from JSON and convert names like 'K_UP'
    into pygame key constants.
    """
    raw = load_json(path)
    controls = {}

    for action, key_name in raw.items():
        controls[action] = getattr(pygame, key_name)

    return controls


def format_key_binding(key_code):
    """Return a short label suitable for HUD instructions."""
    return pygame.key.name(key_code).upper()


def load_sprite(path, fallback_size=(32, 32), colour=(255, 255, 255)):
    """
    Try to load an image. If it does not exist yet, create a simple
    placeholder surface so the game still works.
    """
    if os.path.exists(path):
        return pygame.image.load(path).convert_alpha()

    surface = pygame.Surface(fallback_size, pygame.SRCALPHA)
    pygame.draw.rect(surface, colour, surface.get_rect(), border_radius=6)
    return surface


def create_tone_sound(frequencies, duration, volume=0.35, sample_rate=22050, decay=3.0):
    """Create a short procedural tone so the game has usable sounds without asset files."""
    if not pygame.mixer.get_init():
        return None

    sample_count = max(1, int(sample_rate * duration))
    amplitude = int(32767 * max(0.0, min(1.0, volume)))
    frequencies = tuple(frequencies)
    buffer = array("h")

    for i in range(sample_count):
        t = i / sample_rate
        envelope = math.exp(-decay * t / max(duration, 0.001))
        sample = 0.0
        for freq in frequencies:
            sample += math.sin(math.tau * freq * t)
        sample /= max(1, len(frequencies))
        buffer.append(int(amplitude * sample * envelope))

    return pygame.mixer.Sound(buffer=buffer)


def create_noise_sound(duration, volume=0.35, sample_rate=22050, decay=1.5, smoothness=0.82, drive=2.4):
    """Create filtered noise for hiss or exhaust-like sounds."""
    if not pygame.mixer.get_init():
        return None

    sample_count = max(1, int(sample_rate * duration))
    amplitude = int(32767 * max(0.0, min(1.0, volume)))
    buffer = array("h")
    previous = 0.0

    for i in range(sample_count):
        t = i / sample_rate
        envelope = math.exp(-decay * t / max(duration, 0.001))
        white = random.uniform(-1.0, 1.0)
        previous = previous * smoothness + white * (1.0 - smoothness)
        high_pass = white - previous
        sample = max(-1.0, min(1.0, high_pass * drive))
        buffer.append(int(amplitude * sample * envelope))

    return pygame.mixer.Sound(buffer=buffer)


def create_echo_tone_sound(frequencies, duration, volume=0.35, sample_rate=22050, decay=2.5, echoes=None):
    """Create a bright procedural ping with a simple echo tail."""
    if not pygame.mixer.get_init():
        return None

    if echoes is None:
        echoes = (
            (0.0, 1.0),
            (0.12, 0.45),
            (0.24, 0.22),
        )

    sample_count = max(1, int(sample_rate * duration))
    amplitude = int(32767 * max(0.0, min(1.0, volume)))
    frequencies = tuple(frequencies)
    buffer = array("h")

    for i in range(sample_count):
        t = i / sample_rate
        sample = 0.0
        for delay, gain in echoes:
            shifted_t = t - delay
            if shifted_t < 0.0:
                continue
            envelope = math.exp(-decay * shifted_t / max(duration, 0.001))
            partial = 0.0
            for freq in frequencies:
                partial += math.sin(math.tau * freq * shifted_t)
            partial /= max(1, len(frequencies))
            sample += partial * envelope * gain
        sample = max(-1.0, min(1.0, sample))
        buffer.append(int(amplitude * sample))

    return pygame.mixer.Sound(buffer=buffer)


def create_bloop_sound(duration, volume=0.35, sample_rate=22050):
    """Create a rounded descending bloop for liquid or pop-like UI cues."""
    if not pygame.mixer.get_init():
        return None

    sample_count = max(1, int(sample_rate * duration))
    amplitude = int(32767 * max(0.0, min(1.0, volume)))
    buffer = array("h")

    for i in range(sample_count):
        t = i / sample_rate
        phase = t / max(duration, 0.001)
        wobble = math.sin(math.tau * (7.8 * t)) * (1.0 - min(1.0, phase) * 0.35)
        warble = math.sin(math.tau * (14.0 * t) + 0.7) * (1.0 - min(1.0, phase) * 0.6)
        base_freq = 520.0 - 360.0 * phase + wobble * 32.0 + warble * 12.0
        overtone = base_freq * 1.92
        bubble_freq = 230.0 - 125.0 * phase + wobble * 16.0
        sub_bloop = 118.0 - 52.0 * phase + warble * 6.0
        envelope = math.exp(-4.1 * phase) * (1.0 - 0.26 * math.sin(math.pi * min(1.0, phase)))
        sample = (
            math.sin(math.tau * base_freq * t)
            + 0.48 * math.sin(math.tau * overtone * t + 0.35)
            + 0.32 * math.sin(math.tau * bubble_freq * t + 1.1)
            + 0.18 * math.sin(math.tau * sub_bloop * t + 2.1)
        )
        echo_t = t - 0.045
        if echo_t > 0.0:
            echo_phase = echo_t / max(duration, 0.001)
            echo_freq = 365.0 - 210.0 * echo_phase + warble * 8.0
            sample += 0.54 * math.sin(math.tau * echo_freq * echo_t + 0.4) * math.exp(-5.8 * echo_phase)
        glorp = math.sin(math.tau * (82.0 + wobble * 7.0) * t + 2.4)
        sample += 0.18 * glorp * math.exp(-7.0 * phase)
        sample = max(-1.0, min(1.0, sample * 0.66))
        buffer.append(int(amplitude * sample * envelope))

    return pygame.mixer.Sound(buffer=buffer)


def create_fuel_pod_sprite(size=(38, 54)):
    """Create a smaller hollow fuel pod sprite with a clear label."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)

    outer_rect = pygame.Rect(0, 0, width, height)
    body_rect = outer_rect.inflate(-8, -10)
    inner_rect = body_rect.inflate(-8, -12)

    outline_colour = (120, 255, 180)
    accent_colour = (70, 160, 120)
    text_colour = (210, 255, 230)

    pygame.draw.rect(surface, outline_colour, body_rect, width=3, border_radius=8)
    pygame.draw.rect(surface, accent_colour, inner_rect, width=2, border_radius=5)

    cap_width = width * 0.46
    cap_rect = pygame.Rect(0, 0, cap_width, 8)
    cap_rect.midbottom = (width // 2, body_rect.top + 4)
    pygame.draw.rect(surface, outline_colour, cap_rect, width=2, border_radius=3)

    band_y = body_rect.centery + 3
    pygame.draw.line(surface, accent_colour, (body_rect.left + 5, band_y), (body_rect.right - 5, band_y), 2)

    font = pygame.font.SysFont(None, 15, bold=True)
    label = font.render("FUEL", True, text_colour)
    label_rect = label.get_rect(center=(width // 2, body_rect.centery - 8))
    surface.blit(label, label_rect)

    return surface


def create_reactor_sprite(size=(60, 60)):
    """Create an abstract reactor silhouette inspired by a damaged RBMK block."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)

    tower_rect = pygame.Rect(0, 0, int(width * 0.72), int(height * 0.78))
    tower_rect.midbottom = (width // 2, height - 4)
    top_rect = pygame.Rect(0, 0, int(width * 0.9), int(height * 0.18))
    top_rect.midtop = (width // 2, 8)
    core_rect = tower_rect.inflate(-16, -18)

    pygame.draw.rect(surface, (126, 128, 136), tower_rect, border_radius=6)
    pygame.draw.rect(surface, (164, 167, 176), top_rect, border_radius=4)
    pygame.draw.rect(surface, (82, 86, 94), core_rect, border_radius=4)

    # Broken roof slabs and a glowing core read as "ruined reactor" without realism.
    pygame.draw.polygon(
        surface,
        (178, 180, 186),
        [(10, 16), (30, 10), (34, 18), (18, 22)],
    )
    pygame.draw.polygon(
        surface,
        (150, 152, 158),
        [(34, 18), (52, 11), (50, 24), (36, 23)],
    )
    pygame.draw.circle(surface, (255, 157, 50), (width // 2, int(height * 0.55)), 10)
    pygame.draw.circle(surface, (255, 220, 110), (width // 2, int(height * 0.55)), 5)
    pygame.draw.line(surface, (95, 220, 255), (19, 34), (41, 34), 2)
    pygame.draw.line(surface, (95, 220, 255), (19, 42), (41, 42), 2)

    return surface


def draw_glow_circle(screen, colour, center, radius, glow_radius, alpha):
    """Draw a simple additive-looking glow using translucent circles."""
    glow_surface = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
    glow_colour = (*colour, alpha)
    pygame.draw.circle(glow_surface, glow_colour, (glow_radius, glow_radius), glow_radius)
    glow_surface = pygame.transform.smoothscale(
        glow_surface,
        (glow_radius * 2, glow_radius * 2),
    )
    screen.blit(glow_surface, (center[0] - glow_radius, center[1] - glow_radius), special_flags=pygame.BLEND_ALPHA_SDL2)


def create_orb_sprite(diameter=40):
    """Create a glowing gold orb collectible."""
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    center = (diameter // 2, diameter // 2)
    radius = diameter // 2
    pygame.draw.circle(surface, (255, 210, 80, 70), center, radius)
    pygame.draw.circle(surface, (255, 225, 110, 130), center, radius - 4)
    pygame.draw.circle(surface, (255, 236, 160), center, radius - 8)
    pygame.draw.circle(surface, (255, 248, 220), center, radius - 14)
    return surface


# ------------------------------------------------------------
# Game objects
# ------------------------------------------------------------

class Bullet:
    def __init__(self, x, y, vx, vy, from_player=True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.from_player = from_player
        self.alive = True
        self.radius = 3
        self.distance_travelled = 0.0

    def update(self, dt, level):
        old_x = self.x
        old_y = self.y
        step_x = self.vx * dt
        step_y = self.vy * dt
        new_x = self.x + step_x
        new_y = self.y + step_y
        self.distance_travelled += math.hypot(step_x, step_y)

        if self.distance_travelled >= BULLET_RANGE:
            self.alive = False
            return

        min_x, max_x, min_y, max_y = level.world_bounds()
        if (
            new_y < min_y - 120
            or new_y > max_y + 120
        ):
            self.alive = False
            return

        path_start = (old_x, old_y)
        path_end = (new_x, new_y)
        for line in level.collision_lines():
            if line_circle_collision(line, new_x, new_y, self.radius):
                self.alive = False
                return
            (ax, ay), (bx, by) = line
            if segment_intersection_distance(path_start, path_end, (ax, ay), (bx, by)) is not None:
                self.alive = False
                return
            if point_to_segment_distance(ax, ay, old_x, old_y, new_x, new_y) <= self.radius:
                self.alive = False
                return
            if point_to_segment_distance(bx, by, old_x, old_y, new_x, new_y) <= self.radius:
                self.alive = False
                return

        self.x = level.wrap_x(new_x, self.radius)
        self.y = new_y

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
        glow_colour = (255, 170, 80) if self.from_player else (255, 110, 90)
        draw_glow_circle(screen, glow_colour, center, self.radius, self.radius + 7, 80)
        draw_glow_circle(screen, glow_colour, center, self.radius, self.radius + 3, 130)
        pygame.draw.circle(screen, (255, 220, 120), center, self.radius)


class ThrustParticle:
    def __init__(self, x, y, vx, vy, life=THRUST_PARTICLE_LIFE):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = random.uniform(1.0, 2.6)
        self.brightness = random.randint(150, 230)
        self.alive = True

    def update(self, dt):
        self.vx *= 0.96
        self.vy *= 0.96
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        t = max(0.0, min(1.0, self.life / self.max_life))
        radius = max(1, int(self.size * t + 0.5))
        shade = int(self.brightness * t)
        colour = (shade, shade, min(255, shade + 15))
        pygame.draw.circle(screen, colour, (int(self.x + offset_x - camera_x), int(self.y - camera_y)), radius)


class SparkParticle:
    def __init__(self, x, y, vx, vy, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = random.uniform(1.0, 3.2)
        self.alive = True

    def update(self, dt):
        self.vx *= 0.95
        self.vy = self.vy * 0.95 + 120.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        t = max(0.0, min(1.0, self.life / self.max_life))
        radius = max(1, int(self.size * t + 0.5))
        colour = (255, int(220 * t), int(120 * t))
        pygame.draw.circle(screen, colour, (int(self.x + offset_x - camera_x), int(self.y - camera_y)), radius)


class FlameParticle:
    def __init__(self, x, y, vx, vy, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = random.uniform(2.0, 4.2)
        self.alive = True

    def update(self, dt):
        self.vx *= 0.94
        self.vy = self.vy * 0.92 - 70.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        t = max(0.0, min(1.0, self.life / self.max_life))
        radius = max(1, int(self.size * t + 0.5))
        colour = (255, int(140 + 70 * t), int(30 + 50 * t))
        pygame.draw.circle(screen, colour, (int(self.x + offset_x - camera_x), int(self.y - camera_y)), radius)


class ReactorDebrisParticle:
    def __init__(self, x, y, vx, vy, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.width = random.uniform(6.0, 14.0)
        self.height = random.uniform(4.0, 9.0)
        self.angle = random.uniform(0.0, 360.0)
        self.spin = random.uniform(-380.0, 380.0)
        self.alive = True

    def update(self, dt):
        self.vx *= 0.985
        self.vy += 220.0 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle += self.spin * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        t = max(0.0, min(1.0, self.life / self.max_life))
        debris = pygame.Surface((int(self.width + 4), int(self.height + 4)), pygame.SRCALPHA)
        colour = (int(170 * t), int(174 * t), int(182 * t))
        glow = (255, int(120 * t), int(40 * t), int(110 * t))
        rect = pygame.Rect(2, 2, int(self.width), int(self.height))
        pygame.draw.rect(debris, colour, rect, border_radius=2)
        pygame.draw.rect(debris, glow, rect.inflate(2, 2), width=1, border_radius=3)
        rotated = pygame.transform.rotate(debris, self.angle)
        pos = rotated.get_rect(center=(int(self.x + offset_x - camera_x), int(self.y - camera_y)))
        screen.blit(rotated, pos)


class Ship:
    def __init__(self, x, y, sprite):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.angle = -90.0
        self.radius = SHIP_RADIUS
        self.sprite = sprite
        self.alive = True
        self.fuel = min(SHIP_START_FUEL, SHIP_MAX_FUEL)
        self.thrusting = False
        self.tractor_active = False
        self.force_field_active = False
        self.has_orb = False
        self.orb_pulse_time = 0.0
        self.orb_pulse_phase = 0.0
        self.bounce_flash_time = 0.0
        self.transporter_state = None
        self.transporter_time = 0.0
        self.transporter_duration = 0.0

    def start_materialize(self):
        self.transporter_state = 'materialize'
        self.transporter_duration = SHIP_TRANSPORTER_MATERIALIZE_DURATION
        self.transporter_time = self.transporter_duration
        self.vx = 0.0
        self.vy = 0.0
        self.thrusting = False
        self.tractor_active = False
        self.force_field_active = False

    def start_dematerialize(self):
        self.transporter_state = 'dematerialize'
        self.transporter_duration = SHIP_TRANSPORTER_DEMATERIALIZE_DURATION
        self.transporter_time = self.transporter_duration
        self.vx = 0.0
        self.vy = 0.0
        self.thrusting = False
        self.tractor_active = False
        self.force_field_active = False

    def is_transporting(self):
        return self.transporter_state is not None and self.transporter_time > 0.0

    def is_operational(self):
        return self.alive and not self.is_transporting()

    def update_transporter(self, dt):
        if not self.is_transporting():
            return False
        self.transporter_time = max(0.0, self.transporter_time - dt)
        if self.transporter_time > 0.0:
            return False
        self.transporter_state = None
        self.transporter_duration = 0.0
        return True

    def update(self, dt, keys, controls, level):
        self.thrusting = False
        self.tractor_active = keys[controls['tractor']] and self.fuel > 0.0
        self.force_field_active = self.tractor_active and self.alive and not self.is_transporting()
        self.orb_pulse_time = max(0.0, self.orb_pulse_time - dt)
        self.bounce_flash_time = max(0.0, self.bounce_flash_time - dt)
        if self.has_orb:
            pulse_rate = ORB_PULSE_FAST_RATE if self.orb_pulse_time > 0.0 else ORB_PULSE_SLOW_RATE
            self.orb_pulse_phase = (self.orb_pulse_phase + dt * pulse_rate) % 1.0

        if keys[controls['rotate_left']]:
            self.angle -= SHIP_ROTATION_SPEED * dt
        if keys[controls['rotate_right']]:
            self.angle += SHIP_ROTATION_SPEED * dt

        self.vy += level.gravity * dt

        if keys[controls['thrust']] and self.fuel > 0:
            angle_rad = math.radians(self.angle)
            thrust_x = math.cos(angle_rad) * SHIP_THRUST
            thrust_y = math.sin(angle_rad) * SHIP_THRUST
            self.vx += thrust_x * dt
            self.vy += thrust_y * dt
            self.fuel = max(0.0, self.fuel - 12.0 * dt)
            self.thrusting = True

        if self.tractor_active:
            self.fuel = max(0.0, self.fuel - TRACTOR_FUEL_BURN_RATE * dt)
            if self.fuel <= 0.0:
                self.tractor_active = False
                self.force_field_active = False

        self.vx *= SHIP_DAMPING
        self.vy *= SHIP_DAMPING

        collision_radius = self.collision_radius()
        steps = max(1, int(math.ceil(max(abs(self.vx), abs(self.vy)) * dt / max(1.0, collision_radius * 0.35))))
        step_dt = dt / steps
        for _ in range(steps):
            prev_x = self.x
            prev_y = self.y
            self.x += self.vx * step_dt
            self.y += self.vy * step_dt
            self.x = level.wrap_x(self.x, self.radius)

            collided_line = None
            for line in level.collision_lines():
                if line_circle_collision(line, self.x, self.y, collision_radius):
                    collided_line = line
                    break

            if collided_line is None:
                continue

            if self.can_bounce():
                self.x = prev_x
                self.y = prev_y
                self.bounce_off_line(collided_line, level)
            else:
                self.alive = False
            break

    def can_bounce(self):
        return self.force_field_active or SHIP_BOUNCES_INSTEAD_OF_DYING

    def force_field_hit_radius(self):
        return max(self.radius, FORCE_FIELD_RADIUS)

    def collision_radius(self):
        if self.can_bounce():
            return self.force_field_hit_radius()
        return self.radius

    def get_triangle_points(self):
        angle_rad = math.radians(self.angle)
        ux = math.cos(angle_rad)
        uy = math.sin(angle_rad)
        px = -uy
        py = ux

        nose_len = self.radius * SHIP_NOSE_LEN_MULT
        base_back = self.radius * SHIP_BASE_BACK_MULT
        half_base = self.radius * SHIP_BASE_HALF_MULT

        nose = (self.x + ux * nose_len, self.y + uy * nose_len)
        base_centre = (self.x - ux * base_back, self.y - uy * base_back)
        base_left = (base_centre[0] + px * half_base, base_centre[1] + py * half_base)
        base_right = (base_centre[0] - px * half_base, base_centre[1] - py * half_base)

        return nose, base_left, base_right

    def get_nose_position(self, offset=0.0):
        nose, _, _ = self.get_triangle_points()
        angle_rad = math.radians(self.angle)
        return (
            nose[0] + math.cos(angle_rad) * offset,
            nose[1] + math.sin(angle_rad) * offset,
        )

    def get_base_centre(self):
        _, base_left, base_right = self.get_triangle_points()
        return ((base_left[0] + base_right[0]) * 0.5, (base_left[1] + base_right[1]) * 0.5)

    def get_base_points(self):
        _, base_left, base_right = self.get_triangle_points()
        return base_left, base_right

    def get_tractor_anchor(self, offset=0.0):
        base_x, base_y = self.get_base_centre()
        angle_rad = math.radians(self.angle)
        down_x = -math.cos(angle_rad)
        down_y = -math.sin(angle_rad)
        return (
            base_x + down_x * offset,
            base_y + down_y * offset,
        )

    def collect_orb(self):
        self.has_orb = True
        self.orb_pulse_time = ORB_PULSE_DURATION

    def trigger_bounce_flash(self):
        self.bounce_flash_time = SHIP_BOUNCE_FLASH_DURATION

    def bounce_off_normal(self, nx, ny, separation=4.0):
        length = math.hypot(nx, ny)
        if length == 0.0:
            nx, ny = 0.0, -1.0
        else:
            nx /= length
            ny /= length
        incoming = self.vx * nx + self.vy * ny
        if incoming > 0.0:
            nx *= -1.0
            ny *= -1.0
            incoming = self.vx * nx + self.vy * ny
        self.vx -= (1.0 + SHIP_BOUNCE_RESTITUTION) * incoming * nx
        self.vy -= (1.0 + SHIP_BOUNCE_RESTITUTION) * incoming * ny
        self.vx *= 0.92
        self.vy *= 0.92
        self.x += nx * separation
        self.y += ny * separation
        self.trigger_bounce_flash()

    def terrain_collision_contacts(self, level, collision_radius, x=None, y=None):
        px = self.x if x is None else x
        py = self.y if y is None else y
        contacts = []
        for line in level.collision_lines():
            if not line_circle_collision(line, px, py, collision_radius):
                continue
            (ax, ay), (bx, by) = line
            cx, cy = closest_point_on_segment(px, py, ax, ay, bx, by)
            nx = px - cx
            ny = py - cy
            dist = math.hypot(nx, ny)
            penetration = collision_radius - dist
            if dist > 1e-6:
                nx /= dist
                ny /= dist
            else:
                seg_dx = bx - ax
                seg_dy = by - ay
                seg_len = math.hypot(seg_dx, seg_dy)
                if seg_len <= 1e-6:
                    continue
                nx = -seg_dy / seg_len
                ny = seg_dx / seg_len
                penetration = max(penetration, collision_radius * 0.35)
            contacts.append((nx, ny, max(0.0, penetration)))
        return contacts

    def bounce_off_line(self, line, level):
        contacts = self.terrain_collision_contacts(level, self.collision_radius())
        if not contacts:
            (ax, ay), (bx, by) = line
            cx, cy = closest_point_on_segment(self.x, self.y, ax, ay, bx, by)
            nx = self.x - cx
            ny = self.y - cy
            if nx == 0.0 and ny == 0.0:
                seg_dx = bx - ax
                seg_dy = by - ay
                seg_len = math.hypot(seg_dx, seg_dy)
                if seg_len > 0.0:
                    nx = -seg_dy / seg_len
                    ny = seg_dx / seg_len
            self.bounce_off_normal(nx, ny)
            return

        total_nx = 0.0
        total_ny = 0.0
        max_penetration = 0.0
        for nx, ny, penetration in contacts:
            weight = max(1.0, penetration * 3.0)
            total_nx += nx * weight
            total_ny += ny * weight
            max_penetration = max(max_penetration, penetration)

        self.bounce_off_normal(total_nx, total_ny, separation=max(4.0, max_penetration + 2.5))

        # Resolve any remaining seam overlap so the shield does not get nudged through tiny gaps.
        for _ in range(3):
            contacts = self.terrain_collision_contacts(level, self.collision_radius())
            if not contacts:
                break
            resolve_nx = sum(nx * max(1.0, penetration * 3.0) for nx, _, penetration in contacts)
            resolve_ny = sum(ny * max(1.0, penetration * 3.0) for _, ny, penetration in contacts)
            resolve_penetration = max(penetration for _, _, penetration in contacts)
            length = math.hypot(resolve_nx, resolve_ny)
            if length <= 1e-6:
                break
            self.x += (resolve_nx / length) * (resolve_penetration + 0.8)
            self.y += (resolve_ny / length) * (resolve_penetration + 0.8)
        self.trigger_bounce_flash()

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        nose, base_left, base_right = self.get_triangle_points()
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        points = [
            (nose[0] + offset_x - camera_x, nose[1] - camera_y),
            (base_left[0] + offset_x - camera_x, base_left[1] - camera_y),
            (base_right[0] + offset_x - camera_x, base_right[1] - camera_y),
        ]
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))

        transport_phase = None
        linear_phase = 1.0
        if self.is_transporting():
            if self.transporter_duration > 0.0:
                linear_phase = 1.0 - (self.transporter_time / self.transporter_duration)
            linear_phase = max(0.0, min(1.0, linear_phase))
            eased_phase = linear_phase * linear_phase * (3.0 - 2.0 * linear_phase)
            if self.transporter_state == 'dematerialize':
                eased_phase = 1.0 - eased_phase
            transport_phase = eased_phase

            min_y = min(point[1] for point in points)
            max_y = max(point[1] for point in points)
            height = max(1, int(math.ceil(max_y - min_y)))
            visible_height = max(1, int(height * max(0.04, transport_phase)))
            clip_top = int(max_y - visible_height)
            clip_rect = pygame.Rect(0, clip_top, SCREEN_WIDTH, max(1, int(max_y - clip_top + 3)))

            for glow_index, inflate in enumerate((16, 10, 5)):
                glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                alpha = int((70 - glow_index * 16) * max(0.2, transport_phase))
                glow_points = []
                for px, py in points:
                    dx = px - center[0]
                    dy = py - center[1]
                    dist = max(1.0, math.hypot(dx, dy))
                    scale = 1.0 + (inflate / dist) * (1.0 - transport_phase + 0.2)
                    glow_points.append((center[0] + dx * scale, center[1] + dy * scale))
                pygame.draw.polygon(glow_surface, (150, 235, 255, alpha), glow_points)
                screen.blit(glow_surface, (0, 0))

            mote_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for idx in range(14):
                seed = idx * 0.71
                travel = ((linear_phase * 1.4) + seed) % 1.0
                if self.transporter_state == 'dematerialize':
                    travel = 1.0 - travel
                horizontal = math.sin(seed * 5.1 + linear_phase * math.tau * 1.3) * (self.radius + 12)
                particle_x = center[0] + horizontal
                particle_y = center[1] + self.radius + 30 - travel * (self.radius * 5.5)
                radius = 2 + (idx % 2)
                glow_alpha = int(90 + 110 * max(0.25, transport_phase))
                colour = (160, 240, 255, glow_alpha) if idx % 3 else (255, 205, 205, int(glow_alpha * 0.85))
                pygame.draw.circle(mote_surface, colour, (int(particle_x), int(particle_y)), radius + 2)
                core = (220, 250, 255) if idx % 3 else (255, 235, 235)
                pygame.draw.circle(mote_surface, core, (int(particle_x), int(particle_y)), radius)
            screen.blit(mote_surface, (0, 0))

            ship_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(ship_surface, (235, 240, 255, int(255 * max(0.1, transport_phase))), points)
            ship_surface.set_clip(clip_rect)
            scan_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            for line_y in range(int(max_y), clip_top - 1, -2):
                glow_alpha = int(100 + 135 * transport_phase)
                core_alpha = int(150 + 105 * transport_phase)
                glow_colour = (150, 240, 255, glow_alpha)
                core_colour = (230, 248, 255, core_alpha)
                if ((line_y // 2) % 4) == 0:
                    glow_colour = (255, 185, 185, int(glow_alpha * 0.75))
                    core_colour = (255, 228, 228, int(core_alpha * 0.8))
                pygame.draw.line(scan_surface, glow_colour, (center[0] - self.radius - 12, line_y), (center[0] + self.radius + 12, line_y), 4)
                pygame.draw.line(scan_surface, core_colour, (center[0] - self.radius - 8, line_y), (center[0] + self.radius + 8, line_y), 2)
            ship_surface.blit(scan_surface, (0, 0))
            ship_surface.set_clip(None)
            screen.blit(ship_surface, (0, 0))

            if linear_phase > 0.82 and self.transporter_state == 'materialize':
                flash = (linear_phase - 0.82) / 0.18
                flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                pygame.draw.polygon(flash_surface, (255, 255, 255, int(110 * flash)), points)
                screen.blit(flash_surface, (0, 0))

        if self.has_orb:
            pulse_strength = 1.0 if self.orb_pulse_time > 0.0 else 0.45
            pulse_wave = 0.55 + 0.45 * math.sin(self.orb_pulse_phase * math.tau)
            glow_radius = int(self.radius + 12 + (10 if self.orb_pulse_time > 0.0 else 6) * pulse_wave)
            draw_glow_circle(
                screen,
                (255, 218, 92),
                center,
                int(self.radius + 2),
                glow_radius,
                int((40 + 95 * pulse_wave) * pulse_strength),
            )
            pulse_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(
                pulse_surface,
                (255, 222, 120, int((24 + 76 * pulse_wave) * pulse_strength)),
                points,
            )
            screen.blit(pulse_surface, (0, 0))

        if self.force_field_active:
            shield_wave = 0.55 + 0.45 * math.sin(pygame.time.get_ticks() * 0.012)
            shield_radius = int(self.force_field_hit_radius() + 2 + shield_wave * 2)
            draw_glow_circle(
                screen,
                (110, 235, 255),
                center,
                shield_radius,
                FORCE_FIELD_GLOW_RADIUS,
                int(54 + 40 * shield_wave),
            )
            shield_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(
                shield_surface,
                (170, 245, 255, int(68 + 42 * shield_wave)),
                center,
                shield_radius,
                2,
            )
            screen.blit(shield_surface, (0, 0))

        fill_colour = (235, 240, 255)
        if self.is_transporting():
            min_y = min(point[1] for point in points)
            max_y = max(point[1] for point in points)
            height = max(1, int(math.ceil(max_y - min_y)))
            visible_height = max(1, int(height * max(0.04, transport_phase)))
            clip_top = int(max_y - visible_height)
            temp_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(temp_surface, (*fill_colour, int(255 * max(0.08, transport_phase))), points)
            temp_surface.set_clip(pygame.Rect(0, clip_top, SCREEN_WIDTH, max(1, int(max_y - clip_top + 3))))
            screen.blit(temp_surface, (0, 0))
            temp_surface.set_clip(None)
        else:
            pygame.draw.polygon(screen, fill_colour, points)

        if self.bounce_flash_time > 0.0:
            flash_phase = int((SHIP_BOUNCE_FLASH_DURATION - self.bounce_flash_time) * 24.0) % 2
            flash_colour = (90, 190, 255) if flash_phase == 0 else (255, 90, 90)
            flash_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(flash_surface, (*flash_colour, 110), points)
            screen.blit(flash_surface, (0, 0))

        outline_colour = (110, 170, 255)
        if self.bounce_flash_time > 0.0:
            flash_phase = int((SHIP_BOUNCE_FLASH_DURATION - self.bounce_flash_time) * 24.0) % 2
            outline_colour = (90, 190, 255) if flash_phase == 0 else (255, 90, 90)
        if self.has_orb:
            pulse_scale = 1.0 if self.orb_pulse_time > 0.0 else 0.55
            pulse_wave = 0.6 + 0.4 * math.sin(self.orb_pulse_phase * math.tau)
            outline_colour = (
                min(255, int(120 + (110 * pulse_wave * pulse_scale))),
                min(255, int(165 + (65 * pulse_wave * pulse_scale))),
                min(255, int(105 + (120 * pulse_wave * pulse_scale))),
            )
        if self.bounce_flash_time > 0.0:
            flash_phase = int((SHIP_BOUNCE_FLASH_DURATION - self.bounce_flash_time) * 24.0) % 2
            outline_colour = (90, 190, 255) if flash_phase == 0 else (255, 90, 90)
        if self.is_transporting():
            min_y = min(point[1] for point in points)
            max_y = max(point[1] for point in points)
            height = max(1, int(math.ceil(max_y - min_y)))
            visible_height = max(1, int(height * max(0.04, transport_phase)))
            clip_top = int(max_y - visible_height)
            temp_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(temp_surface, (*outline_colour, int(255 * max(0.12, transport_phase))), points, 2)
            temp_surface.set_clip(pygame.Rect(0, clip_top, SCREEN_WIDTH, max(1, int(max_y - clip_top + 3))))
            screen.blit(temp_surface, (0, 0))
            temp_surface.set_clip(None)
        else:
            pygame.draw.polygon(screen, outline_colour, points, 2)

    def draw_tractor_beam(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive or not self.tractor_active:
            return
        beam_length = TRACTOR_BEAM_LENGTH
        beam_half_width = TRACTOR_BEAM_HALF_WIDTH
        anchor_x, anchor_y = self.get_tractor_anchor(offset=4.0)
        angle_rad = math.radians(self.angle)
        ux = -math.cos(angle_rad)
        uy = -math.sin(angle_rad)
        px = -uy
        py = ux
        if level is not None:
            beam_length = level.tractor_beam_visible_length(anchor_x, anchor_y, ux, uy, beam_length)
            beam_length = max(
                beam_length,
                level.tractor_beam_target_length(anchor_x, anchor_y, ux, uy, beam_half_width),
            )
        if beam_length <= 2.0:
            return
        tip_x = anchor_x + ux * beam_length
        tip_y = anchor_y + uy * beam_length
        left_x = tip_x + px * beam_half_width
        left_y = tip_y + py * beam_half_width
        right_x = tip_x - px * beam_half_width
        right_y = tip_y - py * beam_half_width
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        points = [
            (anchor_x + offset_x - camera_x, anchor_y - camera_y),
            (left_x + offset_x - camera_x, left_y - camera_y),
            (right_x + offset_x - camera_x, right_y - camera_y),
        ]
        beam_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(beam_surface, (130, 255, 220, 46), points)
        pygame.draw.polygon(beam_surface, (210, 255, 245, 82), points, 2)
        screen.blit(beam_surface, (0, 0))


class Turret:
    def __init__(self, x, y, direction, sprite):
        self.x = x
        self.y = y
        self.direction = direction
        self.sprite = sprite
        self.floor_offset = 10.0
        self.support_angle = 0.0
        self.radius = TURRET_RADIUS
        self.hit_points = TURRET_HIT_POINTS
        self.alive = True
        self.cooldown = 0.0
        self.aim_angle = math.radians(direction)
        self.inaccuracy_degrees = 0.0
        if random.random() > TURRET_ACCURATE_CHANCE:
            self.inaccuracy_degrees = random.uniform(
                TURRET_INACCURATE_SPREAD_MIN,
                TURRET_INACCURATE_SPREAD_MAX,
            )

    def update(self, dt, ship, bullets, level):
        if not self.alive:
            return False

        self.cooldown -= dt
        if self.cooldown > 0:
            return False

        # Very simple AI: fire if ship is not too far away.
        dx = level.wrapped_dx(self.x, ship.x)
        dy = ship.y - self.y
        distance = math.hypot(dx, dy)
        if distance > 1e-6:
            self.aim_angle = math.atan2(dy, dx)
        if distance < 260:
            angle = self.aim_angle
            if self.inaccuracy_degrees > 0.0:
                spread = math.radians(self.inaccuracy_degrees)
                angle += random.uniform(-spread, spread)
            bullets.append(
                Bullet(
                    self.x,
                    self.y,
                    math.cos(angle) * TURRET_BULLET_SPEED,
                    math.sin(angle) * TURRET_BULLET_SPEED,
                    from_player=False,
                )
            )
            self.cooldown = TURRET_FIRE_COOLDOWN
            return True
        return False

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def apply_hit(self):
        if not self.alive:
            return False
        self.hit_points -= 1
        if self.hit_points <= 0:
            self.alive = False
            return True
        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        cx = self.x + offset_x - camera_x
        cy = self.y - camera_y
        support_angle = self.support_angle

        def rotate_rect(rect):
            corners = [
                rotate_point(rect.left, rect.top, cx, cy, support_angle),
                rotate_point(rect.right, rect.top, cx, cy, support_angle),
                rotate_point(rect.right, rect.bottom, cx, cy, support_angle),
                rotate_point(rect.left, rect.bottom, cx, cy, support_angle),
            ]
            return corners

        base_rect = pygame.Rect(0, 0, 44, 18)
        base_rect.center = (cx, cy + 11)
        plinth_rect = pygame.Rect(0, 0, 32, 12)
        plinth_rect.center = (cx, cy + 1)
        head_center = rotate_point(cx, cy - 6, cx, cy, support_angle)

        angle = self.aim_angle
        ux = math.cos(angle)
        uy = math.sin(angle)
        px = -uy
        py = ux

        barrel_back = 6.0
        barrel_len = 28.0
        barrel_half = 4.5
        breech_half_len = 9.0
        breech_half_w = 7.0

        breech_points = [
            (head_center[0] - ux * breech_half_len + px * breech_half_w, head_center[1] - uy * breech_half_len + py * breech_half_w),
            (head_center[0] + ux * breech_half_len + px * breech_half_w, head_center[1] + uy * breech_half_len + py * breech_half_w),
            (head_center[0] + ux * breech_half_len - px * breech_half_w, head_center[1] + uy * breech_half_len - py * breech_half_w),
            (head_center[0] - ux * breech_half_len - px * breech_half_w, head_center[1] - uy * breech_half_len - py * breech_half_w),
        ]
        barrel_start_x = head_center[0] + ux * barrel_back
        barrel_start_y = head_center[1] + uy * barrel_back
        barrel_end_x = head_center[0] + ux * barrel_len
        barrel_end_y = head_center[1] + uy * barrel_len
        barrel_points = [
            (barrel_start_x + px * barrel_half, barrel_start_y + py * barrel_half),
            (barrel_end_x + px * barrel_half, barrel_end_y + py * barrel_half),
            (barrel_end_x - px * barrel_half, barrel_end_y - py * barrel_half),
            (barrel_start_x - px * barrel_half, barrel_start_y - py * barrel_half),
        ]

        shadow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shadow_rect = pygame.Rect(cx - 28, cy + 12, 56, 16)
        pygame.draw.ellipse(shadow_surface, (0, 0, 0, 55), shadow_rect)
        screen.blit(shadow_surface, (0, 0))

        pygame.draw.polygon(screen, (58, 62, 70), rotate_rect(base_rect))
        pygame.draw.polygon(screen, (92, 98, 110), rotate_rect(base_rect.inflate(-6, -6)))
        pygame.draw.polygon(screen, (74, 78, 88), rotate_rect(plinth_rect))

        for x_offset in (-13, 0, 13):
            bolt = rotate_point(cx + x_offset, cy + 11, cx, cy, support_angle)
            pygame.draw.circle(screen, (122, 128, 140), (int(bolt[0]), int(bolt[1])), 3)

        pygame.draw.polygon(screen, (74, 80, 92), breech_points)
        pygame.draw.polygon(screen, (138, 146, 160), breech_points, 1)
        pygame.draw.polygon(screen, (88, 96, 110), barrel_points)
        pygame.draw.polygon(screen, (160, 170, 186), barrel_points, 1)

        pygame.draw.circle(screen, (66, 72, 82), (int(head_center[0]), int(head_center[1])), 13)
        pygame.draw.circle(screen, (124, 132, 148), (int(head_center[0]), int(head_center[1])), 13, 2)
        pygame.draw.circle(screen, (170, 184, 205), (int(head_center[0]), int(head_center[1])), 5)
        pygame.draw.circle(screen, (255, 120, 90), (int(head_center[0] + ux * 6), int(head_center[1] + uy * 6)), 2)


class Tank:
    def __init__(self, x, y, support_line):
        self.x = x
        self.y = y
        self.support_line = support_line
        self.radius = TANK_RADIUS
        self.hit_points = 5
        self.alive = True
        self.cooldown = random.uniform(0.2, 1.1)
        self.direction = random.choice([-1.0, 1.0])
        self.inaccuracy_degrees = random.uniform(TANK_AIM_SPREAD_MIN, TANK_AIM_SPREAD_MAX)

    def update(self, dt, ship, bullets, level):
        if not self.alive:
            return False

        (ax, ay), (bx, by) = self.support_line
        min_x = min(ax, bx) + TANK_HALF_WIDTH
        max_x = max(ax, bx) - TANK_HALF_WIDTH
        self.x += self.direction * TANK_SPEED * dt
        if self.x <= min_x:
            self.x = min_x
            self.direction = 1.0
        elif self.x >= max_x:
            self.x = max_x
            self.direction = -1.0
        self.y = ay - TANK_HALF_HEIGHT

        self.cooldown -= dt
        if self.cooldown > 0:
            return False

        dx = level.wrapped_dx(self.x, ship.x)
        dy = ship.y - self.y
        distance = math.hypot(dx, dy)
        if distance <= TANK_FIRE_RANGE:
            angle = math.atan2(dy, dx)
            spread = math.radians(self.inaccuracy_degrees)
            angle += random.uniform(-spread, spread)
            bullets.append(
                Bullet(
                    self.x,
                    self.y - 4,
                    math.cos(angle) * TANK_BULLET_SPEED,
                    math.sin(angle) * TANK_BULLET_SPEED,
                    from_player=False,
                )
            )
            self.cooldown = TANK_FIRE_COOLDOWN
            return True
        return False

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def apply_hit(self):
        if not self.alive:
            return False
        self.hit_points -= 1
        if self.hit_points <= 0:
            self.alive = False
            return True
        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        cx = self.x + offset_x - camera_x
        cy = self.y - camera_y
        track_rect = pygame.Rect(0, 0, TANK_HALF_WIDTH * 2 + 10, 14)
        track_rect.center = (cx, cy + 9)
        body_rect = pygame.Rect(0, 0, TANK_HALF_WIDTH * 2, 20)
        body_rect.center = (cx, cy)
        turret_rect = pygame.Rect(0, 0, 28, 14)
        turret_rect.center = (cx, cy - 9)
        cannon_len = 22
        barrel_end_x = cx + self.direction * cannon_len
        barrel_end_y = cy - 9

        pygame.draw.rect(screen, (66, 70, 74), track_rect, border_radius=4)
        for i in range(6):
            wheel_x = track_rect.left + 8 + i * 10
            pygame.draw.circle(screen, (108, 112, 118), (wheel_x, int(cy + 9)), 3)
        pygame.draw.rect(screen, (104, 122, 88), body_rect, border_radius=5)
        pygame.draw.rect(screen, (132, 150, 114), turret_rect, border_radius=5)
        pygame.draw.line(screen, (160, 170, 140), (cx, cy - 9), (barrel_end_x, barrel_end_y), 4)


class Gate:
    def __init__(self, gate_id, x, y, width, height, slide_dx=0.0, slide_dy=0.0, open_duration=3.5, slide_time=0.55):
        self.gate_id = gate_id
        self.closed_x = x
        self.closed_y = y
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        if self.height >= self.width:
            self.height = min(self.height, 200.0)
            slide_amount = abs(slide_dy) if abs(slide_dy) > 0.0 else abs(slide_dx)
            if slide_amount <= 0.0:
                slide_amount = min(96.0, self.height * 0.45)
            slide_sign = -1.0 if (slide_dy < 0.0 or (slide_dy == 0.0 and slide_dx < 0.0)) else 1.0
            self.slide_dx = 0.0
            self.slide_dy = slide_sign * slide_amount
        else:
            self.width = min(self.width, 200.0)
            slide_amount = abs(slide_dx) if abs(slide_dx) > 0.0 else abs(slide_dy)
            if slide_amount <= 0.0:
                slide_amount = min(96.0, self.width * 0.45)
            slide_sign = -1.0 if (slide_dx < 0.0 or (slide_dx == 0.0 and slide_dy < 0.0)) else 1.0
            self.slide_dx = slide_sign * slide_amount
            self.slide_dy = 0.0
        self.half_w = width * 0.5
        self.half_h = height * 0.5
        self.half_w = self.width * 0.5
        self.half_h = self.height * 0.5
        self.open_duration = open_duration
        self.slide_time = max(0.05, slide_time)
        self.open_timer = 0.0
        self.open_amount = 0.0
        self.radius = math.hypot(self.half_w, self.half_h)

    def activate(self):
        self.open_timer = self.open_duration

    def update(self, dt, level=None, ship=None):
        prev_x = self.x
        prev_y = self.y
        prev_open_amount = self.open_amount
        if self.open_timer > 0.0:
            self.open_timer = max(0.0, self.open_timer - dt)
        target_amount = 1.0 if self.open_timer > 0.0 else 0.0
        step = dt / self.slide_time
        if self.open_amount < target_amount:
            self.open_amount = min(target_amount, self.open_amount + step)
        elif self.open_amount > target_amount:
            self.open_amount = max(target_amount, self.open_amount - step)
        self.x = self.closed_x + self.slide_dx * self.open_amount
        self.y = self.closed_y + self.slide_dy * self.open_amount

        if (
            level is not None
            and ship is not None
            and ship.is_operational()
            and ship.can_bounce()
            and (abs(self.x - prev_x) > 1e-6 or abs(self.y - prev_y) > 1e-6)
        ):
            ship_radius = ship.collision_radius()
            if self.contains_point(ship.x, ship.y, ship_radius, level):
                pushed_x = level.wrap_x(ship.x + (self.x - prev_x), ship.radius)
                pushed_y = ship.y + (self.y - prev_y)
                if ship.terrain_collision_contacts(level, ship_radius, x=pushed_x, y=pushed_y):
                    self.x = prev_x
                    self.y = prev_y
                    self.open_amount = prev_open_amount

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return circle_rect_collision(dx, y, radius, 0.0, self.y, self.half_w, self.half_h)

    def segments(self, level=None):
        left = self.x - self.half_w
        right = self.x + self.half_w
        top = self.y - self.half_h
        bottom = self.y + self.half_h
        return [
            ((left, top), (right, top)),
            ((right, top), (right, bottom)),
            ((right, bottom), (left, bottom)),
            ((left, bottom), (left, top)),
        ]

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        cx = int(self.x + offset_x - camera_x)
        cy = int(self.y - camera_y)
        rect = pygame.Rect(0, 0, int(self.width), int(self.height))
        rect.center = (cx, cy)
        if self.height >= self.width:
            panel_rect = rect.inflate(-8, 0)
            core_rect = panel_rect.inflate(-6, -8)
        else:
            panel_rect = rect.inflate(0, -8)
            core_rect = panel_rect.inflate(-8, -6)

        glow_alpha = int(30 + 70 * (1.0 - self.open_amount))
        glow_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(glow_surface, (120, 240, 255, glow_alpha), panel_rect.inflate(8, 8), border_radius=7)
        screen.blit(glow_surface, (0, 0))

        pygame.draw.rect(screen, (70, 94, 108), panel_rect, border_radius=6)
        pygame.draw.rect(screen, (170, 226, 242), panel_rect, 2, border_radius=6)
        pygame.draw.rect(screen, (42, 58, 72), core_rect, border_radius=4)
        pygame.draw.line(screen, (126, 186, 204), (core_rect.left + 3, core_rect.top + 3), (core_rect.right - 3, core_rect.top + 3), 2)
        pygame.draw.line(screen, (18, 26, 36), (core_rect.left + 3, core_rect.bottom - 3), (core_rect.right - 3, core_rect.bottom - 3), 2)
        if self.height >= self.width:
            seam_y = core_rect.centery
            pygame.draw.line(screen, (98, 148, 166), (core_rect.left + 2, seam_y), (core_rect.right - 2, seam_y), 2)
        else:
            seam_x = core_rect.centerx
            pygame.draw.line(screen, (98, 148, 166), (seam_x, core_rect.top + 2), (seam_x, core_rect.bottom - 2), 2)


class Switch:
    def __init__(self, x, y, gate_id, radius=14):
        self.x = x
        self.y = y
        self.gate_id = gate_id
        self.radius = radius
        self.floor_offset = 18.0
        self.support_angle = 0.0
        self.flash_time = 0.0

    def activate(self, gate):
        self.flash_time = 0.22
        if gate is not None:
            gate.activate()

    def update(self, dt):
        self.flash_time = max(0.0, self.flash_time - dt)

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None, gate=None):
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        cx = self.x + offset_x - camera_x
        cy = self.y - camera_y
        base_rect = pygame.Rect(0, 0, 24, 12)
        base_rect.center = (cx, cy + 12)
        active = gate is not None and gate.open_timer > 0.0
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() * 0.012)
        if self.flash_time > 0.0:
            lens_colour = (255, 245, 170)
            glow_colour = (255, 235, 120)
            glow_alpha = int(120 + 90 * pulse)
        elif active:
            lens_colour = (140, 255, 185)
            glow_colour = (80, 235, 160)
            glow_alpha = int(70 + 45 * pulse)
        else:
            lens_colour = (255, 142, 92)
            glow_colour = (255, 112, 70)
            glow_alpha = int(52 + 24 * pulse)

        base_points = [
            rotate_point(base_rect.left, base_rect.top, cx, cy, self.support_angle),
            rotate_point(base_rect.right, base_rect.top, cx, cy, self.support_angle),
            rotate_point(base_rect.right, base_rect.bottom, cx, cy, self.support_angle),
            rotate_point(base_rect.left, base_rect.bottom, cx, cy, self.support_angle),
        ]
        draw_glow_circle(screen, glow_colour, (int(cx), int(cy)), self.radius - 4, self.radius + 10, glow_alpha)
        pygame.draw.polygon(screen, (96, 104, 116), base_points)
        pygame.draw.polygon(screen, (150, 160, 174), base_points, 2)
        pygame.draw.circle(screen, lens_colour, (int(cx), int(cy)), self.radius - 4)
        pygame.draw.circle(screen, (245, 248, 255), (int(cx), int(cy)), self.radius - 4, 2)


class FuelPod:
    def __init__(self, x, y, sprite):
        self.x = x
        self.y = y
        self.sprite = sprite
        # Match the pod's tall drawn silhouette more closely so shield contact reads correctly.
        self.radius = max(18, int(max(sprite.get_width(), sprite.get_height()) * 0.46))
        self.support_angle = 0.0
        self.hit_points = 2
        self.destroyed = False
        self.fuel_remaining = FUEL_POD_AMOUNT
        self.spawn_cooldown = 0.0
        self.depleted_effect_played = False
        self.flash_time = 0.0

    def contains_point(self, x, y, radius=0.0, level=None):
        if self.destroyed:
            return False
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def apply_hit(self):
        if self.destroyed:
            return False
        self.flash_time = 0.20
        self.hit_points -= 1
        if self.hit_points <= 0:
            self.destroyed = True
            self.fuel_remaining = 0.0
            self.depleted_effect_played = True
            return True
        return False

    def tractor_beam_overlap(self, ship, level):
        angle_rad = math.radians(ship.angle)
        ux = -math.cos(angle_rad)
        uy = -math.sin(angle_rad)
        px = -uy
        py = ux
        anchor_x, anchor_y = ship.get_tractor_anchor(offset=4.0)
        rel_x = level.wrapped_dx(anchor_x, self.x)
        rel_y = self.y - anchor_y
        along = rel_x * ux + rel_y * uy
        perp = rel_x * px + rel_y * py
        if along < 0.0 or along > TRACTOR_BEAM_LENGTH:
            return False
        width_here = TRACTOR_BEAM_HALF_WIDTH * (0.45 + 0.55 * (1.0 - along / TRACTOR_BEAM_LENGTH))
        if abs(perp) > width_here + self.radius:
            return False
        return not level.tractor_terrain_blocked(
            anchor_x,
            anchor_y,
            self.x,
            self.y,
            end_clearance=self.radius + 6.0,
        )

    def update(self, ship, level, tractor_active, dt, fuel_particles):
        self.flash_time = max(0.0, self.flash_time - dt)
        if self.destroyed or self.fuel_remaining <= 0.0:
            return False
        self.spawn_cooldown = max(0.0, self.spawn_cooldown - dt)
        if not tractor_active or not self.tractor_beam_overlap(ship, level):
            return False

        while self.fuel_remaining > 0.0 and self.spawn_cooldown <= 0.0:
            amount = min(FUEL_PARTICLE_VALUE, self.fuel_remaining)
            self.fuel_remaining -= amount
            fuel_particles.append(FuelTransferParticle(self.x, self.y, amount, self))
            self.spawn_cooldown += FUEL_PARTICLE_SPAWN_INTERVAL

        if self.fuel_remaining <= 0.0 and not self.depleted_effect_played:
            self.depleted_effect_played = True
            return True
        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if self.destroyed or self.fuel_remaining <= 0.0:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center_x = int(self.x + offset_x - camera_x)
        center_y = int(self.y - camera_y)
        rect = self.sprite.get_rect(center=(center_x, center_y))
        fill_ratio = max(0.0, min(1.0, self.fuel_remaining / FUEL_POD_AMOUNT))
        fill_height = int((self.sprite.get_height() - 16) * fill_ratio)
        if fill_height > 0:
            fill_surface = pygame.Surface(self.sprite.get_size(), pygame.SRCALPHA)
            fill_rect = pygame.Rect(8, self.sprite.get_height() - 10 - fill_height, self.sprite.get_width() - 16, fill_height)
            fill_colour = (90, 255, 180, 110) if self.hit_points > 1 else (70, 170, 130, 88)
            pygame.draw.rect(fill_surface, fill_colour, fill_rect, border_radius=5)
            screen.blit(fill_surface, rect)
        sprite_image = self.sprite
        if abs(self.support_angle) > 1e-4:
            sprite_image = pygame.transform.rotate(self.sprite, -math.degrees(self.support_angle))
        sprite_rect = sprite_image.get_rect(center=(center_x, center_y))
        screen.blit(sprite_image, sprite_rect)
        if self.hit_points == 1:
            damage_surface = pygame.Surface(self.sprite.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(damage_surface, (28, 34, 32, 96), damage_surface.get_rect(), border_radius=7)
            pygame.draw.line(damage_surface, (255, 232, 210, 190), (12, 14), (24, 28), 2)
            pygame.draw.line(damage_surface, (255, 232, 210, 170), (24, 28), (18, 42), 2)
            pygame.draw.line(damage_surface, (255, 232, 210, 150), (22, 20), (30, 34), 1)
            if abs(self.support_angle) > 1e-4:
                damage_surface = pygame.transform.rotate(damage_surface, -math.degrees(self.support_angle))
            screen.blit(damage_surface, damage_surface.get_rect(center=(center_x, center_y)), special_flags=pygame.BLEND_ALPHA_SDL2)
        if self.flash_time > 0.0:
            flash_alpha = int(220 * (self.flash_time / 0.20))
            flash_surface = pygame.Surface(self.sprite.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(flash_surface, (255, 252, 210, flash_alpha), flash_surface.get_rect(), border_radius=7)
            if abs(self.support_angle) > 1e-4:
                flash_surface = pygame.transform.rotate(flash_surface, -math.degrees(self.support_angle))
            screen.blit(flash_surface, flash_surface.get_rect(center=(center_x, center_y)), special_flags=pygame.BLEND_ALPHA_SDL2)


class FuelTransferParticle:
    def __init__(self, x, y, fuel_amount, source_pod=None):
        self.x = x + random.uniform(-8.0, 8.0)
        self.y = y + random.uniform(-10.0, 10.0)
        self.fuel_amount = fuel_amount
        self.source_pod = source_pod
        self.state = "pulling"
        self.fade_time = FUEL_PARTICLE_FADE_TIME
        self.alive = True

    def update(self, dt, ship, level):
        if not self.alive:
            return False

        if self.state == "pulling":
            if not ship.alive or not ship.tractor_active:
                self.state = "fading"
            else:
                target_x, target_y = ship.get_tractor_anchor(offset=-TRACTOR_TARGET_OFFSET)
                if level.tractor_terrain_blocked(self.x, self.y, target_x, target_y):
                    self.state = "fading"
                    return False
                dx = level.wrapped_dx(self.x, target_x)
                dy = target_y - self.y
                dist = math.hypot(dx, dy)
                if dist <= ship.radius + 4.0:
                    ship.fuel = min(SHIP_MAX_FUEL, ship.fuel + self.fuel_amount)
                    self.alive = False
                    return True
                step = FUEL_PARTICLE_PULL_SPEED * dt
                if dist > 0.0:
                    self.x = level.wrap_x(self.x + (dx / dist) * min(step, dist), 0.0)
                    self.y += (dy / dist) * min(step, dist)
        if self.state == "fading":
            self.fade_time -= dt
            self.y -= 18.0 * dt
            if self.fade_time <= 0.0:
                self.alive = False
        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
        if self.state == "pulling":
            alpha = 120
        else:
            alpha = int(130 * max(0.0, self.fade_time / FUEL_PARTICLE_FADE_TIME))
        draw_glow_circle(screen, (120, 255, 185), center, 3, 8, alpha)
        pygame.draw.circle(screen, (220, 255, 235), center, 2)


class Orb:
    def __init__(self, x, y, sprite):
        self.x = x
        self.y = y
        self.sprite = sprite
        self.radius = sprite.get_width() * 0.5
        self.support_angle = 0.0
        self.plinth_x = x
        self.plinth_y = y
        self.plinth_half_width = 27.0
        self.plinth_alive = True
        self.plinth_hit_points = 5
        self.plinth_flash_time = 0.0
        self.collected = False
        self.vx = 0.0
        self.vy = 0.0
        self.resting = True
        self.beam_locked_last_frame = False

    def set_plinth_position(self, x, y):
        self.plinth_x = x
        self.plinth_y = y
        self.plinth_alive = True
        self.plinth_hit_points = 5
        self.plinth_flash_time = 0.0
        self.x = x
        self.y = self.plinth_support_y()
        self.vx = 0.0
        self.vy = 0.0
        self.resting = True

    def plinth_support_y(self):
        return self.plinth_support_y_for_offset(0.0)

    def plinth_support_y_for_offset(self, offset_x):
        floor_y = self.plinth_y + self.radius
        plinth_top_y = floor_y - 34.0
        cap_bottom_y = plinth_top_y + 6.0
        edge_lift = min(1.0, abs(offset_x) / max(1.0, self.plinth_half_width - 8.0))
        cradle_y = cap_bottom_y - 7.0 + 7.0 * (edge_lift * edge_lift)
        return cradle_y - self.radius + 1.0

    def resolve_plinth_collision(self, level):
        if not self.plinth_alive:
            return False
        dx = level.wrapped_dx(self.plinth_x, self.x)
        if abs(dx) > (self.plinth_half_width - 4.0):
            return False
        support_y = self.plinth_support_y_for_offset(dx)
        if self.y < support_y:
            return False
        self.x = level.wrap_x(self.x, self.radius)
        self.y = support_y
        self.vx = 0.0
        self.vy = 0.0
        self.resting = True
        return True

    def plinth_contains_point(self, x, y, radius=0.0, level=None):
        if not self.plinth_alive:
            return False
        dx = self.plinth_x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.plinth_x)
        support_y = self.plinth_support_y_for_offset(max(-self.plinth_half_width, min(self.plinth_half_width, dx)))
        plinth_center_y = support_y + self.radius - 15.0
        return abs(dx) <= (self.plinth_half_width + radius) and abs(plinth_center_y - y) <= (22.0 + radius)

    def destroy_plinth(self):
        if not self.plinth_alive:
            return False
        self.plinth_alive = False
        if not self.collected:
            self.resting = False
            self.vx *= 0.3
            self.vy = max(self.vy, 0.0)
        return True

    def hit_plinth(self):
        if not self.plinth_alive:
            return False
        self.plinth_flash_time = 0.20
        self.plinth_hit_points -= 1
        if self.plinth_hit_points <= 0:
            return self.destroy_plinth()
        return False

    def update(self, ship, level, tractor_active, dt):
        if self.collected:
            return False

        self.plinth_flash_time = max(0.0, self.plinth_flash_time - dt)

        beam_locked = False
        if tractor_active:
            angle_rad = math.radians(ship.angle)
            ux = -math.cos(angle_rad)
            uy = -math.sin(angle_rad)
            px = -uy
            py = ux
            anchor_x, anchor_y = ship.get_tractor_anchor(offset=4.0)
            rel_x = level.wrapped_dx(anchor_x, self.x)
            rel_y = self.y - anchor_y
            along = rel_x * ux + rel_y * uy
            perp = rel_x * px + rel_y * py
            beam_length = TRACTOR_BEAM_LENGTH
            beam_half_width = TRACTOR_BEAM_HALF_WIDTH
            if 0.0 <= along <= beam_length:
                width_here = beam_half_width * (0.45 + 0.55 * (1.0 - along / beam_length))
                beam_locked = abs(perp) <= width_here
                if beam_locked:
                    beam_locked = not level.tractor_terrain_blocked(
                        anchor_x,
                        anchor_y,
                        self.x,
                        self.y,
                        end_clearance=self.radius + 6.0,
                    )

            if beam_locked:
                target_x, target_y = ship.get_tractor_anchor(offset=-TRACTOR_TARGET_OFFSET)
                pull_dx = level.wrapped_dx(self.x, target_x)
                pull_dy = target_y - self.y
                pull_dist = max(1.0, math.hypot(pull_dx, pull_dy))
                pull_scale = TRACTOR_PULL_SPEED * (1.0 + 0.35 * (beam_length - along) / beam_length) * dt
                step = min(pull_scale, pull_dist)
                self.x = level.wrap_x(self.x + (pull_dx / pull_dist) * step, self.radius)
                self.y += (pull_dy / pull_dist) * step
                self.vx = (pull_dx / pull_dist) * (step / max(dt, 1e-6))
                self.vy = (pull_dy / pull_dist) * (step / max(dt, 1e-6))
                self.resting = False
                if math.hypot(level.wrapped_dx(ship.x, self.x), self.y - ship.y) <= ship.radius + self.radius:
                    self.collected = True
                    ship.collect_orb()
                    return True

        if self.beam_locked_last_frame and not beam_locked:
            self.vx *= 0.2
            self.vy = max(0.0, self.vy)

        if not beam_locked and not self.resting:
            self.vy = min(ORB_FALL_MAX_SPEED, self.vy + level.gravity * dt)
            steps = max(1, int(math.ceil(max(abs(self.vx), abs(self.vy)) * dt / max(1.0, self.radius * 0.3))))
            step_dt = dt / steps
            for _ in range(steps):
                self.x = level.wrap_x(self.x + self.vx * step_dt, self.radius)
                self.y += self.vy * step_dt
                if self.resolve_plinth_collision(level) or level.resolve_orb_terrain_collision(self):
                    self.vx = 0.0
                    self.vy = 0.0
                    self.resting = True
                    break
            if not self.resting:
                self.vx *= ORB_FALL_DAMPING

        self.beam_locked_last_frame = beam_locked

        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        plinth_offset_x = level.draw_world_offset(self.plinth_x, camera_x) if level else 0.0
        plinth_cx = int(self.plinth_x + plinth_offset_x - camera_x)
        floor_y = int(self.plinth_y + self.radius - camera_y)
        plinth_base_y = floor_y
        plinth_top_y = floor_y - 34
        body_rect = pygame.Rect(0, 0, 30, max(14, plinth_base_y - plinth_top_y))
        body_rect.midtop = (plinth_cx, plinth_top_y)
        cap_rect = pygame.Rect(0, 0, 54, 16)
        cap_rect.midbottom = (plinth_cx, plinth_top_y + 6)
        foot_rect = pygame.Rect(0, 0, 42, 10)
        foot_rect.midbottom = (plinth_cx, plinth_base_y)
        active_plinth = self.plinth_alive and not self.collected
        if active_plinth:
            body_fill = (146, 104, 18)
            body_outline = (236, 194, 78)
            cap_fill = (242, 204, 92)
            cap_outline = (255, 232, 154)
            cradle_colour = (176, 122, 26)
            lip_colour = (255, 236, 170)
            foot_fill = (188, 148, 44)
            foot_outline = (248, 215, 112)
            draw_glow_circle(screen, (255, 208, 82), (plinth_cx, plinth_top_y + 8), 18, 34, 78)
        else:
            body_fill = (86, 88, 92)
            body_outline = (138, 142, 150)
            cap_fill = (116, 120, 128)
            cap_outline = (164, 168, 176)
            cradle_colour = (84, 88, 96)
            lip_colour = (176, 180, 188)
            foot_fill = (104, 108, 116)
            foot_outline = (156, 160, 168)
        if self.plinth_alive:
            plinth_surface = pygame.Surface((96, 80), pygame.SRCALPHA)
            local_cx = plinth_surface.get_width() // 2
            local_floor_y = 66
            local_top_y = local_floor_y - 34
            local_body_rect = pygame.Rect(0, 0, 30, max(14, local_floor_y - local_top_y))
            local_body_rect.midtop = (local_cx, local_top_y)
            local_cap_rect = pygame.Rect(0, 0, 54, 16)
            local_cap_rect.midbottom = (local_cx, local_top_y + 6)
            local_foot_rect = pygame.Rect(0, 0, 42, 10)
            local_foot_rect.midbottom = (local_cx, local_floor_y)
            pygame.draw.rect(plinth_surface, body_fill, local_body_rect, border_radius=6)
            pygame.draw.rect(plinth_surface, body_outline, local_body_rect, 2, border_radius=6)
            pygame.draw.ellipse(plinth_surface, cap_fill, local_cap_rect)
            pygame.draw.ellipse(plinth_surface, cap_outline, local_cap_rect, 2)
            cradle_rect = local_cap_rect.inflate(-10, -1)
            pygame.draw.arc(plinth_surface, cradle_colour, cradle_rect, math.pi, math.tau, 3)
            lip_rect = local_cap_rect.inflate(-16, -8)
            pygame.draw.arc(plinth_surface, lip_colour, lip_rect, math.pi, math.tau, 2)
            pygame.draw.rect(plinth_surface, foot_fill, local_foot_rect, border_radius=4)
            pygame.draw.rect(plinth_surface, foot_outline, local_foot_rect, 2, border_radius=4)
            if self.plinth_flash_time > 0.0:
                flash_alpha = int(220 * (self.plinth_flash_time / 0.20))
                flash_surface = pygame.Surface(plinth_surface.get_size(), pygame.SRCALPHA)
                pygame.draw.rect(flash_surface, (255, 248, 210, flash_alpha), local_body_rect, border_radius=6)
                pygame.draw.ellipse(flash_surface, (255, 252, 220, flash_alpha), local_cap_rect)
                pygame.draw.rect(flash_surface, (255, 244, 200, flash_alpha), local_foot_rect, border_radius=4)
                plinth_surface.blit(flash_surface, (0, 0))
            if abs(self.support_angle) > 1e-4:
                plinth_surface = pygame.transform.rotate(plinth_surface, -math.degrees(self.support_angle))
            screen.blit(plinth_surface, plinth_surface.get_rect(center=(plinth_cx, plinth_base_y - 20)))
        else:
            rubble_rect = pygame.Rect(0, 0, 40, 10)
            rubble_rect.midbottom = (plinth_cx, plinth_base_y)
            pygame.draw.rect(screen, (102, 104, 110), rubble_rect, border_radius=4)
            pygame.draw.rect(screen, (146, 148, 156), rubble_rect, 2, border_radius=4)

        if self.collected:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
        draw_glow_circle(screen, (255, 205, 90), center, int(self.radius), int(self.radius + 10), 90)
        rect = self.sprite.get_rect(center=center)
        screen.blit(self.sprite, rect)


class Reactor:
    def __init__(self, x, y, sprite):
        self.x = x
        self.y = y
        self.sprite = sprite
        self.radius = max(sprite.get_width(), sprite.get_height()) * 0.34
        self.support_angle = 0.0
        self.hit_points = REACTOR_HIT_POINTS
        self.alive = True

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def apply_hit(self):
        if not self.alive:
            return False
        self.hit_points -= 1
        if self.hit_points <= 0:
            self.alive = False
            return True
        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        if self.alive:
            image = self.sprite
            if abs(self.support_angle) > 1e-4:
                image = pygame.transform.rotate(self.sprite, -math.degrees(self.support_angle))
            rect = image.get_rect(center=(self.x + offset_x - camera_x, self.y - camera_y))
            screen.blit(image, rect)


class Rock:
    def __init__(self, x, y, diameter=20):
        self.x = x
        self.y = y
        self.diameter = diameter
        self.radius = diameter * 0.5
        self.alive = True
        self.vx = 0.0
        self.vy = 0.0
        self.angle = random.uniform(0.0, 360.0)
        self.angular_velocity = 0.0
        self.dynamic = False
        self.support_signature = None

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

    def apply_hit(self):
        if not self.alive:
            return False
        self.alive = False
        return True

    def update(self, dt, level, support_rocks):
        if not self.alive:
            return

        supported, support_type, support_obj = level.find_dynamic_rock_support(self, support_rocks)
        current_support_signature = level.make_rock_support_signature(support_type, support_obj, supported)
        if not self.dynamic:
            if self.support_signature is None:
                self.support_signature = current_support_signature
            else:
                support_kind = self.support_signature[0]
                if support_kind == "floor":
                    if supported is not None:
                        self.x, self.y = supported
                        self.x = level.wrap_x(self.x, self.radius)
                    self.vx = 0.0
                    self.vy = 0.0
                    self.angular_velocity = 0.0
                    return
                if current_support_signature == self.support_signature:
                    if supported is not None:
                        self.x, self.y = supported
                        self.x = level.wrap_x(self.x, self.radius)
                    self.vx = 0.0
                    self.vy = 0.0
                    self.angular_velocity = 0.0
                    return
                self.dynamic = True

        self.vy = min(ROCK_MAX_FALL_SPEED, self.vy + level.gravity * ROCK_GRAVITY_SCALE * dt)
        steps = max(1, int(math.ceil(max(abs(self.vx), abs(self.vy)) * dt / max(1.0, self.radius * 0.35))))
        step_dt = dt / steps
        for _ in range(steps):
            self.x = level.wrap_x(self.x + self.vx * step_dt, self.radius)
            self.y += self.vy * step_dt
            terrain_contact = level.resolve_rock_terrain_collision(self)
            if terrain_contact:
                self.vx *= ROCK_TERRAIN_FRICTION
                self.vy = min(0.0, self.vy)
                if abs(self.vx) < ROCK_STOP_SPEED:
                    self.vx = 0.0
                if abs(self.vy) < ROCK_STOP_SPEED:
                    self.vy = 0.0
        self.angle = (self.angle + self.angular_velocity * dt) % 360.0

        supported, support_type, support_obj = level.find_dynamic_rock_support(self, support_rocks)
        if supported is not None:
            self.x, self.y = supported
            self.x = level.wrap_x(self.x, self.radius)
            self.vy = 0.0
            if support_type == "rock" and support_obj is not None:
                dx = level.wrapped_dx(support_obj.x, self.x)
                balance = max(-1.0, min(1.0, dx / max(1.0, support_obj.radius + self.radius)))
                self.vx += balance * ROCK_SLIDE_ACCEL * dt
                self.angular_velocity += balance * 220.0 * dt
                self.vx *= 0.98
            else:
                self.vx *= ROCK_GROUND_DAMPING
                self.angular_velocity *= ROCK_GROUND_DAMPING
        else:
            self.vx *= ROCK_AIR_DAMPING
            self.angular_velocity *= ROCK_AIR_DAMPING

        self.support_signature = level.make_rock_support_signature(support_type, support_obj, supported)

        self.vx = max(-90.0, min(90.0, self.vx))
        self.angular_velocity = max(-240.0, min(240.0, self.angular_velocity))

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if not self.alive:
            return
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
        pygame.draw.circle(screen, (115, 118, 126), center, int(self.radius))
        pygame.draw.circle(screen, (170, 174, 182), center, int(self.radius), 1)
        angle_rad = math.radians(self.angle)
        mark_x = center[0] + math.cos(angle_rad) * self.radius * 0.55
        mark_y = center[1] + math.sin(angle_rad) * self.radius * 0.55
        pygame.draw.circle(screen, (88, 92, 100), (int(mark_x), int(mark_y)), max(1, int(self.radius * 0.25)))


def normalize_cave_line_records(lines):
    records = []
    for line in lines or []:
        if isinstance(line, dict):
            points = line.get("points", [])
            colour = tuple(line.get("colour", [120, 220, 255]))
        else:
            points = line
            colour = (120, 220, 255)
        if len(points) != 2:
            continue
        records.append({"points": [tuple(points[0]), tuple(points[1])], "colour": colour})
    return records


class Level:
    def __init__(self, level_data, sprites):
        self.name = level_data["name"]
        self.gravity = level_data["gravity"]
        self.background_colour = tuple(level_data.get("background_colour", [0, 0, 0]))
        self.ship_start = tuple(level_data["ship_start"])
        self.authored_line_records = normalize_cave_line_records(level_data["cave_lines"])
        self.authored_lines = tuple(tuple(record["points"]) for record in self.authored_line_records)
        if not self.authored_lines:
            raise ValueError(f"Level '{self.name}' has no cave lines")
        self.terrain_line_records = []
        world_bounds = level_data.get("world_bounds")

        if world_bounds:
            self.world_min_x, self.world_max_x, self.world_min_y, self.world_max_y = world_bounds
        else:
            points = []
            for line in self.authored_lines:
                points.extend([line[0], line[1]])
            self.world_min_x = min(p[0] for p in points)
            self.world_max_x = max(p[0] for p in points)
            self.world_min_y = min(p[1] for p in points)
            self.world_max_y = max(p[1] for p in points)
        self.terrain_line_records = roughen_floor_line_records(self.authored_line_records, self.world_max_y, self.name)
        self.terrain_line_records = smooth_cave_line_records(self.terrain_line_records, iterations=2)
        self.terrain_lines = tuple(tuple(record["points"]) for record in self.terrain_line_records)
        self.world_width = self.world_max_x - self.world_min_x
        self.solid_spatial_cols = max(1, int(math.ceil(max(self.world_width, 1.0) / SOLID_SPATIAL_CELL_SIZE)))
        self.solid_spatial_index = {}
        self.terrain_spatial_index = {}
        self.rebuild_terrain_spatial_index()
        self.orbit_top_y = self.world_min_y - ORBIT_SCROLL_SPACE
        self.render_width = int(math.ceil(self.world_width))
        terrain_max_y = max(max(start[1], end[1]) for start, end in self.terrain_lines)
        self.render_height = int(math.ceil(terrain_max_y - self.orbit_top_y + 18.0))
        self.star_field = self.build_star_field()

        self.turrets = [
            Turret(t["x"], t["y"], t.get("direction", -90), sprites["turret"])
            for t in level_data.get("turrets", [])
        ]
        self.gates = [
            Gate(
                gate_data["id"],
                gate_data["x"],
                gate_data["y"],
                gate_data.get("width", 28),
                gate_data.get("height", 180),
                gate_data.get("slide_dx", 0.0),
                gate_data.get("slide_dy", 0.0),
                gate_data.get("open_duration", 3.5),
                gate_data.get("slide_time", 0.55),
            )
            for gate_data in level_data.get("gates", [])
        ]
        self.gates_by_id = {gate.gate_id: gate for gate in self.gates}
        self.switches = [
            Switch(
                switch_data["x"],
                switch_data["y"],
                switch_data["gate_id"],
                switch_data.get("radius", 14),
            )
            for switch_data in level_data.get("switches", [])
        ]

        self.fuel_pods = [
            FuelPod(f["x"], f["y"], sprites["fuel_pod"])
            for f in level_data.get("fuel_pods", [])
        ]
        orb_data = level_data.get("orb")
        self.orb = Orb(orb_data["x"], orb_data["y"], sprites["orb"]) if orb_data else None

        reactor_data = level_data.get("reactor")
        self.reactor = None
        if reactor_data:
            self.reactor = Reactor(reactor_data["x"], reactor_data["y"], sprites["reactor"])

        self.initialize_authored_object_positions()
        self.rocks = self.build_rocks(level_data)
        self.rocks_unlocked = False
        self.tanks = self.build_tanks(level_data)
        self.settle_rocks()
        self.rebuild_solid_spatial_index()
        self.terrain_surface = self.build_terrain_surface()

    def build_rocks(self, level_data):
        rocks = [
            Rock(r["x"], r["y"], r.get("diameter", 20))
            for r in level_data.get("rocks", [])
        ]

        for pile in level_data.get("rock_piles", []):
            count = min(pile["count"], ROCK_PILE_MAX_COUNT)
            diameter = pile.get("diameter", 20)
            spacing = diameter * 0.88
            row_step = diameter * 0.82
            base_width = pile.get("base_width", max(4, int(math.sqrt(count)) + 1))
            rng = random.Random(pile.get("seed", 0))
            origin_x = pile["x"]
            origin_y = pile["y"]

            placed = 0
            row = 0
            while placed < count:
                row_count = max(1, base_width - row)
                row_y = origin_y - row * row_step
                x_shift = rng.uniform(-1.5, 1.5)
                for col in range(row_count):
                    if placed >= count:
                        break
                    col_offset = (col - (row_count - 1) * 0.5) * spacing
                    rock_x = origin_x + col_offset + x_shift + rng.uniform(-1.0, 1.0)
                    rock_y = row_y + rng.uniform(-1.0, 1.0)
                    candidate = Rock(rock_x, rock_y, diameter)
                    if self.static_position_conflicts(candidate, padding=8.0):
                        continue
                    rocks.append(candidate)
                    placed += 1
                row += 1

        return rocks

    def authored_support_angle(self, x, y):
        best_line = None
        best_dist = float("inf")
        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            cx, cy = closest_point_on_segment(x, y, ax, ay, bx, by)
            dist = math.hypot(x - cx, y - cy)
            if dist < best_dist:
                best_dist = dist
                best_line = line
        if best_line is None:
            return 0.0
        (ax, ay), (bx, by) = best_line
        angle = math.atan2(by - ay, bx - ax)
        if angle > math.pi * 0.5:
            angle -= math.pi
        elif angle < -math.pi * 0.5:
            angle += math.pi
        return angle

    def initialize_authored_object_positions(self):
        """Respect authored level coordinates instead of re-snapping objects on load."""
        for turret in self.turrets:
            turret.support_angle = self.authored_support_angle(turret.x, turret.y)
        for fuel_pod in self.fuel_pods:
            fuel_pod.support_angle = self.authored_support_angle(fuel_pod.x, fuel_pod.y)
        for switch in self.switches:
            switch.support_angle = self.authored_support_angle(switch.x, switch.y)
        if self.reactor:
            self.reactor.support_angle = self.authored_support_angle(self.reactor.x, self.reactor.y)
        if self.orb:
            self.orb.support_angle = self.authored_support_angle(self.orb.x, self.orb.y)
            # Level files store the orb's visible position. The plinth anchor sits below it.
            self.orb.plinth_x = self.orb.x
            self.orb.plinth_y = self.orb.y + 34.0
            self.orb.plinth_alive = True
            self.orb.plinth_hit_points = 5
            self.orb.plinth_flash_time = 0.0
            self.orb.vx = 0.0
            self.orb.vy = 0.0
            self.orb.resting = True

    def tank_support_line(self, x, y):
        best_line = None
        best_dist = float("inf")
        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) >= 0.01:
                continue
            seg_min_x = min(ax, bx) + TANK_HALF_WIDTH
            seg_max_x = max(ax, bx) - TANK_HALF_WIDTH
            if seg_min_x > seg_max_x or not (seg_min_x <= x <= seg_max_x):
                continue
            support_y = ay - TANK_HALF_HEIGHT
            dist = abs(support_y - y)
            if dist < best_dist:
                best_dist = dist
                best_line = line
        return best_line

    def build_tanks(self, level_data):
        tanks = []
        for tank_data in level_data.get("tanks", []):
            support_line = self.tank_support_line(tank_data["x"], tank_data["y"])
            if support_line is None:
                continue
            tank = Tank(tank_data["x"], tank_data["y"], support_line)
            tank.x = tank_data["x"]
            tank.y = tank_data["y"]
            if self.position_conflicts(tank, tanks):
                continue
            tanks.append(tank)
        return tanks

    def _solid_x_cells(self, x, radius):
        if self.world_width <= 0.0:
            start = int(math.floor((x - radius - self.world_min_x) / SOLID_SPATIAL_CELL_SIZE))
            end = int(math.floor((x + radius - self.world_min_x) / SOLID_SPATIAL_CELL_SIZE))
            return list(range(start, end + 1))

        local_x = (x - self.world_min_x) % self.world_width
        start = int(math.floor((local_x - radius) / SOLID_SPATIAL_CELL_SIZE))
        end = int(math.floor((local_x + radius) / SOLID_SPATIAL_CELL_SIZE))
        return sorted({cell % self.solid_spatial_cols for cell in range(start, end + 1)})

    def _solid_y_cells(self, y, radius):
        start = int(math.floor((y - radius - self.world_min_y) / SOLID_SPATIAL_CELL_SIZE))
        end = int(math.floor((y + radius - self.world_min_y) / SOLID_SPATIAL_CELL_SIZE))
        return range(start, end + 1)

    def _bbox_cells(self, min_x, max_x, min_y, max_y):
        start_col = int(math.floor((min_x - self.world_min_x) / SOLID_SPATIAL_CELL_SIZE))
        end_col = int(math.floor((max_x - self.world_min_x) / SOLID_SPATIAL_CELL_SIZE))
        start_row = int(math.floor((min_y - self.world_min_y) / SOLID_SPATIAL_CELL_SIZE))
        end_row = int(math.floor((max_y - self.world_min_y) / SOLID_SPATIAL_CELL_SIZE))
        return start_col, end_col, start_row, end_row

    def _register_solid(self, kind, obj, x, y, radius):
        for row in self._solid_y_cells(y, radius):
            for col in self._solid_x_cells(x, radius):
                self.solid_spatial_index.setdefault((col, row), []).append((kind, obj))

    def rebuild_solid_spatial_index(self):
        self.solid_spatial_index = {}

        for turret in self.turrets:
            if turret.alive:
                self._register_solid("turret", turret, turret.x, turret.y, turret.radius)

        for tank in self.tanks:
            if tank.alive:
                self._register_solid("tank", tank, tank.x, tank.y, tank.radius)

        for rock in self.rocks:
            if rock.alive:
                self._register_solid("rock", rock, rock.x, rock.y, rock.radius)

        for gate in self.gates:
            self._register_solid("gate", gate, gate.x, gate.y, gate.radius)

        for switch in self.switches:
            self._register_solid("switch", switch, switch.x, switch.y, switch.radius)

        for fuel_pod in self.fuel_pods:
            if not fuel_pod.destroyed and fuel_pod.fuel_remaining > 0.0:
                self._register_solid("fuel_pod", fuel_pod, fuel_pod.x, fuel_pod.y, fuel_pod.radius)

        if self.reactor and self.reactor.alive:
            self._register_solid("reactor", self.reactor, self.reactor.x, self.reactor.y, self.reactor.radius)

    def rebuild_terrain_spatial_index(self):
        self.terrain_spatial_index = {}
        for line in self.terrain_lines:
            (ax, ay), (bx, by) = line
            min_x = min(ax, bx)
            max_x = max(ax, bx)
            min_y = min(ay, by)
            max_y = max(ay, by)
            start_col, end_col, start_row, end_row = self._bbox_cells(min_x, max_x, min_y, max_y)
            for row in range(start_row, end_row + 1):
                for col in range(start_col, end_col + 1):
                    self.terrain_spatial_index.setdefault((col, row), []).append(line)

    def nearby_solids(self, x, y, radius, kinds=None):
        result = {kind: [] for kind in kinds} if kinds is not None else {}
        seen = set()
        for row in self._solid_y_cells(y, radius):
            for col in self._solid_x_cells(x, radius):
                for kind, obj in self.solid_spatial_index.get((col, row), ()):
                    if kinds is not None and kind not in kinds:
                        continue
                    key = (kind, id(obj))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.setdefault(kind, []).append(obj)
        return result

    def solids_in_bounds(self, min_x, max_x, min_y, max_y, kinds=None):
        result = {kind: [] for kind in kinds} if kinds is not None else {}
        seen = set()
        start_col, end_col, start_row, end_row = self._bbox_cells(min_x, max_x, min_y, max_y)
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                for kind, obj in self.solid_spatial_index.get((col, row), ()):
                    if kinds is not None and kind not in kinds:
                        continue
                    key = (kind, id(obj))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.setdefault(kind, []).append(obj)
        return result

    def terrain_lines_in_bounds(self, min_x, max_x, min_y, max_y):
        lines = []
        seen = set()
        start_col, end_col, start_row, end_row = self._bbox_cells(min_x, max_x, min_y, max_y)
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                for line in self.terrain_spatial_index.get((col, row), ()):
                    key = id(line)
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append(line)
        return lines

    def tractor_blocker_bounds(self, start_x, start_y, end_x, end_y, padding=0.0):
        return (
            min(start_x, end_x) - padding,
            max(start_x, end_x) + padding,
            min(start_y, end_y) - padding,
            max(start_y, end_y) + padding,
        )

    def position_conflicts(self, obj, existing_tanks):
        for tank in existing_tanks:
            if math.hypot(tank.x - obj.x, tank.y - obj.y) < 54:
                return True
        for turret in self.turrets:
            if math.hypot(turret.x - obj.x, turret.y - obj.y) < 54:
                return True
        if self.reactor and math.hypot(self.reactor.x - obj.x, self.reactor.y - obj.y) < 70:
            return True
        for pod in self.fuel_pods:
            if math.hypot(pod.x - obj.x, pod.y - obj.y) < 50:
                return True
        if self.orb and math.hypot(self.orb.x - obj.x, self.orb.y - obj.y) < 60:
            return True
        for rock in self.rocks:
            if math.hypot(rock.x - obj.x, rock.y - obj.y) < 44:
                return True
        return False

    def static_position_conflicts(self, obj, padding=0.0):
        candidates = []
        if self.reactor:
            candidates.append(self.reactor)
        candidates.extend(self.turrets)
        candidates.extend(self.fuel_pods)
        if self.orb:
            candidates.append(self.orb)

        for other in candidates:
            if other is obj:
                continue
            dx = self.wrapped_dx(other.x, obj.x)
            min_gap = getattr(other, "radius", 20.0) + getattr(obj, "radius", 20.0) + padding
            if math.hypot(dx, other.y - obj.y) < min_gap:
                return True
        return False

    def snap_object_to_floor(self, obj, sprite, occupied=None):
        half_w = sprite.get_width() * 0.5
        half_h = sprite.get_height() * 0.5
        floor_offset = getattr(obj, "floor_offset", 0.0)
        best = None
        best_dist = float("inf")
        fallback = None
        fallback_dist = float("inf")
        occupied = occupied or []

        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) >= 0.01:
                continue

            seg_min_x = min(ax, bx)
            seg_max_x = max(ax, bx)
            if (seg_max_x - seg_min_x) < sprite.get_width():
                continue

            cand_x = max(seg_min_x + half_w, min(seg_max_x - half_w, obj.x))
            cand_y = ay - half_h - floor_offset
            dist = math.hypot(cand_x - obj.x, cand_y - obj.y)
            if dist < fallback_dist:
                fallback_dist = dist
                fallback = (cand_x, cand_y)
            if self.placement_overlaps(cand_x, cand_y, obj, occupied):
                continue
            if dist < best_dist:
                best_dist = dist
                best = (cand_x, cand_y)

        if best is None:
            best = fallback

        if best is not None:
            obj.x, obj.y = best

    def placement_overlaps(self, cand_x, cand_y, obj, occupied):
        obj_radius = getattr(obj, "radius", 20.0)
        for other in occupied:
            dx = self.wrapped_dx(other.x, cand_x)
            other_radius = getattr(other, "radius", 20.0)
            if math.hypot(dx, other.y - cand_y) < (obj_radius + other_radius + 10.0):
                return True
        return False

    def snap_switch_to_floor(self, switch, occupied=None):
        best = None
        best_dist = float("inf")
        occupied = occupied or []

        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            seg_dx = bx - ax
            seg_dy = by - ay
            seg_len = math.hypot(seg_dx, seg_dy)
            if seg_len <= 1e-6:
                continue

            contact_x, contact_y = closest_point_on_segment(switch.x, switch.y, ax, ay, bx, by)
            normal_x = -seg_dy / seg_len
            normal_y = seg_dx / seg_len
            if normal_y > 0.0:
                normal_x *= -1.0
                normal_y *= -1.0

            cand_x = contact_x + normal_x * switch.floor_offset
            cand_y = contact_y + normal_y * switch.floor_offset
            dist = math.hypot(cand_x - switch.x, cand_y - switch.y)
            if self.placement_overlaps(cand_x, cand_y, switch, occupied):
                continue
            if dist < best_dist:
                best_dist = dist
                best = (cand_x, cand_y)

        if best is not None:
            switch.x, switch.y = best

    def floor_y_beneath(self, x, current_y, radius):
        best_y = None
        wrapped_x = self.wrap_x(x, radius)
        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) >= 0.01:
                continue
            seg_min_x = min(ax, bx) + radius
            seg_max_x = max(ax, bx) - radius
            if seg_min_x <= wrapped_x <= seg_max_x:
                cand_y = ay - radius
                if cand_y + 0.01 < current_y:
                    continue
                if best_y is None or cand_y < best_y:
                    best_y = cand_y
        return best_y

    def settle_rocks(self):
        if not self.rocks:
            return

        settled = []
        for rock in sorted(self.rocks, key=lambda rock: (rock.y, rock.x), reverse=True):
            support, support_type, support_obj = self.find_dynamic_rock_support(rock, settled)
            if support is not None:
                rock.x, rock.y = support
            rock.support_signature = self.make_rock_support_signature(support_type, support_obj, support)
            settled.append(rock)

    def make_rock_support_signature(self, support_type, support_obj, support_point):
        if support_type == "rock" and support_obj is not None:
            return ("rock", id(support_obj))
        if support_type == "floor" and support_obj is not None:
            return ("floor", tuple(map(tuple, support_obj)))
        return None

    def find_dynamic_rock_support(self, rock, settled_rocks):
        best = None
        best_y = None
        best_type = None
        best_obj = None
        radius = rock.radius

        for line in self.authored_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) >= 0.01:
                continue

            seg_min_x = min(ax, bx) + radius
            seg_max_x = max(ax, bx) - radius
            if seg_min_x > seg_max_x:
                continue

            cand_x = max(seg_min_x, min(seg_max_x, rock.x))
            cand_y = ay - radius
            if cand_y + 0.01 < rock.y:
                continue
            if self.rock_intersects_any(cand_x, cand_y, rock.radius, settled_rocks):
                continue
            if best_y is None or cand_y < best_y:
                best = (cand_x, cand_y)
                best_y = cand_y
                best_type = "floor"
                best_obj = line

        for other in settled_rocks:
            if not other.alive:
                continue
            dx = self.wrapped_dx(other.x, rock.x)
            max_dx = rock.radius + other.radius
            if abs(dx) > max_dx:
                continue

            vertical = math.sqrt(max(0.0, max_dx * max_dx - dx * dx))
            cand_x = self.wrap_x(other.x + dx, rock.radius)
            cand_y = other.y - vertical
            if cand_y + 0.01 < rock.y:
                continue
            if self.rock_intersects_any(cand_x, cand_y, rock.radius, settled_rocks, ignore=other):
                continue
            if best_y is None or cand_y < best_y:
                best = (cand_x, cand_y)
                best_y = cand_y
                best_type = "rock"
                best_obj = other

        return best, best_type, best_obj

    def rock_intersects_any(self, x, y, radius, rocks, ignore=None):
        for other in rocks:
            if other is ignore or not other.alive:
                continue
            dx = self.wrapped_dx(other.x, x)
            if math.hypot(dx, other.y - y) < (other.radius + radius - 0.01):
                return True
        return False

    def resolve_rock_terrain_collision(self, rock):
        collided = False
        wrap_offsets = (0.0,)
        if self.world_width > 0.0:
            wrap_offsets = (-self.world_width, 0.0, self.world_width)

        for _ in range(4):
            best_hit = None
            for line in self.collision_lines():
                (ax, ay), (bx, by) = line
                for wrap_offset in wrap_offsets:
                    shifted_ax = ax + wrap_offset
                    shifted_bx = bx + wrap_offset
                    cx, cy = closest_point_on_segment(rock.x, rock.y, shifted_ax, ay, shifted_bx, by)
                    dx = rock.x - cx
                    dy = rock.y - cy
                    dist = math.hypot(dx, dy)
                    penetration = rock.radius - dist
                    if penetration <= 0.0:
                        continue

                    if dist > 1e-6:
                        nx = dx / dist
                        ny = dy / dist
                    else:
                        speed = math.hypot(rock.vx, rock.vy)
                        if speed > 1e-6:
                            nx = -rock.vx / speed
                            ny = -rock.vy / speed
                        else:
                            seg_dx = shifted_bx - shifted_ax
                            seg_dy = by - ay
                            seg_len = math.hypot(seg_dx, seg_dy)
                            if seg_len <= 1e-6:
                                continue
                            nx = -seg_dy / seg_len
                            ny = seg_dx / seg_len
                            if ny > 0.0:
                                nx *= -1.0
                                ny *= -1.0

                    if best_hit is None or penetration > best_hit[0]:
                        best_hit = (penetration, nx, ny)

            if best_hit is None:
                break

            penetration, nx, ny = best_hit
            rock.x = self.wrap_x(rock.x + nx * (penetration + 0.05), rock.radius)
            rock.y += ny * (penetration + 0.05)
            vn = rock.vx * nx + rock.vy * ny
            if vn < 0.0:
                rock.vx -= vn * nx
                rock.vy -= vn * ny
            tangent_x = -ny
            tangent_y = nx
            vt = rock.vx * tangent_x + rock.vy * tangent_y
            rock.vx = tangent_x * vt * ROCK_TERRAIN_FRICTION
            rock.vy = tangent_y * vt * ROCK_TERRAIN_FRICTION
            if abs(rock.vx) < ROCK_STOP_SPEED:
                rock.vx = 0.0
            if abs(rock.vy) < ROCK_STOP_SPEED:
                rock.vy = 0.0
            rock.angular_velocity *= ROCK_GROUND_DAMPING
            collided = True

        return collided

    def resolve_orb_terrain_collision(self, orb):
        for line in self.collision_lines():
            (ax, ay), (bx, by) = line
            cx, cy = closest_point_on_segment(orb.x, orb.y, ax, ay, bx, by)
            dx = orb.x - cx
            dy = orb.y - cy
            dist = math.hypot(dx, dy)
            if dist >= orb.radius or dist == 0.0:
                if dist != 0.0 or point_to_segment_distance(orb.x, orb.y, ax, ay, bx, by) >= orb.radius:
                    continue
                seg_dx = bx - ax
                seg_dy = by - ay
                seg_len = math.hypot(seg_dx, seg_dy)
                if seg_len == 0.0:
                    continue
                nx = -seg_dy / seg_len
                ny = seg_dx / seg_len
            else:
                nx = dx / dist
                ny = dy / dist

            penetration = orb.radius - max(dist, 0.0)
            if penetration <= 0.0:
                continue

            orb.x = self.wrap_x(orb.x + nx * (penetration + 0.05), orb.radius)
            orb.y += ny * (penetration + 0.05)
            return True
        return False

    def update(self, dt, ship=None):
        for gate in self.gates:
            gate.update(dt, self, ship)
        for switch in self.switches:
            switch.update(dt)
        if not self.rocks_unlocked:
            self.rebuild_solid_spatial_index()
            return
        settled = []
        for rock in sorted((rock for rock in self.rocks if rock.alive), key=lambda rock: (rock.y, rock.x), reverse=True):
            rock.update(dt, self, settled)
            settled.append(rock)
        self.rebuild_solid_spatial_index()

    def world_bounds(self):
        return (self.world_min_x, self.world_max_x, self.world_min_y, self.world_max_y)

    def wrap_x(self, x, radius=0.0):
        if self.world_width <= 0:
            return x
        if x < self.world_min_x - radius:
            return x + self.world_width
        if x > self.world_max_x + radius:
            return x - self.world_width
        return x

    def wrapped_dx(self, from_x, to_x):
        dx = to_x - from_x
        if self.world_width <= 0:
            return dx
        half_width = self.world_width * 0.5
        if dx > half_width:
            dx -= self.world_width
        elif dx < -half_width:
            dx += self.world_width
        return dx

    def camera_for(self, world_x, world_y):
        world_width = self.world_max_x - self.world_min_x
        camera_min_y = self.orbit_top_y
        world_height = self.world_max_y - camera_min_y

        if world_width <= SCREEN_WIDTH:
            camera_x = self.world_min_x - (SCREEN_WIDTH - world_width) * 0.5
        else:
            camera_x = world_x - SCREEN_WIDTH * 0.5

        if world_height <= SCREEN_HEIGHT:
            camera_y = camera_min_y - (SCREEN_HEIGHT - world_height) * 0.5
        else:
            camera_y = max(
                camera_min_y,
                min(self.world_max_y - SCREEN_HEIGHT, world_y - SCREEN_HEIGHT * 0.5),
            )

        return camera_x, camera_y

    def draw_world_offset(self, world_x, camera_x):
        if self.world_width <= SCREEN_WIDTH:
            return 0.0
        anchor_x = camera_x + SCREEN_WIDTH * 0.5
        return anchor_x + self.wrapped_dx(anchor_x, world_x) - world_x


    def build_star_field(self):
        rng = random.Random(f"{self.name}-stars")
        stars = []
        for _ in range(STARFIELD_STAR_COUNT):
            stars.append({
                "x": rng.uniform(self.world_min_x, self.world_max_x),
                "y": rng.uniform(self.orbit_top_y + 18.0, self.world_min_y + STARFIELD_FADE_START + STARFIELD_FADE_DISTANCE),
                "radius": rng.choice((1, 1, 1, 2)),
                "alpha": rng.randint(90, 180),
            })
        return stars

    def draw_star_field(self, screen, camera_x=0.0, camera_y=0.0):
        height_into_upper_band = self.world_min_y - camera_y
        fade = max(0.0, min(1.0, (height_into_upper_band - STARFIELD_FADE_START) / STARFIELD_FADE_DISTANCE))
        if fade <= 0.0:
            return

        star_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for star in self.star_field:
            offset_x = self.draw_world_offset(star["x"], camera_x) if self.world_width > SCREEN_WIDTH else 0.0
            screen_x = int(star["x"] + offset_x - camera_x)
            screen_y = int(star["y"] - camera_y)
            if screen_x < -6 or screen_x > SCREEN_WIDTH + 6 or screen_y < -6 or screen_y > SCREEN_HEIGHT + 6:
                continue
            alpha = int(star["alpha"] * fade)
            glow = max(40, int(alpha * 0.55))
            pygame.draw.circle(star_surface, (170, 210, 255, glow), (screen_x, screen_y), star["radius"] + 2)
            pygame.draw.circle(star_surface, (245, 248, 255, alpha), (screen_x, screen_y), star["radius"])
        screen.blit(star_surface, (0, 0))

    def draw_line_to_surface(self, surface, colour, line, width):
        (ax, ay), (bx, by) = line
        start = (ax - self.world_min_x, ay - self.orbit_top_y)
        end = (bx - self.world_min_x, by - self.orbit_top_y)
        glow_outer = (
            min(255, int(colour[0] * 0.58 + 18)),
            min(255, int(colour[1] * 0.58 + 18)),
            min(255, int(colour[2] * 0.58 + 18)),
            84,
        )
        glow_inner = (
            min(255, int(colour[0] * 0.78 + 28)),
            min(255, int(colour[1] * 0.78 + 28)),
            min(255, int(colour[2] * 0.78 + 28)),
            126,
        )
        pygame.draw.line(surface, glow_outer, start, end, width + 18)
        pygame.draw.line(surface, glow_inner, start, end, width + 11)
        pygame.draw.line(surface, colour, start, end, width)

    def build_terrain_surface(self):
        surface = pygame.Surface((self.render_width + 1, self.render_height + 1), pygame.SRCALPHA)
        for record in self.terrain_line_records:
            self.draw_line_to_surface(surface, record["colour"], tuple(record["points"]), 5)
        return surface

    def collision_lines(self):
        return self.terrain_lines

    def tractor_terrain_blocked(self, start_x, start_y, target_x, target_y, end_clearance=0.0):
        """True when cave terrain or solid blockers interrupt the tractor path."""
        path_start = (start_x, start_y)
        path_end = (target_x, target_y)
        path_length = math.hypot(path_end[0] - path_start[0], path_end[1] - path_start[1])
        blocker_limit = max(0.0, path_length - end_clearance)
        min_x, max_x, min_y, max_y = self.tractor_blocker_bounds(
            start_x,
            start_y,
            target_x,
            target_y,
            padding=TRACTOR_BLOCKER_QUERY_PADDING,
        )

        for line in self.terrain_lines_in_bounds(min_x, max_x, min_y, max_y):
            (ax, ay), (bx, by) = line
            along = segment_intersection_distance(path_start, path_end, (ax, ay), (bx, by))
            if along is not None and along < blocker_limit:
                return True

        nearby = self.solids_in_bounds(min_x, max_x, min_y, max_y, kinds=TRACTOR_BLOCKER_KINDS)
        for rock in nearby.get("rock", ()):
            if not rock.alive:
                continue
            distance = point_to_segment_distance(rock.x, rock.y, path_start[0], path_start[1], path_end[0], path_end[1])
            if distance >= rock.radius:
                continue
            along = (
                (rock.x - path_start[0]) * (path_end[0] - path_start[0])
                + (rock.y - path_start[1]) * (path_end[1] - path_start[1])
            ) / max(path_length, 1e-6)
            if along < blocker_limit:
                return True

        for gate in nearby.get("gate", ()):
            for segment in gate.segments(self):
                along = segment_intersection_distance(path_start, path_end, segment[0], segment[1])
                if along is not None and along < blocker_limit:
                    return True

        for switch in nearby.get("switch", ()):
            distance = point_to_segment_distance(switch.x, switch.y, path_start[0], path_start[1], path_end[0], path_end[1])
            if distance >= switch.radius:
                continue
            along = (
                (switch.x - path_start[0]) * (path_end[0] - path_start[0])
                + (switch.y - path_start[1]) * (path_end[1] - path_start[1])
            ) / max(path_length, 1e-6)
            if along < blocker_limit:
                return True

        return False

    def tractor_beam_visible_length(self, start_x, start_y, dir_x, dir_y, max_length):
        """Return how far the tractor beam can be drawn before hitting terrain or solid blockers."""
        nearest = max_length
        end_x = start_x + dir_x * max_length
        end_y = start_y + dir_y * max_length
        path_start = (start_x, start_y)
        path_end = (end_x, end_y)
        path_length = math.hypot(path_end[0] - path_start[0], path_end[1] - path_start[1])
        min_x, max_x, min_y, max_y = self.tractor_blocker_bounds(
            start_x,
            start_y,
            end_x,
            end_y,
            padding=TRACTOR_BLOCKER_QUERY_PADDING,
        )

        for line in self.terrain_lines_in_bounds(min_x, max_x, min_y, max_y):
            (ax, ay), (bx, by) = line
            along = segment_intersection_distance(path_start, path_end, (ax, ay), (bx, by))
            if along is not None and along < nearest:
                nearest = along

        nearby = self.solids_in_bounds(min_x, max_x, min_y, max_y, kinds=TRACTOR_BLOCKER_KINDS)
        for rock in nearby.get("rock", ()):
            if not rock.alive:
                continue
            distance = point_to_segment_distance(rock.x, rock.y, path_start[0], path_start[1], path_end[0], path_end[1])
            if distance >= rock.radius:
                continue
            along = (
                (rock.x - path_start[0]) * (path_end[0] - path_start[0])
                + (rock.y - path_start[1]) * (path_end[1] - path_start[1])
            ) / max(path_length, 1e-6)
            if 0.0 <= along < nearest:
                nearest = along

        for gate in nearby.get("gate", ()):
            for segment in gate.segments(self):
                along = segment_intersection_distance(path_start, path_end, segment[0], segment[1])
                if along is not None and along < nearest:
                    nearest = along

        for switch in nearby.get("switch", ()):
            distance = point_to_segment_distance(switch.x, switch.y, path_start[0], path_start[1], path_end[0], path_end[1])
            if distance >= switch.radius:
                continue
            along = (
                (switch.x - path_start[0]) * (path_end[0] - path_start[0])
                + (switch.y - path_start[1]) * (path_end[1] - path_start[1])
            ) / max(path_length, 1e-6)
            if 0.0 <= along < nearest:
                nearest = along

        return max(0.0, nearest)

    def tractor_beam_target_length(self, start_x, start_y, dir_x, dir_y, beam_half_width):
        """Extend beam visuals to the nearest valid reachable target resting on terrain."""
        nearest = 0.0
        targets = [pod for pod in self.fuel_pods if pod.fuel_remaining > 0.0]
        if self.orb and not self.orb.collected:
            targets.append(self.orb)

        perp_x = -dir_y
        perp_y = dir_x
        for target in targets:
            rel_x = target.x - start_x
            rel_y = target.y - start_y
            along = rel_x * dir_x + rel_y * dir_y
            if along < 0.0 or along > TRACTOR_BEAM_LENGTH:
                continue
            width_here = beam_half_width * (0.45 + 0.55 * (1.0 - along / TRACTOR_BEAM_LENGTH))
            perp = abs(rel_x * perp_x + rel_y * perp_y)
            if perp > width_here + getattr(target, "radius", 0.0):
                continue
            if self.tractor_terrain_blocked(
                start_x,
                start_y,
                target.x,
                target.y,
                end_clearance=getattr(target, "radius", 0.0) + 6.0,
            ):
                continue
            nearest = max(nearest, along + getattr(target, "radius", 0.0) * 0.35)

        return nearest

    def ship_escaped(self, ship):
        return self.ship_in_orbit(ship)

    def ship_in_orbit(self, ship):
        return (ship.y + ship.radius) < (self.orbit_top_y + ORBIT_ESCAPE_MARGIN)

    def draw(self, screen, camera_x=0.0, camera_y=0.0):
        screen.fill(self.background_colour)
        self.draw_star_field(screen, camera_x, camera_y)
        if self.world_width > 0:
            local_camera_x = (camera_x - self.world_min_x) % self.world_width
        else:
            local_camera_x = 0.0
        dest_y = int(round(-(camera_y - self.orbit_top_y)))
        first_x = int(round(-local_camera_x))
        screen.blit(self.terrain_surface, (first_x, dest_y))
        if first_x + self.render_width < SCREEN_WIDTH:
            screen.blit(self.terrain_surface, (first_x + self.render_width, dest_y))
        if first_x > 0:
            screen.blit(self.terrain_surface, (first_x - self.render_width, dest_y))

        for fuel_pod in self.fuel_pods:
            fuel_pod.draw(screen, camera_x, camera_y, self)

        if self.orb:
            self.orb.draw(screen, camera_x, camera_y, self)

        for gate in self.gates:
            gate.draw(screen, camera_x, camera_y, self)

        for switch in self.switches:
            switch.draw(screen, camera_x, camera_y, self, self.gates_by_id.get(switch.gate_id))

        for turret in self.turrets:
            turret.draw(screen, camera_x, camera_y, self)

        for tank in self.tanks:
            tank.draw(screen, camera_x, camera_y, self)

        for rock in self.rocks:
            rock.draw(screen, camera_x, camera_y, self)

        if self.reactor:
            self.reactor.draw(screen, camera_x, camera_y, self)


# ------------------------------------------------------------
# Main game class
# ------------------------------------------------------------

class Game:
    def __init__(self, start_level=1, level_file=None):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)

        self.controls = load_controls()

        self.sprites = {
            "ship": load_sprite("assets/ship.png", (36, 24), (240, 240, 255)),
            "turret": load_sprite("assets/turret.png", (24, 24), (255, 100, 100)),
            "reactor": create_reactor_sprite(),
            "fuel_pod": create_fuel_pod_sprite(),
            "orb": create_orb_sprite(),
        }

        if level_file is not None:
            self.level_paths = [level_file]
        else:
            self.level_paths = [
                path
                for path in sorted(glob.glob("levels/*.json"))
                if is_playable_level_data(load_json(path))
            ]
        if not self.level_paths:
            raise RuntimeError("No playable level JSON files found in levels/")

        self.level_index = max(0, min(len(self.level_paths) - 1, start_level - 1))
        self.level = None
        self.ship = None
        self.bullets = []
        self.thrust_particles = []
        self.spark_particles = []
        self.flame_particles = []
        self.reactor_debris_particles = []
        self.fuel_transfer_particles = []
        self.ship_destruction_time = 0.0
        self.escape_timer = None
        self.level_destroyed = False
        self.level_destruction_time = 0.0
        self.pending_next_level_after_destruction = False
        self.pending_orbit_exit_action = None
        self.game_won = False
        self.score = 0
        self.next_extra_life_score = EXTRA_LIFE_SCORE
        self.lives = 3
        self.running = True
        self.paused = False
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.screen_flash_time = 0.0
        self.screen_flash_duration = 0.0
        self.camera_shake_time = 0.0
        self.camera_shake_duration = 0.0
        self.camera_shake_strength = 0.0
        self.sound_enabled = pygame.mixer.get_init() is not None
        self.sounds = {}
        self.tractor_channel = None
        self.thruster_channel = None
        self.setup_audio()
        self.load_level(self.level_index)

    def setup_audio(self):
        if not self.sound_enabled:
            return

        self.sounds = {
            "player_fire": create_tone_sound((760, 1120, 1380), 0.09, volume=0.26, decay=8.0),
            "enemy_fire": create_tone_sound((240, 310, 420), 0.11, volume=0.22, decay=7.0),
            "tractor_loop": create_tone_sound((90, 120, 180), 0.28, volume=0.18, decay=0.8),
            "thruster_loop": create_noise_sound(0.72, volume=0.06, decay=0.12, smoothness=0.965, drive=4.8),
            "orb_pickup": create_tone_sound((523, 659, 784, 1047), 0.42, volume=0.34, decay=2.2),
            "orbit_ping": create_echo_tone_sound((1319, 1760, 2093), 0.80, volume=0.34, decay=4.2),
            "fuel_pod_plop": create_bloop_sound(0.34, volume=0.34),
            "explosion_small": create_noise_sound(0.42, volume=0.34, decay=2.8, smoothness=0.72, drive=3.8),
            "explosion_medium": create_noise_sound(0.62, volume=0.44, decay=2.4, smoothness=0.78, drive=4.2),
            "explosion_large": create_noise_sound(0.96, volume=0.58, decay=1.9, smoothness=0.82, drive=4.6),
            "explosion_reactor": create_noise_sound(1.35, volume=0.78, decay=1.25, smoothness=0.88, drive=5.0),
        }
        self.tractor_channel = pygame.mixer.Channel(1)
        self.thruster_channel = pygame.mixer.Channel(2)

    def play_sound(self, name):
        if not self.sound_enabled:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def update_audio(self):
        if not self.sound_enabled or self.tractor_channel is None or self.thruster_channel is None:
            return

        tractor_active = (
            self.ship is not None
            and self.ship.is_operational()
            and self.ship.tractor_active
            and not self.level_destroyed
            and not self.paused
        )
        if tractor_active:
            if not self.tractor_channel.get_busy():
                loop_sound = self.sounds.get("tractor_loop")
                if loop_sound is not None:
                    self.tractor_channel.play(loop_sound, loops=-1)
        else:
            self.tractor_channel.stop()

        thruster_active = (
            self.ship is not None
            and self.ship.is_operational()
            and self.ship.thrusting
            and not self.level_destroyed
            and not self.paused
        )
        if thruster_active:
            if not self.thruster_channel.get_busy():
                loop_sound = self.sounds.get("thruster_loop")
                if loop_sound is not None:
                    self.thruster_channel.play(loop_sound, loops=-1)
        else:
            self.thruster_channel.stop()

    def stop_audio(self):
        if not self.sound_enabled:
            return
        if self.tractor_channel is not None:
            self.tractor_channel.stop()
        if self.thruster_channel is not None:
            self.thruster_channel.stop()

    def load_level(self, level_index):
        level_data = load_json(self.level_paths[level_index])
        self.level = Level(level_data, self.sprites)
        self.ship = Ship(*self.level.ship_start, self.sprites["ship"])
        self.bullets.clear()
        self.thrust_particles.clear()
        self.spark_particles.clear()
        self.flame_particles.clear()
        self.reactor_debris_particles.clear()
        self.fuel_transfer_particles.clear()
        self.ship_destruction_time = 0.0
        self.escape_timer = None
        self.level_destroyed = False
        self.level_destruction_time = 0.0
        self.pending_next_level_after_destruction = False
        self.pending_orbit_exit_action = None
        self.ship.start_materialize()
        self.camera_x, self.camera_y = self.level.camera_for(self.ship.x, self.ship.y)
        self.screen_flash_time = 0.0
        self.screen_flash_duration = 0.0
        self.camera_shake_time = 0.0
        self.camera_shake_duration = 0.0
        self.camera_shake_strength = 0.0
        self.update_audio()

    def advance_to_next_level(self):
        next_index = self.level_index + 1
        if next_index >= len(self.level_paths):
            self.game_won = True
            self.running = False
            return
        self.level_index = next_index
        self.load_level(self.level_index)

    def respawn_ship(self):
        self.ship = Ship(*self.level.ship_start, self.sprites["ship"])
        if self.level.orb and self.level.orb.collected:
            self.ship.has_orb = True
        self.ship.start_materialize()
        self.bullets.clear()
        self.thrust_particles.clear()
        self.fuel_transfer_particles.clear()
        self.ship_destruction_time = 0.0
        self.update_audio()

    def begin_orbit_exit(self, action):
        if not self.ship.alive or self.ship.is_transporting():
            return
        self.pending_orbit_exit_action = action
        self.play_sound("orbit_ping")
        self.ship.start_dematerialize()
        self.bullets.clear()
        self.thrust_particles.clear()
        self.fuel_transfer_particles.clear()

    def spawn_turret_explosion(self, x, y):
        self.play_sound("explosion_medium")
        for _ in range(TURRET_EXPLOSION_PARTICLES):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(TURRET_SPARK_SPEED_MIN, TURRET_SPARK_SPEED_MAX)
            life = random.uniform(TURRET_SPARK_LIFE_MIN, TURRET_SPARK_LIFE_MAX)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(18):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(80.0, 240.0)
            life = random.uniform(0.25, 0.70)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-12.0, 12.0),
                    y + random.uniform(-10.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(10.0, 70.0),
                    life,
                )
            )

        for _ in range(10):
            angle = random.uniform(math.pi * 1.05, math.pi * 1.95)
            speed = random.uniform(90.0, 220.0)
            life = random.uniform(0.45, 0.95)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-10.0, 10.0),
                    y + random.uniform(-8.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(20.0, 80.0),
                    life,
                )
            )

    def spawn_rock_explosion(self, x, y):
        self.play_sound("explosion_small")
        for _ in range(26):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(50.0, 170.0)
            life = random.uniform(0.45, 0.95)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-6.0, 6.0),
                    y + random.uniform(-6.0, 6.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(5.0, 45.0),
                    life,
                )
            )

        for _ in range(12):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(35.0, 140.0)
            life = random.uniform(0.14, 0.30)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

    def spawn_plinth_explosion(self, x, y):
        self.play_sound("explosion_medium")
        self.screen_flash_time = max(self.screen_flash_time, 0.18)
        self.screen_flash_duration = max(self.screen_flash_duration, 0.18)

        for _ in range(42):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(90.0, 240.0)
            life = random.uniform(0.18, 0.48)
            self.spark_particles.append(
                SparkParticle(
                    x + random.uniform(-10.0, 10.0),
                    y + random.uniform(-10.0, 10.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(20):
            angle = random.uniform(-math.pi, 0.1)
            speed = random.uniform(50.0, 170.0)
            life = random.uniform(0.20, 0.55)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-16.0, 16.0),
                    y + random.uniform(-10.0, 10.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(10.0, 55.0),
                    life,
                )
            )

        for _ in range(16):
            angle = random.uniform(math.pi * 1.02, math.pi * 1.98)
            speed = random.uniform(70.0, 220.0)
            life = random.uniform(0.45, 1.05)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-12.0, 12.0),
                    y + random.uniform(-8.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(10.0, 70.0),
                    life,
                )
            )

    def spawn_tank_explosion(self, x, y):
        self.play_sound("explosion_medium")
        for _ in range(32):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(90.0, 240.0)
            life = random.uniform(0.22, 0.55)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(20):
            angle = random.uniform(-math.pi, 0.15)
            speed = random.uniform(70.0, 200.0)
            life = random.uniform(0.28, 0.72)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-16.0, 16.0),
                    y + random.uniform(-8.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(15.0, 75.0),
                    life,
                )
            )

        for _ in range(12):
            angle = random.uniform(math.pi * 1.05, math.pi * 1.95)
            speed = random.uniform(80.0, 210.0)
            life = random.uniform(0.40, 0.90)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-12.0, 12.0),
                    y + random.uniform(-6.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(20.0, 70.0),
                    life,
                )
            )

    def spawn_fuel_pod_plop(self, x, y):
        self.play_sound("fuel_pod_plop")
        for _ in range(14):
            angle = random.uniform(-math.pi * 0.95, -math.pi * 0.05)
            speed = random.uniform(22.0, 74.0)
            life = random.uniform(0.08, 0.16)
            self.spark_particles.append(
                SparkParticle(
                    x + random.uniform(-6.0, 6.0),
                    y + random.uniform(-4.0, 4.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(6.0, 18.0),
                    life,
                )
            )

        for _ in range(8):
            angle = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            speed = random.uniform(18.0, 52.0)
            life = random.uniform(0.10, 0.20)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-8.0, 8.0),
                    y + random.uniform(-2.0, 5.0),
                    math.cos(angle) * speed * 0.45,
                    math.sin(angle) * speed - random.uniform(10.0, 22.0),
                    life,
                )
            )

        for _ in range(4):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(10.0, 26.0)
            life = random.uniform(0.12, 0.22)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y - 4.0,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

    def spawn_bullet_impact(self, x, y, from_player=False):
        spark_count = 8 if from_player else 6
        for _ in range(spark_count):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(60.0, 180.0)
            life = random.uniform(0.10, 0.24)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        flame_count = 3 if from_player else 2
        for _ in range(flame_count):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(30.0, 110.0)
            life = random.uniform(0.10, 0.22)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-2.0, 2.0),
                    y + random.uniform(-2.0, 2.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(5.0, 30.0),
                    life,
                )
            )

    def spawn_reactor_explosion(self, x, y):
        self.play_sound("explosion_reactor")
        self.screen_flash_time = 0.28
        self.screen_flash_duration = 0.28
        self.camera_shake_time = 0.9
        self.camera_shake_duration = 0.9
        self.camera_shake_strength = 18.0
        for _ in range(REACTOR_EXPLOSION_PARTICLES):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(140.0, 420.0)
            life = random.uniform(0.35, 0.95)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(46):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(90.0, 280.0)
            life = random.uniform(0.45, 1.15)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-26.0, 26.0),
                    y + random.uniform(-16.0, 16.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(35.0, 130.0),
                    life,
                )
            )

        for _ in range(REACTOR_DEBRIS_PARTICLES):
            angle = random.uniform(math.pi * 1.05, math.pi * 1.95)
            speed = random.uniform(180.0, 420.0)
            life = random.uniform(1.1, 2.3)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-30.0, 30.0),
                    y + random.uniform(-22.0, 16.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(110.0, 230.0),
                    life,
                )
            )

        for _ in range(24):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(55.0, 170.0)
            life = random.uniform(0.16, 0.38)
            self.spark_particles.append(
                SparkParticle(
                    x + random.uniform(-8.0, 8.0),
                    y + random.uniform(-8.0, 8.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

    def spawn_reactor_hit_sparks(self, x, y):
        for _ in range(REACTOR_HIT_SPARKS):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(80.0, 220.0)
            life = random.uniform(0.15, 0.35)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

    def spawn_ship_explosion(self, x, y, vx=0.0, vy=0.0):
        self.play_sound("explosion_large")
        for _ in range(SHIP_DESTRUCTION_SPARKS):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(90.0, 250.0)
            life = random.uniform(0.25, 0.65)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    vx + math.cos(angle) * speed,
                    vy + math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(10):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(40.0, 120.0)
            life = random.uniform(0.12, 0.30)
            self.spark_particles.append(
                SparkParticle(
                    x + random.uniform(-4.0, 4.0),
                    y + random.uniform(-4.0, 4.0),
                    vx + math.cos(angle) * speed,
                    vy + math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(SHIP_DESTRUCTION_FLAMES):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(70.0, 210.0)
            life = random.uniform(0.25, 0.60)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-8.0, 8.0),
                    y + random.uniform(-6.0, 6.0),
                    vx + math.cos(angle) * speed,
                    vy + math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(SHIP_DEBRIS_PARTICLES):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(110.0, 240.0)
            life = random.uniform(0.45, 0.95)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-9.0, 9.0),
                    y + random.uniform(-7.0, 7.0),
                    vx + math.cos(angle) * speed,
                    vy + math.sin(angle) * speed - random.uniform(10.0, 70.0),
                    life,
                )
            )

    def destroy_ship(self, lose_life=True):
        if not self.ship.alive:
            return
        self.spawn_ship_explosion(self.ship.x, self.ship.y, self.ship.vx, self.ship.vy)
        self.ship.alive = False
        self.ship_destruction_time = SHIP_DESTRUCTION_DURATION
        if lose_life:
            self.lives = max(0, self.lives - 1)

    def ship_collision_response(self, nx, ny, lose_life=True, other_radius=0.0):
        if self.ship.can_bounce():
            distance = math.hypot(nx, ny)
            overlap = (self.ship.collision_radius() + other_radius) - distance
            separation = max(4.0, overlap + 2.0)
            self.ship.bounce_off_normal(nx, ny, separation=separation)
            return
        self.destroy_ship(lose_life=lose_life)

    def handle_ship_solid_collisions(self, ship_collision_radius):
        nearby = self.level.nearby_solids(self.ship.x, self.ship.y, ship_collision_radius, kinds=SHIP_SOLID_KINDS)
        for kind in SHIP_SOLID_KINDS:
            for solid in nearby.get(kind, ()): 
                if getattr(solid, "alive", True) is False:
                    continue
                if kind == "fuel_pod" and solid.fuel_remaining <= 0.0:
                    continue
                if not solid.contains_point(self.ship.x, self.ship.y, ship_collision_radius, self.level):
                    continue
                dx = self.level.wrapped_dx(solid.x, self.ship.x)
                if kind == "gate":
                    self.destroy_ship()
                    return True
                self.ship_collision_response(dx, self.ship.y - solid.y, other_radius=solid.radius)
                return True
        return False

    def handle_gate_ship_contact(self):
        if not self.ship.is_operational():
            return False
        ship_collision_radius = self.ship.collision_radius()
        for gate in self.level.nearby_solids(self.ship.x, self.ship.y, ship_collision_radius, kinds=("gate",)).get("gate", ()):
            if gate.contains_point(self.ship.x, self.ship.y, ship_collision_radius, self.level):
                self.destroy_ship()
                return True
        return False

    def handle_bullet_solid_collision(self, bullet):
        nearby = self.level.nearby_solids(bullet.x, bullet.y, bullet.radius, kinds=BULLET_SOLID_KINDS)

        for gate in nearby.get("gate", ()):
            if gate.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                bullet.alive = False
                self.spawn_bullet_impact(bullet.x, bullet.y, from_player=bullet.from_player)
                return True

        for switch in nearby.get("switch", ()):
            if not switch.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                continue
            bullet.alive = False
            self.spawn_bullet_impact(bullet.x, bullet.y, from_player=bullet.from_player)
            if bullet.from_player:
                switch.activate(self.level.gates_by_id.get(switch.gate_id))
            return True

        for rock in nearby.get("rock", ()):
            if not rock.alive or not rock.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                continue
            bullet.alive = False
            self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
            destroyed = rock.apply_hit()
            if destroyed:
                self.add_score(SCORE_ROCK)
                self.level.rocks_unlocked = True
                self.spawn_rock_explosion(rock.x, rock.y)
            return True

        if not bullet.from_player:
            return False

        for turret in nearby.get("turret", ()):
            if not turret.alive or not turret.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                continue
            bullet.alive = False
            self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
            destroyed = turret.apply_hit()
            if destroyed:
                self.add_score(SCORE_TURRET)
                self.spawn_turret_explosion(turret.x, turret.y)
            return True

        for tank in nearby.get("tank", ()):
            if not tank.alive or not tank.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                continue
            bullet.alive = False
            self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
            destroyed = tank.apply_hit()
            if destroyed:
                self.add_score(SCORE_TANK)
                self.spawn_tank_explosion(tank.x, tank.y)
            return True

        reactor = self.level.reactor
        if reactor and reactor.alive and reactor in nearby.get("reactor", ()) and reactor.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
            bullet.alive = False
            self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
            destroyed = reactor.apply_hit()
            if destroyed:
                self.add_score(SCORE_REACTOR)
                self.award_extra_life()
                self.spawn_reactor_explosion(reactor.x, reactor.y)
                self.escape_timer = REACTOR_ESCAPE_TIME
            else:
                self.spawn_reactor_hit_sparks(reactor.x, reactor.y)
            return True

        return False

    def random_level_point(self):
        if self.level.terrain_lines and random.random() < 0.7:
            (ax, ay), (bx, by) = random.choice(self.level.terrain_lines)
            t = random.random()
            return (ax + (bx - ax) * t, ay + (by - ay) * t)
        min_x, max_x, min_y, max_y = self.level.world_bounds()
        return (random.uniform(min_x, max_x), random.uniform(min_y, max_y))

    def spawn_level_destruction(self, sparks, flames):
        for _ in range(sparks):
            x, y = self.random_level_point()
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(80.0, 320.0)
            life = random.uniform(0.25, 0.90)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(flames):
            x, y = self.random_level_point()
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(60.0, 220.0)
            life = random.uniform(0.20, 0.65)
            self.flame_particles.append(
                FlameParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

    def trigger_level_self_destruct(self):
        if self.level_destroyed:
            return
        self.level_destroyed = True
        self.level_destruction_time = LEVEL_SELF_DESTRUCT_DURATION
        self.pending_next_level_after_destruction = True
        self.bullets.clear()
        self.thrust_particles.clear()
        self.spawn_level_destruction(LEVEL_DESTRUCT_SPARK_BURST, LEVEL_DESTRUCT_FLAME_BURST)
        self.destroy_ship()

    def respawn_after_orbit_breach(self):
        self.respawn_ship()
        self.bullets.clear()
        self.spark_particles.clear()
        self.flame_particles.clear()
        self.reactor_debris_particles.clear()
        self.fuel_transfer_particles.clear()

    def add_score(self, points):
        self.score += points
        while self.score >= self.next_extra_life_score:
            self.lives += 1
            self.next_extra_life_score += EXTRA_LIFE_SCORE

    def award_extra_life(self):
        self.lives += 1

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                    continue

                if event.key == self.controls["pause"]:
                    self.paused = not self.paused
                    continue

                if event.key == self.controls["fire"]:
                    if self.game_won:
                        continue

                    keys = pygame.key.get_pressed()
                    shield_active = keys[self.controls["tractor"]]

                    if self.ship.is_operational() and not self.level_destroyed and not shield_active:
                        angle = math.radians(self.ship.angle)
                        bullet_x, bullet_y = self.ship.get_nose_position(offset=BULLET_SPAWN_OFFSET)
                        self.bullets.append(
                            Bullet(
                                bullet_x,
                                bullet_y,
                                math.cos(angle) * BULLET_SPEED,
                                math.sin(angle) * BULLET_SPEED,
                            )
                        )
                        self.play_sound("player_fire")
                    elif (not self.ship.alive) and self.lives > 0 and not self.level_destroyed and self.ship_destruction_time <= 0.0:
                        self.respawn_ship()

    def update(self, dt):
        if self.game_won or self.paused:
            return

        self.level.update(dt, self.ship)
        if self.handle_gate_ship_contact():
            return

        if self.ship and self.ship.alive and self.ship.update_transporter(dt):
            if self.pending_orbit_exit_action == "advance":
                self.pending_orbit_exit_action = None
                self.advance_to_next_level()
                return
            if self.pending_orbit_exit_action == "respawn":
                self.pending_orbit_exit_action = None
                self.respawn_after_orbit_breach()
                return

        keys = pygame.key.get_pressed()
        if self.ship.is_operational() and not self.level_destroyed:
            was_alive = self.ship.alive
            self.ship.update(dt, keys, self.controls, self.level)
            ship_collision_radius = self.ship.collision_radius()

            if was_alive and not self.ship.alive:
                self.ship.alive = True
                self.destroy_ship()

            if self.ship.alive:
                self.handle_ship_solid_collisions(ship_collision_radius)

        if self.ship.is_operational() and self.ship.thrusting and not self.level_destroyed:
            base_left, base_right = self.ship.get_base_points()
            rear_angle = math.radians(self.ship.angle + 180.0)
            spread = math.radians(THRUST_SPREAD_DEGREES)
            for _ in range(THRUST_PARTICLES_PER_FRAME):
                t = random.uniform(0.15, 0.85)
                base_x = base_left[0] + (base_right[0] - base_left[0]) * t
                base_y = base_left[1] + (base_right[1] - base_left[1]) * t
                jitter = random.uniform(-1.0, 1.0)
                particle_angle = rear_angle + jitter * spread
                speed = random.uniform(THRUST_SPEED_MIN, THRUST_SPEED_MAX)
                self.thrust_particles.append(
                    ThrustParticle(
                        base_x,
                        base_y,
                        self.ship.vx + math.cos(particle_angle) * speed,
                        self.ship.vy + math.sin(particle_angle) * speed,
                    )
                )

        if self.ship.is_operational() and not self.level_destroyed:
            for turret in self.level.turrets:
                fired = turret.update(dt, self.ship, self.bullets, self.level)
                if fired:
                    self.play_sound("enemy_fire")

            for tank in self.level.tanks:
                fired = tank.update(dt, self.ship, self.bullets, self.level)
                if fired:
                    self.play_sound("enemy_fire")

            for fuel_pod in self.level.fuel_pods:
                depleted = fuel_pod.update(self.ship, self.level, self.ship.tractor_active, dt, self.fuel_transfer_particles)
                if depleted:
                    self.spawn_fuel_pod_plop(fuel_pod.x, fuel_pod.y)

            if self.level.orb:
                if self.level.orb.update(self.ship, self.level, self.ship.tractor_active, dt):
                    self.play_sound("orb_pickup")

        for fuel_particle in self.fuel_transfer_particles:
            fuel_particle.update(dt, self.ship, self.level)

        if not self.level_destroyed:
            for bullet in self.bullets:
                bullet.update(dt, self.level)
                if not bullet.alive:
                    self.spawn_bullet_impact(bullet.x, bullet.y, from_player=bullet.from_player)
                    continue

                if BULLETS_DESTROY_SHIP and not bullet.from_player and self.ship.is_operational():
                    hit_radius = self.ship.force_field_hit_radius() if self.ship.force_field_active else self.ship.radius
                    if math.hypot(self.level.wrapped_dx(bullet.x, self.ship.x), self.ship.y - bullet.y) <= (hit_radius + bullet.radius):
                        bullet.alive = False
                        self.spawn_bullet_impact(bullet.x, bullet.y, from_player=False)
                        if self.ship.force_field_active:
                            self.ship.trigger_bounce_flash()
                        else:
                            self.ship_collision_response(
                                self.level.wrapped_dx(bullet.x, self.ship.x),
                                self.ship.y - bullet.y,
                            )
                        continue

                if self.handle_bullet_solid_collision(bullet):
                    continue

                for fuel_pod in self.level.nearby_solids(bullet.x, bullet.y, bullet.radius, kinds=("fuel_pod",)).get("fuel_pod", ()):
                    if fuel_pod.destroyed or fuel_pod.fuel_remaining <= 0.0:
                        continue
                    if not fuel_pod.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                        continue
                    bullet.alive = False
                    self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
                    destroyed = fuel_pod.apply_hit()
                    if destroyed:
                        self.spawn_fuel_pod_plop(fuel_pod.x, fuel_pod.y)
                    break

                if not bullet.alive:
                    continue

                if self.level.orb and bullet.from_player and self.level.orb.plinth_contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                    bullet.alive = False
                    self.spawn_bullet_impact(bullet.x, bullet.y, from_player=True)
                    if self.level.orb.hit_plinth():
                        self.add_score(SCORE_PLINTH)
                        self.spawn_plinth_explosion(self.level.orb.plinth_x, self.level.orb.plinth_y + self.level.orb.radius - 12.0)
                    continue

        if self.escape_timer is not None and not self.level_destroyed and self.level.ship_escaped(self.ship):
            self.begin_orbit_exit("advance")


        if (
            self.ship.is_operational()
            and not self.level_destroyed
            and self.escape_timer is None
            and self.level.ship_in_orbit(self.ship)
        ):
            self.begin_orbit_exit("respawn")

        if self.escape_timer is not None and not self.level_destroyed:
            self.escape_timer = max(0.0, self.escape_timer - dt)
            if self.escape_timer <= 0.0:
                self.trigger_level_self_destruct()

        if self.level_destroyed and self.level_destruction_time > 0.0:
            self.level_destruction_time = max(0.0, self.level_destruction_time - dt)
            self.spawn_level_destruction(LEVEL_DESTRUCT_SPARKS_PER_FRAME, LEVEL_DESTRUCT_FLAMES_PER_FRAME)
            if self.level_destruction_time <= 0.0 and self.pending_next_level_after_destruction:
                self.pending_next_level_after_destruction = False
                self.advance_to_next_level()
                return

        if self.screen_flash_time > 0.0:
            self.screen_flash_time = max(0.0, self.screen_flash_time - dt)

        if self.camera_shake_time > 0.0:
            self.camera_shake_time = max(0.0, self.camera_shake_time - dt)

        self.camera_x, self.camera_y = self.level.camera_for(self.ship.x, self.ship.y)
        shake_x = 0.0
        shake_y = 0.0
        if self.camera_shake_time > 0.0 and self.camera_shake_duration > 0.0:
            shake_phase = self.camera_shake_time / self.camera_shake_duration
            shake_amount = self.camera_shake_strength * shake_phase
            shake_x = random.uniform(-shake_amount, shake_amount)
            shake_y = random.uniform(-shake_amount, shake_amount)
        self.camera_x += shake_x
        self.camera_y += shake_y

        if self.ship_destruction_time > 0.0:
            self.ship_destruction_time = max(0.0, self.ship_destruction_time - dt)

        for particle in self.thrust_particles:
            particle.update(dt)

        for spark in self.spark_particles:
            spark.update(dt)

        for flame in self.flame_particles:
            flame.update(dt)

        for debris in self.reactor_debris_particles:
            debris.update(dt)

        self.bullets = [b for b in self.bullets if b.alive]
        self.thrust_particles = [p for p in self.thrust_particles if p.alive]
        self.spark_particles = [s for s in self.spark_particles if s.alive]
        self.flame_particles = [f for f in self.flame_particles if f.alive]
        self.reactor_debris_particles = [d for d in self.reactor_debris_particles if d.alive]
        self.fuel_transfer_particles = [p for p in self.fuel_transfer_particles if p.alive]
        self.update_audio()

    def draw_hud(self):
        fuel_text = self.font.render(f"Fuel: {int(self.ship.fuel)}", True, (255, 255, 255))
        level_text = self.font.render(self.level.name, True, (255, 255, 255))
        lives_text = self.font.render(f"Lives: {self.lives}", True, (255, 255, 255))
        score_text = self.font.render(f"Score: {self.score}", True, (255, 230, 140))
        self.screen.blit(fuel_text, (10, 10))
        self.screen.blit(level_text, (10, 40))
        self.screen.blit(lives_text, (10, 70))
        self.screen.blit(score_text, (10, 100))

        if self.level.reactor and self.level.reactor.alive:
            reactor_text = self.font.render(
                f"Reactor: {self.level.reactor.hit_points}/{REACTOR_HIT_POINTS}",
                True,
                (255, 220, 120),
            )
            self.screen.blit(reactor_text, (10, 130))

        if self.escape_timer is not None and not self.level_destroyed:
            timer_text = self.font.render(f"Escape: {self.escape_timer:0.1f}s", True, (255, 120, 120))
            self.screen.blit(timer_text, (10, 160))
            orbit_text = self.font.render("Reactor critical - climb to orbit to escape", True, (120, 255, 120))
            self.screen.blit(orbit_text, (10, 190))

        if self.level_destroyed:
            msg = self.font.render("LEVEL SELF-DESTRUCTED", True, (255, 90, 60))
            rect = msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(msg, rect)
            return

        if self.paused:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((8, 16, 28, 150))
            self.screen.blit(overlay, (0, 0))
            pause_text = self.font.render("PAUSED", True, (220, 245, 255))
            pause_hint = self.font.render("Press P to resume", True, (140, 210, 255))
            self.screen.blit(pause_text, pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 18)))
            self.screen.blit(pause_hint, pause_hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 18)))
            return

        if not self.ship.alive:
            if self.lives > 0:
                if self.ship_destruction_time > 0.0:
                    message = "Ship destroyed"
                else:
                    respawn_key = format_key_binding(self.controls["fire"])
                    message = f"Ship destroyed - press {respawn_key} to respawn"
            else:
                message = "Ship destroyed - no lives left, press ESC to quit"
            crash_text = self.font.render(message, True, (255, 120, 120))
            rect = crash_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(crash_text, rect)

    def draw(self):
        self.level.draw(self.screen, self.camera_x, self.camera_y)

        for flame in self.flame_particles:
            flame.draw(self.screen, self.camera_x, self.camera_y, self.level)

        for particle in self.thrust_particles:
            particle.draw(self.screen, self.camera_x, self.camera_y, self.level)

        for spark in self.spark_particles:
            spark.draw(self.screen, self.camera_x, self.camera_y, self.level)

        for bullet in self.bullets:
            bullet.draw(self.screen, self.camera_x, self.camera_y, self.level)

        for fuel_particle in self.fuel_transfer_particles:
            fuel_particle.draw(self.screen, self.camera_x, self.camera_y, self.level)

        for debris in self.reactor_debris_particles:
            debris.draw(self.screen, self.camera_x, self.camera_y, self.level)

        self.ship.draw_tractor_beam(self.screen, self.camera_x, self.camera_y, self.level)
        self.ship.draw(self.screen, self.camera_x, self.camera_y, self.level)

        if self.screen_flash_time > 0.0 and self.screen_flash_duration > 0.0:
            flash_phase = self.screen_flash_time / self.screen_flash_duration
            flash_alpha = int(190 * flash_phase)
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 244, 210, flash_alpha))
            self.screen.blit(flash, (0, 0))

        self.draw_hud()
        pygame.display.flip()

    def run(self):
        while self.running:
            # dt = seconds since last frame.
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)

            if not self.ship.alive:
                keys = pygame.key.get_pressed()
                if keys[pygame.K_ESCAPE]:
                    self.running = False

            self.draw()

        self.stop_audio()
        if self.game_won:
            self.screen.fill((8, 8, 20))
            win_msg = self.font.render("Escape successful - all levels complete!", True, (120, 255, 120))
            hint = self.font.render("Press ESC to quit", True, (220, 220, 220))
            self.screen.blit(win_msg, win_msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20)))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)))
            pygame.display.flip()
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        waiting = False
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        waiting = False
                self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Cave Flyer.")
    parser.add_argument(
        "--level",
        type=int,
        default=1,
        help="Level number to start on (1-based).",
    )
    parser.add_argument(
        "--level-file",
        default=None,
        help="Path to a specific level JSON file to run directly.",
    )
    args = parser.parse_args()

    Game(start_level=args.level, level_file=args.level_file).run()
