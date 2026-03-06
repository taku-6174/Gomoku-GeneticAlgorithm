import pygame
import sys
import os
import math
import copy
from engine import GomokuAnalyzer

# ─────────────────────────────────────────────
#  Pygame 設定
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  engine.py の self.weights キーに対応した入力フィールド定義
#
#  quick_evaluate / evaluate_pattern_hierarchical で使われる主要キー:
#    five, open_four, dead_four, open_three, dead_three, open_two
#    defense_weight  ← 防御倍率（float 可）
#    fork_44, fork_43, fork_33
# ─────────────────────────────────────────────
WEIGHT_DEFS = [
    # ( 表示ラベル,             weightsキー,        デフォルト値 )
    ("五連       (five)",        "five",             100000),
    ("活四  (open_four)",        "open_four",         12000),
    ("眠四  (dead_four)",        "dead_four",          5000),
    ("活三 (open_three)",        "open_three",         1500),
    ("眠三 (dead_three)",        "dead_three",          200),
    ("活二   (open_two)",        "open_two",             50),
    ("防御係数 (def_weight)",    "defense_weight",      1.2),
    ("両四フォーク (fork_44)",   "fork_44",           15000),
    ("四三フォーク (fork_43)",   "fork_43",            8000),
    ("両三フォーク (fork_33)",   "fork_33",            3000),
]
NUM_WEIGHTS = len(WEIGHT_DEFS)


def make_default_fields():
    return [str(d) for _, _, d in WEIGHT_DEFS]


def apply_weights_to_analyzer(analyzer: GomokuAnalyzer, field_values: list):
    """field_values（文字列リスト）を float にパースして analyzer.weights に反映"""
    for i, (_, key, _) in enumerate(WEIGHT_DEFS):
        try:
            analyzer.weights[key] = float(field_values[i])
        except (ValueError, KeyError):
            pass   # 変換失敗はデフォルト値のまま


# ─────────────────────────────────────────────
#  重み入力画面
# ─────────────────────────────────────────────

def _box_rect(pi, wi, col_x, row_start_y, row_h):
    return pygame.Rect(col_x[pi], row_start_y + 20 + wi * row_h, 220, 26)


def draw_weight_input_screen(f_b, f_w, active, error_msg=""):
    screen.fill((228, 233, 255))

    title = font_title.render("進化個体 重み設定", True, (0, 60, 120))
    screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 18))

    sub = font_medium.render("個体A(黒) と 個体B(白) の評価重みを入力してください", True, (60, 60, 60))
    screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 56))

    col_x       = [SCREEN_WIDTH // 2 - 270, SCREEN_WIDTH // 2 + 50]
    row_start_y = 100
    row_h       = 46
    hdrs        = ["● 個体A（黒）", "● 個体B（白）"]
    hdr_colors  = [(30, 30, 30), (180, 50, 50)]

    for pi in range(2):
        hdr = font_medium.render(hdrs[pi], True, hdr_colors[pi])
        screen.blit(hdr, (col_x[pi], row_start_y - 22))

        fields = f_b if pi == 0 else f_w
        for wi in range(NUM_WEIGHTS):
            label, _, _ = WEIGHT_DEFS[wi]
            y = row_start_y + wi * row_h
            is_active = (active == (pi, wi))

            lbl = font_small.render(label, True, (50, 50, 50))
            screen.blit(lbl, (col_x[pi], y))

            box = _box_rect(pi, wi, col_x, row_start_y, row_h)
            bg  = (255, 255, 200) if is_active else (255, 255, 255)
            bdr = (80, 130, 255)  if is_active else (180, 180, 180)
            pygame.draw.rect(screen, bg,  box, border_radius=4)
            pygame.draw.rect(screen, bdr, box, 2, border_radius=4)

            val_surf = font_small.render(fields[wi] + ("|" if is_active else ""), True, (20, 20, 20))
            screen.blit(val_surf, (box.x + 5, box.y + 5))

    if error_msg:
        err = font_small.render(error_msg, True, (200, 0, 0))
        screen.blit(err, (SCREEN_WIDTH // 2 - err.get_width() // 2, SCREEN_HEIGHT - 105))

    btn = pygame.Rect(SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT - 90, 240, 44)
    pygame.draw.rect(screen, (60, 180, 100), btn, border_radius=8)
    bt = font_medium.render("対戦開始！", True, (255, 255, 255))
    screen.blit(bt, (btn.centerx - bt.get_width() // 2, btn.centery - bt.get_height() // 2))

    hint = font_small.render(
        "クリックで選択  /  Tab: 次フィールド  /  Enter: 対戦開始  /  Esc: 戻る",
        True, (100, 100, 100))
    screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 50))

    pygame.display.flip()
    return btn, col_x, row_start_y, row_h


def run_weight_input_screen():
    f_b       = make_default_fields()
    f_w       = make_default_fields()
    active    = (0, 0)
    error_msg = ""
    tab_order = [(pi, wi) for wi in range(NUM_WEIGHTS) for pi in range(2)]

    while True:
        btn, col_x, row_start_y, row_h = draw_weight_input_screen(f_b, f_w, active, error_msg)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if event.type == pygame.KEYDOWN:
                error_msg = ""
                if event.key == pygame.K_ESCAPE:
                    return None
                elif event.key == pygame.K_RETURN:
                    try:
                        [float(v) for v in f_b + f_w]
                        return f_b, f_w
                    except ValueError:
                        error_msg = "※ 数値のみ入力してください"
                elif event.key == pygame.K_TAB:
                    if active in tab_order:
                        idx = tab_order.index(active)
                        active = tab_order[(idx + 1) % len(tab_order)]
                    else:
                        active = tab_order[0]
                elif active is not None:
                    pi, wi = active
                    fields = f_b if pi == 0 else f_w
                    if event.key == pygame.K_BACKSPACE:
                        fields[wi] = fields[wi][:-1]
                    elif event.unicode in "0123456789.-":
                        fields[wi] += event.unicode

            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                if btn.collidepoint(pos):
                    try:
                        [float(v) for v in f_b + f_w]
                        return f_b, f_w
                    except ValueError:
                        error_msg = "※ 数値のみ入力してください"
                    continue
                for pi in range(2):
                    for wi in range(NUM_WEIGHTS):
                        if _box_rect(pi, wi, col_x, row_start_y, row_h).collidepoint(pos):
                            active = (pi, wi)


# ─────────────────────────────────────────────
#  盤面描画
# ─────────────────────────────────────────────

def draw_board(analyzer, game_over, winner, modo=None,
               best_move_for_display=None, fields_b=None, fields_w=None):

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

    ir = pygame.Rect(0, SCREEN_HEIGHT - INFO_AREA_HEIGHT, SCREEN_WIDTH, INFO_AREA_HEIGHT)
    pygame.draw.rect(screen, (240, 240, 240), ir)
    pygame.draw.line(screen, (180, 180, 180),
                     (0, SCREEN_HEIGHT - INFO_AREA_HEIGHT),
                     (SCREEN_WIDTH, SCREEN_HEIGHT - INFO_AREA_HEIGHT), 2)

    title_surf = font_title.render("五目並べ AI解析ツール", True, (0, 60, 120))
    screen.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, 5))

    # EvoVsEvo 専用 情報表示
    if modo == "EvoVsEvo" and fields_b and fields_w:
        cur    = analyzer.current_player
        label  = "個体A（黒）" if cur == 1 else "個体B（白）"
        color  = (20, 20, 20)  if cur == 1 else (160, 40, 40)
        fields = fields_b if cur == 1 else fields_w

        pt = font_medium.render(f"手番: {label}", True, color)
        screen.blit(pt, (20, info_y))

        # 重みサマリー（五連・活四・活三・防御係数を表示）
        idx_map = [("五連", 0), ("活四", 1), ("活三", 3), ("防御", 6)]
        summary = "  ".join(f"{n}:{fields[i]}" for n, i in idx_map)
        ss = font_small.render(summary, True, (60, 60, 60))
        screen.blit(ss, (20, info_y + 25))
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

    note = font_small.render("重みを個別設定して進化個体同士を対戦させる", True, (120, 60, 160))
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
#  盤面同期（EvoVsEvo 用）
# ─────────────────────────────────────────────

def sync_board(src: GomokuAnalyzer, dst: GomokuAnalyzer):
    """src の盤面・履歴・手番を dst にコピー"""
    dst.board          = src.board.copy()
    dst.move_history   = copy.copy(src.move_history)
    dst.current_player = src.current_player


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
    fields_b       = None
    fields_w       = None

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
                result = run_weight_input_screen()
                if result is None:
                    continue   # キャンセル → ホーム再表示
                fields_b, fields_w = result

                # 個体を生成して重みを注入
                analyzer_black = GomokuAnalyzer()
                analyzer_white = GomokuAnalyzer()
                apply_weights_to_analyzer(analyzer_black, fields_b)
                apply_weights_to_analyzer(analyzer_white, fields_w)

                # 共有 analyzer は描画・着手管理のみ担当（重みは不問）
                analyzer = GomokuAnalyzer()

                print("\n[EvoVsEvo] 重み設定:")
                for i, (lbl, key, _) in enumerate(WEIGHT_DEFS):
                    print(f"  {key:20s}  個体A={fields_b[i]:>10}  個体B={fields_w[i]:>10}")
            else:
                analyzer       = GomokuAnalyzer()
                analyzer_black = None
                analyzer_white = None
                fields_b       = None
                fields_w       = None

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
                    # 現在の盤面を手番側の個体に同期 → その個体で思考
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
        draw_board(analyzer, game_over, winner, modo,
                   best_move_for_display, fields_b, fields_w)
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
