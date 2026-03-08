import pygame
import sys
import os
import math
from engine import GomokuAnalyzer

# Pygame設定
CELL_SIZE = 40
MARGIN = 50
BOARD_SIZE = 15
SCREEN_WIDTH = CELL_SIZE * (BOARD_SIZE - 1) + MARGIN * 2
SCREEN_HEIGHT = SCREEN_WIDTH + 80
INFO_AREA_HEIGHT = 80

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("五目並べ AI解析シミュレーター - 九州大学芸術工学部 編入プロジェクト")

# 日本語フォントの設定
def get_japanese_font(size):
    """利用可能な日本語フォントを探す"""
    font_paths = [
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/yugothic.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
        "/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc",
        "/usr/share/fonts/truetype/takao-gothic/TakaoGothic.ttf",
    ]
    
    for path in font_paths:
        try:
            if os.path.exists(path):
                return pygame.font.Font(path, size)
        except:
            pass
    
    try:
        return pygame.font.SysFont("meiryo", size)
    except:
        return pygame.font.SysFont(None, size)

# フォントの初期化
font_small = get_japanese_font(14)
font_medium = get_japanese_font(18)
font_large = get_japanese_font(24)
font_title = get_japanese_font(28)


def draw_board(analyzer, game_over, winner, modo=None, best_move_for_display=None):
    """盤面と情報を描画（評価値表示付き）"""
    
    # 背景（グラデーション風）
    for y in range(SCREEN_HEIGHT):
        color_value = 220 - (y / SCREEN_HEIGHT * 20)
        pygame.draw.line(screen, (color_value, 179, 92), (0, y), (SCREEN_WIDTH, y))
    
    # 情報表示エリアのy座標
    info_y = SCREEN_HEIGHT - INFO_AREA_HEIGHT + 10
    
    # 盤面背景（木目調）
    board_bg = pygame.Rect(
        MARGIN - 15, MARGIN - 15,
        CELL_SIZE * (BOARD_SIZE - 1) + 30,
        CELL_SIZE * (BOARD_SIZE - 1) + 30
    )
    pygame.draw.rect(screen, (199, 155, 95), board_bg)
    pygame.draw.rect(screen, (150, 110, 70), board_bg, 3)
    
    # 罫線を描画
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
    
    # スコア計算
    scores = analyzer.evaluate_board()
    
    # 石と評価値の描画
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            x = MARGIN + c * CELL_SIZE
            y = MARGIN + r * CELL_SIZE
            
            # 黒石の描画
            if analyzer.board[r][c] == 1:
                pygame.draw.circle(screen, (30, 30, 30), (x+2, y+2), 16)
                pygame.draw.circle(screen, (20, 20, 20), (x, y), 16)
                pygame.draw.circle(screen, (100, 100, 100), (x, y), 16, 2)
            
            # 白石の描画
            elif analyzer.board[r][c] == 2:
                pygame.draw.circle(screen, (230, 230, 230), (x+2, y+2), 16)
                pygame.draw.circle(screen, (250, 250, 250), (x, y), 16)
                pygame.draw.circle(screen, (200, 200, 200), (x, y), 16, 2)
            
            # 空マスの評価値表示
            else:
                should_display_score = False
                if modo == "PvsAI" and analyzer.current_player == 2:
                    # PvsAI：AI（白）の手番
                    should_display_score = True
                elif modo == "AIvsAI":
                    # AIvsAI：常に表示
                    should_display_score = True
                elif modo == "AIvsHuman" and analyzer.current_player == 1:
                    # AIvsHuman：AI（黒）の手番
                    should_display_score = True
                
                if should_display_score:
                    score_value = scores[r][c]
                    
                    if score_value > 0:
                        # 対数スケールで正規化
                        log_score = min(100, max(1, int(math.log10(score_value + 1) * 20)))
                        
                        # スコアに応じた色
                        if log_score >= 90:
                            color = (255, 50, 50)      # 赤
                        elif log_score >= 70:
                            color = (255, 150, 50)     # 橙
                        elif log_score >= 50:
                            color = (255, 255, 50)     # 黄
                        elif log_score >= 30:
                            color = (50, 200, 50)      # 緑
                        elif log_score >= 10:
                            color = (100, 150, 255)    # 青
                        else:
                            color = (150, 150, 150)    # 灰
                        
                        # 背景円（半透明）
                        circle_surface = pygame.Surface((28, 28), pygame.SRCALPHA)
                        pygame.draw.circle(circle_surface, (255, 255, 255, 200), (14, 14), 14)
                        screen.blit(circle_surface, (x-14, y-14))
                        
                        # スコア数値表示
                        score_text = font_small.render(str(log_score), True, color)
                        text_rect = score_text.get_rect(center=(x, y))
                        screen.blit(score_text, text_rect)
    
    # AIの最善手をハイライト
    if best_move_for_display and not game_over:
        br, bc = best_move_for_display
        if analyzer.board[br][bc] == 0:
            bx = MARGIN + bc * CELL_SIZE
            by = MARGIN + br * CELL_SIZE
            pulse = (pygame.time.get_ticks() // 300) % 2
            if pulse:
                pygame.draw.circle(screen, (255, 0, 0), (bx, by), 20, 3)
    
    # 情報表示エリア（下部）
    info_rect = pygame.Rect(0, SCREEN_HEIGHT - INFO_AREA_HEIGHT, SCREEN_WIDTH, INFO_AREA_HEIGHT)
    pygame.draw.rect(screen, (240, 240, 240), info_rect)
    pygame.draw.line(screen, (180, 180, 180), (0, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 
                    (SCREEN_WIDTH, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 2)
    
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
        "スペース: モード選択へ",
        "ESC: 終了"
    ]
    
    for i, text in enumerate(controls):
        control_text = font_small.render(text, True, (80, 80, 80))
        screen.blit(control_text, (SCREEN_WIDTH - 200, info_y + i * 20))
    
    # 評価値の凡例
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
    
    # ゲーム終了時の表示
    if game_over and winner is not None:
        # 半透明オーバーレイ
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # 勝利メッセージ
        if winner == 0:
            win_text = font_large.render("引き分け！", True, (255, 255, 0))
        else:
            winner_color = "黒" if winner == 1 else "白"
            win_text = font_large.render(f"{winner_color}の勝利！", True, (255, 255, 0))
        
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
    """ホーム画面の描画（3ボタン）"""
    screen.fill((200, 220, 255))

    btn_p_vs_ai = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 40, 200, 50)
    btn_ai_vs_ai = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 30, 200, 50)
    btn_ai_vs_human = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 100, 200, 50)
    
    # タイトル
    title = font_title.render("五目並べ AI解析シミュレーター", True, (0, 60, 120))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 4 - 60))
    
    # サブタイトル
    subtitle = font_medium.render("九州大学芸術工学部 編入プロジェクト", True, (0, 0, 0))
    screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, SCREEN_HEIGHT // 4))

    # ボタン1：人間 vs AI（人間先手）
    pygame.draw.rect(screen, (100, 150, 255), btn_p_vs_ai)
    txt1 = font_medium.render("人間 vs AI (人間先手)", True, (255, 255, 255))
    screen.blit(txt1, (btn_p_vs_ai.centerx - txt1.get_width() // 2, btn_p_vs_ai.centery - txt1.get_height() // 2))

    # ボタン2：AI vs AI
    pygame.draw.rect(screen, (100, 200, 150), btn_ai_vs_ai)
    txt2 = font_medium.render("AI vs AI", True, (255, 255, 255))
    screen.blit(txt2, (btn_ai_vs_ai.centerx - txt2.get_width() // 2, btn_ai_vs_ai.centery - txt2.get_height() // 2))

    # ボタン3：AI vs Human（AI先手）
    pygame.draw.rect(screen, (200, 150, 100), btn_ai_vs_human)
    txt3 = font_medium.render("AI vs 人間 (AI先手)", True, (255, 255, 255))
    screen.blit(txt3, (btn_ai_vs_human.centerx - txt3.get_width() // 2, btn_ai_vs_human.centery - txt3.get_height() // 2))

    pygame.display.flip()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                
                if btn_p_vs_ai.collidepoint(pos):
                    return "PvsAI"
                elif btn_ai_vs_ai.collidepoint(pos):
                    return "AIvsAI"
                elif btn_ai_vs_human.collidepoint(pos):
                    return "AIvsHuman"


def main():
    """メインゲームループ"""
    analyzer = GomokuAnalyzer()
    game_over = False
    winner = None
    modo = None
    in_game = False
    show_mode_select = True

    clock = pygame.time.Clock()
    
    # AIの思考時間設定
    ai_thinking_time = 500
    last_ai_move_time = 0
    best_move_for_display = None

    print("=" * 50)
    print("五目並べ AI解析シミュレーター")
    print("=" * 50)
    
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
            best_move_for_display = None
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
                    show_mode_select = True
                    in_game = False
                    continue
            
            # プレイヤーのクリック処理
            if in_game and not game_over and event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                
                # 盤面内のクリック判定
                if (MARGIN <= mx <= SCREEN_WIDTH - MARGIN and 
                    MARGIN <= my <= SCREEN_HEIGHT - INFO_AREA_HEIGHT - MARGIN):
                    
                    c = round((mx - MARGIN) / CELL_SIZE)
                    r = round((my - MARGIN) / CELL_SIZE)
                    
                    if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                        # モードに応じて人間の手番か判定
                        human_turn = False
                        if modo == "PvsAI" and analyzer.current_player == 1:
                            human_turn = True
                        elif modo == "AIvsHuman" and analyzer.current_player == 2:
                            human_turn = True
                        
                        if human_turn and analyzer.put_stone(r, c, analyzer.current_player):
                            print(f"人間 ({'黒' if analyzer.current_player == 1 else '白'}): ({r}, {c}) に着手")
                            
                            if analyzer.check_win(r, c, analyzer.current_player):
                                winner = analyzer.current_player
                                game_over = True
                                in_game = False
                                print(f"人間の勝利！")
                            elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                                winner = 0
                                game_over = True
                                in_game = False
                                print("引き分け！")
                            else:
                                # 手番交代
                                analyzer.current_player = 3 - analyzer.current_player
                                last_ai_move_time = pygame.time.get_ticks()
                                best_move_for_display = None
        
        # ゲームロジック（AIのターン処理）
        if in_game and not game_over:
            current_time = pygame.time.get_ticks()
            
            # AIが手番かどうかの判定
            ai_turn = False
            if modo == "PvsAI" and analyzer.current_player == 2:
                ai_turn = True
            elif modo == "AIvsAI":
                ai_turn = True  # AIvsAIでは常にどちらかのAIが手番
            elif modo == "AIvsHuman" and analyzer.current_player == 1:
                ai_turn = True
            
            if ai_turn and current_time - last_ai_move_time > 500:
                # AIが手を打つ
                best_move = analyzer.get_best_move()
                best_move_for_display = best_move
                
                if best_move:
                    r, c = best_move
                    stone_player = analyzer.current_player
                    
                    if analyzer.put_stone(r, c, stone_player):
                        player_name = "黒" if stone_player == 1 else "白"
                        print(f"{player_name}(AI): ({r}, {c}) に着手")
                        
                        if analyzer.check_win(r, c, stone_player):
                            winner = stone_player
                            game_over = True
                            in_game = False
                            print(f"{player_name}の勝利！")
                        elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                            winner = 0
                            game_over = True
                            in_game = False
                            print("引き分け！")
                        else:
                            # 手番交代
                            analyzer.current_player = 3 - analyzer.current_player
                            best_move_for_display = None
                
                last_ai_move_time = current_time
        
        # 描画
        draw_board(analyzer, game_over, winner, modo, best_move_for_display)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()