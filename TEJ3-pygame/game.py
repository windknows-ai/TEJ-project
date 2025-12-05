import pygame
import sys
import random
import math

pygame.init()

WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("TEJ-project")
clock = pygame.time.Clock()
FPS = 60

font = pygame.font.SysFont(None, 26)
level_font = pygame.font.SysFont(None, 72)
level_popup_font = pygame.font.SysFont(None, 96)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 80, 80)
BLUE = (80, 80, 255)
YELLOW = (255, 255, 80)
GREEN = (80, 255, 80)
GREY = (180, 180, 180)
PURPLE = (200, 80, 255)
HOMING_GREEN = (140, 255, 140)
LASER_COLOR = (180, 255, 255)
CANNON_LASER_COLOR = (160, 255, 160)

INFO_COLOR_CTRL = (200, 220, 255)
INFO_COLOR_WEAPON = (200, 255, 200)
INFO_COLOR_HOMING = (180, 255, 180)
INFO_COLOR_CANNON = (180, 255, 230)
INFO_COLOR_ENEMY = (255, 220, 220)
INFO_COLOR_LEVEL = (255, 255, 180)
INFO_COLOR_SHOP = (220, 220, 220)

PLAYER_POS = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
PLAYER_BASE_RADIUS = 20.0
PLAYER_RADIUS = PLAYER_BASE_RADIUS * 0.56

BULLET_SPEED = 10.0
HOMING_SPEED = BULLET_SPEED * 1.1
BASE_BULLET_DAMAGE = 1.0
BASE_LASER_DAMAGE = 2.5
BASE_BULLET_RADIUS = 4.0 * 1.7
BASE_BULLET_INTERVAL = 120
LASER_MAX_RANGE = 1000.0

YELLOW_INTERVAL_FACTOR = 4.0 / 3.0

def price_disc(x):
    if x >= 4000:
        x = int(x * 0.6)
    elif x >= 3000:
        x = int(x * 0.7)
    else:
        x = int(x * 0.8)
    t = x // 10 % 10
    o = x % 10
    if t and o:
        x = x // 100 * 100
    return x

bullet_radius_base = BASE_BULLET_RADIUS
bullet_interval_base_ms = BASE_BULLET_INTERVAL
bullet_radius = bullet_radius_base
bullet_interval_ms = bullet_interval_base_ms

weapon_mode = "bullet"
laser_unlocked = False
LASER_BUY_COST = price_disc(5000)

cannon_owned = False
cannon_level = 0
CANNON_BUY_COST = price_disc(7500)
CANNON_UPGRADE_COSTS = [
    price_disc(10000),
    price_disc(15000),
    price_disc(20000)
]

homing_owned = False
homing_level = 0
HOMING_BUY_COST = price_disc(2000)
HOMING_UPGRADE_COSTS = [
    price_disc(3000),
    price_disc(4500),
    price_disc(6500)
]
homing_hit_counter = 0

DAMAGE_BASE_MULT = 1.0
DAMAGE_PER_LEVEL = 0.10
DMG_MAX_LEVEL = 20
DAMAGE_BASE_COST = 8000
DAMAGE_COST_STEP = 800

damage_level = 0
damage_multiplier = DAMAGE_BASE_MULT + DAMAGE_PER_LEVEL * damage_level
damage_upgrade_cost = DAMAGE_BASE_COST
damage_shop_unlocked = False
damage_shop_hint_timer = 0.0

BULLET_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(BULLET_EVENT, bullet_interval_ms)

bullets = []
laser_beams = []
enemies = []
explosions = []

MIN_RADIUS = 6
coins = 0

coin_multiplier = 1.0
speed_level_factor = 1.0
grey_purple_prob_multiplier = 1.0
hp_multiplier = 1.0
PURPLE_HITS_FACTOR = 1.0

post20_hp_mult = 1.0
post20_speed_mult = 1.0
post20_spawn_mult = 1.0
post20_coin_mult = 1.0
spawn_base_interval_20plus = None

auto_level_enabled = False
auto_level_interval = 20.0
next_auto_level_time = None

density30_active = False
cannon_hit_counter = 0

def get_coin_gain(base_reward):
    return int(base_reward * coin_multiplier * post20_coin_mult)

def register_homing_hits(n=1):
    global homing_hit_counter
    if weapon_mode != "bullet":
        return
    if not homing_owned or homing_level <= 0:
        return
    homing_hit_counter += n
    thr = homing_threshold()
    while homing_hit_counter >= thr:
        homing_hit_counter -= thr
        spawn_homing_barrage(homing_projectile_count())

def apply_damage(enemy, base_damage):
    enemy.hit(base_damage * damage_multiplier)

def explode_grey(center_pos):
    aoe_radius = 130
    for e in enemies:
        if not e.alive:
            continue
        if e.pos.distance_to(center_pos) <= aoe_radius + e.radius:
            apply_damage(e, BASE_BULLET_DAMAGE * 7)
    explosions.append({
        "pos": center_pos.copy(),
        "time": 0.3,
        "duration": 0.3,
        "min_r": 20.0,
        "max_r": 130.0
    })

class Enemy:
    def __init__(self, x, y, radius, color, hp, speed, reward, kind):
        self.pos = pygame.Vector2(x, y)
        self.radius = radius
        self.color = color
        self.max_hp = float(hp)
        self.hp = float(hp)
        self.alive = True
        self.speed = speed
        self.reward = reward
        self.kind = kind
        self.teleport_timer = 0.0
        self.spawn_radius = radius
        self.shield_timer = 7.0 if self.kind == "grey" else 0.0
        if self.kind == "purple":
            self.phase = "growing"
            self.hits_taken = 0.0
            self.initial_radius = self.spawn_radius
            self.max_hits = max(1, int(20 * PURPLE_HITS_FACTOR + 0.5))
            self.max_radius = self.spawn_radius * 2.5
            self.attach_target = None
            self.attach_timer = 0.0
            self.has_revived = False
        else:
            self.phase = None
            self.hits_taken = 0.0
            self.initial_radius = radius
            self.max_radius = radius
            self.attach_target = None
            self.attach_timer = 0.0
            self.has_revived = False

    def update(self, dt):
        if not self.alive:
            return
        if self.kind == "purple" and self.phase == "attached":
            if self.attach_target is None or (not self.attach_target.alive):
                global coins
                coins += get_coin_gain(self.reward)
                self.alive = False
                return
            self.pos = self.attach_target.pos.copy()
            self.attach_timer += dt
            if (not self.has_revived) and self.attach_timer >= 5.0:
                self.phase = "reborn"
                self.has_revived = True
                self.attach_target = None
                self.attach_timer = 0.0
                self.radius = self.spawn_radius
                self.initial_radius = self.spawn_radius
                self.max_radius = self.spawn_radius
                self.hp = float(10 * hp_multiplier * post20_hp_mult * 1.4)
                self.max_hp = self.hp
                self.shield_timer = 3.0
            return
        if self.kind == "green":
            self.teleport_timer += dt
            while self.teleport_timer >= 3.0:
                self.teleport_timer -= 3.0
                offset = self.pos - PLAYER_POS
                r = offset.length()
                if r > 0:
                    ang = random.uniform(0, 2 * math.pi)
                    self.pos = pygame.Vector2(
                        PLAYER_POS.x + r * math.cos(ang),
                        PLAYER_POS.y + r * math.sin(ang)
                    )
        d = PLAYER_POS - self.pos
        if d.length() != 0:
            d = d.normalize() * self.speed
            self.pos += d
        if self.shield_timer > 0:
            self.shield_timer -= dt
            if self.shield_timer < 0:
                self.shield_timer = 0

    def draw(self, surf):
        if not self.alive:
            return
        if (
            self.kind == "purple"
            and self.phase == "attached"
            and self.attach_target is not None
            and self.attach_target.alive
        ):
            host = self.attach_target
            d = host.pos - PLAYER_POS
            if d.length() == 0:
                d = pygame.Vector2(1, 0)
            perp = pygame.Vector2(-d.y, d.x)
            if perp.length() == 0:
                perp = pygame.Vector2(0, 1)
            perp = perp.normalize()
            p = host.pos + perp * (host.radius + self.radius)
            pygame.draw.circle(
                surf,
                self.color,
                (int(p.x), int(p.y)),
                int(self.radius)
            )
            return
        pygame.draw.circle(
            surf,
            self.color,
            (int(self.pos.x), int(self.pos.y)),
            int(self.radius)
        )
        if self.shield_timer > 0:
            pygame.draw.circle(
                surf,
                (160, 200, 255),
                (int(self.pos.x), int(self.pos.y)),
                int(self.radius + 6),
                2
            )
            text = font.render(f"{self.shield_timer:.1f}", True, WHITE)
            surf.blit(text, text.get_rect(center=(int(self.pos.x), int(self.pos.y))))
        hp_ratio = self.hp / self.max_hp if self.max_hp > 0 else 0
        bw = self.radius * 2
        bh = 5
        bx = self.pos.x - self.radius
        by = self.pos.y - self.radius - 8
        pygame.draw.rect(surf, BLACK, (bx, by, bw, bh))
        pygame.draw.rect(surf, WHITE, (bx, by, bw * hp_ratio, bh))

    def hit(self, dmg):
        global coins
        if not self.alive:
            return
        if self.shield_timer > 0 and self.kind in ("grey", "purple"):
            return
        if self.kind == "purple":
            if self.phase == "growing":
                self.hits_taken += dmg
                f = min(self.hits_taken, self.max_hits) / float(self.max_hits)
                self.radius = self.initial_radius + (self.max_radius - self.initial_radius) * f
                if self.hits_taken >= self.max_hits and self.phase == "growing":
                    self.radius = self.spawn_radius
                    self.initial_radius = self.spawn_radius
                    self.max_radius = self.spawn_radius * 2.5
                    cands = [e for e in enemies if e.alive and e is not self]
                    if cands:
                        self.attach_target = random.choice(cands)
                        self.phase = "attached"
                        self.attach_timer = 0.0
                return
            if self.phase == "attached":
                return
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False
            coins += get_coin_gain(self.reward)
            if self.kind == "grey":
                explode_grey(self.pos)

def random_edge_position():
    s = random.choice(["top", "bottom", "left", "right"])
    if s == "top":
        return random.randint(0, WIDTH), -20
    if s == "bottom":
        return random.randint(0, WIDTH), HEIGHT + 20
    if s == "left":
        return -20, random.randint(0, HEIGHT)
    return WIDTH + 20, random.randint(0, HEIGHT)

def spawn_enemy_at_edge(base, kind):
    x, y = random_edge_position()
    enemies.append(
        Enemy(
            x,
            y,
            base["radius"],
            base["color"],
            base["hp"],
            base["speed"],
            base["reward"],
            kind
        )
    )

RED_BASE_TEMPLATE = {
    "color": RED,
    "radius": 18,
    "hp": 5,
    "speed": 1.0,
    "reward": 20
}
BLUE_BASE_TEMPLATE = {
    "color": BLUE,
    "radius": 26,
    "hp": 15,
    "speed": 0.5,
    "reward": 70
}
YELLOW_BASE_TEMPLATE = {
    "color": YELLOW,
    "radius": 18,
    "hp": 7,
    "speed": 3.0,
    "reward": 35
}
GREEN_BASE_TEMPLATE = {
    "color": GREEN,
    "radius": 20,
    "hp": 25,
    "speed": 0.5,
    "reward": 100
}
GREY_BASE_TEMPLATE = {
    "color": GREY,
    "radius": 22,
    "hp": 20,
    "speed": 0.4,
    "reward": 70
}
PURPLE_BASE_TEMPLATE = {
    "color": PURPLE,
    "radius": 18 * 1.5,
    "hp": 9999,
    "speed": 1.0 * 0.3 * 0.85,
    "reward": 150
}

def build_base(t):
    return {
        "color": t["color"],
        "radius": max(t["radius"] * 0.7, MIN_RADIUS),
        "hp": int(t["hp"] * hp_multiplier * post20_hp_mult + 0.5),
        "speed": t["speed"],
        "reward": t["reward"]
    }

reds_since_last_blue = 0
next_blue_after = random.randint(5, 8)
reds_since_last_yellow = 0
_base_y = random.randint(3, 6)
next_yellow_after = max(1, int(math.ceil(_base_y * YELLOW_INTERVAL_FACTOR)))

CLONE_EVENT = pygame.USEREVENT + 2
CLONE_INTERVAL = 1500
pygame.time.set_timer(CLONE_EVENT, CLONE_INTERVAL)

game_time = 0.0
current_level = 1
yellow_unlocked = False
green_unlocked = False
red_speedup_done = False

level_text_timer = 0.0
LEVEL_POPUP_DURATION = 1.0

def trigger_level_up():
    global current_level
    global level_text_timer
    global coin_multiplier
    global speed_level_factor
    global CLONE_INTERVAL
    global grey_purple_prob_multiplier
    global hp_multiplier
    global auto_level_enabled
    global next_auto_level_time
    global coins
    global PURPLE_HITS_FACTOR
    global auto_level_interval
    global density30_active
    global post20_hp_mult
    global post20_speed_mult
    global post20_spawn_mult
    global post20_coin_mult
    global spawn_base_interval_20plus
    global damage_shop_unlocked
    global damage_shop_hint_timer

    current_level += 1
    level_text_timer = LEVEL_POPUP_DURATION

    if current_level == 4:
        auto_level_enabled = True
        auto_level_interval = 20.0
        next_auto_level_time = game_time + auto_level_interval

    if current_level == 5:
        coin_multiplier *= 1.15

    if current_level == 7:
        speed_level_factor *= 1.20
        for e in enemies:
            if e.alive:
                e.speed *= 1.20

    if current_level == 10:
        CLONE_INTERVAL = int(CLONE_INTERVAL * 0.85)
        if CLONE_INTERVAL < 200:
            CLONE_INTERVAL = 200
        pygame.time.set_timer(CLONE_EVENT, CLONE_INTERVAL)

    if current_level == 13:
        density30_active = True

    if current_level == 16:
        speed_level_factor *= 1.15
        grey_purple_prob_multiplier *= 1.15
        for e in enemies:
            if e.alive:
                e.speed *= 1.15

    if current_level == 20:
        spawn_base_interval_20plus = CLONE_INTERVAL
        hp_multiplier *= 1.35
        PURPLE_HITS_FACTOR *= 1.35
        for e in enemies:
            if not e.alive:
                continue
            e.max_hp *= 1.35
            e.hp = max(1.0, e.hp * 1.35)
            if e.kind == "purple" and hasattr(e, "max_hits"):
                e.max_hits = max(1, int(e.max_hits * 1.35 + 0.5))

    if current_level > 10:
        coins += 500

    if current_level == 25:
        damage_shop_unlocked = True
        damage_shop_hint_timer = 7.0

    if current_level > 20:
        bonus_lv = current_level - 20

        new_hp_mult = 1.0 + min(0.1 * bonus_lv, 3.0)
        new_spd_mult = 1.0 + min(0.05 * bonus_lv, 1.5)
        new_spawn_mult = 1.0 + min(0.1 * bonus_lv, 3.0)
        new_coin_mult = 1.0 + min(0.05 * bonus_lv, 1.5)

        if new_hp_mult > post20_hp_mult:
            f = new_hp_mult / post20_hp_mult
            post20_hp_mult = new_hp_mult
            for e in enemies:
                if not e.alive:
                    continue
                e.max_hp *= f
                e.hp = max(1.0, e.hp * f)
                if e.kind == "purple" and hasattr(e, "max_hits"):
                    e.max_hits = max(1, int(e.max_hits * f + 0.5))

        if new_spd_mult > post20_speed_mult:
            f = new_spd_mult / post20_speed_mult
            post20_speed_mult = new_spd_mult
            for e in enemies:
                if e.alive and e.kind != "yellow":
                    e.speed *= f

        if spawn_base_interval_20plus is not None and new_spawn_mult != post20_spawn_mult:
            post20_spawn_mult = new_spawn_mult
            CLONE_INTERVAL = int(spawn_base_interval_20plus / post20_spawn_mult)
            if CLONE_INTERVAL < 80:
                CLONE_INTERVAL = 80
            pygame.time.set_timer(CLONE_EVENT, CLONE_INTERVAL)

        post20_coin_mult = new_coin_mult

def spawn_clone():
    global reds_since_last_blue
    global next_blue_after
    global reds_since_last_yellow
    global next_yellow_after
    global game_time

    elapsed = game_time

    if reds_since_last_blue >= next_blue_after:
        base = build_base(BLUE_BASE_TEMPLATE)
        kind = "blue"
        reds_since_last_blue = 0
        if elapsed >= 120:
            next_blue_after = random.randint(2, 3)
        elif elapsed >= 60:
            next_blue_after = random.randint(3, 5)
        else:
            next_blue_after = random.randint(5, 8)
    else:
        if yellow_unlocked and reds_since_last_yellow >= next_yellow_after:
            base = build_base(YELLOW_BASE_TEMPLATE)
            kind = "yellow"
            reds_since_last_yellow = 0
            if elapsed >= 120:
                _b = random.randint(2, 3)
            elif elapsed >= 60:
                _b = random.randint(2, 4)
            else:
                _b = random.randint(3, 6)
            next_yellow_after = max(1, int(math.ceil(_b * YELLOW_INTERVAL_FACTOR)))
        else:
            reds_since_last_blue += 1
            reds_since_last_yellow += 1
            base = build_base(RED_BASE_TEMPLATE)
            kind = "red"

            if green_unlocked:
                has_green = any(e.alive and e.kind == "green" for e in enemies)
                if elapsed >= 120:
                    bp = 0.45
                elif elapsed >= 60:
                    bp = 0.35
                else:
                    bp = 0.25
                if (not has_green) and random.random() < bp:
                    base = build_base(GREEN_BASE_TEMPLATE)
                    kind = "green"

            if elapsed >= 60 and kind == "red":
                r = random.random()
                grey_prob_base = 0.13
                purple_prob_base = 0.10
                grey_prob = grey_prob_base * grey_purple_prob_multiplier
                purple_prob = purple_prob_base * grey_purple_prob_multiplier
                has_purple = any(e.alive and e.kind == "purple" for e in enemies)
                if r < grey_prob:
                    base = build_base(GREY_BASE_TEMPLATE)
                    kind = "grey"
                elif (not has_purple) and r < grey_prob + purple_prob:
                    base = build_base(PURPLE_BASE_TEMPLATE)
                    kind = "purple"

    speed = base["speed"]
    if 40 <= elapsed < 60 and kind == "red":
        speed = base["speed"] * 1.15
    if elapsed >= 60 and kind != "grey":
        speed *= 1.1125
    speed *= 0.75
    speed *= 0.9
    if kind == "yellow":
        speed *= 0.85
    speed *= speed_level_factor
    if kind != "yellow":
        speed *= post20_speed_mult
    base["speed"] = speed

    if current_level >= 13 and kind == "red":
        choices = [BLUE_BASE_TEMPLATE]
        if green_unlocked:
            choices.append(GREEN_BASE_TEMPLATE)
        if yellow_unlocked:
            choices.append(YELLOW_BASE_TEMPLATE)
        tmpl = random.choice(choices)
        base = build_base(tmpl)
        if tmpl is BLUE_BASE_TEMPLATE:
            kind = "blue"
        elif tmpl is GREEN_BASE_TEMPLATE:
            kind = "green"
        else:
            kind = "yellow"
        speed = base["speed"]
        if elapsed >= 60 and kind != "grey":
            speed *= 1.1125
        speed *= 0.75
        speed *= 0.9
        if kind == "yellow":
            speed *= 0.85
        speed *= speed_level_factor
        if kind != "yellow":
            speed *= post20_speed_mult
        base["speed"] = speed

    spawn_enemy_at_edge(base, kind)

    if density30_active and kind not in ("grey", "purple"):
        if random.random() < 0.3:
            spawn_enemy_at_edge(base, kind)

berserk_active = False
berserk_timer = 0.0
BERSERK_COOLDOWN = 35.0
berserk_cd_timer = 0.0

def get_weapon_base_interval():
    if weapon_mode == "bullet":
        return bullet_interval_base_ms
    return int(bullet_interval_base_ms / 0.5)

def update_effective_bullet_stats():
    global bullet_radius
    global bullet_interval_ms
    base_interval = get_weapon_base_interval()
    if berserk_active:
        bullet_radius = bullet_radius_base * 1.7
        bullet_interval_ms = max(20, int(base_interval / 1.7))
    else:
        bullet_radius = bullet_radius_base
        bullet_interval_ms = base_interval
    pygame.time.set_timer(BULLET_EVENT, bullet_interval_ms)

size_level = 0
fire_level = 0
MAX_SIZE_LEVEL = 30
MAX_FIRE_LEVEL = 20
MAX_SIZE_MULT = 2.5 * 0.85

def recalc_bullet_radius_base():
    global bullet_radius_base
    mult = 1.0 + 0.05 * size_level
    if mult > MAX_SIZE_MULT:
        mult = MAX_SIZE_MULT
    bullet_radius_base = BASE_BULLET_RADIUS * mult
    update_effective_bullet_stats()

def recalc_bullet_interval_base():
    global bullet_interval_base_ms
    f = 1.0 - 0.05 * fire_level
    if f < 0.235:
        f = 0.235
    bullet_interval_base_ms = int(BASE_BULLET_INTERVAL * f)
    if bullet_interval_base_ms < 20:
        bullet_interval_base_ms = 20
    update_effective_bullet_stats()

def get_size_upgrade_cost(l):
    if l < 5:
        return price_disc(100)
    if l < 10:
        return price_disc(200)
    if l < 15:
        return price_disc(450)
    return price_disc(700)

def get_fire_upgrade_cost(l):
    if l < 5:
        return price_disc(200)
    if l < 10:
        return price_disc(350)
    if l < 15:
        return price_disc(600)
    return price_disc(900)

recalc_bullet_radius_base()
recalc_bullet_interval_base()

flash_timer = 0.0
freeze_timer = 0.0
w_unlocked = False
w_cd_timer = 0.0
W_SKILL_COST = price_disc(1200)

shop_open = False
help_open = False
help_scroll = 0.0

def homing_threshold():
    if homing_level >= 4:
        return 10
    if homing_level >= 3:
        return 11
    return 12

def homing_projectile_count():
    if homing_level <= 0:
        return 0
    return 3 + (homing_level - 1)

def acquire_nearest_enemy(pos):
    n = None
    best = float("inf")
    for e in enemies:
        if not e.alive:
            continue
        d2 = (e.pos.x - pos.x) ** 2 + (e.pos.y - pos.y) ** 2
        if d2 < best:
            best = d2
            n = e
    return n

def spawn_homing_barrage(c):
    if c <= 0:
        return
    alive = [e for e in enemies if e.alive]
    if not alive:
        return
    step = 2 * math.pi / c
    for i in range(c):
        a = step * i
        d = pygame.Vector2(math.cos(a), math.sin(a))
        bullets.append({
            "pos": PLAYER_POS.copy(),
            "vel": d * BULLET_SPEED,
            "radius": bullet_radius * 0.8,
            "damage": BASE_BULLET_DAMAGE,
            "homing": True,
            "target": alive[i % len(alive)],
            "homing_delay": 0.25,
            "source": "homing"
        })

def cannon_threshold():
    if cannon_level >= 3:
        return 7
    return 10

def get_cannon_positions():
    if not cannon_owned or cannon_level <= 0:
        return []
    n = cannon_level
    r = 40.0
    base_angle = game_time * 0.8
    lst = []
    for i in range(n):
        a = base_angle + 2 * math.pi * i / n
        lst.append(
            pygame.Vector2(
                PLAYER_POS.x + r * math.cos(a),
                PLAYER_POS.y + r * math.sin(a)
            )
        )
    return lst

def draw_cannons():
    if not cannon_owned or cannon_level <= 0:
        return
    r = int(PLAYER_RADIUS * 0.3)
    if r < 2:
        r = 2
    for pos in get_cannon_positions():
        pygame.draw.circle(
            screen,
            WHITE,
            (int(pos.x), int(pos.y)),
            r
        )

def add_laser_beam(start, end, width, color, duration=0.08):
    laser_beams.append({
        "start": start.copy(),
        "end": end.copy(),
        "width": width,
        "time": duration,
        "duration": duration,
        "color": color
    })

def fire_floating_cannons(main_damage):
    if weapon_mode != "laser":
        return
    if not cannon_owned or cannon_level <= 0:
        return
    pos_list = get_cannon_positions()
    if not pos_list:
        return
    dmg = main_damage
    for pos in pos_list:
        target = acquire_nearest_enemy(pos)
        if target is None:
            continue
        d = target.pos - pos
        if d.length() == 0:
            continue
        d = d.normalize()
        start = pos.copy()
        end = pos + d * LASER_MAX_RANGE
        w = bullet_radius * 1.2
        hit = []
        for e in enemies:
            if not e.alive:
                continue
            if e.kind == "grey" and e.shield_timer > 0:
                continue
            if e.kind == "purple" and getattr(e, "phase", None) == "attached":
                continue
            ap = e.pos - start
            ab = end - start
            ab2 = ab.x * ab.x + ab.y * ab.y
            if ab2 == 0:
                continue
            t = max(0, min(1, (ap.x * ab.x + ap.y * ab.y) / ab2))
            cp = start + ab * t
            if e.pos.distance_to(cp) <= e.radius + w / 2:
                hit.append(e)
        for e in hit:
            apply_damage(e, dmg)
        if hit:
            add_laser_beam(start, end, w, CANNON_LASER_COLOR, 0.08)

def on_main_hits(hit_count):
    global cannon_hit_counter
    if weapon_mode != "laser":
        return
    if not cannon_owned or cannon_level <= 0:
        return
    if hit_count <= 0:
        return
    cannon_hit_counter += hit_count
    thr = cannon_threshold()
    while cannon_hit_counter >= thr:
        cannon_hit_counter -= thr
        fire_floating_cannons(BASE_LASER_DAMAGE)

def shoot_bullet():
    mx, my = pygame.mouse.get_pos()
    d = pygame.Vector2(mx, my) - PLAYER_POS
    if d.length() == 0:
        return
    d = d.normalize()
    bullets.append({
        "pos": PLAYER_POS.copy(),
        "vel": d * BULLET_SPEED,
        "radius": bullet_radius,
        "damage": BASE_BULLET_DAMAGE,
        "homing": False,
        "target": None,
        "homing_delay": 0.0,
        "source": "main"
    })
    if berserk_active:
        ang = 20
        for dd in (d.rotate(ang), d.rotate(-ang)):
            bullets.append({
                "pos": PLAYER_POS.copy(),
                "vel": dd * (BULLET_SPEED * 0.5),
                "radius": bullet_radius * 0.5,
                "damage": BASE_BULLET_DAMAGE,
                "homing": False,
                "target": None,
                "homing_delay": 0.0,
                "source": "side"
            })

def shoot_laser():
    mx, my = pygame.mouse.get_pos()
    d = pygame.Vector2(mx, my) - PLAYER_POS
    if d.length() == 0:
        return
    d = d.normalize()
    start = PLAYER_POS.copy()
    end = PLAYER_POS + d * LASER_MAX_RANGE
    hits = []
    w = bullet_radius * 1.5
    dmg = BASE_LASER_DAMAGE
    for e in enemies:
        if not e.alive:
            continue
        if e.kind == "grey" and e.shield_timer > 0:
            continue
        if e.kind == "purple" and getattr(e, "phase", None) == "attached":
            continue
        ap = e.pos - start
        ab = end - start
        ab2 = ab.x * ab.x + ab.y * ab.y
        if ab2 == 0:
            continue
        t = max(0, min(1, (ap.x * ab.x + ap.y * ab.y) / ab2))
        cp = start + ab * t
        if e.pos.distance_to(cp) <= e.radius + w / 2:
            hits.append(e)
    hit_count = 0
    for e in hits:
        apply_damage(e, dmg)
        hit_count += 1
    if hit_count > 0:
        register_homing_hits(hit_count)
        on_main_hits(hit_count)
    add_laser_beam(start, end, w, LASER_COLOR)
    if berserk_active and hits:
        chain_dmg = dmg * 0.4
        for e in hits:
            cand = [
                x for x in enemies
                if x.alive
                and x is not e
                and not (x.kind == "grey" and x.shield_timer > 0)
                and not (x.kind == "purple" and getattr(x, "phase", None) == "attached")
            ]
            cand.sort(key=lambda x: x.pos.distance_to(e.pos))
            count = 0
            for t in cand:
                apply_damage(t, chain_dmg)
                add_laser_beam(e.pos, t.pos, w * 0.8, LASER_COLOR)
                count += 1
                if count >= 2:
                    break

def update_bullets(dt):
    global bullets
    new_list = []
    for b in bullets:
        if b.get("homing", False):
            if b["homing_delay"] > 0:
                b["homing_delay"] -= dt
                if b["homing_delay"] < 0:
                    b["homing_delay"] = 0
            if b["homing_delay"] == 0:
                t = b.get("target")
                if t is None or (not t.alive):
                    t = acquire_nearest_enemy(b["pos"])
                    b["target"] = t
                if t is not None and t.alive:
                    d = t.pos - b["pos"]
                    if d.length() != 0:
                        d = d.normalize()
                        b["vel"] = d * HOMING_SPEED
        b["pos"] += b["vel"]
        if (
            b["pos"].x < -20
            or b["pos"].x > WIDTH + 20
            or b["pos"].y < -20
            or b["pos"].y > HEIGHT + 20
        ):
            continue
        blocked = False
        for e in enemies:
            if not e.alive:
                continue
            if e.kind == "purple" and getattr(e, "phase", None) == "attached":
                continue
            if b["pos"].distance_to(e.pos) <= e.radius + b["radius"]:
                if e.kind == "grey" and e.shield_timer > 0:
                    blocked = True
                    break
                dmg = b.get("damage", BASE_BULLET_DAMAGE)
                apply_damage(e, dmg)
                if b.get("source") == "main":
                    register_homing_hits(1)
                    on_main_hits(1)
                blocked = True
                break
        if not blocked:
            new_list.append(b)
    bullets = new_list

def draw_bullets():
    for b in bullets:
        c = HOMING_GREEN if b.get("homing", False) else WHITE
        pygame.draw.circle(
            screen,
            c,
            (int(b["pos"].x), int(b["pos"].y)),
            int(b["radius"])
        )

def update_lasers(dt):
    global laser_beams
    new_list = []
    for beam in laser_beams:
        beam["time"] -= dt
        if beam["time"] > 0:
            new_list.append(beam)
    laser_beams = new_list

def draw_lasers():
    for beam in laser_beams:
        t = beam["time"] / beam["duration"]
        alpha = int(255 * t)
        if alpha < 0:
            alpha = 0
        c = beam["color"]
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(
            surf,
            (c[0], c[1], c[2], alpha),
            (int(beam["start"].x), int(beam["start"].y)),
            (int(beam["end"].x), int(beam["end"].y)),
            max(1, int(beam["width"]))
        )
        screen.blit(surf, (0, 0))

def update_explosions(dt):
    global explosions
    new_list = []
    for ex in explosions:
        ex["time"] -= dt
        if ex["time"] <= 0:
            continue
        t = ex["time"]
        d = ex["duration"]
        ex["cur_r"] = ex["min_r"] + (ex["max_r"] - ex["min_r"]) * ((d - t) / d)
        new_list.append(ex)
    explosions = new_list

def draw_explosions():
    for ex in explosions:
        t = ex["time"]
        d = ex["duration"]
        alpha = int(200 * (t / d))
        if alpha < 0:
            alpha = 0
        r = int(ex.get("cur_r", ex["max_r"]))
        surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(
            surf,
            (180, 220, 255, alpha),
            (int(ex["pos"].x), int(ex["pos"].y)),
            r,
            2
        )
        screen.blit(surf, (0, 0))

def draw_ui():
    elapsed = game_time
    sps = 1000.0 / bullet_interval_ms if bullet_interval_ms > 0 else 0.0
    time_text = font.render(f"Time: {elapsed:.1f}s", True, WHITE)
    coin_text = font.render(f"Coins: {coins}", True, WHITE)
    lv_text = font.render(
        f"Size Lv(A): {size_level}/{MAX_SIZE_LEVEL}   Fire Lv(D): {fire_level}/{MAX_FIRE_LEVEL}",
        True,
        WHITE
    )
    speed_text = font.render(f"bullet speed: {sps:.2f} /s", True, WHITE)
    weapon_str = "Bullet" if weapon_mode == "bullet" else "Laser"
    weapon_text = font.render(f"Weapon: {weapon_str}  (R to switch)", True, WHITE)
    screen.blit(time_text, (10, 10))
    screen.blit(coin_text, (10, 35))
    screen.blit(lv_text, (10, 60))
    screen.blit(speed_text, (10, 85))
    screen.blit(weapon_text, (10, 110))

    hp_factor = hp_multiplier * post20_hp_mult
    spd_factor = speed_level_factor * post20_speed_mult
    spawn_factor = 1500.0 / CLONE_INTERVAL if CLONE_INTERVAL > 0 else 0.0
    status_text = font.render(
        f"HP x{hp_factor:.2f}  SPD x{spd_factor:.2f}  SPAWN x{spawn_factor:.2f}",
        True,
        WHITE
    )
    rect = status_text.get_rect()
    rect.top = 10
    rect.centerx = int(WIDTH * 0.68)
    screen.blit(status_text, rect)

    hint1 = "E: Shop   P: Info   S: Berserk 700g 35s CD"
    hint1_text = font.render(hint1, True, WHITE)
    screen.blit(hint1_text, (10, 135))

    extras = []
    if w_unlocked:
        extras.append("W: Freeze 5s 40s CD")
    if homing_owned and homing_level > 0:
        extras.append(f"Homing Lv{homing_level}")
    if cannon_owned and cannon_level > 0:
        extras.append(f"Cannons Lv{cannon_level}")
    if laser_unlocked:
        extras.append("Laser Cannon (R to use)")
    if extras:
        hint2 = " | ".join(extras)
        hint2_text = font.render(hint2, True, WHITE)
        screen.blit(hint2_text, (10, 160))

    lv_text = font.render(f"Lv.{current_level}", True, WHITE)
    screen.blit(lv_text, (WIDTH - 80, 10))

    y = 185
    if berserk_active:
        b_text = font.render(f"Berserk: {berserk_timer:.1f}s", True, YELLOW)
        screen.blit(b_text, (10, y))
        y += 25
    elif berserk_cd_timer > 0:
        cd_text = font.render(f"Berserk CD: {berserk_cd_timer:.1f}s", True, YELLOW)
        screen.blit(cd_text, (10, y))
        y += 25

    if w_unlocked and w_cd_timer > 0:
        w_text = font.render(f"W CD: {w_cd_timer:.1f}s", True, BLUE)
        screen.blit(w_text, (10, y))
        y += 25

    if damage_shop_unlocked and damage_shop_hint_timer > 0:
        msg = "Lv25 Special Shop unlocked: Press E then X to buy +10% damage."
        h = font.render(msg, True, YELLOW)
        hr = h.get_rect()
        hr.midbottom = (WIDTH // 2, HEIGHT - 10)
        screen.blit(h, hr)

def draw_level_overlay():
    if level_text_timer <= 0:
        return
    alpha = int(255 * (level_text_timer / LEVEL_POPUP_DURATION))
    if alpha < 0:
        alpha = 0
    surf = level_popup_font.render(f"Lv.{current_level}", True, WHITE)
    surf.set_alpha(alpha)
    x = WIDTH - surf.get_width() - 20
    y = 40
    screen.blit(surf, (x, y))

def draw_flash_overlay():
    if flash_timer <= 0:
        return
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((80, 80, 255, 180))
    screen.blit(overlay, (0, 0))

def draw_shop():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    panel_width, panel_height = 640, 460
    panel_x = (WIDTH - panel_width) // 2
    panel_y = (HEIGHT - panel_height) // 2

    pygame.draw.rect(screen, (60, 60, 60), (panel_x, panel_y, panel_width, panel_height))
    pygame.draw.rect(screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 2)

    title = level_font.render("SHOP", True, WHITE)
    screen.blit(
        title,
        (panel_x + panel_width // 2 - title.get_width() // 2, panel_y + 10)
    )

    y = panel_y + 80
    screen.blit(font.render(f"Coins: {coins}", True, WHITE), (panel_x + 30, y))
    y += 35

    if size_level < MAX_SIZE_LEVEL:
        a_cost = get_size_upgrade_cost(size_level)
        a_line = f"A: +5% bullet size (Lv {size_level}->{size_level+1}, Cost {a_cost})"
    else:
        a_line = f"A: bullet size (MAX Lv {MAX_SIZE_LEVEL})"

    if fire_level < MAX_FIRE_LEVEL:
        d_cost = get_fire_upgrade_cost(fire_level)
        d_line = f"D: +5% fire rate  (Lv {fire_level}->{fire_level+1}, Cost {d_cost})"
    else:
        d_line = f"D: fire rate  (MAX Lv {MAX_FIRE_LEVEL})"

    screen.blit(
        font.render(a_line, True, INFO_COLOR_WEAPON),
        (panel_x + 30, y)
    )
    y += 30
    screen.blit(
        font.render(d_line, True, INFO_COLOR_WEAPON),
        (panel_x + 30, y)
    )
    y += 35

    if not w_unlocked:
        w_line = f"W: Buy Freeze (Cost {W_SKILL_COST}, 5s freeze, 40s CD)"
    else:
        w_line = "W: Freeze Owned (use free, 40s CD)"
    screen.blit(font.render(w_line, True, BLUE), (panel_x + 30, y))
    y += 30

    if weapon_mode == "bullet":
        if not homing_owned:
            h_line = (
                f"F: Buy Homing Barrage "
                f"(Cost {HOMING_BUY_COST}, main 12 hits -> 3 homing)"
            )
        else:
            if homing_level < 4:
                up_cost = HOMING_UPGRADE_COSTS[homing_level - 1]
                h_line = (
                    f"F: Upgrade Homing Lv{homing_level}->"
                    f"{homing_level+1} (Cost {up_cost})"
                )
            else:
                h_line = f"F: Homing Barrage Lv{homing_level} (MAX)"
        screen.blit(
            font.render(h_line, True, INFO_COLOR_HOMING),
            (panel_x + 30, y)
        )
        y += 30

        if not laser_unlocked:
            l_line = (
                f"L: Buy Laser Cannon "
                f"(Cost {LASER_BUY_COST}, 2.5x dmg, 50% ROF)"
            )
        else:
            l_line = "L: Laser Cannon owned (Press R in game to switch)"
        screen.blit(
            font.render(l_line, True, LASER_COLOR),
            (panel_x + 30, y)
        )
        y += 30
    else:
        if not cannon_owned:
            c_line = (
                f"G: Buy Floating Cannons "
                f"(Cost {CANNON_BUY_COST}, 1 cannon)"
            )
        else:
            if cannon_level < 4:
                up_cost = CANNON_UPGRADE_COSTS[cannon_level - 1]
                c_line = (
                    f"G: Upgrade Cannons Lv{cannon_level}->"
                    f"{cannon_level+1} (Cost {up_cost})"
                )
            else:
                c_line = f"G: Floating Cannons Lv{cannon_level} (MAX)"
        screen.blit(
            font.render(c_line, True, INFO_COLOR_CANNON),
            (panel_x + 30, y)
        )
        y += 30

        if laser_unlocked:
            l_line = "L: Laser Cannon already owned."
        else:
            l_line = f"L: Buy Laser Cannon (Cost {LASER_BUY_COST})"
        screen.blit(
            font.render(l_line, True, LASER_COLOR),
            (panel_x + 30, y)
        )
        y += 30

    if damage_shop_unlocked:
        if damage_level < DMG_MAX_LEVEL:
            next_mult = DAMAGE_BASE_MULT + DAMAGE_PER_LEVEL * (damage_level + 1)
            cost_show = price_disc(damage_upgrade_cost)
            dmg_line = (
                f"X: +10% global damage (Lv {damage_level}->{damage_level+1}, "
                f"x{damage_multiplier:.2f} -> x{next_mult:.2f}, Cost {cost_show})"
            )
        else:
            dmg_line = (
                f"X: Damage bonus MAX (Lv {damage_level}/{DMG_MAX_LEVEL}, "
                f"x{damage_multiplier:.2f})"
            )
        screen.blit(font.render(dmg_line, True, YELLOW), (panel_x + 30, y))
        y += 30

    y += 10
    tip1 = "In shop: A/D/W plus F (bullet-only) or G (laser-only)."
    tip2 = "Prices shown are discounted; 'base' in Info means original price."
    tip3 = "Press E or ESC to close. In game: R switch weapon, N restart."
    screen.blit(font.render(tip1, True, INFO_COLOR_SHOP), (panel_x + 30, y))
    y += 25
    screen.blit(font.render(tip2, True, INFO_COLOR_SHOP), (panel_x + 30, y))
    y += 25
    screen.blit(font.render(tip3, True, INFO_COLOR_SHOP), (panel_x + 30, y))

def draw_help():
    global help_scroll

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))

    panel_width, panel_height = 720, 560
    panel_x = (WIDTH - panel_width) // 2
    panel_y = (HEIGHT - panel_height) // 2

    pygame.draw.rect(screen, (40, 40, 40), (panel_x, panel_y, panel_width, panel_height))
    pygame.draw.rect(screen, WHITE, (panel_x, panel_y, panel_width, panel_height), 2)

    title = level_font.render("INFO", True, WHITE)
    screen.blit(
        title,
        (panel_x + panel_width // 2 - title.get_width() // 2, panel_y + 10)
    )

    lines = []

    c = INFO_COLOR_CTRL
    lines.append(("Controls:", c))
    lines.append(("  - Mouse: aim", c))
    lines.append(("  - S: Berserk (700g, 10s, 35s CD)", c))
    lines.append(("  - W: Freeze (after buy, 5s freeze, 40s CD)", c))
    lines.append(("  - E: Shop   | P: Info   | N: Restart", c))
    lines.append(("  - R: Switch weapon (Bullet / Laser, if Laser owned)", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_WEAPON
    lines.append(("Weapons:", c))
    lines.append(("  - Bullet: normal projectiles, affected by size/fire upgrades.", c))
    lines.append(("  - Laser Cannon (L in bullet-shop, 5000g base):", c))
    lines.append(("      2.5x damage, 50% of bullet fire rate (slower).", c))
    lines.append(("      Fixed beam length, hits all enemies along the line.", c))
    lines.append(("      In Berserk: beams chain to up to 2 nearest enemies", c))
    lines.append(("         regardless of distance (cannot chain to itself).", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_HOMING
    lines.append(("Homing Barrage (F in shop, BULLET ONLY):", c))
    lines.append(("  - Lv1 (2000g base): every 12 valid MAIN hits -> 3 homing shots.", c))
    lines.append(("  - Lv2 (+3000 base): every 12 hits -> 4 shots.", c))
    lines.append(("  - Lv3 (+4500 base): every 11 hits -> 5 shots.", c))
    lines.append(("  - Lv4 (+6500 base): every 10 hits -> 6 shots.", c))
    lines.append(("  - Only MAIN bullets/lasers count hits.", c))
    lines.append(("      (no count for side shots, homing bullets, cannon lasers,", c))
    lines.append(("       explosions, or berserk chain beams).", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_CANNON
    lines.append(("Floating Cannons (G in shop, LASER ONLY):", c))
    lines.append(("  - Buy (7500g base) to get 1 white orbiting cannon around player.", c))
    lines.append(("  - Up to Lv4 (10000/15000/20000 base) => up to 4 cannons.", c))
    lines.append(("  - Cannons are white disks (30% of player radius).", c))
    lines.append(("  - Only after MAIN hits reach threshold (10 hits, Lv3+ 7 hits)", c))
    lines.append(("      they fire bright green laser beams (fixed range).", c))
    lines.append(("  - Cannon laser damage = 100% of main laser damage.", c))
    lines.append(("  - Cannon hits do NOT count toward homing triggers.", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_ENEMY
    lines.append(("Enemies:", c))
    lines.append(("  - Red: 5 HP, base speed 1.0, 20 coins.", c))
    lines.append(("  - Blue: 15 HP, slower, 70 coins.", c))
    lines.append(("  - Yellow: 7 HP, very fast, 35 coins,", c))
    lines.append(("      spawn chance -25% and 15% slower than before.", c))
    lines.append(("  - Green: 25 HP, slow, teleports every 3s, 100 coins.", c))
    lines.append(("  - Grey: 20 HP, speed 0.4, 7s shield on spawn, then explodes", c))
    lines.append(("          dealing 7-hit damage in an area (no homing count).", c))
    lines.append(("  - Purple: grows by hits. At max size attaches to a random enemy.", c))
    lines.append(("      If host dies within 5s -> purple dies; else revives smaller,", c))
    lines.append(("      with +40% HP and 3s shield (then behaves like a normal enemy).", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_LEVEL
    lines.append(("Level effects (key):", c))
    lines.append(("  - Lv4: auto-level starts (20s interval).", c))
    lines.append(("  - Lv5: +15% coin gain.", c))
    lines.append(("  - Lv7: enemies +20% speed, auto-level interval 13s (Lv7~20).", c))
    lines.append(("  - Lv10: spawn rate +15%, and each level above 10 gives +500 coins.", c))
    lines.append(("  - Lv13: reds become blue/green/yellow; non-grey/purple spawn", c))
    lines.append(("          density +30%.", c))
    lines.append(("  - Lv16: enemies +15% speed, grey & purple spawn chance +15%.", c))
    lines.append(("  - Lv20: all HP +35% (purple hit cap +35%).", c))
    lines.append(("  - After Lv20 (based on base stats):", c))
    lines.append(("      * each level adds +10% HP (up to +300% total => 4x HP),", c))
    lines.append(("      * +5% enemy speed (up to +150% total => 2.5x speed),", c))
    lines.append(("      * +10% spawn density (up to +300% total => 4x spawn),", c))
    lines.append(("      * +5% kill coin reward (up to +150% total => 2.5x coins),", c))
    lines.append(("      * yellow enemies are NOT affected by this post-20 speed bonus.", c))
    lines.append(("      * auto-level interval becomes 10s.", c))
    lines.append(("", WHITE))

    c = INFO_COLOR_SHOP
    lines.append(("Shop items:", c))
    lines.append(("  - A/D: bullet size / fire rate (affects both Bullet & Laser).", c))
    lines.append(("  - W: Freeze skill (1200g base, 5s stop enemies, 40s CD).", c))
    lines.append(("  - F: Homing Barrage (Bullet-only, main hits only).", c))
    lines.append(("  - G: Floating Cannons (Laser-only, green laser beams).", c))
    lines.append(("  - L: Laser Cannon (buy in Bullet shop, then R to switch).", c))
    lines.append(("  - Lv25+: X: +10% global damage per purchase", c))
    lines.append(("           (based on base damage, up to +200% => 3x total,", c))
    lines.append(("            cost 8000 base then +800 base each time,", c))
    lines.append(("            up to 20 purchases).", c))
    lines.append(("  - Prices in game are discounted; values marked 'base' are original prices.", c))
    lines.append(("", WHITE))
    lines.append(("Use UP/DOWN or mouse wheel to scroll. Press P/E/ESC to close.", c))

    inner_top = panel_y + 70
    inner_bottom = panel_y + panel_height - 20
    visible_height = inner_bottom - inner_top
    line_height = 22
    content_height = len(lines) * line_height
    max_scroll = max(0, content_height - visible_height)

    if help_scroll < 0:
        help_scroll = 0
    if help_scroll > max_scroll:
        help_scroll = max_scroll

    for i, (line, color) in enumerate(lines):
        y = inner_top + i * line_height - help_scroll
        if y + line_height < inner_top or y > inner_bottom:
            continue
        t = font.render(line, True, color)
        screen.blit(t, (panel_x + 20, y))

running = True

while running:
    dt_ms = clock.tick(FPS)
    dt = dt_ms / 1000.0

    paused = shop_open or help_open

    if not paused:
        game_time += dt

    elapsed = game_time

    if (not yellow_unlocked) and elapsed >= 20:
        yellow_unlocked = True
        trigger_level_up()

    if (not green_unlocked) and elapsed >= 40:
        green_unlocked = True
        trigger_level_up()

    if (not red_speedup_done) and elapsed >= 90:
        red_speedup_done = True
        CLONE_INTERVAL = int(CLONE_INTERVAL * 0.7)
        if CLONE_INTERVAL < 300:
            CLONE_INTERVAL = 300
        pygame.time.set_timer(CLONE_EVENT, CLONE_INTERVAL)
        trigger_level_up()

    if auto_level_enabled and (not paused):
        if current_level >= 21:
            desired = 10.0
        elif current_level >= 7:
            desired = 13.0
        else:
            desired = 20.0
        if auto_level_interval != desired:
            auto_level_interval = desired
            next_auto_level_time = game_time + auto_level_interval
        while next_auto_level_time is not None and game_time >= next_auto_level_time:
            trigger_level_up()
            next_auto_level_time += auto_level_interval

    if not paused:
        if level_text_timer > 0:
            level_text_timer -= dt
        if berserk_active:
            berserk_timer -= dt
            if berserk_timer <= 0:
                berserk_active = False
                berserk_timer = 0.0
                update_effective_bullet_stats()
        if berserk_cd_timer > 0:
            berserk_cd_timer -= dt
            if berserk_cd_timer < 0:
                berserk_cd_timer = 0.0
        if w_cd_timer > 0:
            w_cd_timer -= dt
            if w_cd_timer < 0:
                w_cd_timer = 0.0
        if damage_shop_hint_timer > 0:
            damage_shop_hint_timer -= dt
            if damage_shop_hint_timer < 0:
                damage_shop_hint_timer = 0.0

    if not (shop_open or help_open):
        if flash_timer > 0:
            flash_timer -= dt
            if flash_timer < 0:
                flash_timer = 0.0
        if freeze_timer > 0:
            freeze_timer -= dt
            if freeze_timer < 0:
                freeze_timer = 0.0
        update_explosions(dt)
        update_lasers(dt)

    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

        if ev.type == pygame.MOUSEWHEEL and help_open:
            help_scroll -= ev.y * 30

        if ev.type == BULLET_EVENT and (not shop_open) and (not help_open):
            if weapon_mode == "bullet":
                shoot_bullet()
            else:
                shoot_laser()

        if ev.type == CLONE_EVENT and (not shop_open) and (not help_open):
            spawn_clone()

        if ev.type == pygame.KEYDOWN:
            k = ev.key

            if k == pygame.K_e:
                shop_open = not shop_open
                if shop_open:
                    help_open = False

            if k == pygame.K_p:
                help_open = not help_open
                if help_open:
                    shop_open = False

            if help_open:
                if k == pygame.K_UP:
                    help_scroll -= 30
                elif k == pygame.K_DOWN:
                    help_scroll += 30

            if k == pygame.K_n:
                bullets.clear()
                enemies.clear()
                explosions.clear()
                laser_beams.clear()

                game_time = 0.0
                coins = 0

                size_level = 0
                fire_level = 0

                PLAYER_RADIUS = PLAYER_BASE_RADIUS * 0.56

                bullet_radius_base = BASE_BULLET_RADIUS
                bullet_interval_base_ms = BASE_BULLET_INTERVAL

                berserk_active = False
                berserk_timer = 0.0
                berserk_cd_timer = 0.0

                recalc_bullet_radius_base()
                recalc_bullet_interval_base()

                w_unlocked = False
                w_cd_timer = 0.0

                laser_unlocked = False
                weapon_mode = "bullet"

                cannon_owned = False
                cannon_level = 0
                cannon_hit_counter = 0

                homing_owned = False
                homing_level = 0
                homing_hit_counter = 0

                flash_timer = 0.0
                freeze_timer = 0.0

                reds_since_last_blue = 0
                next_blue_after = random.randint(5, 8)
                reds_since_last_yellow = 0
                _base_y = random.randint(3, 6)
                next_yellow_after = max(
                    1,
                    int(math.ceil(_base_y * YELLOW_INTERVAL_FACTOR))
                )

                CLONE_EVENT = pygame.USEREVENT + 2
                CLONE_INTERVAL = 1500
                pygame.time.set_timer(CLONE_EVENT, CLONE_INTERVAL)

                yellow_unlocked = False
                green_unlocked = False
                red_speedup_done = False
                current_level = 1
                level_text_timer = 0.0

                coin_multiplier = 1.0
                speed_level_factor = 1.0
                grey_purple_prob_multiplier = 1.0
                hp_multiplier = 1.0
                PURPLE_HITS_FACTOR = 1.0

                post20_hp_mult = 1.0
                post20_spawn_mult = 1.0
                post20_speed_mult = 1.0
                post20_coin_mult = 1.0

                spawn_base_interval_20plus = None

                auto_level_enabled = False
                auto_level_interval = 20.0
                next_auto_level_time = None

                density30_active = False

                damage_level = 0
                damage_multiplier = DAMAGE_BASE_MULT + DAMAGE_PER_LEVEL * damage_level
                damage_upgrade_cost = DAMAGE_BASE_COST
                damage_shop_unlocked = False
                damage_shop_hint_timer = 0.0

                shop_open = False
                help_open = False
                help_scroll = 0.0

                update_effective_bullet_stats()
                continue

            if shop_open:
                if k == pygame.K_a and size_level < MAX_SIZE_LEVEL:
                    c = get_size_upgrade_cost(size_level)
                    if coins >= c:
                        coins -= c
                        size_level += 1
                        recalc_bullet_radius_base()
                elif k == pygame.K_d and fire_level < MAX_FIRE_LEVEL:
                    c = get_fire_upgrade_cost(fire_level)
                    if coins >= c:
                        coins -= c
                        fire_level += 1
                        recalc_bullet_interval_base()
                elif k == pygame.K_w:
                    if (not w_unlocked) and coins >= W_SKILL_COST:
                        coins -= W_SKILL_COST
                        w_unlocked = True
                elif k == pygame.K_f and weapon_mode == "bullet":
                    if not homing_owned:
                        if coins >= HOMING_BUY_COST:
                            coins -= HOMING_BUY_COST
                            homing_owned = True
                            homing_level = 1
                    else:
                        if homing_level < 4:
                            up = HOMING_UPGRADE_COSTS[homing_level - 1]
                            if coins >= up:
                                coins -= up
                                homing_level += 1
                elif k == pygame.K_g and weapon_mode == "laser":
                    if not cannon_owned:
                        if coins >= CANNON_BUY_COST:
                            coins -= CANNON_BUY_COST
                            cannon_owned = True
                            cannon_level = 1
                    else:
                        if cannon_level < 4:
                            up = CANNON_UPGRADE_COSTS[cannon_level - 1]
                            if coins >= up:
                                coins -= up
                                cannon_level += 1
                elif k == pygame.K_l and weapon_mode == "bullet":
                    if (not laser_unlocked) and coins >= LASER_BUY_COST:
                        coins -= LASER_BUY_COST
                        laser_unlocked = True
                elif k == pygame.K_x and damage_shop_unlocked and damage_level < DMG_MAX_LEVEL:
                    cost_disc = price_disc(damage_upgrade_cost)
                    if coins >= cost_disc:
                        coins -= cost_disc
                        damage_level += 1
                        damage_multiplier = DAMAGE_BASE_MULT + DAMAGE_PER_LEVEL * damage_level
                        damage_upgrade_cost = DAMAGE_BASE_COST + DAMAGE_COST_STEP * damage_level
                elif k == pygame.K_ESCAPE:
                    shop_open = False
                continue

            if help_open:
                if k == pygame.K_ESCAPE:
                    help_open = False
                continue

            if k == pygame.K_r and laser_unlocked:
                if weapon_mode == "bullet":
                    weapon_mode = "laser"
                else:
                    weapon_mode = "bullet"
                update_effective_bullet_stats()

            if k == pygame.K_s:
                if (not berserk_active) and berserk_cd_timer <= 0 and coins >= 700:
                    coins -= 700
                    berserk_active = True
                    berserk_timer = 10.0
                    berserk_cd_timer = 35.0
                    update_effective_bullet_stats()

            if k == pygame.K_w:
                if w_unlocked and w_cd_timer <= 0:
                    flash_timer = 0.4
                    freeze_timer = 5.0
                    w_cd_timer = 40.0

    if not (shop_open or help_open):
        if freeze_timer <= 0:
            for en in enemies:
                en.update(dt)
        update_bullets(dt)

    screen.fill((30, 30, 30))

    pygame.draw.circle(screen, WHITE, PLAYER_POS, int(PLAYER_RADIUS))

    for en in enemies:
        en.draw(screen)

    draw_cannons()
    draw_bullets()
    draw_explosions()
    draw_lasers()
    draw_flash_overlay()
    draw_ui()
    draw_level_overlay()

    if shop_open:
        draw_shop()

    if help_open:
        draw_help()

    pygame.display.flip()

pygame.quit()
sys.exit()
