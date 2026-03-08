import random
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from engine import GomokuAnalyzer
import matplotlib.pyplot as plt


# --- 1. 対戦ロジックをトップレベルに移動（並列化のため） ---
def play_match_worker(args):
    """
    並列実行用ワーカー。重みデータのみを受け取って対戦させる。
    """
    w1, w2, depth, start_player = args
    board = GomokuAnalyzer()
    board.board.fill(0)
    
    # 評価関数の重みをセット
    weights = [None, w1, w2] 
    
    current_turn = start_player
    for _ in range(15 * 15):
        board.weights = weights[current_turn]
        r, c = board.get_best_move(depth_limit=depth)
        
        if r is not None:
            board.put_stone(r, c, current_turn)
            if board.check_win(r, c, current_turn):
                return current_turn
        else:
            return 0 # 引き分け
        current_turn = 3 - current_turn
    return 0

class Individual:
    def __init__(self, weights=None):
        self.analyzer = GomokuAnalyzer()
        if weights:
            self.analyzer.weights = weights.copy()
        else:
            self.randomize_weights()
        self.fitness = 0.0

    def randomize_weights(self):
        # 3. 加算的な初期化（0付近の重みも動くようにする）
        for key in self.analyzer.weights:
            self.analyzer.weights[key] += random.uniform(-100, 100)

class Generation:
    def __init__(self, size=16):
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1
        self.hall_of_fame = [] # 歴代最強個体のリスト

    def evaluate_all(self):
        print(f"第 {self.generation_number} 世代の評価中（並列処理実行中）...")
        
        default_weights = GomokuAnalyzer().weights
        tasks = []
        
        # 各個体のタスクを作成
        for idx, ind in enumerate(self.individuals):
            # 対戦相手のリスト（デフォルト個体 + HOF個体 + ランダムな仲間2人）
            opponents = [default_weights]
            if self.hall_of_fame:
                opponents.extend(self.hall_of_fame)
            
            others = [i.analyzer.weights for i in self.individuals if i != ind]
            opponents.extend(random.sample(others, min(len(others), 2)))

            # 各相手と先手・後手2回ずつ（計4試合以上）
            for opp_w in opponents:
                for game in range(2):
                    # args: (重み1, 重み2, depth, 先手)
                    tasks.append((idx, ind.analyzer.weights, opp_w, 1, 1 if game == 0 else 2))

        # 2. 並列処理の実行
       # evaluate_all メソッド内
        with ProcessPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(play_match_worker, [(t[1], t[2], t[3], t[4]) for t in tasks]))
        # 結果の集計
        for (task, winner) in zip(tasks, results):
            idx = task[0]
            start_player = task[4]
            # 自分が勝った場合（自分が先手で1、または後手で2）
            if (start_player == 1 and winner == 1) or (start_player == 2 and winner == 2):
                self.individuals[idx].fitness += 1.0
            elif winner == 0:
                self.individuals[idx].fitness += 0.2 # 引き分けにも微少な加点

        # 勝率に換算（試合数で割る）
        matches_per_ind = len(tasks) // len(self.individuals)
        for ind in self.individuals:
            ind.fitness = (ind.fitness / matches_per_ind) * 100

    def evolve(self):
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        
        # 1. Hall of Fame の更新（現世代の1位を保存）
        best_w = self.individuals[0].analyzer.weights.copy()
        if not self.hall_of_fame:
            self.hall_of_fame.append(best_w)
        else:
            # 過去のHOFより強ければ入れ替え、あるいは追加
            self.hall_of_fame = [best_w] + self.hall_of_fame[:2] # 直近3世代のベストを保持

        # エリート保存（上位2体）
        next_gen = [Individual(weights=i.analyzer.weights) for i in self.individuals[:2]]
        
        # 4. トーナメント選択による次世代生成
        while len(next_gen) < len(self.individuals):
            p1 = self.tournament_selection()
            p2 = self.tournament_selection()
            
            # 交叉
            child_weights = {}
            for key in p1.analyzer.weights:
                child_weights[key] = p1.analyzer.weights[key] if random.random() < 0.5 else p2.analyzer.weights[key]
                
                # 3. 加算的な突然変異
                if random.random() < 0.2:
                    child_weights[key] += random.uniform(-200, 200) # スケールに合わせて調整
            
            next_gen.append(Individual(weights=child_weights))
        
        self.individuals = next_gen
        self.generation_number += 1

    def tournament_selection(self, k=3):
        """k個体をランダムに選び、最も優秀なものを親にする"""
        selected = random.sample(self.individuals, k)
        return max(selected, key=lambda x: x.fitness)

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
    # Windowsで並列処理を行うためにこれが必要です
    multiprocessing.freeze_support() 

    gen = Generation(size=16) 
    history = []

    for i in range(100):
        # 修正ポイント：引数の (elite=current_best_ind) を消す
        gen.evaluate_all() 
        
        # 評価後にソートして、その世代のベストを記録
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
    with open("best_weights.txt", "w", encoding="utf-8") as f:
    # indent=4 をつけると綺麗に改行されます
        json.dump(history[-1]['weights'], f, indent=4)
    
    save_fitness_graph(history)