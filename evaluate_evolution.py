# evaluate_evolution.py
import json
from ga_manager import Individual, play_match
from engine import GomokuAnalyzer

def main():
    # 初期個体
    default = GomokuAnalyzer()
    default_ind = Individual(weights=default.weights)
    
    # 進化個体
    with open("best_weights_ver5.txt", "r") as f:
        best = json.load(f)
    best_ind = Individual(weights=best)
    
    print("進化個体と初期個体の対戦を開始...")
    
    # 集計用
    results = {
        "best_first": 0,   # 進化個体が先手の勝ち
        "best_second": 0,  # 進化個体が後手の勝ち
        "default_first": 0, # 初期個体が先手の勝ち
        "default_second": 0, # 初期個体が後手の勝ち
        "draw": 0
    }
    
    for i in range(100):  # 1000回対戦
        if i % 2 == 0:
            # 進化個体が先手、初期個体が後手
            winner = play_match(best_ind, default_ind)
            if winner == 1:
                results["best_first"] += 1
            elif winner == 2:
                results["default_second"] += 1
            else:
                results["draw"] += 1
        else:
            # 初期個体が先手、進化個体が後手
            winner = play_match(default_ind, best_ind)
            if winner == 1:
                results["default_first"] += 1
            elif winner == 2:
                results["best_second"] += 1
            else:
                results["draw"] += 1
    
    # 集計
    best_total = results["best_first"] + results["best_second"]
    default_total = results["default_first"] + results["default_second"]
    
    print("\n=== 対戦結果 ===")
    print(f"進化個体: {best_total}勝 (先手:{results['best_first']}, 後手:{results['best_second']})")
    print(f"初期個体: {default_total}勝 (先手:{results['default_first']}, 後手:{results['default_second']})")
    print(f"引分: {results['draw']}")
    print(f"進化個体の先手勝率: {results['best_first']/50*100:.1f}%")  # 先手番は50回
    print(f"進化個体の後手勝率: {results['best_second']/50*100:.1f}%")
    print(f"総合勝率: {best_total/100*100:.1f}%")
    
    # 先手有利の度合いを確認
    total_first = results["best_first"] + results["default_first"]
    total_second = results["best_second"] + results["default_second"]
    print(f"\n先手勝率: {total_first/100*100:.1f}%")
    print(f"後手勝率: {total_second/100*100:.1f}%")

if __name__ == "__main__":
    main()