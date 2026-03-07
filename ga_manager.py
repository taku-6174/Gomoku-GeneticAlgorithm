import random
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from engine import GomokuAnalyzer
import matplotlib.pyplot as plt
import os
import time
import csv

# ============================================================
# 固定基準個体の重み（ver6のデフォルト重みそのまま）
# 毎世代必ずこれと対戦 → 絶対的な強さを測る
# ============================================================
REFERENCE_WEIGHTS = {
    'five':             100000,
    'open_four':         12000,
    'dead_four':          5000,
    'open_three':         1500,
    'dead_three':          200,
    'open_two':             50,
    'defense_weight':      1.2,
    'def_open_four':     50000,
    'def_open_three':     2000,
    'def_dead_three':      300,
    'fork_44':           15000,
    'fork_43':            8000,
    'fork_33':            3000,
    'center_bonus':        100,
    'continuity_weight':   100,
}

# 探索深さは固定（GAで変化させない）
FIXED_DEPTH = 3  # depth=3固定（重みの差がゲームに出やすくなる）


# ============================================================
# 対戦ワーカー（並列処理用）
# 個体は常に w1 = player1 で固定
# ============================================================
def play_match_worker(args):
    w1, w2, depth, start_player = args
    board = GomokuAnalyzer()
    board.board.fill(0)
    board.move_history = []

    weights = [None, w1, w2]

    current_turn = start_player
    for _ in range(15 * 15):
        board.weights = weights[current_turn]
        board.current_player = current_turn
        r, c = board.get_best_move(depth_limit=depth)

        if r is not None:
            board.put_stone(r, c, current_turn)
            if board.check_win(r, c, current_turn):
                return current_turn  # 勝者のプレイヤー番号を返す
        else:
            return 0  # 引き分け
        current_turn = 3 - current_turn
    return 0


# ============================================================
# 個体クラス
# ============================================================
class Individual:
    def __init__(self, weights=None):
        self.analyzer = GomokuAnalyzer()
        if weights:
            self.analyzer.weights = weights.copy()
        else:
            self.randomize_weights()
        self.fitness = 0.0

    def randomize_weights(self):
        """初期重みに対して加算的にランダム化"""
        for key in self.analyzer.weights:
            if key == 'defense_weight':
                self.analyzer.weights[key] = random.uniform(0.8, 2.0)
            else:
                self.analyzer.weights[key] += random.uniform(-100, 100)
                self.analyzer.weights[key] = max(1, self.analyzer.weights[key])

    def mutate(self, mutation_rate=0.2, mutation_strength=200):
        """突然変異"""
        for key in self.analyzer.weights:
            if random.random() < mutation_rate:
                if key == 'defense_weight':
                    self.analyzer.weights[key] += random.uniform(-0.2, 0.2)
                    self.analyzer.weights[key] = max(0.5, min(3.0, self.analyzer.weights[key]))
                else:
                    self.analyzer.weights[key] += random.uniform(-mutation_strength, mutation_strength)
                    self.analyzer.weights[key] = max(1, self.analyzer.weights[key])


# ============================================================
# 世代クラス
# ============================================================
class Generation:
    def __init__(self, size=12):
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1
        self.hall_of_fame = []  # 歴代最強上位3体

    def evaluate_all(self):
        print(f"第 {self.generation_number} 世代の評価中...")

        tasks = []
        task_owner = []

        for idx, ind in enumerate(self.individuals):
            # 対戦相手リスト
            opponents = [REFERENCE_WEIGHTS] * 3  # 基準個体×6

            # Hall of Fame 上位2体
            if self.hall_of_fame:
                opponents.extend(self.hall_of_fame[:2])

            # 仲間からランダムに6体
            others = [i.analyzer.weights for i in self.individuals if i != ind]
            if others:
                opponents.extend(random.sample(others, min(len(others), 3)))

            # 各相手と先手・後手を3回ずつ（6試合/相手）
            for opp_w in opponents:
                for start_player in [1, 2, 1, 2, 1, 2]:
                    tasks.append((ind.analyzer.weights, opp_w, FIXED_DEPTH, start_player))
                    task_owner.append(idx)

        print(f"  {len(tasks)} 試合を並列実行中...")
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            results = list(executor.map(play_match_worker, tasks))

        # fitnessリセット
        for ind in self.individuals:
            ind.fitness = 0.0

        # ★ fitnessバグ修正: 個体は常にplayer1(w1)なのでwinner==1で勝利
        for i, winner in enumerate(results):
            owner_idx = task_owner[i]
            if winner == 1:
                self.individuals[owner_idx].fitness += 1.0
            # 引き分け・負けは0点

        # 個体ごとの実際の試合数で正規化
        match_counts = [0] * len(self.individuals)
        for owner_idx in task_owner:
            match_counts[owner_idx] += 1

        for idx, ind in enumerate(self.individuals):
            if match_counts[idx] > 0:
                ind.fitness = (ind.fitness / match_counts[idx]) * 100

    def update_hall_of_fame(self):
        """歴代最強上位3体を保持"""
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        best_ind = self.individuals[0]

        hof_candidate = Individual(weights=best_ind.analyzer.weights.copy())
        hof_candidate.fitness = best_ind.fitness
        self.hall_of_fame.append(hof_candidate)

        self.hall_of_fame.sort(key=lambda x: x.fitness, reverse=True)
        self.hall_of_fame = self.hall_of_fame[:3]

        # HoFに渡すのは重みだけ（workerに渡すため）
        self._hof_weights = [h.analyzer.weights for h in self.hall_of_fame]

    def evolve(self):
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)

        # エリート保存（上位2体）
        next_gen = [Individual(weights=ind.analyzer.weights.copy())
                    for ind in self.individuals[:2]]

        # トーナメント選択 + 交叉 + 突然変異
        while len(next_gen) < len(self.individuals):
            p1 = self._tournament_selection(k=3)
            p2 = self._tournament_selection(k=3)

            child_weights = {}
            for key in p1.analyzer.weights:
                child_weights[key] = (p1.analyzer.weights[key]
                                      if random.random() < 0.5
                                      else p2.analyzer.weights[key])

            child = Individual(weights=child_weights)
            child.mutate()
            next_gen.append(child)

        self.individuals = next_gen
        self.generation_number += 1

    def _tournament_selection(self, k=3):
        selected = random.sample(self.individuals, min(k, len(self.individuals)))
        return max(selected, key=lambda x: x.fitness)


# ============================================================
# グラフ保存
# ============================================================
def save_fitness_graph(history, filename='evolution_graph.png'):
    gens      = [h['gen'] for h in history]
    best_fits = [h['best_fitness'] for h in history]
    avg_fits  = [h['avg_fitness'] for h in history]

    plt.figure(figsize=(12, 6))
    plt.plot(gens, best_fits, marker='o', label='Best Fitness',    color='blue',   linewidth=2)
    plt.plot(gens, avg_fits,  marker='s', label='Average Fitness', color='orange', linewidth=2)
    plt.title('AI Evolution Progress - Fitness', fontsize=14, fontweight='bold')
    plt.xlabel('Generation', fontsize=12)
    plt.ylabel('Fitness (Win %)', fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 100)
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    print(f"グラフを {filename} として保存しました。")
    plt.close()


# ============================================================
# メイン実行
# ============================================================
if __name__ == "__main__":
    multiprocessing.freeze_support()

    POPULATION_SIZE = 12
    GENERATIONS     = 30
    
    print("=" * 60)
    print("五目並べ AI 遺伝的アルゴリズム進化開始")
    print("=" * 60)
    print(f"個体数: {POPULATION_SIZE}")
    print(f"世代数: {GENERATIONS}")
    print(f"探索深さ: {FIXED_DEPTH} (固定)")
    print("=" * 60)

    gen     = Generation(size=POPULATION_SIZE)
    history = []
    start_time = time.time()

    for gen_idx in range(GENERATIONS):
        gen_start = time.time()

        gen.evaluate_all()
        gen.update_hall_of_fame()

        fitness_values = [ind.fitness for ind in gen.individuals]
        best_fitness   = max(fitness_values)
        avg_fitness    = sum(fitness_values) / len(fitness_values)
        worst_fitness  = min(fitness_values)

        gen_elapsed = time.time() - gen_start
        print(f"\n--- 第 {gen_idx + 1} 世代 終了 ({gen_elapsed:.1f}秒) ---")
        print(f"  最高勝率: {best_fitness:.2f}%")
        print(f"  平均勝率: {avg_fitness:.2f}%")
        print(f"  最低勝率: {worst_fitness:.2f}%")

        if gen.hall_of_fame:
            print(f"  HoF上位: {[f'{h.fitness:.1f}%' for h in gen.hall_of_fame[:3]]}")

        best_ind = max(gen.individuals, key=lambda x: x.fitness)
        history.append({
            'gen':           gen_idx + 1,
            'best_fitness':  best_fitness,
            'avg_fitness':   avg_fitness,
            'worst_fitness': worst_fitness,
            'weights':       best_ind.analyzer.weights.copy(),
        })

        gen.evolve()

    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"進化完了！（全体: {total_elapsed:.1f}秒）")
    print(f"{'=' * 60}")
    print(f"初代最高勝率:     {history[0]['best_fitness']:.2f}%")
    print(f"最終世代最高勝率: {history[-1]['best_fitness']:.2f}%")
    print(f"改善幅:           {history[-1]['best_fitness'] - history[0]['best_fitness']:.2f}%")

    # 最良重みを保存
    best_weights = history[-1]['weights']
    with open("best_weights.txt", "w", encoding="utf-8") as f:
        json.dump(best_weights, f, indent=4, ensure_ascii=False)
    print("\n最良重みを best_weights.txt に保存しました。")

    save_fitness_graph(history)
    print("\nプログラム完了。")