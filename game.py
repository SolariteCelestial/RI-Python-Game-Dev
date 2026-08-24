import os
import sys
import pygame
import math
import random

# ── Headless / Codespaces environment fixes ───────────────────────────────────
if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":99"
if not os.environ.get("XDG_RUNTIME_DIR"):
    os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-vscode"
    os.makedirs("/tmp/runtime-vscode", exist_ok=True)
os.environ["SDL_AUDIODRIVER"] = "dummy"

# ─────────────────────────────────────────
#  INITIALISE pygame
# ─────────────────────────────────────────
pygame.init()

SCREEN_WIDTH  = 640
SCREEN_HEIGHT = 480
TITLE         = "Top-Down Cube Knight"
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()
FPS = 60

# ─────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────
BLACK  = ( 15,  15,  20)
WHITE  = (240, 240, 240)
GRAY   = ( 40,  40,  40)
RED    = (220,  50,  50)
ORANGE = (255, 150,  50)
CYAN   = (150, 255, 255)
YELLOW = (255, 255, 100)

# ─────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────
PLAYER_SPEED = 5
FRICTION = 0.8
ENEMY_SPEED = 2
MAX_ENEMIES = 6

# ─────────────────────────────────────────
#  CLASSES
# ─────────────────────────────────────────
class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.vel_x = 0
        self.vel_y = 0
        self.facing = 'RIGHT' # 'UP', 'DOWN', 'LEFT', 'RIGHT'
        
        # Combat
        self.hp = 5
        self.invuln_timer = 0
        self.attack_timer = 0
        self.attack_cooldown = 0
        self.attack_rect = None
        self.recoil_timer = 0

    def update(self, keys):
        # 1. Handle Movement (Input vs Recoil)
        if self.recoil_timer > 0:
            self.recoil_timer -= 1
            self.vel_x *= FRICTION
            self.vel_y *= FRICTION
        else:
            self.vel_x = 0
            self.vel_y = 0
            
            # 4-Way Movement
            if keys[pygame.K_LEFT]:
                self.vel_x = -PLAYER_SPEED
                self.facing = 'LEFT'
            elif keys[pygame.K_RIGHT]:
                self.vel_x = PLAYER_SPEED
                self.facing = 'RIGHT'
            if keys[pygame.K_UP]:
                self.vel_y = -PLAYER_SPEED
                self.facing = 'UP'
            elif keys[pygame.K_DOWN]:
                self.vel_y = PLAYER_SPEED
                self.facing = 'DOWN'

        self.rect.x += self.vel_x
        self.rect.y += self.vel_y

        # Screen bounds
        self.rect.clamp_ip(screen.get_rect())

        # 2. Attack Timers & Hitbox positioning
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            
        if self.attack_timer > 0:
            self.attack_timer -= 1
            # Position hitbox based on facing direction
            if self.facing == 'RIGHT':
                self.attack_rect = pygame.Rect(self.rect.right, self.rect.y - 15, 45, 60)
            elif self.facing == 'LEFT':
                self.attack_rect = pygame.Rect(self.rect.left - 45, self.rect.y - 15, 45, 60)
            elif self.facing == 'UP':
                self.attack_rect = pygame.Rect(self.rect.x - 15, self.rect.top - 45, 60, 45)
            elif self.facing == 'DOWN':
                self.attack_rect = pygame.Rect(self.rect.x - 15, self.rect.bottom, 60, 45)
        else:
            self.attack_rect = None

        if self.invuln_timer > 0:
            self.invuln_timer -= 1

    def attack(self):
        if self.attack_cooldown == 0 and self.attack_timer == 0:
            self.attack_timer = 10     
            self.attack_cooldown = 20  

    def take_damage(self, amount, knock_dx, knock_dy):
        if self.invuln_timer == 0:
            self.hp -= amount
            self.invuln_timer = 60 # 1 second of i-frames
            self.vel_x = knock_dx * 8
            self.vel_y = knock_dy * 8
            self.recoil_timer = 15

    def draw(self, surface):
        if self.invuln_timer > 0 and (self.invuln_timer // 4) % 2 == 0:
            return # Flicker

        pygame.draw.rect(surface, WHITE, self.rect)
        
        # Draw Eye to show direction
        eye_x, eye_y = self.rect.centerx, self.rect.centery
        if self.facing == 'RIGHT': eye_x += 8
        elif self.facing == 'LEFT': eye_x -= 12
        elif self.facing == 'UP': eye_y -= 12
        elif self.facing == 'DOWN': eye_y += 8
        pygame.draw.rect(surface, BLACK, (eye_x, eye_y, 4, 4))

        # Draw Slash Hitbox
        if self.attack_rect:
            pygame.draw.rect(surface, CYAN, self.attack_rect, 2)


class Enemy:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.hp = 3
        self.vel_x = 0
        self.vel_y = 0
        self.facing = 'DOWN'
        
        self.state = "chase" # chase, windup, attack, cooldown, stunned
        self.state_timer = 0
        self.attack_rect = None

    def update(self, player):
        if self.state == "chase":
            # Move towards player
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            dist = math.hypot(dx, dy)
            
            if dist > 0:
                self.vel_x = (dx / dist) * ENEMY_SPEED
                self.vel_y = (dy / dist) * ENEMY_SPEED
            
            self.rect.x += self.vel_x
            self.rect.y += self.vel_y

            # Determine facing for attack based on largest delta
            if abs(dx) > abs(dy):
                self.facing = 'RIGHT' if dx > 0 else 'LEFT'
            else:
                self.facing = 'DOWN' if dy > 0 else 'UP'

            # Attack trigger range
            if dist < 65:
                self.state = "windup"
                self.state_timer = 25 # Windup frames

        elif self.state == "windup":
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "attack"
                self.state_timer = 15 

        elif self.state == "attack":
            self.state_timer -= 1
            
            # Spawn hitbox based on facing
            if self.facing == 'RIGHT':
                self.attack_rect = pygame.Rect(self.rect.right, self.rect.y - 5, 30, 40)
            elif self.facing == 'LEFT':
                self.attack_rect = pygame.Rect(self.rect.left - 30, self.rect.y - 5, 30, 40)
            elif self.facing == 'UP':
                self.attack_rect = pygame.Rect(self.rect.x - 5, self.rect.top - 30, 40, 30)
            elif self.facing == 'DOWN':
                self.attack_rect = pygame.Rect(self.rect.x - 5, self.rect.bottom, 40, 30)
                
            if self.state_timer <= 0:
                self.attack_rect = None
                self.state = "cooldown"
                self.state_timer = 40 

        elif self.state == "cooldown":
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "chase"

        elif self.state == "stunned":
            # Knockback friction
            self.rect.x += self.vel_x
            self.rect.y += self.vel_y
            self.vel_x *= FRICTION
            self.vel_y *= FRICTION
            
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "chase"

    def draw(self, surface):
        color = RED
        if self.state == "windup": color = ORANGE
        elif self.state == "stunned": color = GRAY
        
        pygame.draw.rect(surface, color, self.rect)
        
        # Enemy Attack hitbox
        if self.attack_rect:
            pygame.draw.rect(surface, RED, self.attack_rect)

class Spark:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 10
        self.life = 10

    def update(self):
        self.radius += 3
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, YELLOW, (int(self.x), int(self.y)), int(self.radius), 2)

def draw_grid(surface):
    for x in range(0, SCREEN_WIDTH, 40):
        pygame.draw.line(surface, GRAY, (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, 40):
        pygame.draw.line(surface, GRAY, (0, y), (SCREEN_WIDTH, y))

# ─────────────────────────────────────────
#  GAME SETUP
# ─────────────────────────────────────────
player = Player(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)
enemies = []
sparks = []

spawn_timer = 0
SPAWN_RATE = 120 # Spawn an enemy every 2 seconds (60 frames * 2)

screen_shake = 0
flash_frames = 0

# ─────────────────────────────────────────
#  GAME LOOP
# ─────────────────────────────────────────
running = True
while running:

    # ── EVENT HANDLING ───────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_x or event.key == pygame.K_SPACE:
                player.attack()

    keys = pygame.key.get_pressed()

    # ── UPDATE ───────────────────────────
    player.update(keys)
    
    # Spawner Logic
    spawn_timer -= 1
    if spawn_timer <= 0 and len(enemies) < MAX_ENEMIES:
        spawn_timer = SPAWN_RATE
        # Spawn randomly at screen edges
        edge = random.choice(['top', 'bottom', 'left', 'right'])
        if edge == 'top': ex, ey = random.randint(0, SCREEN_WIDTH), -30
        elif edge == 'bottom': ex, ey = random.randint(0, SCREEN_WIDTH), SCREEN_HEIGHT + 30
        elif edge == 'left': ex, ey = -30, random.randint(0, SCREEN_HEIGHT)
        else: ex, ey = SCREEN_WIDTH + 30, random.randint(0, SCREEN_HEIGHT)
        enemies.append(Enemy(ex, ey))

    for enemy in enemies[:]:
        enemy.update(player)
        
        # --- COMBAT LOGIC ---
        
        # 1. PARRY: Both attacks hit each other
        if player.attack_rect and enemy.attack_rect:
            if player.attack_rect.colliderect(enemy.attack_rect):
                enemy.state = "stunned"
                enemy.state_timer = 45
                enemy.attack_rect = None
                
                # Calculate knockback direction based on positions
                dx = enemy.rect.centerx - player.rect.centerx
                dy = enemy.rect.centery - player.rect.centery
                dist = math.hypot(dx, dy)
                if dist != 0:
                    enemy.vel_x = (dx / dist) * 8
                    enemy.vel_y = (dy / dist) * 8
                    player.vel_x = -(dx / dist) * 6
                    player.vel_y = -(dy / dist) * 6
                
                player.recoil_timer = 10
                sparks.append(Spark(player.attack_rect.centerx, player.attack_rect.centery))
                screen_shake = 10
                flash_frames = 2
                
                player.attack_rect = None 
                continue 

        # 2. Player hits Enemy Body
        if player.attack_rect and player.attack_rect.colliderect(enemy.rect):
            if enemy.state != "stunned":
                enemy.hp -= 1
                if enemy.hp <= 0:
                    enemies.remove(enemy)
                else:
                    enemy.state = "stunned"
                    enemy.state_timer = 20
                    
                    # Knockback
                    dx = enemy.rect.centerx - player.rect.centerx
                    dy = enemy.rect.centery - player.rect.centery
                    dist = math.hypot(dx, dy)
                    if dist != 0:
                        enemy.vel_x = (dx / dist) * 6
                        enemy.vel_y = (dy / dist) * 6
                        player.vel_x = -(dx / dist) * 3
                        player.vel_y = -(dy / dist) * 3
                        
                    player.recoil_timer = 8
                    sparks.append(Spark(enemy.rect.centerx, enemy.rect.centery))

        # 3. Enemy Sword hits Player Body
        if enemy.attack_rect and enemy.attack_rect.colliderect(player.rect):
            dx = player.rect.centerx - enemy.rect.centerx
            dy = player.rect.centery - enemy.rect.centery
            dist = math.hypot(dx, dy)
            if dist != 0:
                player.take_damage(1, dx/dist, dy/dist)
            else:
                player.take_damage(1, 1, 0)

    for spark in sparks[:]:
        spark.update()
        if spark.life <= 0:
            sparks.remove(spark)

    # ── RENDER ───────────────────────────
    render_offset = [0, 0]
    if screen_shake > 0:
        screen_shake -= 1
        render_offset = [random.randint(-5, 5), random.randint(-5, 5)]

    if render_offset != [0,0]:
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    else:
        surface = screen

    surface.fill(BLACK)
    draw_grid(surface)

    # Draw Entities
    for enemy in enemies:
        enemy.draw(surface)
    player.draw(surface)
    for spark in sparks:
        spark.draw(surface)

    # Draw Health UI
    for i in range(player.hp):
        pygame.draw.rect(surface, WHITE, (10 + (i * 20), 10, 15, 15))
    if player.hp <= 0:
        # Simple Game Over overlay
        pygame.draw.rect(surface, (100, 0, 0), (0, SCREEN_HEIGHT//2 - 20, SCREEN_WIDTH, 40))

    if render_offset != [0,0]:
        screen.fill(BLACK)
        screen.blit(surface, render_offset)

    if flash_frames > 0:
        flash_frames -= 1
        screen.fill(WHITE)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()