import pygame
import sys
import os
import math
import copy
from engine import GomokuAnalyzer

# ============================================================
#  ★★★ 進化個体の重み設定 ★★★
#  EvoVsEvo モード用。ここを書き換えて対戦させる。
#  キーは engine.py の GomokuAnalyzer.weights と同じ。
# ============================================================

WEIGHTS_A = {   # 個体A（黒）
   "five": 141884.30845660297,
    "guaranteed_four": 75493.05468189875,
    "open_four": 11842.691377980767,
    "dead_four": 1388.7012068175336,
    "open_three": 2586.28549971406,
    "dead_three": 200.67032230114344,
    "open_two": 20.941799463498594,
    "fork_44": 7230.454135865415,
    "fork_43": 3303.116845603808,
    "fork_33": 1363.1920075485698,
    "both_open_threats": 31599.875771517913,
    "defense_weight": 0.9457253075005674,
    "def_open_four": 127608.39107361011,
    "def_open_three": 3208.263031972154,
    "def_dead_three": 107.16019258978189,
    "def_multiple_threats": 5365.7740532704465,
    "center_bonus": 80.68683520128805,
    "continuity_weight": 77.85109027389922,
    "mcts_simulation_depth": 2
}

WEIGHTS_B = {   # 個体B（白）― ここを変えて差をつける
    'five': 100000,
            'guaranteed_four': 50000,
            'open_four': 12000,
            'dead_four': 5000,
            'open_three': 1500,
            'dead_three': 200,
            'open_two': 50,
            
            # === フォーク・両見 ===
            'fork_44': 15000,
            'fork_43': 8000,
            'fork_33': 3000,
            'both_open_threats': 10000,  # 新規：両見検出ボーナス
            
            # === 防御関連 ===
            'defense_weight': 1.2,
            'def_open_four': 50000,      # 相手の活四防ぐ
            'def_open_three': 2000,      # 相手の活三防ぐ
            'def_dead_three': 300,
            'def_multiple_threats': 15000,  # 新規：複数脅威同時ブロック
            
            # === その他 ===
            'center_bonus': 100,
            'continuity_weight': 100,
            'mcts_simulation_depth': 3,
}

# ============================================================

# Pygame設定
CELL_SIZE = 40
MARGIN = 50
BOARD_SIZE = 15
SCREEN_WIDTH  = CELL_SIZE * (BOARD_SIZE - 1) + MARGIN * 2
SCREEN_HEIGHT = SCREEN_WIDTH + 80
INFO_AREA_HEIGHT = 80

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("五目並べ AI解析シミュレーター - 九州大学芸術工学部 編入プロジェクト")

def get_japanese_font(size):
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

font_small  = get_japanese_font(14)
font_medium = get_japanese_font(18)
font_large  = get_japanese_font(24)
font_title  = get_japanese_font(28)


def apply_weights(analyzer: GomokuAnalyzer, weights: dict):
    """weights 辞書を analyzer.weights に上書きする"""
    for key, val in weights.items():
        if key in analyzer.weights:
            analyzer.weights[key] = val


def sync_board(src: GomokuAnalyzer, dst: GomokuAnalyzer):
    """src の盤面・履歴・手番を dst にコピー"""
    dst.board          = src.board.copy()
    dst.move_history   = copy.copy(src.move_history)
    dst.current_player = src.current_player


# ─────────────────────────────────────────────
#  盤面描画
# ─────────────────────────────────────────────

def draw_board(analyzer, game_over, winner, modo=None, best_move_for_display=None):

    for y in range(SCREEN_HEIGHT):
        cv = 220 - (y / SCREEN_HEIGHT * 20)
        pygame.draw.line(screen, (cv, 179, 92), (0, y), (SCREEN_WIDTH, y))

    info_y = SCREEN_HEIGHT - INFO_AREA_HEIGHT + 10

    board_bg = pygame.Rect(MARGIN - 15, MARGIN - 15,
                           CELL_SIZE * (BOARD_SIZE - 1) + 30,
                           CELL_SIZE * (BOARD_SIZE - 1) + 30)
    pygame.draw.rect(screen, (199, 155, 95), board_bg)
    pygame.draw.rect(screen, (150, 110, 70), board_bg, 3)

    for i in range(BOARD_SIZE):
        pygame.draw.line(screen, (0, 0, 0),
                         (MARGIN, MARGIN + i * CELL_SIZE),
                         (SCREEN_WIDTH - MARGIN, MARGIN + i * CELL_SIZE), 2)
        pygame.draw.line(screen, (0, 0, 0),
                         (MARGIN + i * CELL_SIZE, MARGIN),
                         (MARGIN + i * CELL_SIZE, SCREEN_HEIGHT - INFO_AREA_HEIGHT - MARGIN), 2)

    for sr, sc in [(3,3),(3,11),(7,7),(11,3),(11,11)]:
        pygame.draw.circle(screen, (0, 0, 0),
                           (MARGIN + sc * CELL_SIZE, MARGIN + sr * CELL_SIZE), 5)

    scores = analyzer.evaluate_board()

    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            x = MARGIN + c * CELL_SIZE
            y = MARGIN + r * CELL_SIZE

            if analyzer.board[r][c] == 1:
                pygame.draw.circle(screen, (30, 30, 30),    (x+2, y+2), 16)
                pygame.draw.circle(screen, (20, 20, 20),    (x, y),     16)
                pygame.draw.circle(screen, (100, 100, 100), (x, y),     16, 2)
            elif analyzer.board[r][c] == 2:
                pygame.draw.circle(screen, (230, 230, 230), (x+2, y+2), 16)
                pygame.draw.circle(screen, (250, 250, 250), (x, y),     16)
                pygame.draw.circle(screen, (200, 200, 200), (x, y),     16, 2)
            else:
                show = (
                    (modo == "PvsAI"     and analyzer.current_player == 2) or
                    (modo in ("AIvsAI", "EvoVsEvo"))                        or
                    (modo == "AIvsHuman" and analyzer.current_player == 1)
                )
                if show:
                    sv = scores[r][c]
                    if sv > 0:
                        ls = min(100, max(1, int(math.log10(sv + 1) * 20)))
                        if   ls >= 90: col = (255,  50,  50)
                        elif ls >= 70: col = (255, 150,  50)
                        elif ls >= 50: col = (255, 255,  50)
                        elif ls >= 30: col = ( 50, 200,  50)
                        elif ls >= 10: col = (100, 150, 255)
                        else:          col = (150, 150, 150)
                        cs = pygame.Surface((28, 28), pygame.SRCALPHA)
                        pygame.draw.circle(cs, (255, 255, 255, 200), (14, 14), 14)
                        screen.blit(cs, (x-14, y-14))
                        st = font_small.render(str(ls), True, col)
                        screen.blit(st, st.get_rect(center=(x, y)))

    if best_move_for_display and not game_over:
        br, bc = best_move_for_display
        if analyzer.board[br][bc] == 0:
            if (pygame.time.get_ticks() // 300) % 2:
                pygame.draw.circle(screen, (255, 0, 0),
                                   (MARGIN + bc * CELL_SIZE, MARGIN + br * CELL_SIZE), 20, 3)

    # 情報エリア
    ir = pygame.Rect(0, SCREEN_HEIGHT - INFO_AREA_HEIGHT, SCREEN_WIDTH, INFO_AREA_HEIGHT)
    pygame.draw.rect(screen, (240, 240, 240), ir)
    pygame.draw.line(screen, (180, 180, 180),
                     (0, SCREEN_HEIGHT - INFO_AREA_HEIGHT),
                     (SCREEN_WIDTH, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 2)

    title_surf = font_title.render("五目並べ AI解析ツール", True, (0, 60, 120))
    screen.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, 5))

    # EvoVsEvo 専用：手番の個体名を表示
    if modo == "EvoVsEvo":
        cur   = analyzer.current_player
        label = "個体A（黒）" if cur == 1 else "個体B（白）"
        color = (20, 20, 20) if cur == 1 else (160, 40, 40)
        pt = font_medium.render(f"手番: {label}", True, color)
        screen.blit(pt, (20, info_y))
        ct = font_small.render(f"着手数: {len(analyzer.move_history)}", True, (0, 0, 0))
        screen.blit(ct, (20, info_y + 25))
    else:
        pt = font_medium.render(
            f"現在の手番: {'黒' if analyzer.current_player == 1 else '白'}", True, (0, 0, 0))
        screen.blit(pt, (20, info_y))
        ct = font_small.render(f"着手数: {len(analyzer.move_history)}", True, (0, 0, 0))
        screen.blit(ct, (20, info_y + 25))

    for i, t in enumerate(["【操作方法】", "スペース: モード選択へ", "ESC: 終了"]):
        screen.blit(font_small.render(t, True, (80, 80, 80)), (SCREEN_WIDTH - 200, info_y + i * 20))

    for i, (t, c) in enumerate([
        ("赤(90-100): 勝ち確定", (255,  50,  50)),
        ("橙(70-89): 強力",      (255, 150,  50)),
        ("黄(50-69): 良い",      (255, 255,  50)),
        ("緑(30-49): 普通",      ( 50, 200,  50)),
        ("青(10-29): 悪い",      (100, 150, 255)),
        ("灰(1-9): 最悪",        (150, 150, 150)),
    ]):
        screen.blit(font_small.render(t, True, c), (SCREEN_WIDTH - 250, info_y + 40 + i * 18))

    if game_over and winner is not None:
        ov = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        screen.blit(ov, (0, 0))

        if winner == 0:
            msg = "引き分け！"
        elif modo == "EvoVsEvo":
            msg = f"{'個体A（黒）' if winner == 1 else '個体B（白）'}の勝利！"
        else:
            msg = f"{'黒' if winner == 1 else '白'}の勝利！"

        wt = font_large.render(msg, True, (255, 255, 0))
        screen.blit(wt, wt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30)))
        rt = font_medium.render("スペースキーで新しいゲームを開始", True, (255, 255, 255))
        screen.blit(rt, rt.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20)))
        tm = font_small.render(f"総着手数: {len(analyzer.move_history)}手", True, (200, 200, 200))
        screen.blit(tm, tm.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50)))


# ─────────────────────────────────────────────
#  ホーム画面
# ─────────────────────────────────────────────

def draw_home_screen():
    screen.fill((200, 220, 255))

    bw = 240
    bx = SCREEN_WIDTH // 2 - bw // 2
    btns = [
        pygame.Rect(bx, SCREEN_HEIGHT // 2 - 100, bw, 46),
        pygame.Rect(bx, SCREEN_HEIGHT // 2 -  40, bw, 46),
        pygame.Rect(bx, SCREEN_HEIGHT // 2 +  20, bw, 46),
        pygame.Rect(bx, SCREEN_HEIGHT // 2 +  95, bw, 50),
    ]
    labels  = ["人間 vs AI（人間先手）", "AI vs AI（同一個体）",
               "AI vs 人間（AI先手）",   "🧬 異なる個体で対決"]
    colors  = [(100,150,255),(100,200,150),(200,150,100),(140,70,200)]
    results = ["PvsAI","AIvsAI","AIvsHuman","EvoVsEvo"]

    title = font_title.render("五目並べ AI解析シミュレーター", True, (0, 60, 120))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 4 - 60))
    sub = font_medium.render("九州大学芸術工学部 編入プロジェクト", True, (0, 0, 0))
    screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, SCREEN_HEIGHT // 4))

    for btn, lbl, col in zip(btns, labels, colors):
        pygame.draw.rect(screen, col, btn, border_radius=8)
        s = font_medium.render(lbl, True, (255, 255, 255))
        screen.blit(s, (btn.centerx - s.get_width()//2, btn.centery - s.get_height()//2))

    note = font_small.render("WEIGHTS_A / WEIGHTS_B をコードで設定して対戦", True, (120, 60, 160))
    screen.blit(note, (SCREEN_WIDTH // 2 - note.get_width() // 2, btns[3].bottom + 5))

    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                for btn, res in zip(btns, results):
                    if btn.collidepoint(pos):
                        return res


# ─────────────────────────────────────────────
#  メインループ
# ─────────────────────────────────────────────

def main():
    game_over        = False
    winner           = None
    modo             = None
    in_game          = False
    show_mode_select = True

    analyzer       = GomokuAnalyzer()
    analyzer_black = None
    analyzer_white = None

    clock             = pygame.time.Clock()
    last_ai_move_time = 0
    best_move_for_display = None

    print("=" * 50)
    print("五目並べ AI解析シミュレーター")
    print("=" * 50)

    while True:

        # ── モード選択 ──────────────────────────
        if show_mode_select:
            modo = draw_home_screen()

            if modo == "EvoVsEvo":
                analyzer_black = GomokuAnalyzer()
                analyzer_white = GomokuAnalyzer()
                apply_weights(analyzer_black, WEIGHTS_A)
                apply_weights(analyzer_white, WEIGHTS_B)
                analyzer = GomokuAnalyzer()   # 描画・着手管理用（重みは不問）

                print("\n[EvoVsEvo] 重み設定:")
                print(f"  個体A(黒): {WEIGHTS_A}")
                print(f"  個体B(白): {WEIGHTS_B}")
            else:
                analyzer       = GomokuAnalyzer()
                analyzer_black = None
                analyzer_white = None

            game_over             = False
            winner                = None
            in_game               = True
            show_mode_select      = False
            last_ai_move_time     = pygame.time.get_ticks()
            best_move_for_display = None
            print(f"\n選択モード: {modo}\nゲーム開始！")

        # ── イベント処理 ────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                elif event.key == pygame.K_SPACE:
                    show_mode_select = True
                    in_game          = False
                    continue

            if in_game and not game_over and event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if (MARGIN <= mx <= SCREEN_WIDTH - MARGIN and
                        MARGIN <= my <= SCREEN_HEIGHT - INFO_AREA_HEIGHT - MARGIN):
                    c = round((mx - MARGIN) / CELL_SIZE)
                    r = round((my - MARGIN) / CELL_SIZE)
                    if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                        human_turn = (
                            (modo == "PvsAI"     and analyzer.current_player == 1) or
                            (modo == "AIvsHuman" and analyzer.current_player == 2)
                        )
                        if human_turn and analyzer.put_stone(r, c, analyzer.current_player):
                            print(f"人間 ({'黒' if analyzer.current_player == 1 else '白'}): ({r}, {c})")
                            if analyzer.check_win(r, c, analyzer.current_player):
                                winner, game_over, in_game = analyzer.current_player, True, False
                                print("人間の勝利！")
                            elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                                winner, game_over, in_game = 0, True, False
                                print("引き分け！")
                            else:
                                analyzer.current_player = 3 - analyzer.current_player
                                last_ai_move_time        = pygame.time.get_ticks()
                                best_move_for_display    = None

        # ── AI のターン ──────────────────────────
        if in_game and not game_over:
            current_time = pygame.time.get_ticks()

            ai_turn = (
                (modo == "PvsAI"     and analyzer.current_player == 2) or
                (modo == "AIvsAI")                                       or
                (modo == "AIvsHuman" and analyzer.current_player == 1) or
                (modo == "EvoVsEvo")
            )

            if ai_turn and current_time - last_ai_move_time > 500:

                if modo == "EvoVsEvo":
                    if analyzer.current_player == 1:
                        sync_board(analyzer, analyzer_black)
                        analyzer_black.current_player = 1
                        best_move    = analyzer_black.get_best_move()
                        acting_label = "個体A（黒）"
                    else:
                        sync_board(analyzer, analyzer_white)
                        analyzer_white.current_player = 2
                        best_move    = analyzer_white.get_best_move()
                        acting_label = "個体B（白）"
                else:
                    best_move    = analyzer.get_best_move()
                    acting_label = "黒" if analyzer.current_player == 1 else "白"

                best_move_for_display = best_move

                if best_move:
                    r, c         = best_move
                    stone_player = analyzer.current_player
                    if analyzer.put_stone(r, c, stone_player):
                        print(f"{acting_label}(AI): ({r}, {c}) に着手")
                        if analyzer.check_win(r, c, stone_player):
                            winner, game_over, in_game = stone_player, True, False
                            print(f"{acting_label}の勝利！")
                        elif len(analyzer.move_history) == BOARD_SIZE * BOARD_SIZE:
                            winner, game_over, in_game = 0, True, False
                            print("引き分け！")
                        else:
                            analyzer.current_player = 3 - analyzer.current_player
                            best_move_for_display   = None

                last_ai_move_time = current_time

        # ── 描画 ────────────────────────────────
        draw_board(analyzer, game_over, winner, modo, best_move_for_display)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
