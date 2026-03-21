import argparse
import glob
import json
import math
import os
import random
import subprocess
import sys
import time

import pygame

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:
    tk = None
    filedialog = None


SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 900
SIDEBAR_WIDTH = 320
CANVAS_WIDTH = SCREEN_WIDTH - SIDEBAR_WIDTH
BG_COLOUR = (12, 14, 22)
GRID_COLOUR = (28, 34, 46)
TEXT_COLOUR = (226, 232, 244)
MUTED_TEXT = (152, 164, 184)
HIGHLIGHT = (255, 224, 120)
PANEL_BG = (24, 30, 42)
PANEL_BORDER = (52, 64, 86)
BUTTON_BG = (46, 58, 78)
BUTTON_HOVER = (66, 82, 108)
BUTTON_ACTIVE = (96, 120, 156)
BUTTON_TEXT = (238, 242, 250)
TURRET_SPRITE_WIDTH = 24
TURRET_SPRITE_HEIGHT = 24
TURRET_FLOOR_OFFSET = 10.0
FUEL_POD_SPRITE_WIDTH = 38
FUEL_POD_SPRITE_HEIGHT = 54
ORB_SPRITE_DIAMETER = 40
REACTOR_SPRITE_WIDTH = 60
REACTOR_SPRITE_HEIGHT = 60
SWITCH_FLOOR_OFFSET = 18.0
ORB_PLINTH_HEIGHT = 54.0
LINE_ENDPOINT_SNAP_DISTANCE = 18.0

TOOLS = [
    ("select", "1 Select"),
    ("line", "2 Cave Line"),
    ("ship_start", "3 Ship Start"),
    ("turret", "4 Turret"),
    ("fuel_pod", "5 Fuel Pod"),
    ("orb", "6 Orb"),
    ("reactor", "7 Reactor"),
    ("rock", "8 Rock"),
    ("gate", "9 Gate"),
    ("switch", "0 Switch"),
]

TOOL_KEYS = {
    pygame.K_1: "select",
    pygame.K_2: "line",
    pygame.K_3: "ship_start",
    pygame.K_4: "turret",
    pygame.K_5: "fuel_pod",
    pygame.K_6: "orb",
    pygame.K_7: "reactor",
    pygame.K_8: "rock",
    pygame.K_9: "gate",
    pygame.K_0: "switch",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def point_segment_distance(px, py, ax, ay, bx, by):
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))
    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(px - cx, py - cy)


def closest_point_on_segment(px, py, ax, ay, bx, by):
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq <= 1e-9:
        return ax, ay
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))
    return ax + t * abx, ay + t * aby


def rect_hit(px, py, cx, cy, half_w, half_h):
    return (cx - half_w) <= px <= (cx + half_w) and (cy - half_h) <= py <= (cy + half_h)


def world_distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def default_level():
    return {
        "name": "Untitled",
        "gravity": 80.0,
        "ship_start": [220, 180],
        "background_colour": [10, 10, 18],
        "world_bounds": [80, 1500, 60, 1280],
        "cave_lines": [],
        "turrets": [],
        "gates": [],
        "switches": [],
        "fuel_pods": [],
        "orb": None,
        "rocks": [],
        "rock_piles": [],
        "reactor": None,
    }


def expand_rock_piles(data):
    rocks = list(data.get("rocks", []))
    for pile in data.get("rock_piles", []):
        count = min(int(pile.get("count", 0)), 28)
        diameter = pile.get("diameter", 20)
        spacing = diameter * 0.88
        row_step = diameter * 0.82
        base_width = pile.get("base_width", max(4, int(math.sqrt(max(1, count))) + 1))
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
                rocks.append({"x": round(rock_x, 1), "y": round(rock_y, 1), "diameter": diameter})
                placed += 1
            row += 1
    data["rocks"] = rocks
    data["rock_piles"] = []
    return data


class LevelEditor:
    def __init__(self, path):
        pygame.init()
        pygame.display.set_caption("Cave Flyer Level Editor")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        self.small_font = pygame.font.SysFont(None, 20)
        self.path = path
        self.level_paths = sorted(glob.glob("levels/*.json"))
        self.level = self.load_level(path)
        if self.path not in self.level_paths and self.path.endswith(".json"):
            self.level_paths.append(self.path)
            self.level_paths.sort()
        self.tool = "select"
        self.selected = None
        self.dragging = False
        self.drag_mode = None
        self.drag_offset = (0.0, 0.0)
        self.pan_drag = False
        self.line_start = None
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.zoom = 1.0
        self.running = True
        self.status = f"Loaded {os.path.basename(path)}"
        self.unsaved = False
        self.last_saved_at = None
        self.save_as_name = self.default_save_name(path)
        self.active_gate_id = self.level["gates"][0]["id"] if self.level["gates"] else None
        self.ui_buttons = []
        self.text_fields = []
        self.active_text_field = None
        self.minimap_rect = None
        self.show_level_list = False
        self.center_camera()

    def default_save_name(self, path):
        if not path:
            return "new_level"
        base = os.path.splitext(os.path.basename(path))[0]
        return base or "new_level"

    def save_target_path(self, name):
        cleaned = os.path.basename(name.strip())
        if not cleaned:
            return None
        if not cleaned.lower().endswith(".json"):
            cleaned += ".json"
        return os.path.join("levels", cleaned)

    def open_level(self, path):
        self.path = path
        if self.path not in self.level_paths and self.path.endswith(".json"):
            self.level_paths.append(self.path)
            self.level_paths.sort()
        self.level = self.load_level(path)
        self.selected = None
        self.dragging = False
        self.drag_mode = None
        self.line_start = None
        self.unsaved = False
        self.active_text_field = None
        self.save_as_name = self.default_save_name(path)
        self.active_gate_id = self.level["gates"][0]["id"] if self.level["gates"] else None
        self.center_camera()
        self.status = f"Loaded {os.path.basename(path)}"

    def collection_key(self, kind):
        mapping = {
            "turret": "turrets",
            "fuel_pod": "fuel_pods",
            "rock": "rocks",
            "gate": "gates",
            "switch": "switches",
        }
        return mapping[kind]

    def load_level(self, path):
        if path and os.path.exists(path):
            data = load_json(path)
        else:
            data = default_level()
        data = expand_rock_piles(data)
        data.setdefault("turrets", [])
        data.setdefault("gates", [])
        data.setdefault("switches", [])
        data.setdefault("fuel_pods", [])
        data.setdefault("rocks", [])
        data.setdefault("rock_piles", [])
        data.setdefault("orb", None)
        data.setdefault("reactor", None)
        return data

    def save(self):
        if not self.path:
            self.save_as()
            return
        save_json(self.path, self.level)
        self.unsaved = False
        self.last_saved_at = time.strftime("%H:%M:%S")
        self.save_as_name = self.default_save_name(self.path)
        self.status = f"Saved {os.path.basename(self.path)}"

    def save_as(self):
        if tk is None or filedialog is None:
            self.status = "Save As dialog unavailable on this system"
            return
        levels_dir = os.path.abspath("levels")
        os.makedirs(levels_dir, exist_ok=True)
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        initial_name = self.default_save_name(self.path or self.save_as_name)
        initial_file = initial_name if initial_name.lower().endswith(".json") else f"{initial_name}.json"
        selected = filedialog.asksaveasfilename(
            parent=root,
            title="Save Level As",
            initialdir=levels_dir,
            initialfile=initial_file,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        root.destroy()
        if not selected:
            self.status = "Save As cancelled"
            return
        target_path = os.path.abspath(selected)
        if os.path.commonpath([levels_dir, target_path]) != levels_dir:
            self.status = "Save As must be inside the levels folder"
            return
        target_path = os.path.relpath(target_path, os.getcwd())
        self.path = target_path
        if self.path not in self.level_paths:
            self.level_paths.append(self.path)
            self.level_paths.sort()
        self.save()

    def new_level(self):
        if self.unsaved:
            self.status = "Save current level before creating a new one"
            return
        self.path = None
        self.level = self.load_level("")
        self.selected = None
        self.dragging = False
        self.drag_mode = None
        self.line_start = None
        self.unsaved = True
        self.last_saved_at = None
        self.active_text_field = None
        self.save_as_name = "new_level"
        self.active_gate_id = None
        self.show_level_list = False
        self.center_camera()
        self.status = "Created new unsaved level"

    def play_current_level(self):
        if self.unsaved:
            self.status = "Save current level before playing"
            return
        game_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        try:
            self.status = f"Playing {os.path.basename(self.path)}"
            pygame.display.flip()
            result = subprocess.run(
                [sys.executable, game_path, "--level-file", self.path],
                cwd=os.path.dirname(game_path),
                check=False,
            )
        except OSError as exc:
            self.status = f"Play failed: {exc}"
            return

        pygame.display.set_caption("Cave Flyer Level Editor")
        if result.returncode == 0:
            self.status = f"Returned from playtest: {os.path.basename(self.path)}"
        else:
            self.status = f"Playtest exited with code {result.returncode}"

    def center_camera(self):
        min_x, max_x, min_y, max_y = self.level["world_bounds"]
        self.camera_x = (min_x + max_x) * 0.5
        self.camera_y = (min_y + max_y) * 0.5

    def world_to_screen(self, point):
        x = (point[0] - self.camera_x) * self.zoom + CANVAS_WIDTH * 0.5
        y = (point[1] - self.camera_y) * self.zoom + SCREEN_HEIGHT * 0.5
        return x, y

    def screen_to_world(self, point):
        x = (point[0] - CANVAS_WIDTH * 0.5) / self.zoom + self.camera_x
        y = (point[1] - SCREEN_HEIGHT * 0.5) / self.zoom + self.camera_y
        return x, y

    def canvas_contains(self, screen_pos):
        return 0 <= screen_pos[0] < CANVAS_WIDTH and 0 <= screen_pos[1] < SCREEN_HEIGHT

    def next_gate_id(self):
        used = {gate["id"] for gate in self.level["gates"]}
        index = 1
        while True:
            gate_id = f"gate_{index}"
            if gate_id not in used:
                return gate_id
            index += 1

    def nearest_gate_id(self, world_pos):
        nearest_id = None
        nearest_dist = float("inf")
        for gate in self.level["gates"]:
            dist = world_distance((gate["x"], gate["y"]), world_pos)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_id = gate["id"]
        return nearest_id

    def snap_line_endpoint(self, world_pos, exclude=None):
        best_point = None
        best_dist = LINE_ENDPOINT_SNAP_DISTANCE
        for line_index, line in enumerate(self.level["cave_lines"]):
            for point_index, point in enumerate(line):
                if exclude == (line_index, point_index):
                    continue
                dist = math.hypot(point[0] - world_pos[0], point[1] - world_pos[1])
                if dist <= best_dist:
                    best_dist = dist
                    best_point = [round(point[0], 1), round(point[1], 1)]
        return best_point if best_point is not None else [round(world_pos[0], 1), round(world_pos[1], 1)]

    def vertical_surface_below(self, world_pos, require_horizontal=False, min_width=0.0):
        x, y = world_pos
        best = None
        best_y = float("inf")
        for line in self.level["cave_lines"]:
            (ax, ay), (bx, by) = line
            if require_horizontal and abs(ay - by) >= 0.01:
                continue
            seg_min_x = min(ax, bx)
            seg_max_x = max(ax, bx)
            if x < seg_min_x or x > seg_max_x:
                continue
            if require_horizontal and (seg_max_x - seg_min_x) < min_width:
                continue
            if abs(bx - ax) <= 1e-9:
                surface_y = min(ay, by)
            else:
                t = (x - ax) / (bx - ax)
                if t < 0.0 or t > 1.0:
                    continue
                surface_y = ay + (by - ay) * t
            if surface_y < y:
                continue
            if surface_y < best_y:
                best_y = surface_y
                best = (line, (x, surface_y))
        return best

    def drop_object_to_surface(self, world_pos, sprite_width, sprite_height, floor_offset=0.0):
        hit = self.vertical_surface_below(world_pos)
        if hit is None:
            return world_pos
        _, (x, surface_y) = hit
        return (x, surface_y - sprite_height * 0.5 - floor_offset)

    def drop_switch_to_surface(self, world_pos):
        hit = self.vertical_surface_below(world_pos)
        if hit is None:
            return world_pos
        (ax, ay), (bx, by) = hit[0]
        contact_x, contact_y = hit[1]
        seg_dx = bx - ax
        seg_dy = by - ay
        seg_len = math.hypot(seg_dx, seg_dy)
        if seg_len <= 1e-9:
            return world_pos
        normal_x = -seg_dy / seg_len
        normal_y = seg_dx / seg_len
        if normal_y > 0.0:
            normal_x *= -1.0
            normal_y *= -1.0
        return (
            contact_x + normal_x * SWITCH_FLOOR_OFFSET,
            contact_y + normal_y * SWITCH_FLOOR_OFFSET,
        )

    def drop_orb_with_plinth_to_surface(self, world_pos):
        hit = self.vertical_surface_below(world_pos)
        if hit is None:
            return world_pos
        _, (x, surface_y) = hit
        return (x, surface_y - ORB_PLINTH_HEIGHT)

    def snap_switch_to_surface(self, world_pos):
        return self.drop_switch_to_surface(world_pos)

    def snap_turret_to_floor(self, world_pos):
        return self.drop_object_to_surface(
            world_pos,
            TURRET_SPRITE_WIDTH,
            TURRET_SPRITE_HEIGHT,
            TURRET_FLOOR_OFFSET,
        )

    def mark_dirty(self, message):
        self.unsaved = True
        self.status = message

    def register_button(self, rect, action, enabled=True):
        self.ui_buttons.append((rect, action, enabled))

    def register_text_field(self, rect, field_id, value, enabled=True):
        self.text_fields.append((rect, field_id, enabled))
        active = self.active_text_field == field_id
        pygame.draw.rect(self.screen, (20, 24, 34), rect, border_radius=6)
        pygame.draw.rect(self.screen, HIGHLIGHT if active else PANEL_BORDER, rect, 2, border_radius=6)
        text = self.small_font.render(str(value), True, TEXT_COLOUR if enabled else MUTED_TEXT)
        self.screen.blit(text, (rect.x + 8, rect.y + 6))

    def draw_button(self, rect, label, action, enabled=True, active=False):
        mouse_pos = pygame.mouse.get_pos()
        hovered = enabled and rect.collidepoint(mouse_pos)
        colour = BUTTON_ACTIVE if active else BUTTON_HOVER if hovered else BUTTON_BG
        border = HIGHLIGHT if active else PANEL_BORDER
        if not enabled:
            colour = (34, 38, 48)
            border = (52, 56, 66)
        pygame.draw.rect(self.screen, colour, rect, border_radius=6)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)
        text_colour = BUTTON_TEXT if enabled else (112, 118, 128)
        text = self.small_font.render(label, True, text_colour)
        self.screen.blit(text, text.get_rect(center=rect.center))
        self.register_button(rect, action, enabled)

    def draw_panel(self, x, y, width, height, title):
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, PANEL_BG, rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, 2, border_radius=8)
        title_text = self.small_font.render(title, True, HIGHLIGHT)
        self.screen.blit(title_text, (x + 12, y + 10))
        return rect

    def draw_property_row(self, x, y, width, label, value, minus_action=None, plus_action=None, center_action=None):
        label_text = self.small_font.render(label, True, MUTED_TEXT)
        self.screen.blit(label_text, (x, y + 6))
        value_rect = pygame.Rect(x + 120, y, width - 188, 28)
        pygame.draw.rect(self.screen, (18, 22, 30), value_rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_BORDER, value_rect, 1, border_radius=6)
        value_text = self.small_font.render(str(value), True, TEXT_COLOUR)
        self.screen.blit(value_text, value_text.get_rect(center=value_rect.center))
        if minus_action is not None:
            self.draw_button(pygame.Rect(x + width - 60, y, 28, 28), "-", minus_action)
        if plus_action is not None:
            self.draw_button(pygame.Rect(x + width - 28, y, 28, 28), "+", plus_action)
        if center_action is not None:
            self.draw_button(pygame.Rect(x + width - 92, y, 60, 28), "Edit", center_action)

    def current_gate(self):
        if not self.active_gate_id:
            return None
        for gate in self.level["gates"]:
            if gate["id"] == self.active_gate_id:
                return gate
        return None

    def cycle_active_gate(self, step):
        gates = self.level["gates"]
        if not gates:
            self.active_gate_id = None
            return
        ids = [gate["id"] for gate in gates]
        if self.active_gate_id not in ids:
            self.active_gate_id = ids[0]
            return
        index = ids.index(self.active_gate_id)
        self.active_gate_id = ids[(index + step) % len(ids)]
        self.status = f"Active gate: {self.active_gate_id}"

    def get_selection_summary(self):
        if self.selected is None:
            return "None"
        kind = self.selected[0]
        if kind == "ship_start":
            x, y = self.level["ship_start"]
            return f"Ship Start ({int(x)}, {int(y)})"
        if kind == "orb":
            orb = self.level["orb"]
            return f"Orb ({int(orb['x'])}, {int(orb['y'])})"
        if kind == "reactor":
            reactor = self.level["reactor"]
            return f"Reactor ({int(reactor['x'])}, {int(reactor['y'])})"
        if kind == "line":
            line = self.level["cave_lines"][self.selected[1]]
            return f"Line {self.selected[1]} {tuple(map(int, line[0]))}->{tuple(map(int, line[1]))}"
        if kind == "line_point":
            line = self.level["cave_lines"][self.selected[1]]
            point = line[self.selected[2]]
            return f"Line Pt ({int(point[0])}, {int(point[1])})"
        container = self.level[self.collection_key(kind)]
        item = container[self.selected[1]]
        if kind == "rock":
            return f"Rock diameter={item.get('diameter', 20)}"
        if kind == "gate":
            return f"Gate {item['id']} {int(item['width'])}x{int(item['height'])}"
        if kind == "switch":
            return f"Switch -> {item['gate_id']}"
        return f"{kind.title()} {self.selected[1]}"

    def hit_test(self, world_pos):
        px, py = world_pos
        for index, line in enumerate(self.level["cave_lines"]):
            for point_index, point in enumerate(line):
                if world_distance(point, world_pos) <= 12.0 / self.zoom:
                    return ("line_point", index, point_index)

        object_kinds = [
            "switch",
            "gate",
            "turret",
            "fuel_pod",
            "rock",
        ]
        for kind in object_kinds:
            items = self.level[self.collection_key(kind)]
            for index in range(len(items) - 1, -1, -1):
                item = items[index]
                if kind in ("turret", "fuel_pod", "switch"):
                    radius = 18 if kind != "switch" else 16
                    if math.hypot(item["x"] - px, item["y"] - py) <= radius / self.zoom + 8:
                        return (kind, index)
                elif kind == "rock":
                    radius = item.get("diameter", 20) * 0.5
                    if math.hypot(item["x"] - px, item["y"] - py) <= radius + 8 / self.zoom:
                        return (kind, index)
                elif kind == "gate":
                    if rect_hit(px, py, item["x"], item["y"], item["width"] * 0.5, item["height"] * 0.5):
                        return (kind, index)

        if self.level["orb"] is not None:
            orb_x = self.level["orb"]["x"]
            orb_y = self.level["orb"]["y"]
            if math.hypot(orb_x - px, orb_y - py) <= 22.0 / self.zoom:
                return ("orb",)
            if rect_hit(px, py, orb_x, orb_y + 34.0, 28.0 / self.zoom, 32.0 / self.zoom):
                return ("orb",)
        if self.level["reactor"] is not None and math.hypot(self.level["reactor"]["x"] - px, self.level["reactor"]["y"] - py) <= 24.0 / self.zoom:
            return ("reactor",)
        if math.hypot(self.level["ship_start"][0] - px, self.level["ship_start"][1] - py) <= 18.0 / self.zoom:
            return ("ship_start",)

        nearest_line = None
        nearest_dist = float("inf")
        for index, line in enumerate(self.level["cave_lines"]):
            dist = point_segment_distance(px, py, line[0][0], line[0][1], line[1][0], line[1][1])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_line = index
        if nearest_line is not None and nearest_dist <= 10.0 / self.zoom:
            return ("line", nearest_line)
        return None

    def gate_handle_points(self, gate):
        if gate["height"] >= gate["width"]:
            length_dir = (0.0, -1.0)
            thickness_dir = (1.0, 0.0)
        else:
            length_dir = (1.0, 0.0)
            thickness_dir = (0.0, -1.0)
        slide_dx = gate.get("slide_dx", 0.0)
        slide_dy = gate.get("slide_dy", 0.0)
        slide_len = math.hypot(slide_dx, slide_dy)
        if slide_len <= 1e-6:
            slide_dir = length_dir
        else:
            slide_dir = (slide_dx / slide_len, slide_dy / slide_len)
        return {
            "length": (
                gate["x"] + length_dir[0] * max(gate["width"], gate["height"]) * 0.5,
                gate["y"] + length_dir[1] * max(gate["width"], gate["height"]) * 0.5,
            ),
            "thickness": (
                gate["x"] + thickness_dir[0] * min(gate["width"], gate["height"]) * 0.5,
                gate["y"] + thickness_dir[1] * min(gate["width"], gate["height"]) * 0.5,
            ),
            "slide": (
                gate["x"] + slide_dx,
                gate["y"] + slide_dy,
            ),
        }

    def gate_handle_hit(self, world_pos):
        if self.selected is None or self.selected[0] != "gate":
            return None
        gate = self.level["gates"][self.selected[1]]
        for handle_name, handle_pos in self.gate_handle_points(gate).items():
            if world_distance(handle_pos, world_pos) <= 14.0 / self.zoom:
                return handle_name
        return None

    def get_selected_item(self):
        if self.selected is None:
            return None
        kind = self.selected[0]
        if kind in ("ship_start", "orb", "reactor", "line", "line_point"):
            return None
        return self.level[self.collection_key(kind)][self.selected[1]]

    def delete_selected(self):
        if self.selected is None:
            return
        kind = self.selected[0]
        if kind == "ship_start":
            return
        if kind == "orb":
            self.level["orb"] = None
        elif kind == "reactor":
            self.level["reactor"] = None
        elif kind == "line":
            del self.level["cave_lines"][self.selected[1]]
        elif kind == "line_point":
            del self.level["cave_lines"][self.selected[1]]
        else:
            del self.level[self.collection_key(kind)][self.selected[1]]
        self.selected = None
        self.mark_dirty("Deleted selection")

    def zoom_by(self, delta):
        self.zoom = max(0.25, min(4.0, self.zoom * delta))
        self.status = f"Zoom {self.zoom:.2f}"

    def perform_ui_action(self, action):
        if not action:
            return
        name = action[0]
        if name == "set_tool":
            self.tool = action[1]
            self.line_start = None
            self.status = f"Tool: {self.tool}"
        elif name == "save":
            self.save()
        elif name == "save_as":
            self.save_as()
        elif name == "new_level":
            self.new_level()
        elif name == "play_level":
            self.play_current_level()
        elif name == "reload":
            self.open_level(self.path)
            self.status = "Reloaded level from disk"
        elif name == "toggle_level_list":
            if self.unsaved:
                self.status = "Save current level before loading another"
            else:
                self.show_level_list = not self.show_level_list
                self.status = "Level list opened" if self.show_level_list else "Level list closed"
        elif name == "load_level":
            if self.unsaved:
                self.status = "Save current level before loading another"
            else:
                self.open_level(action[1])
                self.show_level_list = False
        elif name == "delete_selected":
            self.delete_selected()
        elif name == "center_camera":
            self.center_camera()
            self.status = "Camera centered"
        elif name == "adjust_gravity":
            self.level["gravity"] = round(max(0.0, self.level["gravity"] + action[1]), 1)
            self.mark_dirty(f"Gravity {self.level['gravity']}")
        elif name == "adjust_zoom":
            self.zoom_by(action[1])
        elif name == "cycle_gate":
            self.cycle_active_gate(action[1])
        elif name == "adjust_property":
            self.adjust_selected_property(action[1], action[2])
        elif name == "set_switch_gate" and self.selected and self.selected[0] == "switch":
            switch = self.level["switches"][self.selected[1]]
            switch["gate_id"] = action[1]
            self.active_gate_id = action[1]
            self.mark_dirty(f"Switch linked to {action[1]}")
        elif name == "snap_switch" and self.selected and self.selected[0] == "switch":
            switch = self.level["switches"][self.selected[1]]
            snapped = self.snap_switch_to_surface((switch["x"], switch["y"]))
            switch["x"], switch["y"] = round(snapped[0], 1), round(snapped[1], 1)
            self.mark_dirty("Switch snapped to terrain")
        elif name == "select_item" and len(action) >= 2:
            self.selected = action[1]
            if self.selected[0] == "gate":
                self.active_gate_id = self.level["gates"][self.selected[1]]["id"]
            elif self.selected[0] == "switch":
                self.active_gate_id = self.level["switches"][self.selected[1]]["gate_id"]
            self.status = self.get_selection_summary()
        elif name == "jump_camera" and len(action) >= 3:
            self.camera_x = action[1]
            self.camera_y = action[2]
            self.status = "Camera moved"

    def begin_text_edit(self, field_id):
        self.active_text_field = field_id
        self.status = f"Editing {field_id}"

    def current_text_value(self):
        if self.active_text_field is None:
            return ""
        field = self.active_text_field
        if field == "level_name":
            return self.level["name"]
        if field == "save_as_name":
            return self.save_as_name
        if field == "gravity":
            return str(self.level["gravity"])
        if field == "gate_id" and self.selected and self.selected[0] == "gate":
            return self.level["gates"][self.selected[1]]["id"]
        if field in ("pos_x", "pos_y"):
            pos = self.selected_position()
            if pos is None:
                return ""
            return str(pos[0] if field == "pos_x" else pos[1])
        return ""

    def selected_position(self):
        if self.selected is None:
            return None
        kind = self.selected[0]
        if kind == "ship_start":
            return self.level["ship_start"]
        if kind == "orb" and self.level["orb"] is not None:
            return [self.level["orb"]["x"], self.level["orb"]["y"]]
        if kind == "reactor" and self.level["reactor"] is not None:
            return [self.level["reactor"]["x"], self.level["reactor"]["y"]]
        if kind == "line_point":
            return self.level["cave_lines"][self.selected[1]][self.selected[2]]
        if kind == "line":
            line = self.level["cave_lines"][self.selected[1]]
            return [(line[0][0] + line[1][0]) * 0.5, (line[0][1] + line[1][1]) * 0.5]
        if kind not in ("line", "line_point"):
            item = self.level[self.collection_key(kind)][self.selected[1]]
            return [item["x"], item["y"]]
        return None

    def apply_drop_snap_to_selected(self):
        if self.selected is None:
            return
        kind = self.selected[0]
        if kind == "turret":
            item = self.level["turrets"][self.selected[1]]
            snapped = self.drop_object_to_surface(
                (item["x"], item["y"]),
                TURRET_SPRITE_WIDTH,
                TURRET_SPRITE_HEIGHT,
                TURRET_FLOOR_OFFSET,
            )
            item["x"], item["y"] = round(snapped[0], 1), round(snapped[1], 1)
        elif kind == "fuel_pod":
            item = self.level["fuel_pods"][self.selected[1]]
            snapped = self.drop_object_to_surface(
                (item["x"], item["y"]),
                FUEL_POD_SPRITE_WIDTH,
                FUEL_POD_SPRITE_HEIGHT,
            )
            item["x"], item["y"] = round(snapped[0], 1), round(snapped[1], 1)
        elif kind == "orb" and self.level["orb"] is not None:
            snapped = self.drop_orb_with_plinth_to_surface((self.level["orb"]["x"], self.level["orb"]["y"]))
            self.level["orb"]["x"], self.level["orb"]["y"] = round(snapped[0], 1), round(snapped[1], 1)
        elif kind == "reactor" and self.level["reactor"] is not None:
            snapped = self.drop_object_to_surface(
                (self.level["reactor"]["x"], self.level["reactor"]["y"]),
                REACTOR_SPRITE_WIDTH,
                REACTOR_SPRITE_HEIGHT,
            )
            self.level["reactor"]["x"], self.level["reactor"]["y"] = round(snapped[0], 1), round(snapped[1], 1)
        elif kind == "switch":
            item = self.level["switches"][self.selected[1]]
            snapped = self.drop_switch_to_surface((item["x"], item["y"]))
            item["x"], item["y"] = round(snapped[0], 1), round(snapped[1], 1)

    def set_selected_position_component(self, axis, value):
        if self.selected is None:
            return
        kind = self.selected[0]
        if kind == "ship_start":
            self.level["ship_start"][axis] = value
        elif kind == "orb" and self.level["orb"] is not None:
            key = "x" if axis == 0 else "y"
            self.level["orb"][key] = value
        elif kind == "reactor" and self.level["reactor"] is not None:
            key = "x" if axis == 0 else "y"
            self.level["reactor"][key] = value
        elif kind == "line_point":
            point = self.level["cave_lines"][self.selected[1]][self.selected[2]]
            candidate = [point[0], point[1]]
            candidate[axis] = value
            snapped = self.snap_line_endpoint(candidate, exclude=(self.selected[1], self.selected[2]))
            self.level["cave_lines"][self.selected[1]][self.selected[2]] = snapped
        elif kind == "line":
            line = self.level["cave_lines"][self.selected[1]]
            center = [(line[0][0] + line[1][0]) * 0.5, (line[0][1] + line[1][1]) * 0.5]
            delta = value - center[axis]
            for point in line:
                point[axis] = round(point[axis] + delta, 1)
        else:
            item = self.level[self.collection_key(kind)][self.selected[1]]
            key = "x" if axis == 0 else "y"
            item[key] = value
            self.apply_drop_snap_to_selected()

    def apply_text_field(self):
        if self.active_text_field is None:
            return
        field = self.active_text_field
        value = self.current_text_value()
        try:
            if field == "gravity":
                self.level["gravity"] = max(0.0, float(value))
            elif field == "level_name":
                self.level["name"] = value or "Untitled"
            elif field == "save_as_name":
                self.save_as_name = value.strip()
                self.save_as()
                self.active_text_field = None
                return
            elif field == "gate_id" and self.selected and self.selected[0] == "gate":
                new_id = value.strip()
                if new_id:
                    old_id = self.level["gates"][self.selected[1]]["id"]
                    self.level["gates"][self.selected[1]]["id"] = new_id
                    for switch in self.level["switches"]:
                        if switch["gate_id"] == old_id:
                            switch["gate_id"] = new_id
                    if self.active_gate_id == old_id:
                        self.active_gate_id = new_id
            elif field == "pos_x":
                self.set_selected_position_component(0, round(float(value), 1))
            elif field == "pos_y":
                self.set_selected_position_component(1, round(float(value), 1))
            self.mark_dirty(f"Updated {field}")
        except ValueError:
            self.status = f"Invalid value for {field}"
        self.active_text_field = None

    def edit_text_field(self, key):
        if self.active_text_field is None:
            return False
        field = self.active_text_field
        value = self.current_text_value()
        if key == pygame.K_RETURN:
            self.apply_text_field()
            return True
        if key == pygame.K_ESCAPE:
            self.active_text_field = None
            self.status = "Edit cancelled"
            return True
        if key == pygame.K_BACKSPACE:
            new_value = value[:-1]
        else:
            char = None
            if key == pygame.K_SPACE and field in ("level_name", "save_as_name"):
                char = " "
            elif 32 <= key <= 126:
                char = chr(key)
            if char is None:
                return False
            if field not in ("level_name", "save_as_name") and char not in "0123456789.-":
                return False
            new_value = value + char

        if field == "level_name":
            self.level["name"] = new_value
        elif field == "save_as_name":
            self.save_as_name = new_value
        elif field == "gravity":
            try:
                self.level["gravity"] = float(new_value) if new_value not in ("", "-", ".", "-.") else 0.0
            except ValueError:
                pass
        elif field == "gate_id" and self.selected and self.selected[0] == "gate":
            self.level["gates"][self.selected[1]]["id"] = new_value
        elif field == "pos_x":
            try:
                self.set_selected_position_component(0, float(new_value) if new_value not in ("", "-", ".", "-.") else 0.0)
            except ValueError:
                pass
        elif field == "pos_y":
            try:
                self.set_selected_position_component(1, float(new_value) if new_value not in ("", "-", ".", "-.") else 0.0)
            except ValueError:
                pass
        return True

    def place_object(self, world_pos):
        x = round(world_pos[0], 1)
        y = round(world_pos[1], 1)
        if self.tool == "ship_start":
            self.level["ship_start"] = [x, y]
            self.selected = ("ship_start",)
        elif self.tool == "turret":
            snapped = self.drop_object_to_surface((x, y), TURRET_SPRITE_WIDTH, TURRET_SPRITE_HEIGHT, TURRET_FLOOR_OFFSET)
            self.level["turrets"].append({"x": round(snapped[0], 1), "y": round(snapped[1], 1), "direction": -90})
            self.selected = ("turret", len(self.level["turrets"]) - 1)
        elif self.tool == "fuel_pod":
            snapped = self.drop_object_to_surface((x, y), FUEL_POD_SPRITE_WIDTH, FUEL_POD_SPRITE_HEIGHT)
            self.level["fuel_pods"].append({"x": round(snapped[0], 1), "y": round(snapped[1], 1)})
            self.selected = ("fuel_pod", len(self.level["fuel_pods"]) - 1)
        elif self.tool == "orb":
            snapped = self.drop_orb_with_plinth_to_surface((x, y))
            self.level["orb"] = {"x": round(snapped[0], 1), "y": round(snapped[1], 1)}
            self.selected = ("orb",)
        elif self.tool == "reactor":
            snapped = self.drop_object_to_surface((x, y), REACTOR_SPRITE_WIDTH, REACTOR_SPRITE_HEIGHT)
            self.level["reactor"] = {"x": round(snapped[0], 1), "y": round(snapped[1], 1)}
            self.selected = ("reactor",)
        elif self.tool == "rock":
            self.level["rocks"].append({"x": x, "y": y, "diameter": 20})
            self.selected = ("rock", len(self.level["rocks"]) - 1)
        elif self.tool == "gate":
            gate = {
                "id": self.next_gate_id(),
                "x": x,
                "y": y,
                "width": 26,
                "height": 190,
                "slide_dy": -88,
                "open_duration": 3.5,
                "slide_time": 0.55,
            }
            self.level["gates"].append(gate)
            self.active_gate_id = gate["id"]
            self.selected = ("gate", len(self.level["gates"]) - 1)
        elif self.tool == "switch":
            snapped = self.drop_switch_to_surface((x, y))
            gate_id = self.active_gate_id or self.nearest_gate_id(snapped) or self.next_gate_id()
            self.level["switches"].append({"x": round(snapped[0], 1), "y": round(snapped[1], 1), "gate_id": gate_id})
            self.selected = ("switch", len(self.level["switches"]) - 1)
        else:
            return
        self.mark_dirty(f"Placed {self.tool}")

    def move_selection(self, world_pos):
        if self.selected is None:
            return
        if self.drag_mode in ("gate_length", "gate_thickness", "gate_slide") and self.selected[0] == "gate":
            gate = self.level["gates"][self.selected[1]]
            dx = world_pos[0] - gate["x"]
            dy = world_pos[1] - gate["y"]
            if gate["height"] >= gate["width"]:
                if self.drag_mode == "gate_length":
                    gate["height"] = max(40, min(200, round(abs(dy) * 2.0, 1)))
                elif self.drag_mode == "gate_thickness":
                    gate["width"] = max(10, min(60, round(abs(dx) * 2.0, 1)))
                elif self.drag_mode == "gate_slide":
                    gate["slide_dy"] = round(dy, 1)
            else:
                if self.drag_mode == "gate_length":
                    gate["width"] = max(40, min(200, round(abs(dx) * 2.0, 1)))
                elif self.drag_mode == "gate_thickness":
                    gate["height"] = max(10, min(60, round(abs(dy) * 2.0, 1)))
                elif self.drag_mode == "gate_slide":
                    gate["slide_dx"] = round(dx, 1)
            return
        x = round(world_pos[0] - self.drag_offset[0], 1)
        y = round(world_pos[1] - self.drag_offset[1], 1)
        kind = self.selected[0]
        if kind == "ship_start":
            self.level["ship_start"] = [x, y]
        elif kind == "orb" and self.level["orb"] is not None:
            self.level["orb"]["x"] = x
            self.level["orb"]["y"] = y
        elif kind == "reactor" and self.level["reactor"] is not None:
            self.level["reactor"]["x"] = x
            self.level["reactor"]["y"] = y
        elif kind == "line_point":
            snapped = self.snap_line_endpoint((x, y), exclude=(self.selected[1], self.selected[2]))
            self.level["cave_lines"][self.selected[1]][self.selected[2]] = snapped
        elif kind == "line":
            line = self.level["cave_lines"][self.selected[1]]
            center = ((line[0][0] + line[1][0]) * 0.5, (line[0][1] + line[1][1]) * 0.5)
            delta_x = x - center[0]
            delta_y = y - center[1]
            self.level["cave_lines"][self.selected[1]] = [
                [round(line[0][0] + delta_x, 1), round(line[0][1] + delta_y, 1)],
                [round(line[1][0] + delta_x, 1), round(line[1][1] + delta_y, 1)],
            ]
        else:
            item = self.level[self.collection_key(kind)][self.selected[1]]
            item["x"] = x
            item["y"] = y

    def nudge_selected(self, dx, dy):
        if self.selected is None:
            return
        kind = self.selected[0]
        if kind == "ship_start":
            self.level["ship_start"][0] += dx
            self.level["ship_start"][1] += dy
        elif kind in ("orb", "reactor"):
            item = self.level[kind]
            if item is not None:
                item["x"] += dx
                item["y"] += dy
        elif kind == "line_point":
            point = self.level["cave_lines"][self.selected[1]][self.selected[2]]
            point[0] += dx
            point[1] += dy
            snapped = self.snap_line_endpoint(point, exclude=(self.selected[1], self.selected[2]))
            point[0], point[1] = snapped
        elif kind == "line":
            for point in self.level["cave_lines"][self.selected[1]]:
                point[0] += dx
                point[1] += dy
        else:
            item = self.level[self.collection_key(kind)][self.selected[1]]
            item["x"] += dx
            item["y"] += dy
            self.apply_drop_snap_to_selected()
        self.mark_dirty("Nudged selection")

    def adjust_selected_property(self, key, step):
        if self.selected is None:
            return
        kind = self.selected[0]
        if kind == "turret":
            turret = self.level["turrets"][self.selected[1]]
            if key == "rotate":
                turret["direction"] = (turret["direction"] + step * 15) % 360
        elif kind == "rock":
            rock = self.level["rocks"][self.selected[1]]
            if key == "diameter":
                rock["diameter"] = max(8, min(80, rock.get("diameter", 20) + step * 2))
        elif kind == "gate":
            gate = self.level["gates"][self.selected[1]]
            if key == "length":
                if gate["height"] >= gate["width"]:
                    gate["height"] = max(40, min(200, gate["height"] + step * 10))
                else:
                    gate["width"] = max(40, min(200, gate["width"] + step * 10))
            elif key == "thickness":
                if gate["height"] >= gate["width"]:
                    gate["width"] = max(10, min(60, gate["width"] + step * 2))
                else:
                    gate["height"] = max(10, min(60, gate["height"] + step * 2))
            elif key == "slide":
                if gate["height"] >= gate["width"]:
                    gate["slide_dy"] = gate.get("slide_dy", -88) + step * 8
                else:
                    gate["slide_dx"] = gate.get("slide_dx", 88) + step * 8
            elif key == "duration":
                gate["open_duration"] = max(0.5, round(gate.get("open_duration", 3.5) + step * 0.2, 2))
            elif key == "slide_time":
                gate["slide_time"] = max(0.1, round(gate.get("slide_time", 0.55) + step * 0.05, 2))
            elif key == "flip":
                width = gate["width"]
                height = gate["height"]
                gate["width"] = min(180, max(26, height))
                gate["height"] = min(180, max(26, width))
                if gate["height"] >= gate["width"]:
                    amount = gate.get("slide_dx", 88) or gate.get("slide_dy", -88) or -88
                    gate.pop("slide_dx", None)
                    gate["slide_dy"] = -abs(amount)
                else:
                    amount = gate.get("slide_dy", -88) or gate.get("slide_dx", 88) or 88
                    gate.pop("slide_dy", None)
                    gate["slide_dx"] = abs(amount)
            self.active_gate_id = gate["id"]
        elif kind == "switch":
            switch = self.level["switches"][self.selected[1]]
            gate_ids = [gate["id"] for gate in self.level["gates"]]
            if gate_ids:
                if key == "gate_link":
                    if switch["gate_id"] not in gate_ids:
                        switch["gate_id"] = gate_ids[0]
                    else:
                        index = gate_ids.index(switch["gate_id"])
                        switch["gate_id"] = gate_ids[(index + step) % len(gate_ids)]
                    self.active_gate_id = switch["gate_id"]
                elif switch["gate_id"] not in gate_ids:
                    switch["gate_id"] = gate_ids[0]
                else:
                    index = gate_ids.index(switch["gate_id"])
                    switch["gate_id"] = gate_ids[(index + step) % len(gate_ids)]
                self.active_gate_id = switch["gate_id"]
        else:
            return
        self.mark_dirty("Adjusted selection")

    def handle_mouse_down(self, event):
        if event.button == 2:
            self.pan_drag = True
            return
        if event.button == 1 and event.pos[0] >= CANVAS_WIDTH:
            if self.minimap_rect is not None and self.minimap_rect.collidepoint(event.pos):
                min_x, max_x, min_y, max_y = self.level["world_bounds"]
                rx = (event.pos[0] - self.minimap_rect.x) / max(1, self.minimap_rect.width)
                ry = (event.pos[1] - self.minimap_rect.y) / max(1, self.minimap_rect.height)
                self.camera_x = min_x + rx * (max_x - min_x)
                self.camera_y = min_y + ry * (max_y - min_y)
                self.status = "Camera moved from minimap"
                return
            for rect, field_id, enabled in reversed(self.text_fields):
                if enabled and rect.collidepoint(event.pos):
                    self.begin_text_edit(field_id)
                    return
            for rect, action, enabled in reversed(self.ui_buttons):
                if enabled and rect.collidepoint(event.pos):
                    self.perform_ui_action(action)
                    return
            return
        if not self.canvas_contains(event.pos):
            return
        world_pos = self.screen_to_world(event.pos)
        if event.button == 1:
            if self.tool == "select":
                handle_hit = self.gate_handle_hit(world_pos)
                if handle_hit is not None:
                    self.dragging = True
                    self.drag_mode = f"gate_{handle_hit}"
                    self.status = f"Adjusting {handle_hit}"
                    return
                self.selected = self.hit_test(world_pos)
                self.dragging = self.selected is not None
                self.drag_mode = "move" if self.dragging else None
                if self.selected is not None:
                    kind = self.selected[0]
                    if kind == "ship_start":
                        anchor = tuple(self.level["ship_start"])
                    elif kind == "orb":
                        anchor = (self.level["orb"]["x"], self.level["orb"]["y"])
                    elif kind == "reactor":
                        anchor = (self.level["reactor"]["x"], self.level["reactor"]["y"])
                    elif kind == "line_point":
                        point = self.level["cave_lines"][self.selected[1]][self.selected[2]]
                        anchor = (point[0], point[1])
                    elif kind == "line":
                        line = self.level["cave_lines"][self.selected[1]]
                        anchor = ((line[0][0] + line[1][0]) * 0.5, (line[0][1] + line[1][1]) * 0.5)
                    else:
                        item = self.level[self.collection_key(kind)][self.selected[1]]
                        anchor = (item["x"], item["y"])
                        if kind == "gate":
                            self.active_gate_id = item["id"]
                        if kind == "switch":
                            self.active_gate_id = item["gate_id"]
                    self.drag_offset = (world_pos[0] - anchor[0], world_pos[1] - anchor[1])
                    self.status = self.get_selection_summary()
            elif self.tool == "line":
                if self.line_start is None:
                    self.line_start = self.snap_line_endpoint(world_pos)
                    self.status = "Line start set"
                else:
                    end_point = self.snap_line_endpoint(world_pos)
                    self.level["cave_lines"].append([self.line_start, end_point])
                    self.selected = ("line", len(self.level["cave_lines"]) - 1)
                    self.line_start = None
                    self.mark_dirty("Added cave line")
            else:
                self.place_object(world_pos)
        elif event.button == 3:
            hit = self.hit_test(world_pos)
            if hit is not None:
                self.selected = hit
                self.delete_selected()

    def handle_mouse_up(self, event):
        if event.button == 1 and self.dragging:
            if self.drag_mode == "move":
                self.apply_drop_snap_to_selected()
            self.dragging = False
            self.drag_mode = None
            self.mark_dirty("Moved selection")
        if event.button == 2:
            self.pan_drag = False

    def handle_mouse_motion(self, event):
        if self.pan_drag:
            self.camera_x -= event.rel[0] / self.zoom
            self.camera_y -= event.rel[1] / self.zoom
        elif self.dragging and self.selected is not None:
            world_pos = self.screen_to_world(event.pos)
            self.move_selection(world_pos)

    def handle_mouse_wheel(self, event):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if mouse_x >= CANVAS_WIDTH:
            return
        before = self.screen_to_world((mouse_x, mouse_y))
        zoom_factor = 1.1 if event.y > 0 else 1.0 / 1.1
        self.zoom = max(0.25, min(4.0, self.zoom * zoom_factor))
        after = self.screen_to_world((mouse_x, mouse_y))
        self.camera_x += before[0] - after[0]
        self.camera_y += before[1] - after[1]

    def handle_keydown(self, event):
        mods = pygame.key.get_mods()
        if self.active_text_field is not None:
            if self.edit_text_field(event.key):
                return
        if event.key in TOOL_KEYS:
            self.tool = TOOL_KEYS[event.key]
            self.line_start = None
            self.status = f"Tool: {self.tool}"
            return
        if event.key == pygame.K_TAB:
            index = [tool for tool, _ in TOOLS].index(self.tool)
            self.tool = TOOLS[(index + 1) % len(TOOLS)][0]
            self.line_start = None
            self.status = f"Tool: {self.tool}"
            return
        if mods & pygame.KMOD_CTRL:
            if event.key == pygame.K_s:
                self.save()
                return
            if event.key == pygame.K_r:
                if self.path:
                    self.open_level(self.path)
                    self.status = "Reloaded level from disk"
                else:
                    self.status = "No saved file to reload"
                return
        if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            self.delete_selected()
            return
        if event.key == pygame.K_ESCAPE:
            self.line_start = None
            self.dragging = False
            self.selected = None
            self.status = "Selection cleared"
            return
        if event.key == pygame.K_EQUALS:
            self.level["gravity"] = round(self.level["gravity"] + 2.0, 1)
            self.mark_dirty(f"Gravity {self.level['gravity']}")
            return
        if event.key == pygame.K_MINUS:
            self.level["gravity"] = round(max(0.0, self.level["gravity"] - 2.0), 1)
            self.mark_dirty(f"Gravity {self.level['gravity']}")
            return
        if event.key == pygame.K_LEFTBRACKET:
            self.cycle_active_gate(-1)
            return
        if event.key == pygame.K_RIGHTBRACKET:
            self.cycle_active_gate(1)
            return

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            step = 4.0 if mods & pygame.KMOD_SHIFT else 1.0
            dx = -step if event.key == pygame.K_LEFT else step if event.key == pygame.K_RIGHT else 0.0
            dy = -step if event.key == pygame.K_UP else step if event.key == pygame.K_DOWN else 0.0
            self.nudge_selected(dx, dy)
            return

        if self.selected is None:
            return

        if event.key == pygame.K_r:
            self.adjust_selected_property("rotate", 1)
        elif event.key == pygame.K_q:
            self.adjust_selected_property("length", -1)
        elif event.key == pygame.K_w:
            self.adjust_selected_property("length", 1)
        elif event.key == pygame.K_a:
            self.adjust_selected_property("thickness", -1)
        elif event.key == pygame.K_s:
            self.adjust_selected_property("thickness", 1)
        elif event.key == pygame.K_d:
            self.adjust_selected_property("slide", 1)
        elif event.key == pygame.K_f:
            self.adjust_selected_property("slide", -1)
        elif event.key == pygame.K_t:
            self.adjust_selected_property("duration", 1)
        elif event.key == pygame.K_g:
            self.adjust_selected_property("duration", -1)
        elif event.key == pygame.K_y:
            self.adjust_selected_property("slide_time", 1)
        elif event.key == pygame.K_h:
            self.adjust_selected_property("slide_time", -1)
        elif event.key == pygame.K_x:
            self.adjust_selected_property("flip", 1)
        elif event.key == pygame.K_c:
            self.adjust_selected_property("diameter", -1)
        elif event.key == pygame.K_v:
            self.adjust_selected_property("diameter", 1)

    def draw_grid(self):
        step = 40
        grid_surface = pygame.Surface((CANVAS_WIDTH, SCREEN_HEIGHT))
        grid_surface.fill(BG_COLOUR)
        start_x = self.camera_x - (CANVAS_WIDTH * 0.5) / self.zoom
        end_x = self.camera_x + (CANVAS_WIDTH * 0.5) / self.zoom
        start_y = self.camera_y - (SCREEN_HEIGHT * 0.5) / self.zoom
        end_y = self.camera_y + (SCREEN_HEIGHT * 0.5) / self.zoom

        first_x = math.floor(start_x / step) * step
        first_y = math.floor(start_y / step) * step
        x = first_x
        while x <= end_x:
            sx, _ = self.world_to_screen((x, 0))
            pygame.draw.line(grid_surface, GRID_COLOUR, (sx, 0), (sx, SCREEN_HEIGHT))
            x += step
        y = first_y
        while y <= end_y:
            _, sy = self.world_to_screen((0, y))
            pygame.draw.line(grid_surface, GRID_COLOUR, (0, sy), (CANVAS_WIDTH, sy))
            y += step
        self.screen.blit(grid_surface, (0, 0))

    def draw_world_bounds(self):
        min_x, max_x, min_y, max_y = self.level["world_bounds"]
        left, top = self.world_to_screen((min_x, min_y))
        right, bottom = self.world_to_screen((max_x, max_y))
        rect = pygame.Rect(left, top, right - left, bottom - top)
        pygame.draw.rect(self.screen, (60, 76, 110), rect, 2)

    def draw_cave_lines(self):
        for index, line in enumerate(self.level["cave_lines"]):
            start = self.world_to_screen(line[0])
            end = self.world_to_screen(line[1])
            selected = self.selected is not None and self.selected[:2] == ("line", index)
            colour = HIGHLIGHT if selected else (110, 214, 255)
            pygame.draw.line(self.screen, colour, start, end, 3)
            for point_index, point in enumerate(line):
                point_selected = self.selected == ("line_point", index, point_index)
                point_colour = (255, 255, 255) if point_selected else (120, 180, 210)
                pygame.draw.circle(self.screen, point_colour, (int(self.world_to_screen(point)[0]), int(self.world_to_screen(point)[1])), 5)
        if self.line_start is not None:
            start = self.world_to_screen(self.line_start)
            mouse_pos = pygame.mouse.get_pos()
            if self.canvas_contains(mouse_pos):
                pygame.draw.line(self.screen, (255, 180, 120), start, mouse_pos, 2)

    def draw_marker(self, pos, colour, radius=10, outline=(255, 255, 255)):
        sx, sy = self.world_to_screen(pos)
        pygame.draw.circle(self.screen, colour, (int(sx), int(sy)), radius)
        pygame.draw.circle(self.screen, outline, (int(sx), int(sy)), radius, 2)

    def draw_ship_icon(self, pos, selected=False):
        sx, sy = self.world_to_screen(pos)
        scale = max(0.35, self.zoom)
        nose = 14 * scale
        wing_x = 11 * scale
        tail_y = 10 * scale
        points = [
            (sx, sy - nose),
            (sx - wing_x, sy + tail_y),
            (sx + wing_x, sy + tail_y),
        ]
        fill = (232, 238, 255)
        outline = HIGHLIGHT if selected else (110, 170, 255)
        pygame.draw.polygon(self.screen, fill, points)
        pygame.draw.polygon(self.screen, outline, points, max(1, int(2 * scale)))

    def draw_turret_icon(self, turret, selected=False):
        sx, sy = self.world_to_screen((turret["x"], turret["y"]))
        scale = max(0.35, self.zoom)
        outline = HIGHLIGHT if selected else (170, 184, 205)
        base_rect = pygame.Rect(0, 0, max(8, int(28 * scale)), max(4, int(12 * scale)))
        base_rect.center = (sx, sy + 10 * scale)
        plinth_rect = pygame.Rect(0, 0, max(6, int(18 * scale)), max(3, int(8 * scale)))
        plinth_rect.center = (sx, sy + 1 * scale)
        pygame.draw.rect(self.screen, (58, 62, 70), base_rect, border_radius=4)
        pygame.draw.rect(self.screen, (92, 98, 110), base_rect.inflate(-4, -4), border_radius=3)
        pygame.draw.rect(self.screen, (74, 78, 88), plinth_rect, border_radius=3)
        head_radius = max(3, int(9 * scale))
        pygame.draw.circle(self.screen, (66, 72, 82), (int(sx), int(sy - 5 * scale)), head_radius)
        pygame.draw.circle(self.screen, outline, (int(sx), int(sy - 5 * scale)), head_radius, max(1, int(2 * scale)))
        barrel_end = (sx, sy - 24 * scale)
        pygame.draw.line(self.screen, (160, 170, 186), (sx, sy - 5 * scale), barrel_end, max(1, int(4 * scale)))
        pygame.draw.circle(self.screen, (255, 120, 90), (int(barrel_end[0]), int(barrel_end[1])), max(1, int(2 * scale)))

    def draw_fuel_pod_icon(self, pod, selected=False):
        sx, sy = self.world_to_screen((pod["x"], pod["y"]))
        scale = max(0.35, self.zoom)
        outline = HIGHLIGHT if selected else (120, 255, 180)
        body_rect = pygame.Rect(0, 0, max(8, int(24 * scale)), max(12, int(34 * scale)))
        body_rect.center = (sx, sy)
        inner_rect = body_rect.inflate(-8, -10)
        pygame.draw.rect(self.screen, outline, body_rect, max(1, int(2 * scale)), border_radius=max(2, int(6 * scale)))
        pygame.draw.rect(self.screen, (70, 160, 120), inner_rect, max(1, int(2 * scale)), border_radius=max(2, int(4 * scale)))
        fill_rect = inner_rect.inflate(-4, -8)
        pygame.draw.rect(self.screen, (90, 255, 180), fill_rect, border_radius=max(2, int(4 * scale)))

    def draw_orb_icon(self, pos, selected=False):
        sx, sy = self.world_to_screen(pos)
        scale = max(0.35, self.zoom)
        outline = HIGHLIGHT if selected else (255, 236, 160)
        floor_y = sy + ORB_PLINTH_HEIGHT * scale
        plinth_base_y = floor_y
        plinth_top_y = floor_y - 34 * scale
        body_rect = pygame.Rect(0, 0, max(10, int(30 * scale)), max(6, int(plinth_base_y - plinth_top_y)))
        body_rect.midtop = (sx, plinth_top_y)
        cap_rect = pygame.Rect(0, 0, max(18, int(54 * scale)), max(6, int(16 * scale)))
        cap_rect.midbottom = (sx, plinth_top_y + 6)
        foot_rect = pygame.Rect(0, 0, max(14, int(42 * scale)), max(4, int(10 * scale)))
        foot_rect.midbottom = (sx, plinth_base_y)
        glow_size = max(24, int(80 * scale))
        glow_center = glow_size // 2
        glow_surface = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (255, 208, 82, 64), (glow_center, int(glow_center * 0.85)), max(8, int(26 * scale)))
        self.screen.blit(glow_surface, (sx - glow_center, plinth_top_y - 10 * scale))
        pygame.draw.rect(self.screen, (146, 104, 18), body_rect, border_radius=max(2, int(6 * scale)))
        pygame.draw.rect(self.screen, (236, 194, 78), body_rect, max(1, int(2 * scale)), border_radius=max(2, int(6 * scale)))
        pygame.draw.ellipse(self.screen, (242, 204, 92), cap_rect)
        pygame.draw.ellipse(self.screen, (255, 232, 154), cap_rect, max(1, int(2 * scale)))
        cradle_rect = cap_rect.inflate(max(-2, int(-10 * scale)), max(-1, int(-1 * scale)))
        pygame.draw.arc(self.screen, (176, 122, 26), cradle_rect, math.pi, math.tau, max(1, int(3 * scale)))
        lip_rect = cap_rect.inflate(max(-2, int(-16 * scale)), max(-2, int(-8 * scale)))
        pygame.draw.arc(self.screen, (255, 236, 170), lip_rect, math.pi, math.tau, max(1, int(2 * scale)))
        pygame.draw.rect(self.screen, (188, 148, 44), foot_rect, border_radius=max(2, int(4 * scale)))
        pygame.draw.rect(self.screen, (248, 215, 112), foot_rect, max(1, int(2 * scale)), border_radius=max(2, int(4 * scale)))
        outer_radius = max(5, int(14 * scale))
        inner_radius = max(2, int(8 * scale))
        pygame.draw.circle(self.screen, (255, 210, 80), (int(sx), int(sy)), outer_radius)
        pygame.draw.circle(self.screen, (255, 248, 220), (int(sx), int(sy)), inner_radius)
        pygame.draw.circle(self.screen, outline, (int(sx), int(sy)), outer_radius, max(1, int(2 * scale)))

    def draw_reactor_icon(self, pos, selected=False):
        sx, sy = self.world_to_screen(pos)
        scale = max(0.35, self.zoom)
        outline = HIGHLIGHT if selected else (180, 188, 198)
        body_rect = pygame.Rect(0, 0, max(10, int(34 * scale)), max(11, int(36 * scale)))
        body_rect.center = (sx, sy + 2 * scale)
        top_rect = pygame.Rect(0, 0, max(12, int(42 * scale)), max(4, int(10 * scale)))
        top_rect.center = (sx, sy - 16 * scale)
        core_rect = body_rect.inflate(-12, -12)
        pygame.draw.rect(self.screen, (126, 128, 136), body_rect, border_radius=max(2, int(4 * scale)))
        pygame.draw.rect(self.screen, (164, 167, 176), top_rect, border_radius=max(2, int(3 * scale)))
        pygame.draw.rect(self.screen, (82, 86, 94), core_rect, border_radius=max(2, int(3 * scale)))
        pygame.draw.circle(self.screen, (255, 157, 50), (int(sx), int(sy + 4 * scale)), max(2, int(7 * scale)))
        pygame.draw.rect(self.screen, outline, body_rect, max(1, int(2 * scale)), border_radius=max(2, int(4 * scale)))

    def draw_rock_icon(self, rock, selected=False):
        sx, sy = self.world_to_screen((rock["x"], rock["y"]))
        radius = max(5, int(rock.get("diameter", 20) * 0.5 * self.zoom))
        outline = HIGHLIGHT if selected else (170, 174, 182)
        pygame.draw.circle(self.screen, (115, 118, 126), (int(sx), int(sy)), radius)
        pygame.draw.circle(self.screen, outline, (int(sx), int(sy)), radius, 2)
        pygame.draw.circle(self.screen, (88, 92, 100), (int(sx + radius * 0.35), int(sy - radius * 0.2)), max(1, int(radius * 0.25)))

    def draw_switch_icon(self, switch, selected=False, gate_match=False):
        sx, sy = self.world_to_screen((switch["x"], switch["y"]))
        scale = max(0.35, self.zoom)
        if selected:
            lens_colour = (255, 230, 120)
        elif gate_match:
            lens_colour = (150, 255, 172)
        else:
            lens_colour = (255, 140, 98)
        base_rect = pygame.Rect(0, 0, max(6, int(18 * scale)), max(3, int(9 * scale)))
        base_rect.center = (sx, sy + 10 * scale)
        pygame.draw.rect(self.screen, (96, 104, 116), base_rect, border_radius=max(2, int(3 * scale)))
        pygame.draw.rect(self.screen, (150, 160, 174), base_rect, max(1, int(2 * scale)), border_radius=max(2, int(3 * scale)))
        lens_radius = max(3, int(9 * scale))
        pygame.draw.circle(self.screen, lens_colour, (int(sx), int(sy)), lens_radius)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(sx), int(sy)), lens_radius, max(1, int(2 * scale)))

    def draw_objects(self):
        for index, turret in enumerate(self.level["turrets"]):
            self.draw_turret_icon(turret, selected=self.selected == ("turret", index))
        for index, pod in enumerate(self.level["fuel_pods"]):
            self.draw_fuel_pod_icon(pod, selected=self.selected == ("fuel_pod", index))
        for index, rock in enumerate(self.level["rocks"]):
            self.draw_rock_icon(rock, selected=self.selected == ("rock", index))
        for index, gate in enumerate(self.level["gates"]):
            sx, sy = self.world_to_screen((gate["x"], gate["y"]))
            rect = pygame.Rect(0, 0, gate["width"] * self.zoom, gate["height"] * self.zoom)
            rect.center = (sx, sy)
            outline = HIGHLIGHT if self.selected == ("gate", index) else (200, 240, 255)
            pygame.draw.rect(self.screen, (82, 108, 122), rect, border_radius=4)
            pygame.draw.rect(self.screen, outline, rect, 2, border_radius=4)
            label = self.small_font.render(gate["id"], True, outline)
            self.screen.blit(label, (rect.left, rect.top - 18))
            end_x = gate["x"] + gate.get("slide_dx", 0.0)
            end_y = gate["y"] + gate.get("slide_dy", 0.0)
            pygame.draw.line(self.screen, (120, 180, 210), (sx, sy), self.world_to_screen((end_x, end_y)), 2)
            if self.selected == ("gate", index):
                handles = self.gate_handle_points(gate)
                handle_specs = {
                    "length": ((255, 214, 120), "L"),
                    "thickness": ((120, 255, 184), "T"),
                    "slide": ((120, 190, 255), "S"),
                }
                for handle_name, handle_pos in handles.items():
                    hx, hy = self.world_to_screen(handle_pos)
                    colour, letter = handle_specs[handle_name]
                    pygame.draw.circle(self.screen, colour, (int(hx), int(hy)), 9)
                    pygame.draw.circle(self.screen, (255, 255, 255), (int(hx), int(hy)), 9, 2)
                    text = self.small_font.render(letter, True, (18, 22, 28))
                    self.screen.blit(text, text.get_rect(center=(hx, hy)))
        for index, switch in enumerate(self.level["switches"]):
            selected = self.selected == ("switch", index)
            gate_match = switch["gate_id"] == self.active_gate_id
            self.draw_switch_icon(switch, selected=selected, gate_match=gate_match)
            colour = HIGHLIGHT if selected else (150, 255, 172) if gate_match else (255, 140, 98)
            label = self.small_font.render(switch["gate_id"], True, colour)
            sx, sy = self.world_to_screen((switch["x"], switch["y"]))
            self.screen.blit(label, (sx + 10, sy - 10))
        if self.level["orb"] is not None:
            self.draw_orb_icon((self.level["orb"]["x"], self.level["orb"]["y"]), selected=self.selected == ("orb",))
        if self.level["reactor"] is not None:
            self.draw_reactor_icon((self.level["reactor"]["x"], self.level["reactor"]["y"]), selected=self.selected == ("reactor",))
        self.draw_ship_icon(tuple(self.level["ship_start"]), selected=self.selected == ("ship_start",))

    def draw_sidebar(self):
        self.ui_buttons = []
        self.text_fields = []
        self.minimap_rect = None
        sidebar_rect = pygame.Rect(CANVAS_WIDTH, 0, SIDEBAR_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, (18, 22, 32), sidebar_rect)
        title = self.font.render("Level Editor", True, TEXT_COLOUR)
        self.screen.blit(title, (CANVAS_WIDTH + 16, 16))
        file_label = os.path.basename(self.path) if self.path else "(new unsaved level)"
        file_text = self.small_font.render(file_label, True, MUTED_TEXT)
        self.screen.blit(file_text, (CANVAS_WIDTH + 16, 42))

        panel_x = CANVAS_WIDTH + 12
        panel_width = SIDEBAR_WIDTH - 24

        self.draw_panel(panel_x, 72, panel_width, 128, "Tools")
        button_w = (panel_width - 30) // 2
        tool_y = 104
        for index, (tool, label) in enumerate(TOOLS):
            col = index % 2
            row = index // 2
            rect = pygame.Rect(panel_x + 12 + col * (button_w + 6), tool_y + row * 30, button_w, 24)
            self.draw_button(rect, label, ("set_tool", tool), active=self.tool == tool)

        self.draw_panel(panel_x, 208, panel_width, 154, "File")
        self.draw_button(
            pygame.Rect(panel_x + 12, 242, 66, 28),
            "New",
            ("new_level",),
            enabled=not self.unsaved,
        )
        self.draw_button(pygame.Rect(panel_x + 84, 242, 66, 28), "Save", ("save",), enabled=self.path is not None)
        self.draw_button(pygame.Rect(panel_x + 156, 242, 66, 28), "Save As", ("save_as",))
        self.draw_button(
            pygame.Rect(panel_x + 228, 242, 66, 28),
            "Load",
            ("toggle_level_list",),
            enabled=not self.unsaved,
            active=self.show_level_list,
        )
        self.draw_button(
            pygame.Rect(panel_x + 12, 274, 66, 28),
            "Reload",
            ("reload",),
            enabled=self.path is not None,
        )
        self.draw_button(
            pygame.Rect(panel_x + 84, 274, 66, 28),
            "Play",
            ("play_level",),
            enabled=not self.unsaved and self.path is not None,
        )
        save_state = "Unsaved changes" if self.unsaved else "All changes saved"
        save_colour = HIGHLIGHT if self.unsaved else (150, 232, 178)
        save_text = self.small_font.render(save_state, True, save_colour)
        self.screen.blit(save_text, (panel_x + 12, 312))
        saved_at = self.last_saved_at or "Not saved yet"
        saved_text = self.small_font.render(f"Last save: {saved_at}", True, MUTED_TEXT)
        self.screen.blit(saved_text, (panel_x + 12, 330))

        level_panel_height = 34 + min(6, max(1, len(self.level_paths))) * 28 if self.show_level_list else 58
        level_panel = self.draw_panel(panel_x, 370, panel_width, level_panel_height, "Levels")
        current_label = os.path.basename(self.path) if self.path else "(new unsaved level)"
        current_name = self.small_font.render(current_label, True, TEXT_COLOUR)
        self.screen.blit(current_name, (panel_x + 12, 332))
        self.draw_button(pygame.Rect(panel_x + panel_width - 108, 326, 96, 24), "Center View", ("center_camera",))
        if self.show_level_list:
            row_y = 356
            for level_path in self.level_paths[:6]:
                label = os.path.basename(level_path)
                self.draw_button(
                    pygame.Rect(panel_x + 12, row_y, panel_width - 24, 24),
                    label,
                    ("load_level", level_path),
                    enabled=not self.unsaved,
                    active=level_path == self.path,
                )
                row_y += 28

        self.draw_panel(panel_x, 370 + level_panel_height + 8, panel_width, 152, "Level")
        name_label = self.small_font.render("Name", True, MUTED_TEXT)
        level_y = 370 + level_panel_height + 8
        self.screen.blit(name_label, (panel_x + 12, level_y + 34))
        self.register_text_field(pygame.Rect(panel_x + 72, level_y + 28, panel_width - 84, 28), "level_name", self.level["name"])
        self.draw_property_row(panel_x + 12, level_y + 64, panel_width - 24, "Gravity", self.level["gravity"], ("adjust_gravity", -2.0), ("adjust_gravity", 2.0))
        self.draw_property_row(panel_x + 12, level_y + 98, panel_width - 24, "Zoom", f"{self.zoom:.2f}", ("adjust_zoom", 1.0 / 1.1), ("adjust_zoom", 1.1))
        active_gate_label = self.active_gate_id or "None"
        self.draw_property_row(panel_x + 12, level_y + 132, panel_width - 24, "Active Gate", active_gate_label, ("cycle_gate", -1), ("cycle_gate", 1))

        selection_y = level_y + 160
        self.draw_panel(panel_x, selection_y, panel_width, 258, "Selection")
        selection_text = self.small_font.render(self.get_selection_summary()[:34], True, TEXT_COLOUR)
        self.screen.blit(selection_text, (panel_x + 12, selection_y + 32))
        self.draw_button(
            pygame.Rect(panel_x + 12, selection_y + 56, 112, 28),
            "Delete",
            ("delete_selected",),
            enabled=self.selected is not None and self.selected[0] != "ship_start",
        )

        detail_y = selection_y + 96
        if self.selected is None:
            helper = [
                "Select and drag objects with the mouse.",
                "Use Cave Line tool to click start and end points.",
                "Switches auto-snap onto terrain.",
                "Gates and switches can be edited here.",
            ]
            for line in helper:
                text = self.small_font.render(line, True, MUTED_TEXT)
                self.screen.blit(text, (panel_x + 12, detail_y))
                detail_y += 22
        else:
            kind = self.selected[0]
            if kind == "turret":
                turret = self.level["turrets"][self.selected[1]]
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(turret["x"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(turret["x"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(turret["y"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(turret["y"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Direction", int(turret["direction"]), ("adjust_property", "rotate", -1), ("adjust_property", "rotate", 1))
            elif kind == "rock":
                rock = self.level["rocks"][self.selected[1]]
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(rock["x"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(rock["x"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(rock["y"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(rock["y"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Diameter", rock.get("diameter", 20), ("adjust_property", "diameter", -1), ("adjust_property", "diameter", 1))
            elif kind == "gate":
                gate = self.level["gates"][self.selected[1]]
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Gate ID", gate["id"])
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 150, 28), "gate_id", gate["id"])
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(gate["x"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(gate["x"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(gate["y"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(gate["y"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Length", max(gate["width"], gate["height"]), ("adjust_property", "length", -1), ("adjust_property", "length", 1))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Thickness", min(gate["width"], gate["height"]), ("adjust_property", "thickness", -1), ("adjust_property", "thickness", 1))
                detail_y += 34
                slide_amount = gate.get("slide_dx", 0.0) or gate.get("slide_dy", 0.0)
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Slide", int(slide_amount), ("adjust_property", "slide", -1), ("adjust_property", "slide", 1))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Open Time", gate.get("open_duration", 3.5), ("adjust_property", "duration", -1), ("adjust_property", "duration", 1))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Slide Time", gate.get("slide_time", 0.55), ("adjust_property", "slide_time", -1), ("adjust_property", "slide_time", 1))
                detail_y += 38
                self.draw_button(pygame.Rect(panel_x + 12, detail_y, 96, 28), "Flip Axis", ("adjust_property", "flip", 1))
            elif kind == "switch":
                switch = self.level["switches"][self.selected[1]]
                gate_ids = [gate["id"] for gate in self.level["gates"]]
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(switch["x"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(switch["x"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(switch["y"]))
                self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(switch["y"]))
                detail_y += 34
                self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Gate", switch["gate_id"], ("adjust_property", "gate_link", -1), ("adjust_property", "gate_link", 1))
                detail_y += 38
                self.draw_button(pygame.Rect(panel_x + 12, detail_y, 96, 28), "Snap", ("snap_switch",))
                detail_y += 40
                if gate_ids:
                    caption = self.small_font.render("Assign Directly", True, MUTED_TEXT)
                    self.screen.blit(caption, (panel_x + 12, detail_y))
                    detail_y += 24
                    for gate_id in gate_ids[:4]:
                        self.draw_button(
                            pygame.Rect(panel_x + 12, detail_y, panel_width - 24, 24),
                            gate_id,
                            ("set_switch_gate", gate_id),
                            active=switch["gate_id"] == gate_id,
                        )
                        detail_y += 28
            elif kind in ("line", "line_point"):
                pos = self.selected_position()
                if pos is not None:
                    self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(pos[0]))
                    self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(pos[0]))
                    detail_y += 34
                    self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(pos[1]))
                    self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(pos[1]))
                    detail_y += 34
                tip_lines = [
                    "Drag endpoints or whole line.",
                    "Delete removes the whole segment.",
                    "Use Cave Line tool to add more.",
                ]
                for line in tip_lines:
                    text = self.small_font.render(line, True, MUTED_TEXT)
                    self.screen.blit(text, (panel_x + 12, detail_y))
                    detail_y += 22
            else:
                pos = self.selected_position()
                if pos is not None:
                    self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "X", int(pos[0]))
                    self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_x", int(pos[0]))
                    detail_y += 34
                    self.draw_property_row(panel_x + 12, detail_y, panel_width - 24, "Y", int(pos[1]))
                    self.register_text_field(pygame.Rect(panel_x + 132, detail_y, 78, 28), "pos_y", int(pos[1]))
                    detail_y += 34
                tip_lines = [
                    "Drag to reposition.",
                    "Use arrow keys for fine nudge.",
                    "Delete removes selected object.",
                ]
                for line in tip_lines:
                    text = self.small_font.render(line, True, MUTED_TEXT)
                    self.screen.blit(text, (panel_x + 12, detail_y))
                    detail_y += 22

        minimap_y = selection_y + 266
        help_rect = self.draw_panel(panel_x, minimap_y, panel_width, 86, "Minimap")
        map_rect = pygame.Rect(panel_x + 12, 758, panel_width - 24, 42)
        map_rect = pygame.Rect(panel_x + 12, minimap_y + 32, panel_width - 24, 42)
        self.minimap_rect = map_rect
        pygame.draw.rect(self.screen, (14, 18, 26), map_rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_BORDER, map_rect, 1, border_radius=6)
        min_x, max_x, min_y, max_y = self.level["world_bounds"]
        world_w = max(1.0, max_x - min_x)
        world_h = max(1.0, max_y - min_y)
        for line in self.level["cave_lines"]:
            ax = map_rect.x + (line[0][0] - min_x) / world_w * map_rect.width
            ay = map_rect.y + (line[0][1] - min_y) / world_h * map_rect.height
            bx = map_rect.x + (line[1][0] - min_x) / world_w * map_rect.width
            by = map_rect.y + (line[1][1] - min_y) / world_h * map_rect.height
            pygame.draw.line(self.screen, (90, 190, 230), (ax, ay), (bx, by), 1)
        cam_world_w = CANVAS_WIDTH / self.zoom
        cam_world_h = SCREEN_HEIGHT / self.zoom
        view_rect = pygame.Rect(
            map_rect.x + (self.camera_x - cam_world_w * 0.5 - min_x) / world_w * map_rect.width,
            map_rect.y + (self.camera_y - cam_world_h * 0.5 - min_y) / world_h * map_rect.height,
            max(6, cam_world_w / world_w * map_rect.width),
            max(6, cam_world_h / world_h * map_rect.height),
        )
        pygame.draw.rect(self.screen, HIGHLIGHT, view_rect, 2)

        links_y = minimap_y + 92
        list_rect = self.draw_panel(panel_x, links_y, panel_width, 72, "Links")
        row_y = list_rect.y + 30
        for gate_index, gate in enumerate(self.level["gates"][:2]):
            self.draw_button(
                pygame.Rect(panel_x + 12, row_y, 114, 24),
                gate["id"],
                ("select_item", ("gate", gate_index)),
                active=self.selected == ("gate", gate_index),
            )
            row_y += 26
        row_y = list_rect.y + 30
        for switch_index, switch in enumerate(self.level["switches"][:2]):
            self.draw_button(
                pygame.Rect(panel_x + 138, row_y, 158, 24),
                f"SW {switch_index} -> {switch['gate_id']}",
                ("select_item", ("switch", switch_index)),
                active=self.selected == ("switch", switch_index),
            )
            row_y += 26

        status_bg = pygame.Rect(CANVAS_WIDTH, SCREEN_HEIGHT - 40, SIDEBAR_WIDTH, 40)
        pygame.draw.rect(self.screen, (28, 34, 44), status_bg)
        status = self.small_font.render(self.status[:36], True, HIGHLIGHT if self.unsaved else TEXT_COLOUR)
        self.screen.blit(status, (CANVAS_WIDTH + 12, SCREEN_HEIGHT - 28))
        disk_state = "DIRTY" if self.unsaved else "SAVED"
        disk_colour = HIGHLIGHT if self.unsaved else (150, 232, 178)
        disk_text = self.small_font.render(disk_state, True, disk_colour)
        self.screen.blit(disk_text, (CANVAS_WIDTH + SIDEBAR_WIDTH - 70, SCREEN_HEIGHT - 28))

    def draw(self):
        self.draw_grid()
        self.draw_world_bounds()
        self.draw_cave_lines()
        self.draw_objects()
        pygame.draw.line(self.screen, (40, 50, 68), (CANVAS_WIDTH, 0), (CANVAS_WIDTH, SCREEN_HEIGHT), 2)
        self.draw_sidebar()
        pygame.display.flip()

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_mouse_down(event)
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.handle_mouse_up(event)
                elif event.type == pygame.MOUSEMOTION:
                    self.handle_mouse_motion(event)
                elif event.type == pygame.MOUSEWHEEL:
                    self.handle_mouse_wheel(event)
                elif event.type == pygame.KEYDOWN:
                    self.handle_keydown(event)

            self.draw()
            self.clock.tick(60)
        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Cave Flyer mouse-driven level editor")
    parser.add_argument("level", nargs="?", default="levels/level0001.json", help="Path to level JSON file")
    args = parser.parse_args()
    editor = LevelEditor(args.level)
    editor.run()


if __name__ == "__main__":
    main()
