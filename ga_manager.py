import random
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from engine import GomokuAnalyzer
import matplotlib.pyplot as plt
import matplotlib
import time
import os
import csv

# ============================================================================
# 修正サマリー（オリジナルからの変更点）
# ============================================================================
# 修正1: 引き分けスコア 0.2 → 0.0
#        理由: 引き分けで点がもらえると防御過多・引き分け量産の個体に収束するため
#
# 修正2: fitness正規化を「全個体共通の平均試合数」→「個体ごとの実際の試合数」に変更
#        理由: 試合数が多い個体ほど勝率が低く計算されていたバグを修正
#
# 修正3: Hall of Fameをfitnessの高い順でソートして保持
#        理由: 弱い世代の1位が歴代最強を押し出すバグを修正
#
# 修正4: トーナメント選択をエリートだけでなく全個体から選ぶよう変更
#        理由: エリートだけから選ぶと早期収束・多様性消失が起きていた
#
# 修正5: 探索深さの最低値を1→2（初期）、2→3（以降）に引き上げ
#        理由: depth=2だと重みの差が結果に出にくく、GAが強さを正確に判断できなかった
# ============================================================================


# ============================================================================
# フェーズ1B：並列処理用ワーカー関数（トップレベル配置）
# ============================================================================

def play_match_worker(args):
    """
    並列実行用ワーカー。
    重みデータのみを受け取って対戦させ、結果を返す。
    
    Args:
        args: (weights1, weights2, depth, start_player)
    
    Returns:
        winner: 1 (player1勝利), 2 (player2勝利), 0 (引き分け)
    """
    w1, w2, depth, start_player = args
    board = GomokuAnalyzer()
    board.board.fill(0)
    board.move_history = []
    
    # 重みをセット
    weights_list = [None, w1, w2]
    
    current_turn = start_player
    for _ in range(15 * 15):
        board.weights = weights_list[current_turn]
        board.current_player = current_turn
        
        r, c = board.get_best_move(depth_limit=depth)
        
        if r is not None:
            board.put_stone(r, c, current_turn)
            if board.check_win(r, c, current_turn):
                return current_turn
        else:
            return 0  # 引き分け
        
        current_turn = 3 - current_turn
    
    return 0

# ============================================================================
# フェーズ1B：個体クラス（重みの構造化）
# ============================================================================

class Individual:
    """
    遺伝的アルゴリズムの個体
    
    重みを「攻撃」「防御」「戦術」に分類して管理
    """
    def __init__(self, weights=None, depth=None):
        self.analyzer = GomokuAnalyzer()
        
        # 重みの初期化
        if weights:
            self.analyzer.weights = weights.copy()
        else:
            self.randomize_weights()
        
        # 探索深さも進化対象に（フェーズ1B）
        self.depth = depth if depth is not None else 2
        
        self.fitness = 0.0
        self.vcf_success_count = 0  # VCF成功回数（フェーズ2指標）
        self.vct_success_count = 0  # VCT成功回数（フェーズ2指標）

    def randomize_weights(self):
        """
        重みをランダム化（値がマイナスにならないよう工夫）
        """
        for key in self.analyzer.weights:
            base_val = self.analyzer.weights[key]
            
            if key == 'defense_weight':
                # defense_weight は 1.0 ～ 2.0 の範囲
                self.analyzer.weights[key] = random.uniform(0.8, 2.0)
            elif key == 'mcts_simulation_depth':
                # 整数値に
                self.analyzer.weights[key] = random.randint(2, 4)
            else:
                # その他の重みは初期値の 0.5 ～ 1.5 倍
                self.analyzer.weights[key] = max(1, base_val * random.uniform(0.5, 1.5))
    
    def mutate(self, mutation_rate=0.15, mutation_strength=0.2):
        """
        重み付き突然変異（比率ベース）
        
        Args:
            mutation_rate: 突然変異の確率
            mutation_strength: 突然変異の強度（±の幅）
        """
        for key in self.analyzer.weights:
            if random.random() < mutation_rate:
                base_val = self.analyzer.weights[key]
                
                if key == 'defense_weight':
                    # 比率ベース（1.0 ～ 2.0 の範囲を保つ）
                    mutation_factor = random.uniform(1 - mutation_strength, 1 + mutation_strength)
                    self.analyzer.weights[key] = max(0.8, min(2.0, base_val * mutation_factor))
                
                elif key == 'mcts_simulation_depth':
                    # ±1 の範囲で変更
                    change = random.randint(-1, 1)
                    self.analyzer.weights[key] = max(2, min(5, int(base_val) + change))
                
                else:
                    # 比率ベース（1以上を保証）
                    mutation_factor = random.uniform(1 - mutation_strength, 1 + mutation_strength)
                    self.analyzer.weights[key] = max(1, base_val * mutation_factor)
        
        # 探索深さも変更（確率20%）
        if random.random() < 0.2:
            change = random.choice([-1, 0, 1])
            self.depth = max(1, min(4, self.depth + change))

# ============================================================================
# フェーズ1B+フェーズ2：世代クラス
# ============================================================================

class Generation:
    """
    遺伝的アルゴリズムの1世代
    """
    def __init__(self, size=16, use_parallel=True):
        self.individuals = [Individual() for _ in range(size)]
        self.generation_number = 1
        self.hall_of_fame = []  # 歴代最強個体リスト（上位5）
        self.use_parallel = use_parallel
        self.depth_schedule = self._get_depth_schedule()  # 世代による探索深さスケジュール

    def _get_depth_schedule(self):
        """
        修正5: 探索深さを引き上げ（最低3）
        depth=2だと重みの差が結果に出にくいため、最低でも3に設定
        """
        def schedule(generation):
            if generation < 10:
                return 2  # 初期10世代は depth=2
            elif generation < 30:
                return 3  # 10〜30世代は depth=3
            else:
                return 4  # 以降もdepth=3を維持（速度と精度のバランス）
        return schedule

    def evaluate_all(self):
        """
        全個体を評価（並列処理対応）
        
        改良版：各タスクの所有者を明示的に追跡し、
               fitness の集計を正確に行う
        
        各個体を複数の相手と対戦させ、勝率を計算
        """
        print(f"第 {self.generation_number} 世代の評価中...")
        
        # デフォルト個体（初期重み）を生成
        default_weights = GomokuAnalyzer().weights
        
        # 世代スケジュールから探索深さを取得
        base_depth = self.depth_schedule(self.generation_number)
        
        # 並列処理用タスクリスト
        tasks = []           # タスク本体: (weights1, weights2, depth, start_player)
        task_owner = []      # 各タスクがどの個体のものか（個体インデックス）
        
        for idx, ind in enumerate(self.individuals):
            # 対戦相手の選定
            opponents = [default_weights]
            
            # Hall of Fame から上位個体を追加
            if self.hall_of_fame:
                opponents.extend([h.analyzer.weights for h in self.hall_of_fame[:2]])
            
            # ランダムに仲間から3人選ぶ
            others = [i.analyzer.weights for i in self.individuals if i != ind]
            if others:
                opponents.extend(random.sample(others, min(len(others), 3)))
            
            # 各相手と先手・後手で対戦
            for opp_w in opponents:
                for game_num in range(2):
                    depth = ind.depth  # 個体の探索深さを使用
                    start_player = 1 if game_num == 0 else 2
                    
                    # タスクを追加
                    tasks.append((ind.analyzer.weights, opp_w, depth, start_player))
                    task_owner.append(idx)  # ✅ このタスクがどの個体のものかを明示的に記録
        
        # 並列実行
        print(f"  {len(tasks)} 試合を並列実行中...")
        with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            results = list(executor.map(play_match_worker, tasks))
        
        
        # 個体の fitness をリセット
        for ind in self.individuals:
            ind.fitness = 0.0
        
        # 結果を集計 ✅ 修正：task_owner を使って正確に追跡
        for i, winner in enumerate(results):
            owner_idx = task_owner[i]  # この結果の所有者
            task = tasks[i]
            start_player = task[3]  # タスクの先手プレイヤー
            
            # owner_idx の個体が勝ったか判定
            if (start_player == 1 and winner == 1) or (start_player == 2 and winner == 2):
                self.individuals[owner_idx].fitness += 1.0
            elif winner == 0:
                self.individuals[owner_idx].fitness += 0.0  # 修正1: 引き分けは0点（勝ちにいく戦略を強制）
        
        # 修正2: 個体ごとの実際の試合数でfitness正規化
        match_counts = [0] * len(self.individuals)
        for owner_idx in task_owner:
            match_counts[owner_idx] += 1
        
        for idx, ind in enumerate(self.individuals):
            if match_counts[idx] > 0:
                ind.fitness = (ind.fitness / match_counts[idx]) * 100
        

    def update_hall_of_fame(self):
        """
        Hall of Fame を更新（歴代最強上位5体を保持）
        修正3: fitnessの高い順でソートして真の最強個体を保持
        """
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        best_ind = self.individuals[0]
        
        # 現世代1位をHoFに追加（コピーして保持）
        hof_candidate = Individual(
            weights=best_ind.analyzer.weights.copy(),
            depth=best_ind.depth
        )
        hof_candidate.fitness = best_ind.fitness
        self.hall_of_fame.append(hof_candidate)
        
        # fitnessの高い順にソートして上位5体のみ保持
        self.hall_of_fame.sort(key=lambda x: x.fitness, reverse=True)
        self.hall_of_fame = self.hall_of_fame[:5]
        

    def evolve(self):
        """
        次世代を生成（選択・交叉・突然変異）
        
        改良版：各ステップでデバッグ情報を出力
        """
        # fitness でソート
        self.individuals.sort(key=lambda x: x.fitness, reverse=True)
        
        # エリート保存（上位25%）
        elite_count = max(2, len(self.individuals) // 4)
        next_gen = [Individual(
            weights=ind.analyzer.weights.copy(),
            depth=ind.depth
        ) for ind in self.individuals[:elite_count]]
        
        
        # 残りの枠を子供で埋める（ルーレット選択 + 交叉 + 突然変異）
        while len(next_gen) < len(self.individuals):
            # 上位個体をトーナメント選択
            parent1 = self._tournament_selection(elite_count, k=3)
            parent2 = self._tournament_selection(elite_count, k=3)
            
            # 一様交叉
            child_weights = {}
            for key in parent1.analyzer.weights:
                if random.random() < 0.5:
                    child_weights[key] = parent1.analyzer.weights[key]
                else:
                    child_weights[key] = parent2.analyzer.weights[key]
            
            # 子の深さをランダムに設定
            child_depth = random.choice([parent1.depth, parent2.depth])
            
            child = Individual(weights=child_weights, depth=child_depth)
            
            # 突然変異
            child.mutate(mutation_rate=0.15, mutation_strength=0.2)
            
            next_gen.append(child)
        
        self.individuals = next_gen
        self.generation_number += 1

    def _tournament_selection(self, elite_count, k=3):
        """
        修正4: トーナメント選択を全個体から行う（エリートだけでなく）
        多様性を保つため、集団全体からk個体をランダムに選んでトーナメント
        """
        selected = random.sample(self.individuals, min(k, len(self.individuals)))
        return max(selected, key=lambda x: x.fitness)

# ============================================================================
# グラフ保存関数
# ============================================================================

def save_fitness_graph(history, filename='evolution_graph.png'):
    """
    基本グラフ：勝率の推移
    """
    gens = [h['gen'] for h in history]
    best_fits = [h['best_fitness'] for h in history]
    avg_fits = [h['avg_fitness'] for h in history]
    
    plt.figure(figsize=(12, 6))
    
    plt.plot(gens, best_fits, marker='o', label='Best Fitness', color='blue', linewidth=2)
    plt.plot(gens, avg_fits, marker='s', label='Average Fitness', color='orange', linewidth=2)
    
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


def save_fitness_with_depth_graph(history, filename='evolution_with_depth.png'):
    """
    推奨グラフ1：勝率 + 探索深さの同時推移
    
    左軸：勝率（%）
    右軸：探索深さ（段階）
    """
    gens = [h['gen'] for h in history]
    best_fits = [h['best_fitness'] for h in history]
    avg_fits = [h['avg_fitness'] for h in history]
    avg_depths = [h['avg_depth'] for h in history]
    
    fig, ax1 = plt.subplots(figsize=(14, 7))
    
    # 左軸：勝率
    ax1.set_xlabel('Generation', fontsize=12)
    ax1.set_ylabel('Fitness (Win %)', fontsize=12, color='tab:blue')
    ax1.plot(gens, best_fits, marker='o', label='Best Fitness', color='blue', linewidth=2.5)
    ax1.plot(gens, avg_fits, marker='s', label='Average Fitness', color='lightblue', linewidth=2)
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.set_ylim(0, 100)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 右軸：探索深さ
    ax2 = ax1.twinx()
    ax2.set_ylabel('Average Search Depth', fontsize=12, color='tab:red')
    ax2.plot(gens, avg_depths, marker='^', label='Average Depth', color='red', linewidth=2.5, linestyle='--')
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.set_ylim(0, 4)
    
    # タイトルと凡例
    fig.suptitle('AI Evolution: Fitness & Search Depth', fontsize=14, fontweight='bold')
    
    # 凡例を統合
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='center left', fontsize=10)
    
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"グラフを {filename} として保存しました。")
    plt.close()


def save_fitness_distribution_graph(history, filename='fitness_distribution.png'):
    """
    推奨グラフ2：箱ひげ図で個体群の多様性を表示
    
    各世代での勝率分布を可視化
    """
    gens = [h['gen'] for h in history]
    best_fits = [h['best_fitness'] for h in history]
    avg_fits = [h['avg_fitness'] for h in history]
    worst_fits = [h['worst_fitness'] for h in history]
    
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # 上限・下限の帯をプロット
    ax.fill_between(gens, worst_fits, best_fits, alpha=0.3, color='lightblue', label='Range (Worst~Best)')
    ax.plot(gens, best_fits, marker='o', color='darkblue', linewidth=2, label='Best')
    ax.plot(gens, avg_fits, marker='s', color='orange', linewidth=2, label='Average')
    ax.plot(gens, worst_fits, marker='v', color='red', linewidth=2, label='Worst')
    
    ax.set_xlabel('Generation', fontsize=12)
    ax.set_ylabel('Fitness (Win %)', fontsize=12)
    ax.set_title('Fitness Distribution Across Generations', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"グラフを {filename} として保存しました。")
    plt.close()


def save_weights_history_csv(history, filename='weights_evolution.csv'):
    """
    推奨ファイル3：重みの進化過程をCSVで記録
    
    重要な重みを抽出して、世代ごとに記録
    Excelやグラフツールで分析可能
    """
    # 記録する重みのキー（重要なものだけ）
    important_keys = [
        'open_four', 'open_three', 'dead_four', 'dead_three',
        'fork_44', 'fork_43', 'fork_33',
        'defense_weight', 'def_open_four', 'def_open_three',
        'center_bonus', 'continuity_weight'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['gen', 'best_fitness', 'avg_fitness'] + important_keys
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for h in history:
            row = {
                'gen': h['gen'],
                'best_fitness': round(h['best_fitness'], 2),
                'avg_fitness': round(h['avg_fitness'], 2),
            }
            
            # 重みを追加
            weights = h['weights']
            for key in important_keys:
                row[key] = round(weights.get(key, 0), 2)
            
            writer.writerow(row)
    
    print(f"重み進化履歴を {filename} として保存しました。")


def save_weights_history_json(history, filename='weights_history.json'):
    """
    全世代の重み履歴をJSON で保存
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"重み履歴をJSON形式で {filename} として保存しました。")


def save_best_weights_detailed(best_weights, filename='best_weights_detailed.txt'):
    """
    最良個体の重みを詳細テキストで保存
    
    カテゴリごとに分類した形式
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("最良個体の重み詳細\n")
        f.write("=" * 70 + "\n\n")
        
        # === 基本パターン（攻撃） ===
        f.write("【基本パターン（攻撃評価）】\n")
        attack_keys = ['five', 'guaranteed_four', 'open_four', 'dead_four', 'open_three', 'dead_three', 'open_two']
        for key in attack_keys:
            if key in best_weights:
                f.write(f"  {key:.<30} {best_weights[key]:>10.2f}\n")
        
        # === フォーク・両見 ===
        f.write("\n【フォーク・両見評価】\n")
        fork_keys = ['fork_44', 'fork_43', 'fork_33', 'both_open_threats']
        for key in fork_keys:
            if key in best_weights:
                f.write(f"  {key:.<30} {best_weights[key]:>10.2f}\n")
        
        # === 防御関連 ===
        f.write("\n【防御関連】\n")
        defense_keys = ['defense_weight', 'def_open_four', 'def_open_three', 'def_dead_three', 'def_multiple_threats']
        for key in defense_keys:
            if key in best_weights:
                f.write(f"  {key:.<30} {best_weights[key]:>10.2f}\n")
        
        # === その他 ===
        f.write("\n【その他】\n")
        other_keys = ['center_bonus', 'continuity_weight', 'mcts_simulation_depth']
        for key in other_keys:
            if key in best_weights:
                f.write(f"  {key:.<30} {best_weights[key]:>10.2f}\n")
        
        f.write("\n" + "=" * 70 + "\n")
    
    print(f"詳細重みを {filename} として保存しました。")

# ============================================================================
# メイン実行
# ============================================================================

if __name__ == "__main__":
    # Windows で並列処理を行うために必要
    multiprocessing.freeze_support()
    
    # パラメータ
    POPULATION_SIZE = 16
    GENERATIONS = 100
    USE_PARALLEL = True
    
    print("=" * 70)
    print("五目並べ AI 遺伝的アルゴリズム進化開始")
    print("=" * 70)
    print(f"個体数: {POPULATION_SIZE}")
    print(f"世代数: {GENERATIONS}")
    print(f"並列処理: {'有効' if USE_PARALLEL else '無効'}")
    print("=" * 70)
    
    gen = Generation(size=POPULATION_SIZE, use_parallel=USE_PARALLEL)
    history = []
    
    start_time = time.time()
    
    for gen_idx in range(GENERATIONS):
        gen_start_time = time.time()
        
        # 評価フェーズ
        gen.evaluate_all()
        
        # Hall of Fame 更新
        gen.update_hall_of_fame()
        
        # 統計情報を計算
        fitness_values = [ind.fitness for ind in gen.individuals]
        best_fitness = max(fitness_values)
        avg_fitness = sum(fitness_values) / len(fitness_values)
        worst_fitness = min(fitness_values)
        depth_values = [ind.depth for ind in gen.individuals]
        avg_depth = sum(depth_values) / len(depth_values)
        
        # 結果を出力
        gen_elapsed = time.time() - gen_start_time
        print(f"\n--- 第 {gen_idx + 1} 世代 終了 (所要時間: {gen_elapsed:.1f}秒) ---")
        print(f"  【勝率統計】")
        print(f"    最高勝率: {best_fitness:.2f}%")
        print(f"    平均勝率: {avg_fitness:.2f}%")
        print(f"    最低勝率: {worst_fitness:.2f}%")
        print(f"  【探索深さ】")
        print(f"    平均深さ: {avg_depth:.2f}")
        print(f"    推奨深さ（次世代）: {gen.depth_schedule(gen.generation_number + 1)}")
        
        # Hall of Fame 情報
        if gen.hall_of_fame:
            hof_rates = [f'{h.fitness:.1f}%' for h in gen.hall_of_fame[:3]]
            print(f"  【Hall of Fame (上位3)】")
            for i, rate in enumerate(hof_rates, 1):
                print(f"    {i}位: {rate}")
        
        # 履歴に記録
        best_ind = max(gen.individuals, key=lambda x: x.fitness)
        history.append({
            'gen': gen_idx + 1,
            'best_fitness': best_fitness,
            'avg_fitness': avg_fitness,
            'worst_fitness': worst_fitness,
            'best_depth': best_ind.depth,
            'avg_depth': avg_depth,
            'weights': best_ind.analyzer.weights.copy(),
        })
        
        # 進化フェーズ
        gen.evolve()
    
    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"進化完了！（全体所要時間: {total_elapsed:.1f}秒）")
    print(f"{'=' * 70}")
    
    # 最良個体の情報を表示
    best_weights = history[-1]['weights']
    best_depth = history[-1]['best_depth']
    best_fitness = history[-1]['best_fitness']
    
    print(f"\n最良個体の情報（第 {history[-1]['gen']} 世代）:")
    print(f"  勝率: {best_fitness:.2f}%")
    print(f"  推奨探索深さ: {best_depth}")
    print(f"\n  重み詳細:")
    for key, value in sorted(best_weights.items()):
        print(f"    {key:.<30} {value:.2f}")
    
    # ========== ここから結果保存処理 ==========
    
    # 結果を保存
    with open("best_weights.txt", "w", encoding="utf-8") as f:
        json.dump(best_weights, f, indent=4, ensure_ascii=False)
    print("\n最良重みを best_weights.txt に保存しました。")
    
    # グラフと履歴を保存
    print("\nグラフ・履歴を生成中...")
    save_fitness_graph(history)
    save_weights_history_json(history)
    
    
    # 進化の統計情報を表示
    print(f"\n【進化の統計情報】")
    print(f"  初代最高勝率: {history[0]['best_fitness']:.2f}%")
    print(f"  最終世代最高勝率: {history[-1]['best_fitness']:.2f}%")
    print(f"  改善幅: {history[-1]['best_fitness'] - history[0]['best_fitness']:.2f}%")
    print(f"  平均世代時間: {total_elapsed / GENERATIONS:.1f}秒")
    
    # 出力ファイル一覧
    print(f"\n【出力ファイル一覧】")
    print(f"  evolution_graph.png ................. 基本グラフ（勝率推移）")
    print(f"  best_weights.txt ................... 最良重み（JSON形式）")
    print(f"  weights_history.json .............. 全世代重み履歴（JSON）")

    
    print("\nプログラム完了。")