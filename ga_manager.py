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
        self.fitness = 0

    def randomize_weights(self):
        for key in self.analyzer.weights:
            base_val = self.analyzer.weights[key]
            self.analyzer.weights[key] = base_val * random.uniform(0.7, 1.3)

def play_match(player1, player2):
    board_analyzer = player1.analyzer 
    board_analyzer.board.fill(0)
    board_analyzer.move_history = []
    
    current_turn = 1
    for _ in range(15 * 15):
        current_ai = player1 if current_turn == 1 else player2
        board_analyzer.weights = current_ai.analyzer.weights
        
        # 学習速度を優先して depth=1 を推奨
        r, c = board_analyzer.get_best_move(depth_limit=1)
        
        if r is not None:
            board_analyzer.put_stone(r, c, current_turn)
            if board_analyzer.check_win(r, c, current_turn):
                return current_turn
        else:
            return 0
        current_turn = 3 - current_turn
    return 0

class Generation:
    def __init__(self, size=20):
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1

    def evaluate_all(self):
        print(f"第 {self.generation_number} 世代の評価中...")
        for ind in self.individuals:
            ind.fitness = 0

        for i, ind1 in enumerate(self.individuals):
            for _ in range(3): 
                opponent = random.choice(self.individuals[:i] + self.individuals[i+1:])
                res = play_match(ind1, opponent)
                if res == 1: ind1.fitness += 1
                elif res == 2: opponent.fitness += 1

    # --- ここが重要：進化のロジック ---
    def evolve(self):
        # 成績順にソート
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        
        # 上位25%（エリート）を残す
        elite_count = len(self.individuals) // 4
        next_gen = self.individuals[:elite_count]
        
        # 残りの枠を子供で埋める
        while len(next_gen) < len(self.individuals):
            parent1 = random.choice(self.individuals[:elite_count])
            parent2 = random.choice(self.individuals[:elite_count])
            
            # 交叉（DNAを混ぜる）
            child_weights = {}
            for key in parent1.analyzer.weights:
                child_weights[key] = parent1.analyzer.weights[key] if random.random() < 0.5 else parent2.analyzer.weights[key]
                # 突然変異
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
    plt.ylabel('Best Fitness (Wins)')
    plt.grid(True)
    plt.savefig('evolution_graph.png')
    print("グラフを evolution_graph.png として保存しました。")
    plt.show()
    
if __name__ == "__main__":
    # テストとしてまずは 10世代 くらいで回すのがおすすめ
    gen = Generation(size=32) # 個体数は 20-50 程度がバランス良い
    history = []

    for i in range(100): # 本番は 100 に変更
        gen.evaluate_all()
        
        gen.individuals.sort(key=lambda x: x.fitness, reverse=True)
        best_ind = gen.individuals[0]
        
        print(f"--- 第 {i+1} 世代 終了 ---")
        print(f"最高勝数: {best_ind.fitness}")
        
        history.append({
            'gen': i + 1,
            'best_fitness': best_ind.fitness,
            'weights': best_ind.analyzer.weights.copy()
        })
        
        gen.evolve()

    with open("best_weights.txt", "w") as f:
        f.write(str(history[-1]['weights']))
    
    save_fitness_graph(history)