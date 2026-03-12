import glob
import json
import math
import os
import random
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
    TURRET_ACCURATE_CHANCE,
    TURRET_INACCURATE_SPREAD_MIN,
    TURRET_INACCURATE_SPREAD_MAX,
    TANK_AIM_SPREAD_MIN,
    TANK_AIM_SPREAD_MAX,
    ORBIT_SCROLL_SPACE,
    ORBIT_ESCAPE_MARGIN,
    REACTOR_ESCAPE_TIME,
)

SHIP_NOSE_LEN_MULT = 1.45
SHIP_BASE_BACK_MULT = 0.80
SHIP_BASE_HALF_MULT = 1.05
BULLET_SPAWN_OFFSET = 6.0
TRACTOR_BEAM_LENGTH = 270.0
TRACTOR_BEAM_HALF_WIDTH = 54.0
TRACTOR_PULL_SPEED = 110.0
TRACTOR_TARGET_OFFSET = 10.0
ORB_PULSE_DURATION = 1.25
ORB_PULSE_FAST_RATE = 4.0
ORB_PULSE_SLOW_RATE = 1.3
ROCK_GRAVITY_SCALE = 0.55
ROCK_AIR_DAMPING = 0.995
ROCK_GROUND_DAMPING = 0.62
ROCK_SLIDE_ACCEL = 42.0
ROCK_MAX_FALL_SPEED = 220.0
ROCK_TERRAIN_FRICTION = 0.72
ROCK_STOP_SPEED = 7.0
FUEL_PARTICLE_VALUE = 8.0
FUEL_PARTICLE_SPAWN_INTERVAL = 0.055
FUEL_PARTICLE_PULL_SPEED = 175.0
FUEL_PARTICLE_FADE_TIME = 0.45
SHIP_BOUNCE_FLASH_DURATION = 0.32
SHIP_BOUNCE_RESTITUTION = 0.62
ORB_FALL_MAX_SPEED = 260.0
ORB_FALL_DAMPING = 0.985

THRUST_PARTICLES_PER_FRAME = 3
THRUST_SPREAD_DEGREES = 12.0
THRUST_SPEED_MIN = 220.0
THRUST_SPEED_MAX = 300.0
THRUST_PARTICLE_LIFE = 0.20

TURRET_HIT_POINTS = 3
TURRET_RADIUS = 14
TURRET_EXPLOSION_PARTICLES = 44
TURRET_SPARK_SPEED_MIN = 90.0
TURRET_SPARK_SPEED_MAX = 280.0
TURRET_SPARK_LIFE_MIN = 0.25
TURRET_SPARK_LIFE_MAX = 0.55

TANK_RADIUS = 22
TANK_HALF_WIDTH = 28
TANK_HALF_HEIGHT = 16
TANK_SPEED = 42.0
TANK_FIRE_RANGE = 320.0
TANK_FIRE_COOLDOWN = 2.2
TANK_BULLET_SPEED = 260.0
TANKS_PER_LEVEL_MAX = 4

REACTOR_HIT_POINTS = 10
REACTOR_EXPLOSION_PARTICLES = 90
REACTOR_HIT_SPARKS = 14
REACTOR_DEBRIS_PARTICLES = 42

LEVEL_SELF_DESTRUCT_DURATION = 2.8
LEVEL_DESTRUCT_SPARK_BURST = 220
LEVEL_DESTRUCT_FLAME_BURST = 180
LEVEL_DESTRUCT_SPARKS_PER_FRAME = 10
LEVEL_DESTRUCT_FLAMES_PER_FRAME = 12
SHIP_DESTRUCTION_DURATION = 1.1
SHIP_DESTRUCTION_SPARKS = 30
SHIP_DESTRUCTION_FLAMES = 18
SHIP_DEBRIS_PARTICLES = 12


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def load_json(path):
    """Load and return JSON data from a file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def line_circle_collision(line, cx, cy, radius):
    """True if the circle touches the line segment."""
    (ax, ay), (bx, by) = line
    return point_to_segment_distance(cx, cy, ax, ay, bx, by) <= radius


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
        step_x = self.vx * dt
        step_y = self.vy * dt
        self.x += step_x
        self.y += step_y
        self.distance_travelled += math.hypot(step_x, step_y)

        self.x = level.wrap_x(self.x, self.radius)
        if self.distance_travelled >= BULLET_RANGE:
            self.alive = False
            return

        min_x, max_x, min_y, max_y = level.world_bounds()
        if (
            self.y < min_y - 120
            or self.y > max_y + 120
        ):
            self.alive = False
            return

        for line in level.collision_lines():
            if line_circle_collision(line, self.x, self.y, self.radius):
                self.alive = False
                return

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        offset_x = level.draw_world_offset(self.x, camera_x) if level else 0.0
        center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
        glow_colour = (255, 170, 80) if self.from_player else (255, 110, 90)
        draw_glow_circle(screen, glow_colour, center, self.radius, self.radius + 7, 80)
        draw_glow_circle(screen, glow_colour, center, self.radius, self.radius + 3, 130)
        pygame.draw.circle(
            screen,
            (255, 220, 120),
            center,
            self.radius,
        )


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
        # Light velocity decay so particles feel like tiny exhaust debris.
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
        # Cool grey-white tones look like particles rather than flames.
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
        self.has_orb = False
        self.orb_pulse_time = 0.0
        self.orb_pulse_phase = 0.0
        self.bounce_flash_time = 0.0

    def update(self, dt, keys, controls, level):
        self.thrusting = False
        self.tractor_active = keys[controls["tractor"]]
        self.orb_pulse_time = max(0.0, self.orb_pulse_time - dt)
        self.bounce_flash_time = max(0.0, self.bounce_flash_time - dt)
        if self.has_orb:
            pulse_rate = ORB_PULSE_FAST_RATE if self.orb_pulse_time > 0.0 else ORB_PULSE_SLOW_RATE
            self.orb_pulse_phase = (self.orb_pulse_phase + dt * pulse_rate) % 1.0

        if keys[controls["rotate_left"]]:
            self.angle -= SHIP_ROTATION_SPEED * dt
        if keys[controls["rotate_right"]]:
            self.angle += SHIP_ROTATION_SPEED * dt

        # Apply level-specific gravity.
        self.vy += level.gravity * dt

        # Thrust pushes the ship in the direction it is facing.
        if keys[controls["thrust"]] and self.fuel > 0:
            angle_rad = math.radians(self.angle)
            thrust_x = math.cos(angle_rad) * SHIP_THRUST
            thrust_y = math.sin(angle_rad) * SHIP_THRUST
            self.vx += thrust_x * dt
            self.vy += thrust_y * dt
            self.fuel = max(0.0, self.fuel - 12.0 * dt)
            self.thrusting = True

        self.vx *= SHIP_DAMPING
        self.vy *= SHIP_DAMPING

        prev_x = self.x
        prev_y = self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.x = level.wrap_x(self.x, self.radius)

        # Collision with cave walls.
        for line in level.collision_lines():
            if line_circle_collision(line, self.x, self.y, self.radius):
                if SHIP_BOUNCES_INSTEAD_OF_DYING:
                    self.x = prev_x
                    self.y = prev_y
                    self.bounce_off_line(line, level)
                else:
                    self.alive = False
                break

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

    def bounce_off_normal(self, nx, ny):
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
        self.x += nx * 4.0
        self.y += ny * 4.0
        self.trigger_bounce_flash()

    def bounce_off_line(self, line, level):
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
        if self.has_orb:
            pulse_strength = 1.0 if self.orb_pulse_time > 0.0 else 0.45
            pulse_wave = 0.55 + 0.45 * math.sin(self.orb_pulse_phase * math.tau)
            glow_radius = int(self.radius + 12 + (10 if self.orb_pulse_time > 0.0 else 6) * pulse_wave)
            center = (int(self.x + offset_x - camera_x), int(self.y - camera_y))
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
        pygame.draw.polygon(screen, (235, 240, 255), points)
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
        self.radius = TURRET_RADIUS
        self.hit_points = TURRET_HIT_POINTS
        self.alive = True
        self.cooldown = 0.0
        self.inaccuracy_degrees = 0.0
        if random.random() > TURRET_ACCURATE_CHANCE:
            self.inaccuracy_degrees = random.uniform(
                TURRET_INACCURATE_SPREAD_MIN,
                TURRET_INACCURATE_SPREAD_MAX,
            )

    def update(self, dt, ship, bullets, level):
        if not self.alive:
            return

        self.cooldown -= dt
        if self.cooldown > 0:
            return

        # Very simple AI: fire if ship is not too far away.
        dx = level.wrapped_dx(self.x, ship.x)
        dy = ship.y - self.y
        distance = math.hypot(dx, dy)
        if distance < 260:
            angle = math.atan2(dy, dx)
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
        rect = self.sprite.get_rect(center=(self.x + offset_x - camera_x, self.y - camera_y))
        screen.blit(self.sprite, rect)


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
            return

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
            return

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


class FuelPod:
    def __init__(self, x, y, sprite):
        self.x = x
        self.y = y
        self.sprite = sprite
        self.radius = max(14, int(min(sprite.get_width(), sprite.get_height()) * 0.30))
        self.fuel_remaining = FUEL_POD_AMOUNT
        self.spawn_cooldown = 0.0

    def contains_point(self, x, y, radius=0.0, level=None):
        dx = self.x - x
        if level is not None:
            dx = level.wrapped_dx(x, self.x)
        return math.hypot(dx, self.y - y) <= self.radius + radius

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
        return abs(perp) <= width_here + self.radius

    def update(self, ship, level, tractor_active, dt, fuel_particles):
        if self.fuel_remaining <= 0.0:
            return
        self.spawn_cooldown = max(0.0, self.spawn_cooldown - dt)
        if not tractor_active or not self.tractor_beam_overlap(ship, level):
            return

        while self.fuel_remaining > 0.0 and self.spawn_cooldown <= 0.0:
            amount = min(FUEL_PARTICLE_VALUE, self.fuel_remaining)
            self.fuel_remaining -= amount
            fuel_particles.append(FuelTransferParticle(self.x, self.y, amount))
            self.spawn_cooldown += FUEL_PARTICLE_SPAWN_INTERVAL

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
        if self.fuel_remaining <= 0.0:
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
            pygame.draw.rect(fill_surface, (90, 255, 180, 110), fill_rect, border_radius=5)
            screen.blit(fill_surface, rect)
        screen.blit(self.sprite, rect)


class FuelTransferParticle:
    def __init__(self, x, y, fuel_amount):
        self.x = x + random.uniform(-8.0, 8.0)
        self.y = y + random.uniform(-10.0, 10.0)
        self.fuel_amount = fuel_amount
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
        self.collected = False
        self.vx = 0.0
        self.vy = 0.0
        self.resting = True
        self.beam_locked_last_frame = False

    def update(self, ship, level, tractor_active, dt):
        if self.collected:
            return False

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
                if level.resolve_orb_terrain_collision(self):
                    self.vx = 0.0
                    self.vy = 0.0
                    self.resting = True
                    break
            if not self.resting:
                self.vx *= ORB_FALL_DAMPING

        self.beam_locked_last_frame = beam_locked

        return False

    def draw(self, screen, camera_x=0.0, camera_y=0.0, level=None):
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
            rect = self.sprite.get_rect(center=(self.x + offset_x - camera_x, self.y - camera_y))
            screen.blit(self.sprite, rect)


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


class Level:
    def __init__(self, level_data, sprites):
        self.name = level_data["name"]
        self.gravity = level_data["gravity"]
        self.background_colour = tuple(level_data.get("background_colour", [0, 0, 0]))
        self.ship_start = tuple(level_data["ship_start"])
        self.base_cave_lines = [tuple(map(tuple, line)) for line in level_data["cave_lines"]]
        self.cave_lines = list(self.base_cave_lines)
        world_bounds = level_data.get("world_bounds")

        if world_bounds:
            self.world_min_x, self.world_max_x, self.world_min_y, self.world_max_y = world_bounds
        else:
            points = []
            for line in self.base_cave_lines:
                points.extend([line[0], line[1]])
            self.world_min_x = min(p[0] for p in points)
            self.world_max_x = max(p[0] for p in points)
            self.world_min_y = min(p[1] for p in points)
            self.world_max_y = max(p[1] for p in points)
        self.world_width = self.world_max_x - self.world_min_x
        self.orbit_top_y = self.world_min_y - ORBIT_SCROLL_SPACE
        self.render_width = int(math.ceil(self.world_width))
        self.render_height = int(math.ceil(self.world_max_y - self.orbit_top_y))

        self.turrets = [
            Turret(t["x"], t["y"], t.get("direction", -90), sprites["turret"])
            for t in level_data.get("turrets", [])
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

        self.rocks = self.build_rocks(level_data)
        self.rocks_unlocked = False
        self.tanks = self.build_tanks()
        self.snap_objects_to_flat_surfaces()
        self.settle_rocks()
        self.terrain_surface = self.build_terrain_surface()

    def build_rocks(self, level_data):
        rocks = [
            Rock(r["x"], r["y"], r.get("diameter", 20))
            for r in level_data.get("rocks", [])
        ]

        for pile in level_data.get("rock_piles", []):
            count = pile["count"]
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
                    rocks.append(Rock(rock_x, rock_y, diameter))
                    placed += 1
                row += 1

        return rocks

    def snap_objects_to_flat_surfaces(self):
        """Place objects on horizontal terrain instead of letting them float."""
        horizontal_lines = []
        for line in self.base_cave_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) < 0.01:
                horizontal_lines.append(line)

        if not horizontal_lines:
            return

        for turret in self.turrets:
            self.snap_object_to_floor(turret, turret.sprite)

        for pod in self.fuel_pods:
            self.snap_object_to_floor(pod, pod.sprite)

        if self.orb:
            self.snap_object_to_floor(self.orb, self.orb.sprite)

        if self.reactor:
            self.snap_object_to_floor(self.reactor, self.reactor.sprite)

    def build_tanks(self):
        horizontal_lines = []
        for line in self.base_cave_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) < 0.01 and abs(bx - ax) >= 140:
                horizontal_lines.append(line)

        if not horizontal_lines:
            return []

        floor_y = max(line[0][1] for line in horizontal_lines)
        elevated_lines = [line for line in horizontal_lines if line[0][1] < floor_y - 120]
        tanks = []
        desired = random.randint(0, TANKS_PER_LEVEL_MAX)
        attempts = 0
        forced_elevated = desired > 0 and bool(elevated_lines)
        while len(tanks) < desired and attempts < 40:
            attempts += 1
            if forced_elevated:
                line = random.choice(elevated_lines)
            else:
                line = random.choice(horizontal_lines)
            (ax, ay), (bx, by) = line
            min_x = min(ax, bx) + TANK_HALF_WIDTH
            max_x = max(ax, bx) - TANK_HALF_WIDTH
            if min_x >= max_x:
                continue
            x = random.uniform(min_x, max_x)
            y = ay - TANK_HALF_HEIGHT
            tank = Tank(x, y, line)
            if self.position_conflicts(tank, tanks):
                continue
            tanks.append(tank)
            forced_elevated = False
        return tanks

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
        return False

    def snap_object_to_floor(self, obj, sprite):
        half_w = sprite.get_width() * 0.5
        half_h = sprite.get_height() * 0.5
        best = None
        best_dist = float("inf")

        for line in self.base_cave_lines:
            (ax, ay), (bx, by) = line
            if abs(ay - by) >= 0.01:
                continue

            seg_min_x = min(ax, bx)
            seg_max_x = max(ax, bx)
            if (seg_max_x - seg_min_x) < sprite.get_width():
                continue

            cand_x = max(seg_min_x + half_w, min(seg_max_x - half_w, obj.x))
            cand_y = ay - half_h
            dist = math.hypot(cand_x - obj.x, cand_y - obj.y)
            if dist < best_dist:
                best_dist = dist
                best = (cand_x, cand_y)

        if best is not None:
            obj.x, obj.y = best

    def floor_y_beneath(self, x, current_y, radius):
        best_y = None
        wrapped_x = self.wrap_x(x, radius)
        for line in self.base_cave_lines:
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

        for line in self.base_cave_lines:
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
        for line in self.collision_lines():
            (ax, ay), (bx, by) = line
            cx, cy = closest_point_on_segment(rock.x, rock.y, ax, ay, bx, by)
            dx = rock.x - cx
            dy = rock.y - cy
            dist = math.hypot(dx, dy)
            if dist >= rock.radius or dist == 0.0:
                if dist != 0.0 or point_to_segment_distance(rock.x, rock.y, ax, ay, bx, by) >= rock.radius:
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

            penetration = rock.radius - max(dist, 0.0)
            if penetration <= 0.0:
                continue

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

    def update(self, dt):
        if not self.rocks_unlocked:
            return
        settled = []
        for rock in sorted((rock for rock in self.rocks if rock.alive), key=lambda rock: (rock.y, rock.x), reverse=True):
            rock.update(dt, self, settled)
            settled.append(rock)

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

    def draw_line_to_surface(self, surface, colour, line, width):
        (ax, ay), (bx, by) = line
        start = (ax - self.world_min_x, ay - self.orbit_top_y)
        end = (bx - self.world_min_x, by - self.orbit_top_y)
        pygame.draw.line(surface, (70, 210, 255, 84), start, end, width + 14)
        pygame.draw.line(surface, (120, 220, 255, 126), start, end, width + 8)
        pygame.draw.line(surface, colour, start, end, width)

    def build_terrain_surface(self):
        surface = pygame.Surface((self.render_width + 1, self.render_height + 1), pygame.SRCALPHA)
        for line in self.cave_lines:
            self.draw_line_to_surface(surface, (120, 220, 255), line, 3)
        return surface

    def collision_lines(self):
        return list(self.cave_lines)

    def ship_escaped(self, ship):
        return self.ship_in_orbit(ship)

    def ship_in_orbit(self, ship):
        return (ship.y + ship.radius) < (self.orbit_top_y + ORBIT_ESCAPE_MARGIN)

    def draw(self, screen, camera_x=0.0, camera_y=0.0):
        screen.fill(self.background_colour)
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
    def __init__(self):
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

        self.level_paths = sorted(glob.glob("levels/*.json"))
        if not self.level_paths:
            raise RuntimeError("No level JSON files found in levels/")

        self.level_index = 0
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
        self.game_won = False
        self.lives = 3
        self.running = True
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.load_level(self.level_index)

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
        self.camera_x, self.camera_y = self.level.camera_for(self.ship.x, self.ship.y)

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
        self.bullets.clear()
        self.thrust_particles.clear()
        self.fuel_transfer_particles.clear()
        self.ship_destruction_time = 0.0

    def spawn_turret_explosion(self, x, y):
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

    def spawn_reactor_explosion(self, x, y):
        for _ in range(REACTOR_EXPLOSION_PARTICLES):
            angle = random.uniform(0.0, math.tau)
            speed = random.uniform(120.0, 340.0)
            life = random.uniform(0.25, 0.70)
            self.spark_particles.append(
                SparkParticle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    life,
                )
            )

        for _ in range(28):
            angle = random.uniform(-math.pi, 0.0)
            speed = random.uniform(70.0, 210.0)
            life = random.uniform(0.35, 0.85)
            self.flame_particles.append(
                FlameParticle(
                    x + random.uniform(-18.0, 18.0),
                    y + random.uniform(-10.0, 12.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(20.0, 90.0),
                    life,
                )
            )

        for _ in range(REACTOR_DEBRIS_PARTICLES):
            angle = random.uniform(math.pi * 1.05, math.pi * 1.95)
            speed = random.uniform(140.0, 340.0)
            life = random.uniform(1.0, 1.9)
            self.reactor_debris_particles.append(
                ReactorDebrisParticle(
                    x + random.uniform(-22.0, 22.0),
                    y + random.uniform(-16.0, 12.0),
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - random.uniform(80.0, 180.0),
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

    def ship_collision_response(self, nx, ny, lose_life=True):
        if SHIP_BOUNCES_INSTEAD_OF_DYING:
            self.ship.bounce_off_normal(nx, ny)
            return
        self.destroy_ship(lose_life=lose_life)

    def random_level_point(self):
        if self.level.cave_lines and random.random() < 0.7:
            (ax, ay), (bx, by) = random.choice(self.level.cave_lines)
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

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == self.controls["fire"]:
                    if self.game_won:
                        continue

                    if self.ship.alive and not self.level_destroyed:
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
                    elif self.lives > 0 and not self.level_destroyed and self.ship_destruction_time <= 0.0:
                        self.respawn_ship()

    def update(self, dt):
        if self.game_won:
            return

        self.level.update(dt)

        keys = pygame.key.get_pressed()
        if self.ship.alive and not self.level_destroyed:
            was_alive = self.ship.alive
            self.ship.update(dt, keys, self.controls, self.level)

            if was_alive and not self.ship.alive:
                self.ship.alive = True
                self.destroy_ship()

            if self.ship.alive:
                for turret in self.level.turrets:
                    if turret.alive and turret.contains_point(self.ship.x, self.ship.y, self.ship.radius, self.level):
                        dx = self.level.wrapped_dx(turret.x, self.ship.x)
                        self.ship_collision_response(dx, self.ship.y - turret.y)
                        break

            if self.ship.alive:
                for tank in self.level.tanks:
                    if tank.alive and tank.contains_point(self.ship.x, self.ship.y, self.ship.radius, self.level):
                        dx = self.level.wrapped_dx(tank.x, self.ship.x)
                        self.ship_collision_response(dx, self.ship.y - tank.y)
                        break

            if self.ship.alive:
                for rock in self.level.rocks:
                    if rock.alive and rock.contains_point(self.ship.x, self.ship.y, self.ship.radius, self.level):
                        dx = self.level.wrapped_dx(rock.x, self.ship.x)
                        self.ship_collision_response(dx, self.ship.y - rock.y)
                        break

            if self.ship.alive:
                for fuel_pod in self.level.fuel_pods:
                    if fuel_pod.fuel_remaining > 0.0 and fuel_pod.contains_point(self.ship.x, self.ship.y, self.ship.radius, self.level):
                        dx = self.level.wrapped_dx(fuel_pod.x, self.ship.x)
                        self.ship_collision_response(dx, self.ship.y - fuel_pod.y)
                        break

            reactor = self.level.reactor
            if self.ship.alive and reactor and reactor.contains_point(self.ship.x, self.ship.y, self.ship.radius, self.level):
                dx = self.level.wrapped_dx(reactor.x, self.ship.x)
                self.ship_collision_response(dx, self.ship.y - reactor.y)

        if self.ship.alive and self.ship.thrusting and not self.level_destroyed:
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

        if self.ship.alive and not self.level_destroyed:
            for turret in self.level.turrets:
                turret.update(dt, self.ship, self.bullets, self.level)

            for tank in self.level.tanks:
                tank.update(dt, self.ship, self.bullets, self.level)

            for fuel_pod in self.level.fuel_pods:
                fuel_pod.update(self.ship, self.level, self.ship.tractor_active, dt, self.fuel_transfer_particles)

            if self.level.orb:
                self.level.orb.update(self.ship, self.level, self.ship.tractor_active, dt)

        for fuel_particle in self.fuel_transfer_particles:
            fuel_particle.update(dt, self.ship, self.level)

        if not self.level_destroyed:
            for bullet in self.bullets:
                bullet.update(dt, self.level)
                if not bullet.alive:
                    continue

                if BULLETS_DESTROY_SHIP and not bullet.from_player and self.ship.alive:
                    if math.hypot(self.level.wrapped_dx(bullet.x, self.ship.x), self.ship.y - bullet.y) <= (self.ship.radius + bullet.radius):
                        bullet.alive = False
                        self.ship_collision_response(
                            self.level.wrapped_dx(bullet.x, self.ship.x),
                            self.ship.y - bullet.y,
                        )
                        continue

                for rock in self.level.rocks:
                    if not rock.alive:
                        continue
                    if rock.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                        bullet.alive = False
                        rock.apply_hit()
                        self.level.rocks_unlocked = True
                        self.spawn_turret_explosion(rock.x, rock.y)
                        break

                if not bullet.alive or not bullet.from_player:
                    continue

                for turret in self.level.turrets:
                    if not turret.alive:
                        continue
                    if turret.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                        bullet.alive = False
                        destroyed = turret.apply_hit()
                        if destroyed:
                            self.spawn_turret_explosion(turret.x, turret.y)
                            self.lives += 1
                        break

                if not bullet.alive:
                    continue

                for tank in self.level.tanks:
                    if not tank.alive:
                        continue
                    if tank.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                        bullet.alive = False
                        destroyed = tank.apply_hit()
                        if destroyed:
                            self.spawn_turret_explosion(tank.x, tank.y)
                        break

                if not bullet.alive:
                    continue

                reactor = self.level.reactor
                if reactor and reactor.alive and reactor.contains_point(bullet.x, bullet.y, bullet.radius, self.level):
                    bullet.alive = False
                    destroyed = reactor.apply_hit()
                    if destroyed:
                        self.spawn_reactor_explosion(reactor.x, reactor.y)
                        self.escape_timer = REACTOR_ESCAPE_TIME
                    else:
                        self.spawn_reactor_hit_sparks(reactor.x, reactor.y)

        if self.escape_timer is not None and not self.level_destroyed and self.level.ship_escaped(self.ship):
            self.advance_to_next_level()
            return

        if (
            self.ship.alive
            and not self.level_destroyed
            and self.escape_timer is None
            and self.level.ship_in_orbit(self.ship)
        ):
            self.respawn_after_orbit_breach()
            return

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

        self.camera_x, self.camera_y = self.level.camera_for(self.ship.x, self.ship.y)

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

    def draw_hud(self):
        fuel_text = self.font.render(f"Fuel: {int(self.ship.fuel)}", True, (255, 255, 255))
        level_text = self.font.render(self.level.name, True, (255, 255, 255))
        lives_text = self.font.render(f"Lives: {self.lives}", True, (255, 255, 255))
        self.screen.blit(fuel_text, (10, 10))
        self.screen.blit(level_text, (10, 40))
        self.screen.blit(lives_text, (10, 70))

        if self.level.reactor and self.level.reactor.alive:
            reactor_text = self.font.render(
                f"Reactor: {self.level.reactor.hit_points}/{REACTOR_HIT_POINTS}",
                True,
                (255, 220, 120),
            )
            self.screen.blit(reactor_text, (10, 100))

        if self.escape_timer is not None and not self.level_destroyed:
            timer_text = self.font.render(f"Escape: {self.escape_timer:0.1f}s", True, (255, 120, 120))
            self.screen.blit(timer_text, (10, 130))
            orbit_text = self.font.render("Reactor critical - climb to orbit to escape", True, (120, 255, 120))
            self.screen.blit(orbit_text, (10, 160))
        elif not self.level_destroyed:
            orbit_text = self.font.render("Orbit before reactor breach causes a free respawn", True, (180, 220, 255))
            self.screen.blit(orbit_text, (10, 130))

        if self.level_destroyed:
            msg = self.font.render("LEVEL SELF-DESTRUCTED", True, (255, 90, 60))
            rect = msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(msg, rect)
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
    Game().run()
