import random
import json
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
    2つの個体を対戦させる。
    depth: 探索深さ（デフォルト1）
    戻り値: 1 (player1勝利), 2 (player2勝利), 0 (引き分け)
    """
    board_analyzer = player1.analyzer
    board_analyzer.board.fill(0)
    board_analyzer.move_history = []
    
    current_turn = 1
    for _ in range(15 * 15):
        current_ai = player1 if current_turn == 1 else player2
        board_analyzer.weights = current_ai.analyzer.weights
        
        r, c = board_analyzer.get_best_move(depth_limit=depth)
        
        if r is not None:
            board_analyzer.put_stone(r, c, current_turn)
            if board_analyzer.check_win(r, c, current_turn):
                return current_turn
        else:
            return 0  # 引き分け（盤面が埋まった）
        current_turn = 3 - current_turn
    return 0

class Generation:
    def __init__(self, size=16):  # 個体数を16に減らして高速化
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1

    # 修正後のイメージ
    def evaluate_all(self, elite=None):
        print(f"第 {self.generation_number} 世代の評価中...")
        
        total_matches = 0  # 初期化
        
        for ind1 in self.individuals:
            ind1.fitness = 0.0
            others = [i for i in self.individuals if i != ind1]
            
            # 対戦相手を決める
            if elite:
                # エリート＋ランダム1人（合計2人）
                opponents = [elite] + random.sample(others, 1)
            else:
                opponents = random.sample(others, 2)
            
            games_per_pair = 2
            for opponent in opponents:
                for game in range(games_per_pair):
                    total_matches += 1
                    if game % 2 == 0:
                        winner = play_match(ind1, opponent, depth=1)
                        if winner == 1:
                            ind1.fitness += 1
                    else:
                        winner = play_match(opponent, ind1, depth=1)
                        if winner == 2:
                            ind1.fitness += 1
            
            # 勝率計算
            ind1.fitness = (ind1.fitness / (len(opponents) * games_per_pair)) * 100
        
        print(f"評価完了 総対戦数: {total_matches}")

    def evolve(self):
        # fitnessの高い順にソート
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        
        # 上位25%（エリート）を残す（最低1体）
        elite_count = max(1, len(self.individuals) // 10)
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
                if random.random() < 0.2:
                    child_weights[key] *= random.uniform(0.5, 1.5)
            
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
    current_best_ind = None

    for i in range(100):  # 100世代
        gen.evaluate_all(elite=current_best_ind)
        
        gen.individuals.sort(key=lambda x: x.fitness, reverse=True)
        best_ind = gen.individuals[0]
        current_best_ind = gen.individuals[0]

        print(f"--- 第 {i+1} 世代 終了 ---")
        print(f"最高勝率: {best_ind.fitness:.2f}%")
        
        history.append({
            'gen': i + 1,
            'best_fitness': best_ind.fitness,
            'weights': best_ind.analyzer.weights.copy()
        })
        
        gen.evolve()

    # 最良個体の重みを保存
    with open("best_weights.txt", "w", encoding="utf-8") as f:
    # indent=4 をつけると綺麗に改行されます
        json.dump(history[-1]['weights'], f, indent=4)
    
    save_fitness_graph(history)