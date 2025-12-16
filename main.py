import pygame
import sys
import asyncio

# --- 定数 ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 40
FPS = 60
# フレーム時間を計算 (asyncio.sleep(0)を使うため、厳密なFPS制御はclock.tickに任せる)
# FRAME_TIME = 1000 / FPS 

# 色
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 100, 200)
RED = (255, 0, 0)
YELLOW = (255, 215, 0)	
PURPLE = (150, 0, 200)	

# 物理定数
GRAVITY = 0.9
JUMP_STRENGTH = -15
MOVE_SPEED = 5

# ★ ステージデータの定義 ★
STAGE_DATA = {
	1: {
		'map_file': 'map.txt',
		'start_pos': (TILE_SIZE * 2, TILE_SIZE * 5),
		'enemies': [(TILE_SIZE * 15, TILE_SIZE * 7), (TILE_SIZE * 40, TILE_SIZE * 7)]
	},
	2: {
		'map_file': 'map2.txt',
		'start_pos': (TILE_SIZE * 2, TILE_SIZE * 5),
		'enemies': [(TILE_SIZE * 8, TILE_SIZE * 4), (TILE_SIZE * 20, TILE_SIZE * 11)]
	}
}

# --- マップの読み込み ---
def load_map(filename):
	game_map = []
	try:
		# mapファイルのパスを適切に設定してください（ここではコードと同じディレクトリを想定）
		with open(filename, 'r') as f:
			for line in f:
				game_map.append(list(line.strip()))
	except FileNotFoundError:
		# map.txtがない場合の代替マップ
		print(f"Warning: {filename} not found. Using fallback map.")
		# 代替マップの幅を考慮し、マップ外アクセスを防ぐ
		game_map = [list("1111111111111111111111111111111111111111"), 
					list("10000000G1000000000000000000000000000001"), 
					list("10K0000001000000000000000000000000000001"), 
					list("1111111111111111111111111111111111111111")]
	return game_map

# --- プレイヤー ---
class Player:
	def __init__(self, x, y):
		self.rect = pygame.Rect(x, y, TILE_SIZE - 4, TILE_SIZE * 2 - 4)
		self.x_velocity = 0
		self.y_velocity = 0
		self.on_ground = False
		self.moving_left = False
		self.moving_right = False
		
		self.health = 3
		self.alive = True
		self.has_key = False
		
		# 無敵時間属性
		self.invulnerable_timer = 0
		self.INVULNERABLE_DURATION = 60
		
	def move(self, map_data):
		# 1. X軸の移動
		if self.moving_left: self.x_velocity = -MOVE_SPEED
		elif self.moving_right: self.x_velocity = MOVE_SPEED
		else: self.x_velocity = 0
			
		self.rect.x += self.x_velocity
		self.handle_collision(map_data, 'x')
		
		# 2. Y軸の移動 (重力適用)
		self.y_velocity += GRAVITY
		if self.y_velocity > 15: self.y_velocity = 15
		self.rect.y += self.y_velocity
		self.handle_collision(map_data, 'y')

	def jump(self):
		if self.on_ground:
			self.y_velocity = JUMP_STRENGTH
			self.on_ground = False
			
	def handle_collision(self, map_data, direction):
		"""マップとの衝突判定と位置調整"""
		# マップの境界を考慮してチェック範囲を決定
		map_height = len(map_data)
		map_width = len(map_data[0]) if map_height > 0 else 0

		# タイル座標の計算
		tx = max(0, int(self.rect.left // TILE_SIZE))
		bx = min(map_width - 1, int(self.rect.right // TILE_SIZE))
		ty = max(0, int(self.rect.top // TILE_SIZE))
		by = min(map_height - 1, int(self.rect.bottom // TILE_SIZE))
		
		for y in range(ty, by + 1):
			for x in range(tx, bx + 1):
				if 0 <= y < map_height and 0 <= x < map_width:
					if map_data[y][x] == '1':	
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

	def update_invulnerability(self):
		"""無敵タイマーを更新する"""
		if self.invulnerable_timer > 0:
			self.invulnerable_timer -= 1

	def draw(self, screen, scroll_offset):
		# 無敵時間中は点滅させる (8フレームに1回非表示)
		if self.invulnerable_timer == 0 or self.invulnerable_timer % 8 < 4:
			draw_rect = self.rect.move(-scroll_offset[0], -scroll_offset[1])
			pygame.draw.rect(screen, BLUE, draw_rect)

# --- 敵 ---
class Enemy:
	def __init__(self, x, y):
		self.rect = pygame.Rect(x, y, TILE_SIZE - 4, TILE_SIZE - 4)
		self.x_velocity = MOVE_SPEED // 2
		self.direction = 1
		
	def move(self, map_data):
		self.rect.x += self.x_velocity * self.direction
		
		# 進行方向のブロックをチェック
		ty = int(self.rect.centery // TILE_SIZE)
		
		if self.direction == 1: # 右移動
			target_x = int(self.rect.right // TILE_SIZE)
		else: # 左移動
			target_x = int(self.rect.left // TILE_SIZE)

		# マップの境界チェック
		map_height = len(map_data)
		map_width = len(map_data[0]) if map_height > 0 else 0

		# 次のタイルが壁の場合、方向転換
		if 0 <= ty < map_height and 0 <= target_x < map_width:
			if map_data[ty][target_x] == '1':
				self.direction *= -1

		# 足元のタイルのチェック (落下防止)
		floor_y = int((self.rect.bottom + 1) // TILE_SIZE)
		if self.direction == 1: # 右移動時、右下の角
			floor_x = int(self.rect.right // TILE_SIZE)
		else: # 左移動時、左下の角
			floor_x = int(self.rect.left // TILE_SIZE)

		if 0 <= floor_y < map_height and 0 <= floor_x < map_width:
			# 足元にブロックがない場合、方向転換
			if map_data[floor_y][floor_x] != '1':
				self.direction *= -1

	def draw(self, screen, scroll_offset):
		draw_rect = self.rect.move(-scroll_offset[0], -scroll_offset[1])
		pygame.draw.rect(screen, RED, draw_rect)

# --- 初期化 ---
def initialize_game(game_map, stage_info):
	# ステージ情報から開始位置を取得
	px, py = stage_info['start_pos']
	player = Player(px, py)
	
	# カメラの初期化
	camera_scroll = [px - SCREEN_WIDTH // 2, py - SCREEN_HEIGHT // 2]
	
	# 敵の初期化
	enemies = []
	for ex, ey in stage_info['enemies']:
		enemies.append(Enemy(ex, ey))
	
	return player, enemies, camera_scroll

# --- ゲーム本体 (非同期関数に変更) ---
async def game_loop():
	pygame.init()
	screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
	clock = pygame.time.Clock()
	
	# 初期ステージの設定
	CURRENT_STAGE = 1	
	GAME_STATE = 'TITLE_SCREEN'
	
	# ダミーマップで初期化
	game_map = load_map(STAGE_DATA[CURRENT_STAGE]['map_file'])	
	player, enemies, camera_scroll = initialize_game(game_map, STAGE_DATA[CURRENT_STAGE])

	# リセット/ステージ切り替え処理
	def reset_game(stage_num=1):
		nonlocal player, enemies, camera_scroll, GAME_STATE, game_map, CURRENT_STAGE
		
		# 全ステージクリアの判定
		if stage_num > len(STAGE_DATA):
			GAME_STATE = 'ALL_CLEAR'
			return

		CURRENT_STAGE = stage_num
		stage_info = STAGE_DATA[CURRENT_STAGE]
		
		game_map = load_map(stage_info['map_file'])	
		player, enemies, camera_scroll = initialize_game(game_map, stage_info)
		GAME_STATE = 'RUNNING'

	running = True
	while running:
		# --- 1. イベント処理 ---
		for event in pygame.event.get():
			if event.type == pygame.QUIT: running = False
			if event.type == pygame.KEYDOWN:
				
				if GAME_STATE == 'TITLE_SCREEN' and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
					reset_game(1) # ステージ1から開始
				elif (GAME_STATE == 'GAME_OVER' or GAME_STATE == 'ALL_CLEAR') and event.key == pygame.K_RETURN:
					reset_game(1) # ゲームオーバー/クリア時はステージ1からリトライ

				elif GAME_STATE == 'RUNNING':
					if event.key == pygame.K_LEFT: player.moving_left = True
					if event.key == pygame.K_RIGHT: player.moving_right = True
					if event.key in [pygame.K_SPACE, pygame.K_UP]: player.jump()
					
			if event.type == pygame.KEYUP and GAME_STATE == 'RUNNING':
				if event.key == pygame.K_LEFT: player.moving_left = False
				if event.key == pygame.K_RIGHT: player.moving_right = False

		# --- 2. 更新処理 ---
		if GAME_STATE == 'RUNNING':
			player.move(game_map)
			player.update_invulnerability() # 無敵タイマー更新
			
			# カメラ（画面スクロール）の更新
			camera_scroll[0] += (player.rect.centerx - SCREEN_WIDTH // 2 - camera_scroll[0]) // 10
			camera_scroll[1] += (player.rect.centery - SCREEN_HEIGHT // 2 - camera_scroll[1]) // 10
			
			# アイテム・ゴール判定
			grid_x = int(player.rect.centerx // TILE_SIZE)
			grid_y = int(player.rect.centery // TILE_SIZE)
			
			map_height = len(game_map)
			map_width = len(game_map[0]) if map_height > 0 else 0

			if 0 <= grid_y < map_height and 0 <= grid_x < map_width:
				tile = game_map[grid_y][grid_x]
				if tile == 'K':	
					player.has_key = True
					game_map[grid_y][grid_x] = '0'
				elif tile == 'G':	
					if player.has_key:
						# ステージクリア処理 -> 次のステージへ
						# ステージクリアのメッセージ表示のために一時的に状態をSTAGE_CLEARへ遷移
						# reset_gameを次のフレームで行うために、一旦RUNNINGから抜ける
						GAME_STATE = 'STAGE_CLEAR'
			
			# ステージクリア状態からの自動遷移
			if GAME_STATE == 'STAGE_CLEAR':
				 await asyncio.sleep(1) # 1秒待ってから次のステージへ (描画を優先するため、少し長めに待つ)
				 # ステージクリアの描画の後、次のステージへ
				 reset_game(CURRENT_STAGE + 1)
				 # ループの最初に戻り、描画と次のステージのロードを確認させる
				 continue

			# 敵の更新と衝突判定
			next_enemies = []
			for enemy in enemies:
				enemy.move(game_map)
				
				is_stomped = False
				
				if player.rect.colliderect(enemy.rect):
					
					# A. 踏みつけ判定 (撃破)
					# プレイヤーが下降中 (y_velocity > 0) かつ プレイヤーの底辺が敵の中心より上にある場合
					if player.y_velocity > 0 and player.rect.bottom < enemy.rect.centery + 5:
						player.y_velocity = JUMP_STRENGTH * 0.6
						is_stomped = True
						
					# B. ダメージ判定 (踏みつけ失敗時)
					if not is_stomped:
						
						if player.invulnerable_timer == 0: # 無敵時間中でない場合のみダメージ
							player.health -= 1
							player.invulnerable_timer = player.INVULNERABLE_DURATION # タイマーセット
							
							if player.health <= 0:	
								GAME_STATE = 'GAME_OVER'
							else:	
								# ノックバック
								player.y_velocity = -10
								# 衝突方向によるX軸ノックバック
								if player.rect.centerx < enemy.rect.centerx:
									player.x_velocity = -10
								else:
									player.x_velocity = 10
						
						next_enemies.append(enemy) # 踏みつけでなければ敵は残る
						continue

				if not is_stomped:
					next_enemies.append(enemy)
					
			enemies = next_enemies
		
		# --- 3. 描画処理 ---
		screen.fill(WHITE)

		if GAME_STATE == 'TITLE_SCREEN':
			font = pygame.font.Font(None, 80)
			txt = font.render("Key & Goal Quest", True, BLACK)
			screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH//2, 300)))
			
			font_start = pygame.font.Font(None, 40)
			txt_start = font_start.render("Press SPACE or ENTER to Start", True, BLACK)
			screen.blit(txt_start, txt_start.get_rect(center=(SCREEN_WIDTH//2, 400)))
		
		else: # RUNNING / GAME_OVER / STAGE_CLEAR / ALL_CLEAR 状態の描画
			# マップの描画
			for y, row in enumerate(game_map):
				for x, tile in enumerate(row):
					r = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE).move(-camera_scroll[0], -camera_scroll[1])
					if tile == '1': pygame.draw.rect(screen, GREEN, r)
					elif tile == 'K': pygame.draw.ellipse(screen, YELLOW, r)	
					elif tile == 'G': pygame.draw.rect(screen, PURPLE, r)	
			
			player.draw(screen, camera_scroll)
			for enemy in enemies: enemy.draw(screen, camera_scroll)
			
			# ライフ/UI表示
			font = pygame.font.Font(None, 36)
			msg = f"STAGE {CURRENT_STAGE} | LIFE: {player.health} | KEY: {'GOT!' if player.has_key else 'NONE'}"
			screen.blit(font.render(msg, True, BLACK), (20, 20))

			if GAME_STATE == 'GAME_OVER':
				txt = pygame.font.Font(None, 100).render("GAME OVER", True, RED)
				screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH//2, 300)))
				retry_font = pygame.font.Font(None, 50)
				retry_text = retry_font.render("Press ENTER to Retry (Stage 1)", True, BLACK)
				retry_rect = retry_text.get_rect(center=(SCREEN_WIDTH // 2, 380))
				screen.blit(retry_text, retry_rect)
				
			elif GAME_STATE == 'STAGE_CLEAR':
				txt = pygame.font.Font(None, 100).render(f"STAGE {CURRENT_STAGE} CLEAR!", True, GREEN)
				screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH//2, 300)))
			
			elif GAME_STATE == 'ALL_CLEAR':
				txt = pygame.font.Font(None, 100).render("ALL STAGES CLEARED!", True, GREEN)
				screen.blit(txt, txt.get_rect(center=(SCREEN_WIDTH//2, 300)))
				retry_font = pygame.font.Font(None, 50)
				retry_text = retry_font.render("Press ENTER to Play Again", True, BLACK)
				retry_rect = retry_text.get_rect(center=(SCREEN_WIDTH // 2, 380))
				screen.blit(retry_text, retry_rect)


		pygame.display.flip()
		
		# FPSを制御
		clock.tick(FPS)
		
		# 他の非同期タスクに制御を渡す (必須)
		await asyncio.sleep(0) 
	
	pygame.quit()

async def main():
	# ゲームループを非同期タスクとして実行
	await game_loop()

if __name__ == '__main__':
	# asyncio.run() で非同期メイン関数を実行
	try:
		asyncio.run(main())
	except SystemExit:
		# pygame.quit()後の終了処理で発生するSystemExitを捕捉
		pass
	except KeyboardInterrupt:
		# Ctrl+C などでの終了を捕捉
		pass