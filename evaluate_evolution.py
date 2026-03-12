# evaluate_evolution.py
import json
from concurrent.futures import ProcessPoolExecutor
from ga_manager import Individual, play_match_worker, REFERENCE_WEIGHTS
from engine import GomokuAnalyzer

def main():
    # 初期個体
    default_ind = Individual(weights=REFERENCE_WEIGHTS.copy())

    # 進化個体（足りないキーはREFERENCE_WEIGHTSで自動補完）
    with open("initial_weights.txt", "r") as f:
        loaded = json.load(f)
    best = {**REFERENCE_WEIGHTS, **loaded}  # 足りないキーを初期個体の重みで補完
    best_ind = Individual(weights=best)

    print("進化個体と初期個体の対戦を開始...")

    tasks = []
    TOTAL_GAMES = 100
    DEPTH = 3

    for i in range(TOTAL_GAMES):
        if i % 2 == 0:
            tasks.append((best_ind.analyzer.weights, default_ind.analyzer.weights, DEPTH, 1))
        else:
            tasks.append((default_ind.analyzer.weights, best_ind.analyzer.weights, DEPTH, 1))

    print(f"{len(tasks)}試合を並列実行中... (depth={DEPTH})")
    with ProcessPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(play_match_worker, tasks))

    best_first_win  = 0
    best_second_win = 0
    def_first_win   = 0
    def_second_win  = 0
    draw            = 0

    for i, winner in enumerate(results):
        if i % 2 == 0:
            if winner == 1:   best_first_win += 1
            elif winner == 2: def_second_win += 1
            else:             draw += 1
        else:
            if winner == 1:   def_first_win += 1
            elif winner == 2: best_second_win += 1
            else:             draw += 1

    GAMES_PER_SIDE = TOTAL_GAMES // 2
    best_total = best_first_win + best_second_win
    def_total  = def_first_win  + def_second_win

    print("\n========== 対戦結果 ==========")
    print(f"総試合数: {TOTAL_GAMES}  (先手{GAMES_PER_SIDE}試合 / 後手{GAMES_PER_SIDE}試合)")
    print()
    print(f"【進化個体】")
    print(f"  先手勝利: {best_first_win} / {GAMES_PER_SIDE} ({best_first_win / GAMES_PER_SIDE * 100:.1f}%)")
    print(f"  後手勝利: {best_second_win} / {GAMES_PER_SIDE} ({best_second_win / GAMES_PER_SIDE * 100:.1f}%)")
    print(f"  合計勝利: {best_total} / {TOTAL_GAMES} ({best_total / TOTAL_GAMES * 100:.1f}%)")
    print()
    print(f"【初期個体】")
    print(f"  先手勝利: {def_first_win} / {GAMES_PER_SIDE} ({def_first_win / GAMES_PER_SIDE * 100:.1f}%)")
    print(f"  後手勝利: {def_second_win} / {GAMES_PER_SIDE} ({def_second_win / GAMES_PER_SIDE * 100:.1f}%)")
    print(f"  合計勝利: {def_total} / {TOTAL_GAMES} ({def_total / TOTAL_GAMES * 100:.1f}%)")
    print()
    print(f"【引き分け】: {draw} / {TOTAL_GAMES} ({draw / TOTAL_GAMES * 100:.1f}%)")
    print("==============================")

if __name__ == "__main__":
    main()
