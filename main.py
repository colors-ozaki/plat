import pygame
import sys
import asyncio

# --- 定数 ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 40
FPS = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 100, 200)
RED = (255, 0, 0)
YELLOW = (255, 215, 0)	
BROWN = (139, 69, 19)
PURPLE = (150, 0, 200)

GRAVITY = 0.9
JUMP_STRENGTH = -15
MOVE_SPEED = 5

# ステージデータ
STAGE_DATA = {
    1: {
        'map_file': 'map.txt',
        'start_pos': (TILE_SIZE * 2, TILE_SIZE * 5),
        'enemies': [(TILE_SIZE * 15, TILE_SIZE * 7)]
    },
    2: {
        'map_file': 'map2.txt',
        'start_pos': (TILE_SIZE * 2, TILE_SIZE * 4),
        'enemies': [(TILE_SIZE * 10, TILE_SIZE * 7), (TILE_SIZE * 25, TILE_SIZE * 7)]
    }
}

def load_map(filename):
    try:
        with open(filename, 'r') as f:
            return [list(line.strip()) for line in f]
    except FileNotFoundError:
        return [
            list("11111111111111111111"),
            list("100000000000000000D1"),
            list("10K00000000000000001"),
            list("11111111111111111111")
        ]

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE - 4, TILE_SIZE * 2 - 4)
        self.x_velocity = 0
        self.y_velocity = 0
        self.on_ground = False
        self.moving_left = False
        self.moving_right = False
        self.health = 3
        self.max_health = 5
        self.invulnerable_timer = 0
        self.INVULNERABLE_DURATION = 60
        self.has_key = False
        
    def update_invulnerability(self):
        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= 1

    def move(self, map_data):
        if self.moving_left: self.x_velocity = -MOVE_SPEED
        elif self.moving_right: self.x_velocity = MOVE_SPEED
        else: self.x_velocity = 0
            
        self.rect.x += self.x_velocity
        self.handle_collision(map_data, 'x')
        self.y_velocity += GRAVITY
        if self.y_velocity > 15: self.y_velocity = 15
        self.rect.y += self.y_velocity
        self.handle_collision(map_data, 'y')

    def jump(self):
        if self.on_ground:
            self.y_velocity = JUMP_STRENGTH
            self.on_ground = False
            
    def handle_collision(self, map_data, direction):
        tx, bx = int(self.rect.left // TILE_SIZE), int(self.rect.right // TILE_SIZE)
        ty, by = int(self.rect.top // TILE_SIZE), int(self.rect.bottom // TILE_SIZE)
        for y in range(ty, by + 1):
            for x in range(tx, bx + 1):
                if 0 <= y < len(map_data) and 0 <= x < len(map_data[0]):
                    if map_data[y][x] in ['1', 'D']:
                        tile_rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                        if self.rect.colliderect(tile_rect):
                            if direction == 'x':
                                if self.x_velocity > 0: self.rect.right = tile_rect.left
                                elif self.x_velocity < 0: self.rect.left = tile_rect.right
                                self.x_velocity = 0
                            elif direction == 'y':
                                if self.y_velocity > 0:
                                    self.rect.bottom = tile_rect.top
                                    self.on_ground = True
                                elif self.y_velocity < 0:
                                    self.rect.top = tile_rect.bottom
                                self.y_velocity = 0

    def draw(self, screen, scroll_offset):
        if self.invulnerable_timer == 0 or self.invulnerable_timer % 8 < 4:
            draw_rect = self.rect.move(-scroll_offset[0], -scroll_offset[1])
            pygame.draw.rect(screen, BLUE, draw_rect)

class Enemy:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, TILE_SIZE - 4, TILE_SIZE - 4)
        self.x_velocity = MOVE_SPEED // 2
        self.direction = 1
        
    def move(self, map_data):
        self.rect.x += self.x_velocity * self.direction
        tx, bx = int(self.rect.left // TILE_SIZE), int(self.rect.right // TILE_SIZE)
        ty = int(self.rect.centery // TILE_SIZE)
        target_x = bx if self.direction == 1 else tx
        if 0 <= ty < len(map_data) and 0 <= target_x < len(map_data[0]):
            if map_data[ty][target_x] in ['1', 'D']:
                self.direction *= -1

    def draw(self, screen, scroll_offset):
        draw_rect = self.rect.move(-scroll_offset[0], -scroll_offset[1])
        pygame.draw.rect(screen, RED, draw_rect)

async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    
    try:
        font_jp = pygame.font.SysFont("msgothic", 36)
        font_ui = pygame.font.SysFont("msgothic", 24)
    except:
        font_jp = pygame.font.Font(None, 36)
        font_ui = pygame.font.Font(None, 24)

    # --- 内部変数の初期化 ---
    CURRENT_STAGE = 1 
    GAME_STATE = 'TITLE_SCREEN'
    clear_timer = 0
    inventory = ["回復薬"]
    selected_item_index = 0
    display_message = ""
    message_timer = 0
    message_color = BLACK
    player = None
    enemies = []
    camera_scroll = [0, 0]
    game_map = []

    def reset_game(stage_num):
        nonlocal player, enemies, camera_scroll, GAME_STATE, game_map, CURRENT_STAGE, message_timer, inventory
        if stage_num > len(STAGE_DATA):
            GAME_STATE = 'ALL_CLEAR'
            return
        
        CURRENT_STAGE = stage_num
        game_map = load_map(STAGE_DATA[CURRENT_STAGE]['map_file'])
        px, py = STAGE_DATA[CURRENT_STAGE]['start_pos']
        
        player = Player(px, py)
        enemies = [Enemy(ex, ey) for ex, ey in STAGE_DATA[CURRENT_STAGE]['enemies']]
        camera_scroll = [px - SCREEN_WIDTH // 2, py - SCREEN_HEIGHT // 2]
        
        inventory = ["回復薬"]
        GAME_STATE = 'RUNNING'

    reset_game(1)
    GAME_STATE = 'TITLE_SCREEN'

    running = True
    while running:
        # 1. イベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_i and GAME_STATE in ['RUNNING', 'MENU']:
                    GAME_STATE = 'MENU' if GAME_STATE == 'RUNNING' else 'RUNNING'
                
                if GAME_STATE == 'TITLE_SCREEN' and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                    reset_game(1)
                elif GAME_STATE == 'RUNNING':
                    if event.key == pygame.K_LEFT: player.moving_left = True
                    if event.key == pygame.K_RIGHT: player.moving_right = True
                    if event.key in [pygame.K_SPACE, pygame.K_UP]: player.jump()
                elif GAME_STATE == 'MENU':
                    if event.key == pygame.K_UP:
                        selected_item_index = (selected_item_index - 1) % len(inventory) if inventory else 0
                    if event.key == pygame.K_DOWN:
                        selected_item_index = (selected_item_index + 1) % len(inventory) if inventory else 0
                    if event.key == pygame.K_RETURN and inventory:
                        item = inventory[selected_item_index]
                        if item == "回復薬":
                            inventory.pop(selected_item_index)
                            player.health = min(player.health + 1, player.max_health)
                            display_message = "ライフ回復！"; message_color = BLUE; message_timer = 60
                            GAME_STATE = 'RUNNING'
                        elif item == "ステージの鍵":
                            door_opened = False
                            for y, row in enumerate(game_map):
                                for x, tile in enumerate(row):
                                    if tile == 'D':
                                        dist = ((player.rect.centerx - x*TILE_SIZE)**2 + (player.rect.centery - y*TILE_SIZE)**2)**0.5
                                        if dist < TILE_SIZE * 2.5:
                                            game_map[y][x] = 'G' # ゴールに変化
                                            door_opened = True
                            if door_opened:
                                inventory.pop(selected_item_index)
                                display_message = "扉が開いた！ゴールへ急げ！"; message_color = GREEN; message_timer = 90
                                GAME_STATE = 'RUNNING'
                                selected_item_index = 0
                            else:
                                display_message = "扉が遠すぎる..."; message_color = RED; message_timer = 60
                                GAME_STATE = 'RUNNING'

            if event.type == pygame.KEYUP:
                if player:
                    if event.key == pygame.K_LEFT: player.moving_left = False
                    if event.key == pygame.K_RIGHT: player.moving_right = False

        # 2. 更新処理
        if GAME_STATE == 'RUNNING':
            player.move(game_map)
            player.update_invulnerability()
            camera_scroll[0] += (player.rect.centerx - SCREEN_WIDTH // 2 - camera_scroll[0]) // 10
            camera_scroll[1] += (player.rect.centery - SCREEN_HEIGHT // 2 - camera_scroll[1]) // 10
            
            gx, gy = int(player.rect.centerx // TILE_SIZE), int(player.rect.centery // TILE_SIZE)
            if 0 <= gy < len(game_map) and 0 <= gx < len(game_map[0]):
                if game_map[gy][gx] == 'K':
                    player.has_key = True
                    game_map[gy][gx] = '0'
                    inventory.append("ステージの鍵")
                    display_message = "鍵をゲット！"; message_color = GREEN; message_timer = 60
                elif game_map[gy][gx] == 'G':
                    GAME_STATE = 'STAGE_CLEAR'
                    clear_timer = 90
                    display_message = "STAGE CLEAR!"; message_color = BLUE; message_timer = 90

            for enemy in enemies[:]:
                enemy.move(game_map)
                if player.rect.colliderect(enemy.rect):
                    if player.y_velocity > 0 and player.rect.bottom < enemy.rect.centery + 10:
                        player.y_velocity = JUMP_STRENGTH * 0.6
                        enemies.remove(enemy)
                    elif player.invulnerable_timer == 0:
                        player.health -= 1
                        player.invulnerable_timer = player.INVULNERABLE_DURATION
                        if player.health <= 0: GAME_STATE = 'GAME_OVER'

        elif GAME_STATE == 'STAGE_CLEAR':
            clear_timer -= 1
            if clear_timer <= 0: reset_game(CURRENT_STAGE + 1)

        # 3. 描画処理
        screen.fill(WHITE)
        if GAME_STATE == 'TITLE_SCREEN':
            t = font_jp.render("Key Quest - Space to Start", True, BLACK)
            screen.blit(t, t.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)))
        else:
            for y, row in enumerate(game_map):
                for x, tile in enumerate(row):
                    r = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE).move(-camera_scroll[0], -camera_scroll[1])
                    if tile == '1': pygame.draw.rect(screen, GREEN, r)
                    elif tile == 'D': pygame.draw.rect(screen, BROWN, r)
                    elif tile == 'K': pygame.draw.ellipse(screen, YELLOW, r)
                    elif tile == 'G': pygame.draw.rect(screen, PURPLE, r)
            
            if player: player.draw(screen, camera_scroll)
            for enemy in enemies: enemy.draw(screen, camera_scroll)
            
            status_text = f"STAGE {CURRENT_STAGE} | LIFE: {player.health if player else 0}"
            screen.blit(font_ui.render(status_text, True, BLACK), (20, 20))
            
            if message_timer > 0:
                m = font_jp.render(display_message, True, message_color)
                screen.blit(m, m.get_rect(center=(SCREEN_WIDTH//2, 200)))
                message_timer -= 1
            
            if GAME_STATE == 'MENU':
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                screen.blit(overlay, (0, 0))
                title_m = font_jp.render("--- ITEM MENU ---", True, WHITE)
                screen.blit(title_m, (300, 140))
                for i, item in enumerate(inventory):
                    c = YELLOW if i == selected_item_index else WHITE
                    txt = f"{'>' if i==selected_item_index else '  '} {item}"
                    screen.blit(font_jp.render(txt, True, c), (300, 200 + i*50))
            
            if GAME_STATE == 'GAME_OVER':
                go = font_jp.render("GAME OVER", True, RED)
                screen.blit(go, go.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)))
            
            if GAME_STATE == 'ALL_CLEAR':
                ac = font_jp.render("ALL STAGES CLEAR!", True, GREEN)
                screen.blit(ac, ac.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)))

        pygame.display.flip()
        clock.tick(FPS)
        await asyncio.sleep(0) # 非同期処理のための休憩

    pygame.quit()

if __name__ == '__main__':
    asyncio.run(main())
