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
TITLE         = "Hollow Cube"
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()
FPS = 60

# ─────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────
BLACK  = ( 15,  15,  20)
WHITE  = (240, 240, 240)
GRAY   = ( 50,  50,  60)
RED    = (220,  50,  50)
ORANGE = (255, 150,  50)
CYAN   = (150, 255, 255)
YELLOW = (255, 255, 100)

# ─────────────────────────────────────────
#  PHYSICS CONSTANTS
# ─────────────────────────────────────────
GRAVITY = 0.6
MAX_FALL_SPEED = 12
JUMP_FORCE = -10
PLAYER_SPEED = 5
FRICTION = 0.8

# ─────────────────────────────────────────
#  CLASSES
# ─────────────────────────────────────────

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 30, 40)
        self.vel_y = 0
        self.vel_x = 0
        self.is_grounded = False
        self.facing_right = True
        
        # Combat
        self.hp = 5
        self.invuln_timer = 0
        self.attack_timer = 0
        self.attack_cooldown = 0
        self.attack_rect = None
        self.recoil_timer = 0 # Locks movement briefly when parrying/taking damage

    def update(self, keys, platforms):
        # 1. Handle X Movement (Input vs Recoil)
        if self.recoil_timer > 0:
            self.recoil_timer -= 1
            self.vel_x *= FRICTION # Slow down recoil smoothly
        else:
            self.vel_x = 0
            if keys[pygame.K_LEFT]:
                self.vel_x = -PLAYER_SPEED
                self.facing_right = False
            if keys[pygame.K_RIGHT]:
                self.vel_x = PLAYER_SPEED
                self.facing_right = True

        self.rect.x += self.vel_x

        # Screen bounds
        if self.rect.left < 0: self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH: self.rect.right = SCREEN_WIDTH

        # 2. Handle Y Movement (Gravity)
        self.vel_y += GRAVITY
        if self.vel_y > MAX_FALL_SPEED:
            self.vel_y = MAX_FALL_SPEED
        self.rect.y += self.vel_y

        # 3. Platform Collision
        self.is_grounded = False
        for plat in platforms:
            if self.rect.colliderect(plat):
                # Falling onto platform
                if self.vel_y > 0 and self.rect.bottom <= plat.top + self.vel_y + 1:
                    self.rect.bottom = plat.top
                    self.vel_y = 0
                    self.is_grounded = True
                # Hitting head
                elif self.vel_y < 0 and self.rect.top >= plat.bottom + self.vel_y - 1:
                    self.rect.top = plat.bottom
                    self.vel_y = 0

        # 4. Attack Timers
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
            
        if self.attack_timer > 0:
            self.attack_timer -= 1
            # Maintain hitbox position relative to player
            if self.facing_right:
                self.attack_rect = pygame.Rect(self.rect.right, self.rect.y - 10, 50, 60)
            else:
                self.attack_rect = pygame.Rect(self.rect.left - 50, self.rect.y - 10, 50, 60)
        else:
            self.attack_rect = None

        if self.invuln_timer > 0:
            self.invuln_timer -= 1

    def jump(self):
        if self.is_grounded:
            self.vel_y = JUMP_FORCE
            self.is_grounded = False

    def attack(self):
        if self.attack_cooldown == 0 and self.attack_timer == 0:
            self.attack_timer = 10     # Slash lasts 10 frames
            self.attack_cooldown = 20  # Cannot slash for 20 frames

    def take_damage(self, amount, knockback_dir):
        if self.invuln_timer == 0:
            self.hp -= amount
            self.invuln_timer = 60 # 1 second of i-frames
            self.vel_x = knockback_dir * 8
            self.vel_y = -5
            self.recoil_timer = 15

    def draw(self, surface):
        # Flicker if invulnerable
        if self.invuln_timer > 0 and (self.invuln_timer // 4) % 2 == 0:
            return

        pygame.draw.rect(surface, WHITE, self.rect)
        
        # Draw Eye
        eye_x = self.rect.right - 8 if self.facing_right else self.rect.left + 3
        pygame.draw.rect(surface, BLACK, (eye_x, self.rect.top + 8, 5, 5))

        # Draw "Proper" Arc Slash
        if self.attack_timer > 0:
            # We draw a sweeping polygon to simulate a sword arc
            progress = 1 - (self.attack_timer / 10) # 0.0 to 1.0
            
            # Anchor point (player's shoulder)
            anchor_x = self.rect.centerx
            anchor_y = self.rect.centery
            
            # Start angle (above head), End angle (below feet)
            start_angle = math.radians(-60)
            end_angle = math.radians(60)
            
            current_angle = start_angle + (end_angle - start_angle) * progress
            if not self.facing_right:
                current_angle = math.pi - current_angle # Flip for left
                
            radius = 55
            slash_x = anchor_x + math.cos(current_angle) * radius
            slash_y = anchor_y + math.sin(current_angle) * radius
            
            pygame.draw.circle(surface, WHITE, (int(slash_x), int(slash_y)), 10)
            pygame.draw.rect(surface, WHITE, self.attack_rect, 1) # Outline the actual hitbox


class Enemy:
    def __init__(self, x, y, patrol_dist):
        self.rect = pygame.Rect(x, y, 40, 40)
        self.start_x = x
        self.patrol_dist = patrol_dist
        self.hp = 3
        
        self.vel_x = 2
        self.vel_y = 0
        self.facing_right = True
        
        self.state = "patrol" # patrol, windup, attack, cooldown, stunned
        self.state_timer = 0
        self.attack_rect = None

    def update(self, player, platforms):
        # Gravity
        self.vel_y += GRAVITY
        self.rect.y += self.vel_y
        
        for plat in platforms:
            if self.rect.colliderect(plat) and self.vel_y > 0:
                self.rect.bottom = plat.top
                self.vel_y = 0

        # State Machine AI
        if self.state == "patrol":
            self.rect.x += self.vel_x
            
            # Turn around at patrol bounds
            if self.rect.x > self.start_x + self.patrol_dist:
                self.vel_x = -2
                self.facing_right = False
            elif self.rect.x < self.start_x - self.patrol_dist:
                self.vel_x = 2
                self.facing_right = True

            # Sense Player
            dist_to_player = math.hypot(player.rect.centerx - self.rect.centerx, player.rect.centery - self.rect.centery)
            if dist_to_player < 120 and abs(player.rect.y - self.rect.y) < 50:
                self.state = "windup"
                self.state_timer = 30 # Half a second windup
                # Face the player
                self.facing_right = player.rect.centerx > self.rect.centerx

        elif self.state == "windup":
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "attack"
                self.state_timer = 15 # Attack duration

        elif self.state == "attack":
            self.state_timer -= 1
            
            # Create enemy hitbox
            if self.facing_right:
                self.attack_rect = pygame.Rect(self.rect.right, self.rect.y, 40, 40)
            else:
                self.attack_rect = pygame.Rect(self.rect.left - 40, self.rect.y, 40, 40)
                
            if self.state_timer <= 0:
                self.attack_rect = None
                self.state = "cooldown"
                self.state_timer = 60 # Rest before next attack

        elif self.state == "cooldown":
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "patrol"
                self.vel_x = 2 if self.facing_right else -2
                self.start_x = self.rect.x # Set new patrol center

        elif self.state == "stunned":
            # Pushed back by parry
            self.rect.x += self.vel_x
            self.vel_x *= FRICTION
            self.state_timer -= 1
            if self.state_timer <= 0:
                self.state = "patrol"
                self.start_x = self.rect.x
                self.vel_x = 2 if self.facing_right else -2

    def draw(self, surface):
        # Color based on state
        color = RED
        if self.state == "windup": color = ORANGE
        elif self.state == "stunned": color = GRAY
        
        pygame.draw.rect(surface, color, self.rect)
        
        # Enemy Eye
        eye_x = self.rect.right - 8 if self.facing_right else self.rect.left + 3
        pygame.draw.rect(surface, BLACK, (eye_x, self.rect.top + 8, 5, 5))

        # Draw enemy attack slash
        if self.attack_rect:
            pygame.draw.rect(surface, RED, self.attack_rect)

class Spark:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 20
        self.life = 10

    def update(self):
        self.radius += 2
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, YELLOW, (int(self.x), int(self.y)), int(self.radius), 2)

# ─────────────────────────────────────────
#  GAME SETUP
# ─────────────────────────────────────────
player = Player(100, 200)

enemies = [
    Enemy(300, 360, 50),
    Enemy(500, 230, 30)
]

platforms = [
    pygame.Rect(0, 400, SCREEN_WIDTH, 80),  
    pygame.Rect(450, 270, 150, 20),
    pygame.Rect(100, 300, 150, 20)
]

sparks = []
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
            if event.key == pygame.K_z or event.key == pygame.K_UP:
                player.jump()
            if event.key == pygame.K_x or event.key == pygame.K_SPACE:
                player.attack()

    keys = pygame.key.get_pressed()

    # ── UPDATE ───────────────────────────
    player.update(keys, platforms)

    for enemy in enemies[:]:
        enemy.update(player, platforms)
        
        # --- COMBAT LOGIC ---
        
        # 1. Check for Parry (Both hitboxes touch)
        if player.attack_rect and enemy.attack_rect:
            if player.attack_rect.colliderect(enemy.attack_rect):
                # PARRY SUCCESSFUL
                enemy.state = "stunned"
                enemy.state_timer = 45
                enemy.attack_rect = None
                
                # Knockback Enemy
                knock_dir = 1 if player.facing_right else -1
                enemy.vel_x = knock_dir * 8
                enemy.vel_y = -3
                
                # Recoil Player
                player.vel_x = -knock_dir * 6
                player.recoil_timer = 10
                
                # Visual Effects
                sparks.append(Spark(player.attack_rect.centerx, player.attack_rect.centery))
                screen_shake = 10
                flash_frames = 2
                
                # Destroy player's hitbox for this frame to prevent double-hitting
                player.attack_rect = None 
                continue # Skip rest of checks for this enemy

        # 2. Check if Player hit Enemy
        if player.attack_rect and player.attack_rect.colliderect(enemy.rect):
            if enemy.state != "stunned": # Prevent multi-hits while stunned
                enemy.hp -= 1
                if enemy.hp <= 0:
                    enemies.remove(enemy)
                else:
                    # Enemy gets knocked back
                    knock_dir = 1 if player.facing_right else -1
                    enemy.state = "stunned"
                    enemy.state_timer = 20
                    enemy.vel_x = knock_dir * 5
                    
                    # Player gets weapon recoil (HK style)
                    player.vel_x = -knock_dir * 3
                    player.recoil_timer = 8
                    
                    sparks.append(Spark(enemy.rect.centerx, enemy.rect.centery))

        # 3. Check if Enemy hit Player
        if enemy.attack_rect and enemy.attack_rect.colliderect(player.rect):
            knock_dir = 1 if enemy.facing_right else -1
            player.take_damage(1, knock_dir)
            
        elif enemy.rect.colliderect(player.rect) and enemy.state != "stunned":
            # Contact damage
            knock_dir = 1 if enemy.rect.centerx > player.rect.centerx else -1
            player.take_damage(1, -knock_dir)


    # Update Sparks
    for spark in sparks[:]:
        spark.update()
        if spark.life <= 0:
            sparks.remove(spark)

    # Screen Shake Logic
    render_offset = [0, 0]
    if screen_shake > 0:
        screen_shake -= 1
        render_offset = [random.randint(-4, 4), random.randint(-4, 4)]

    # ── RENDER ───────────────────────────
    screen.fill(BLACK)

    # Offset for screen shake
    if render_offset != [0,0]:
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.fill(BLACK)
    else:
        surface = screen

    # Draw Environment
    for plat in platforms:
        pygame.draw.rect(surface, GRAY, plat)

    # Draw Entities
    for enemy in enemies:
        enemy.draw(surface)
        
    player.draw(surface)

    for spark in sparks:
        spark.draw(surface)

    # UI (Health)
    for i in range(player.hp):
        pygame.draw.rect(surface, WHITE, (10 + (i * 20), 10, 15, 15))

    # Apply screen shake offset
    if render_offset != [0,0]:
        screen.blit(surface, render_offset)

    # Screen Flash (for parry)
    if flash_frames > 0:
        flash_frames -= 1
        screen.fill(WHITE)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()