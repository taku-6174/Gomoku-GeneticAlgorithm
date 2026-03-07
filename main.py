import pygame
import sys
import os
from engine import GomokuAnalyzer




# Pygame設定
CELL_SIZE = 40
MARGIN = 50  # 情報表示用に余白を増やす
BOARD_SIZE = 15
SCREEN_WIDTH = CELL_SIZE * (BOARD_SIZE - 1) + MARGIN * 2
SCREEN_HEIGHT = SCREEN_WIDTH + 80  # 下部に情報表示エリア追加
INFO_AREA_HEIGHT = 80

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("五目並べ AI解析シミュレーター - 九州大学芸術工学部 編入プロジェクト")

# 日本語フォントの設定
def get_japanese_font(size):
    """利用可能な日本語フォントを探す"""
    font_paths = [
        # Windows
        "C:/Windows/Fonts/msgothic.ttc",  # MS ゴシック
        "C:/Windows/Fonts/meiryo.ttc",    # メイリオ
        "C:/Windows/Fonts/yugothic.ttf",  # 游ゴシック
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
        # Linux
        "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
        # 汎用
        "arial",  # フォールバック
    ]
    
    for path in font_paths:
        try:
            if os.path.exists(path):
                return pygame.font.Font(path, size)
            elif 'arial' in path.lower():
                return pygame.font.SysFont(path, size)
        except:
            continue
    
    # どのフォントも見つからない場合
    return pygame.font.SysFont(None, size)

# フォントの初期化
font_small = get_japanese_font(14)
font_medium = get_japanese_font(18)
font_large = get_japanese_font(24)
font_title = get_japanese_font(28)

def draw_board(analyzer, game_over, winner, modo=None):
    """盤面と情報を描画"""
    # 背景（グラデーション風）
    for y in range(SCREEN_HEIGHT):
        color_value = 220 - (y / SCREEN_HEIGHT * 20)
        pygame.draw.line(screen, (color_value, 179, 92), (0, y), (SCREEN_WIDTH, y))
    
    # 情報表示エリアのy座標を最初に計算
    info_y = SCREEN_HEIGHT - INFO_AREA_HEIGHT + 10  # この行を追加
    
    # 盤面背景（木目調）
    board_bg = pygame.Rect(
        MARGIN - 15, MARGIN - 15,
        CELL_SIZE * (BOARD_SIZE - 1) + 30,
        CELL_SIZE * (BOARD_SIZE - 1) + 30
    )
    pygame.draw.rect(screen, (199, 155, 95), board_bg)
    pygame.draw.rect(screen, (150, 110, 70), board_bg, 3)
    
    # 罫線
    for i in range(BOARD_SIZE):
        # 横線
        start_x, start_y = MARGIN, MARGIN + i * CELL_SIZE
        end_x, end_y = SCREEN_WIDTH - MARGIN, start_y
        pygame.draw.line(screen, (0, 0, 0), (start_x, start_y), (end_x, end_y), 2)
        
        # 縦線
        start_x, start_y = MARGIN + i * CELL_SIZE, MARGIN
        end_x, end_y = start_x, SCREEN_HEIGHT - INFO_AREA_HEIGHT - MARGIN
        pygame.draw.line(screen, (0, 0, 0), (start_x, start_y), (end_x, end_y), 2)
    
    # 星のマーク（天元など）
    stars = [(3, 3), (3, 11), (7, 7), (11, 3), (11, 11)]
    for sr, sc in stars:
        x = MARGIN + sc * CELL_SIZE
        y = MARGIN + sr * CELL_SIZE
        pygame.draw.circle(screen, (0, 0, 0), (x, y), 5)
    
    # スコア計算と表示
    scores = analyzer.evaluate_board()
    best_move = analyzer.get_best_move()
    
    # 石と評価値の描画
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            x = MARGIN + c * CELL_SIZE
            y = MARGIN + r * CELL_SIZE
            
            # 石の描画
            if analyzer.board[r][c] == 1:  # 黒石
                # 影効果
                pygame.draw.circle(screen, (30, 30, 30), (x+2, y+2), 16)
                # 本体
                pygame.draw.circle(screen, (20, 20, 20), (x, y), 16)
                pygame.draw.circle(screen, (100, 100, 100), (x, y), 16, 2)
                
            elif analyzer.board[r][c] == 2:  # 白石
                # 影効果
                pygame.draw.circle(screen, (230, 230, 230), (x+2, y+2), 16)
                # 本体
                pygame.draw.circle(screen, (250, 250, 250), (x, y), 16)
                pygame.draw.circle(screen, (200, 200, 200), (x, y), 16, 2)
            
              # 空マスの評価値表示
            elif modo != "PvsAI" or (modo == "PvsAI" and analyzer.current_player == 2):
                # numpyをインポートしていない場合のために修正
                score_value = scores[r][c] if r < len(scores) and c < len(scores[0]) else 0
                
                # スコアのログ変換による正規化（改良版評価関数用）
                if score_value > 0:
                    # 対数スケールで正規化（1-100に収める）
                    # numpyを使わない方法に修正
                    import math
                    log_score = min(100, max(1, int(math.log10(score_value + 1) * 20)))
                    
                    # スコアに応じた色（改良版）
                    if log_score >= 90:
                        color = (255, 50, 50)    # 赤: 最善手（活四など）
                    elif log_score >= 70:
                        color = (255, 150, 50)   # 橙: 強力な手（活三など）
                    elif log_score >= 50:
                        color = (255, 255, 50)   # 黄: 良い手
                    elif log_score >= 30:
                        color = (50, 200, 50)    # 緑: 普通の手
                    elif log_score >= 10:
                        color = (100, 150, 255)  # 青: 悪い手
                    else:
                        color = (150, 150, 150)  # 灰: 非常に悪い手
                    
                    # 背景円
                    # 半透明背景を作成
                    circle_surface = pygame.Surface((28, 28), pygame.SRCALPHA)
                    pygame.draw.circle(circle_surface, (255, 255, 255, 200), (14, 14), 14)
                    screen.blit(circle_surface, (x-14, y-14))
                    
                    # 評価値テキスト（2桁まで表示）
                    score_text = font_small.render(str(log_score), True, color)
                    text_rect = score_text.get_rect(center=(x, y))
                    screen.blit(score_text, text_rect)
    
    # AIの思考情報を追加表示
    if modo == "PvsAI" and analyzer.current_player == 2 and not game_over:
        # AIが考えていることを表示
        thinking_text = font_small.render("AIが考え中...", True, (100, 100, 100))
        screen.blit(thinking_text, (SCREEN_WIDTH - 200, info_y + 60))
    
    # 評価値の凡例を追加
    legend_y = info_y + 40
    legend_texts = [
        ("赤(90-100): 勝ち確定", (255, 50, 50)),
        ("橙(70-89): 強力", (255, 150, 50)),
        ("黄(50-69): 良い", (255, 255, 50)),
        ("緑(30-49): 普通", (50, 200, 50)),
        ("青(10-29): 悪い", (100, 150, 255)),
        ("灰(1-9): 最悪", (150, 150, 150))
    ]
    for i, (text, color) in enumerate(legend_texts):
        legend = font_small.render(text, True, color)
        screen.blit(legend, (SCREEN_WIDTH - 250, legend_y + i * 18))

    # AIの最善手をハイライト
    if best_move and not game_over:
        br, bc = best_move
        if analyzer.board[br][bc] == 0:
            bx = MARGIN + bc * CELL_SIZE
            by = MARGIN + br * CELL_SIZE
            # 点滅する赤い枠
            pulse = (pygame.time.get_ticks() // 300) % 2
            if pulse:
                pygame.draw.circle(screen, (255, 0, 0), (bx, by), 20, 3)
    
    # 情報表示エリア（下部）
    info_rect = pygame.Rect(0, SCREEN_HEIGHT - INFO_AREA_HEIGHT, SCREEN_WIDTH, INFO_AREA_HEIGHT)
    pygame.draw.rect(screen, (240, 240, 240), info_rect)
    pygame.draw.line(screen, (180, 180, 180), (0, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 
                    (SCREEN_WIDTH, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 2)
    
    # ゲーム情報 - info_yはすでに定義済み
    
    # タイトル
    title = font_title.render("五目並べ AI解析ツール", True, (0, 60, 120))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 5))
    
    # 現在の手番
    player_text = font_medium.render(f"現在の手番: {'黒' if analyzer.current_player == 1 else '白'}", 
                                   True, (0, 0, 0))
    screen.blit(player_text, (20, info_y))
    
    # 着手数
    move_count = len(analyzer.move_history)
    count_text = font_small.render(f"着手数: {move_count}", True, (0, 0, 0))
    screen.blit(count_text, (20, info_y + 25))
    
    # 操作説明（右側）
    controls = [
        "【操作方法】",
        "スペース: モード選択画面へ",
        "ESC: 終了"
    ]
    
    for i, text in enumerate(controls):
        control_text = font_small.render(text, True, (80, 80, 80))
        screen.blit(control_text, (SCREEN_WIDTH - 200, info_y + i * 20))
    
    # ゲーム終了時の表示
    if game_over and winner is not None:
        # 半透明オーバーレイ
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # 引き分け
        if winner == 0:
            draw_text = font_large.render("引き分け！", True, (255, 255, 0))
            text_rect = draw_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
            screen.blit(draw_text, text_rect)
        else:
            # 勝利メッセージ
            winner_color = "黒" if winner == 1 else "白"
            win_text = font_large.render(f"{winner_color}の勝利！ ", True, (255, 255, 0))
            text_rect = win_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
            screen.blit(win_text, text_rect)
        
        # リスタート指示
        restart_text = font_medium.render("スペースキーで新しいゲームを開始", True, (255, 255, 255))
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        screen.blit(restart_text, restart_rect)
        
        # 総着手数
        total_moves = font_small.render(f"総着手数: {len(analyzer.move_history)}手", True, (200, 200, 200))
        total_rect = total_moves.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
        screen.blit(total_moves, total_rect)

def draw_home_screen():

    """ホーム画面の描画"""
    # 背景
    screen.fill((200, 220, 255))

    btn_p_vs_ai = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2, 200, 50)
    btn_ai_vs_ai = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 70, 200, 50)
    
    # タイトル
    title = font_title.render("五目並べ AI解析シミュレーター", True, (0, 60, 120))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 4 - 60))
    
    # サブタイトル
    subtitle = font_medium.render("九州大学芸術工学部 編入プロジェクト", True, (0, 0, 0))
    screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, SCREEN_HEIGHT // 4))

    # ボタン1：人間 vs AI
    pygame.draw.rect(screen, (100, 150, 255), btn_p_vs_ai)
    txt1 = font_medium.render("人間 vs AI", True, (255, 255, 255))
    screen.blit(txt1, (btn_p_vs_ai.centerx - txt1.get_width()//2, btn_p_vs_ai.centery - txt1.get_height()//2))

    # ボタン2：AI vs AI
    pygame.draw.rect(screen, (100, 200, 150), btn_ai_vs_ai)
    txt2 = font_medium.render("AI vs AI", True, (255, 255, 255))
    screen.blit(txt2, (btn_ai_vs_ai.centerx - txt2.get_width()//2, btn_ai_vs_ai.centery - txt2.get_height()//2))
    pygame.display.flip()
    
    while True:
        for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    # ここで pos を取得する！
                    pos = pygame.mouse.get_pos() 
                    
                    # pos を取得した直後に、どのボタンの上か判定する
                    if btn_p_vs_ai.collidepoint(pos):
                        return "PvsAI"
                    elif btn_ai_vs_ai.collidepoint(pos):
                        return "AIvsAI"
# メインループ
def main():
    analyzer = GomokuAnalyzer()
    game_over = False
    winner = None
    modo = None  # 初期値をNoneに変更
    in_game = False  # ゲーム中かどうかのフラグを追加
    show_mode_select = True  # モード選択画面表示フラグ

    clock = pygame.time.Clock()
    
    print("=" * 50)
    print("五目並べ AI解析シミュレーター")
    print("九州大学芸術工学部 編入プロジェクト")
    print("=" * 50)
    print()
    print("【ゲーム説明】")
    print("・黒が先手、白が後手です")
    print("・マス上の数字はAIの評価値です（1-10、高いほど良い手）")
    print("・赤い枠はAIが推薦する最善手です")
    print()
    print("【操作方法】")
    print("・盤面クリック: 石を置く")
    print("・スペースキー: モード選択に戻る")
    print("・ESCキー: 終了")
    print("=" * 50)
    
    # AIの思考時間を制御するための変数
    ai_thinking_time = 500  # AIの思考時間（ミリ秒）
    last_ai_move_time = 0

    while True:
        # モード選択画面
        if show_mode_select:
            modo = draw_home_screen()
            analyzer = GomokuAnalyzer()
            game_over = False
            winner = None
            in_game = True
            show_mode_select = False
            last_ai_move_time = pygame.time.get_ticks()
            print(f"\n選択モード: {modo}")
            print("ゲーム開始！")
        
        # イベント処理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                
                elif event.key == pygame.K_SPACE:
                    # モード選択画面に戻る
                    show_mode_select = True
                    in_game = False
                    continue
            
            # プレイヤー対AIモードでのマウスクリック処理
            if in_game and not game_over and modo == "PvsAI" and analyzer.current_player == 1:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    
                    # 盤面内のクリック判定
                    if (MARGIN <= mx <= SCREEN_WIDTH - MARGIN and 
                        MARGIN <= my <= SCREEN_HEIGHT - INFO_AREA_HEIGHT - MARGIN):
                        
                        c = round((mx - MARGIN) / CELL_SIZE)
                        r = round((my - MARGIN) / CELL_SIZE)
                        
                        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                            if analyzer.put_stone(r, c, analyzer.current_player):
                                print(f"プレイヤー(黒): ({r}, {c}) に着手")
                                
                                if analyzer.check_win(r, c, analyzer.current_player):
                                    winner = analyzer.current_player
                                    game_over = True
                                    in_game = False
                                    print(f"プレイヤー(黒)の勝利！ ")
                                    print(f"総着手数: {len(analyzer.move_history)}手")
                                    print("スペースキーでモード選択に戻ります")
                                elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                                    winner = 0
                                    game_over = True
                                    in_game = False
                                    print("引き分け！")
                                    print("スペースキーでモード選択に戻ります")
                                else:
                                    # プレイヤーの手番終了、AIの手番に切り替え
                                    analyzer.current_player = 2
                                    last_ai_move_time = pygame.time.get_ticks()  # AIの思考開始時間
        
        if in_game and not game_over:
            # プレイヤー対AIモード - AIの手番
            if modo == "PvsAI" and analyzer.current_player == 2:
                current_time = pygame.time.get_ticks()
                if current_time - last_ai_move_time > 500:  # 500ms遅延
                    best_move = analyzer.get_best_move()
                    if best_move:
                        r, c = best_move
                        if analyzer.put_stone(r, c, analyzer.current_player):
                            print(f"AI(白): ({r}, {c}) に着手")
                            
                            if analyzer.check_win(r, c, analyzer.current_player):
                                winner = analyzer.current_player
                                game_over = True
                                in_game = False
                                print(f"AI(白)の勝利！ ")
                                print(f"総着手数: {len(analyzer.move_history)}手")
                                print("スペースキーでモード選択に戻ります")
                            elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                                winner = 0
                                game_over = True
                                in_game = False
                                print("引き分け！")
                                print("スペースキーでモード選択に戻ります")
                            else:
                                analyzer.current_player = 1  # プレイヤーの手番に戻す
                    
                    last_ai_move_time = current_time
            
            # AI対AIモード
            elif modo == "AIvsAI":
                current_time = pygame.time.get_ticks()
                
                # 一定時間ごとにAIが手を打つ
                if current_time - last_ai_move_time > ai_thinking_time:
                    best_move = analyzer.get_best_move()
                    if best_move:
                        r, c = best_move
                        if analyzer.put_stone(r, c, analyzer.current_player):
                            print(f"{'黒' if analyzer.current_player == 1 else '白'}(AI): ({r}, {c}) に着手")
                            
                            if analyzer.check_win(r, c, analyzer.current_player):
                                winner = analyzer.current_player
                                game_over = True
                                in_game = False
                                print(f" {'黒' if winner == 1 else '白'}の勝利！ ")
                                print(f"総着手数: {len(analyzer.move_history)}手")
                                print("スペースキーでモード選択に戻ります")
                            elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                                winner = 0
                                game_over = True
                                in_game = False
                                print("引き分け！")
                                print("スペースキーでモード選択に戻ります")
                            else:
                                analyzer.current_player = 2 if analyzer.current_player == 1 else 1
                    
                    last_ai_move_time = current_time
        
        # 描画
        draw_board(analyzer, game_over, winner, modo)
        pygame.display.flip()
        clock.tick(60)  # 60FPSに制限

if __name__ == "__main__":
    main()