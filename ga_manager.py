import random
from engine import GomokuAnalyzer
import matplotlib.pyplot as plt

class Individual:
    def __init__(self, weights=None):
        self.analyzer = GomokuAnalyzer()
        if weights:
            self.analyzer.weights = weights.copy()
        else:
            self.randomize_weights()
        self.fitness = 0.0  # 勝率（%）

    def randomize_weights(self):
        for key in self.analyzer.weights:
            base_val = self.analyzer.weights[key]
            # 初期値の0.7～1.3倍の範囲でランダム化
            self.analyzer.weights[key] = base_val * random.uniform(0.7, 1.3)

def play_match(player1, player2, depth=1):
    """
    2つの個体を対戦させる（修正版）
    """
    # 各プレイヤー専用の analyzer を作成（重みをコピー）
    analyzer1 = GomokuAnalyzer()
    analyzer1.weights = player1.analyzer.weights.copy()
    analyzer1.board.fill(0)
    
    analyzer2 = GomokuAnalyzer()
    analyzer2.weights = player2.analyzer.weights.copy()
    analyzer2.board.fill(0)
    
    # 対戦中用の盤面（analyzer1の盤面を使用）
    board = analyzer1.board
    
    current_turn = 1
    for _ in range(15 * 15):
        if current_turn == 1:
            current_ai = analyzer1
            # player1の重みは既に設定済み
        else:
            current_ai = analyzer2
            # player2の重みは既に設定済み
        
        r, c = current_ai.get_best_move(depth_limit=depth)
        
        if r is not None:
            # 両方のanalyzerの盤面を更新
            analyzer1.put_stone(r, c, current_turn)
            analyzer2.put_stone(r, c, current_turn)
            
            if analyzer1.check_win(r, c, current_turn):
                return current_turn
        else:
            return 0
        current_turn = 3 - current_turn
    return 0

class Generation:
    def __init__(self, size=16):  # 個体数を16に減らして高速化
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1

    def evaluate_all(self):
        print(f"第 {self.generation_number} 世代の評価中...")
        
        # fitness を初期化
        for ind in self.individuals:
            ind.fitness = 0.0

        # 基準個体（初期重み）を作成
        baseline_weights = {
            'five': 100000,
            'open_four': 12000,
            'dead_four': 5000,
            'open_three': 1500,
            'dead_three': 200,
            'open_two': 50,
            'defense_weight': 1.2,
            'fork_44': 15000,
            'fork_43': 8000,
            'fork_33': 3000,
            'center_bonus': 100
        }
        baseline = Individual(weights=baseline_weights)

        # 各AIが対戦する相手の数（自分以外の個体からランダムに選ぶ）
        opponents_per_individual = 3
        # 各相手との対戦回数（先後各2回 → 計4回）
        games_per_pair = 4

        total_matches = 0
        expected_matches = len(self.individuals) * (opponents_per_individual + 1) * games_per_pair

        for i, ind1 in enumerate(self.individuals):
            # 対戦相手を選ぶ（自分以外の個体から opponents_per_individual 体）
            others = [ind for j, ind in enumerate(self.individuals) if j != i]
            opponents = random.sample(others, min(opponents_per_individual, len(others)))
            # 基準個体も追加
            opponents.append(baseline)

            for opponent in opponents:
                for game in range(games_per_pair):
                    # 先手後手を交互に
                    if game % 2 == 0:
                        winner = play_match(ind1, opponent, depth=1)
                    else:
                        winner = play_match(opponent, ind1, depth=1)

                    if winner == 1:
                        ind1.fitness += 1
                    elif winner == 2:
                        opponent.fitness += 1  # 相手のfitnessはここでは使わないが、基準個体のfitnessは更新されても無視
                    total_matches += 1

                    # 進捗表示（100試合ごと）
                    if total_matches % 100 == 0:
                        print(f"  試合進捗: {total_matches}/{expected_matches}")

        # 勝率（%）に変換（基準個体との対戦も含めた総試合数で割る）
        total_games_per_individual = (opponents_per_individual + 1) * games_per_pair
        for ind in self.individuals:
            ind.fitness = (ind.fitness / total_games_per_individual) * 100

        print(f"評価完了 総対戦数: {total_matches}")

    def evolve(self):
        # fitnessの高い順にソート
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        
        # 上位25%（エリート）を残す（最低1体）
        elite_count = max(1, len(self.individuals) // 4)
        next_gen = self.individuals[:elite_count]
        
        # 残りの枠を子供で埋める
        while len(next_gen) < len(self.individuals):
            parent1 = random.choice(self.individuals[:elite_count])
            parent2 = random.choice(self.individuals[:elite_count])
            
            # 一様交叉
            child_weights = {}
            for key in parent1.analyzer.weights:
                if random.random() < 0.5:
                    child_weights[key] = parent1.analyzer.weights[key]
                else:
                    child_weights[key] = parent2.analyzer.weights[key]
                
                # 突然変異（10%の確率で0.8～1.2倍）
                if random.random() < 0.1:
                    child_weights[key] *= random.uniform(0.8, 1.2)
            
            next_gen.append(Individual(weights=child_weights))
        
        self.individuals = next_gen
        self.generation_number += 1

def save_fitness_graph(history):
    gens = [h['gen'] for h in history]
    fits = [h['best_fitness'] for h in history]
    
    plt.figure(figsize=(10, 5))
    plt.plot(gens, fits, marker='o')
    plt.title('AI Evolution Progress')
    plt.xlabel('Generation')
    plt.ylabel('Best Fitness (Win %)')
    plt.grid(True)
    plt.savefig('evolution_graph.png')
    print("グラフを evolution_graph.png として保存しました。")
    plt.show()

if __name__ == "__main__":
    gen = Generation(size=16)  # 個体数16でスタート
    history = []

    for i in range(100):  # 100世代
        gen.evaluate_all()
        
        gen.individuals.sort(key=lambda x: x.fitness, reverse=True)
        best_ind = gen.individuals[0]
        
        print(f"--- 第 {i+1} 世代 終了 ---")
        print(f"最高勝率: {best_ind.fitness:.2f}%")
        
        history.append({
            'gen': i + 1,
            'best_fitness': best_ind.fitness,
            'weights': best_ind.analyzer.weights.copy()
        })
        
        gen.evolve()

    # 最良個体の重みを保存
    with open("best_weights.txt", "w") as f:
        f.write(str(history[-1]['weights']))
    
    save_fitness_graph(history)