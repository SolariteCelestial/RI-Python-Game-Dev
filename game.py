import os
import sys
import pygame

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
TITLE         = "Cube Knight"
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()
FPS = 60

# ─────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────
BLACK  = (  0,   0,   0)
WHITE  = (255, 255, 255)
RED    = (255,  50,  50)
GRAY   = ( 60,  60,  60)
CYAN   = (  0, 255, 255) # Color of our sword slash

# ─────────────────────────────────────────
#  PHYSICS & GAME OBJECTS
# ─────────────────────────────────────────
GRAVITY = 0.5
MAX_FALL_SPEED = 12
JUMP_FORCE = -9
PLAYER_SPEED = 5

# Player State
player = pygame.Rect(100, 200, 40, 40)
player_vel_y = 0
is_grounded = False
facing_right = True

# Attack State
attack_rect = None
attack_timer = 0
ATTACK_DURATION = 8     # How many frames the slash lasts
ATTACK_COOLDOWN = 15    # Frames before you can slash again
attack_cooldown_timer = 0

# Enemies (The Cubes)
enemies = [
    pygame.Rect(300, 360, 40, 40),
    pygame.Rect(450, 360, 40, 40),
    pygame.Rect(500, 230, 40, 40) # Platform enemy
]

# Platforms (Floor + floating platform)
platforms = [
    pygame.Rect(0, 400, SCREEN_WIDTH, 80),  # Main Floor
    pygame.Rect(450, 270, 150, 20)          # Floating platform
]

def draw_grid():
    for x in range(0, SCREEN_WIDTH, 40):
        pygame.draw.line(screen, (40, 40, 40), (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, 40):
        pygame.draw.line(screen, (40, 40, 40), (0, y), (SCREEN_WIDTH, y))

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
                
            # HK Jump logic (Z key or UP Arrow)
            if (event.key == pygame.K_z or event.key == pygame.K_UP) and is_grounded:
                player_vel_y = JUMP_FORCE
                is_grounded = False
                
            # HK Slash logic (X key or SPACE)
            if (event.key == pygame.K_x or event.key == pygame.K_SPACE) and attack_cooldown_timer == 0:
                attack_timer = ATTACK_DURATION
                attack_cooldown_timer = ATTACK_COOLDOWN

    # ── UPDATE ───────────────────────────
    keys = pygame.key.get_pressed()

    # 1. Horizontal Movement (Tight controls, no sliding)
    dx = 0
    if keys[pygame.K_LEFT]:
        dx -= PLAYER_SPEED
        facing_right = False
    if keys[pygame.K_RIGHT]:
        dx += PLAYER_SPEED
        facing_right = True
        
    player.x += dx

    # Keep player inside screen bounds horizontally
    if player.left < 0: player.left = 0
    if player.right > SCREEN_WIDTH: player.right = SCREEN_WIDTH

    # 2. Vertical Movement & Gravity
    player_vel_y += GRAVITY
    if player_vel_y > MAX_FALL_SPEED:
        player_vel_y = MAX_FALL_SPEED
    
    player.y += player_vel_y

    # 3. Collision with Platforms
    is_grounded = False
    for plat in platforms:
        if player.colliderect(plat):
            # Falling down onto a platform
            if player_vel_y > 0 and player.bottom <= plat.top + player_vel_y + 1:
                player.bottom = plat.top
                player_vel_y = 0
                is_grounded = True
            # Jumping up into a ceiling
            elif player_vel_y < 0 and player.top >= plat.bottom + player_vel_y - 1:
                player.top = plat.bottom
                player_vel_y = 0

    # 4. Handle Attack (The Slash)
    if attack_cooldown_timer > 0:
        attack_cooldown_timer -= 1

    if attack_timer > 0:
        # Create a hitbox in front of the player
        if facing_right:
            attack_rect = pygame.Rect(player.right, player.y - 10, 50, 60)
        else:
            attack_rect = pygame.Rect(player.left - 50, player.y - 10, 50, 60)
        
        # Check if slash hits any enemies
        for enemy in enemies[:]:
            if attack_rect.colliderect(enemy):
                enemies.remove(enemy) # Destroy the cube!
                
        attack_timer -= 1
    else:
        attack_rect = None

    # ── RENDER ───────────────────────────
    screen.fill(BLACK)
    draw_grid()

    # Draw platforms
    for plat in platforms:
        pygame.draw.rect(screen, GRAY, plat)

    # Draw enemies (Cubes)
    for enemy in enemies:
        pygame.draw.rect(screen, RED, enemy)

    # Draw player
    pygame.draw.rect(screen, WHITE, player)
    
    # Draw player "eye" so you know which way they are facing
    eye_x = player.right - 10 if facing_right else player.left + 5
    pygame.draw.rect(screen, BLACK, (eye_x, player.top + 8, 5, 5))

    # Draw the Slash hitbox
    if attack_rect:
        pygame.draw.rect(screen, CYAN, attack_rect)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()