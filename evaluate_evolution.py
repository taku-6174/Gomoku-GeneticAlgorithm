# evaluate_evolution.py
from ga_manager import Individual, play_match
from engine import GomokuAnalyzer
import ast

def main():
    # 初期個体
    default = GomokuAnalyzer()
    default_ind = Individual(weights=default.weights)
    
    # 進化個体
    with open("best_weights_ver3.txt", "r") as f:
        best = ast.literal_eval(f.read())
    best_ind = Individual(weights=best)
    
    # 対戦実行
    results = {"best_win": 0, "default_win": 0, "draw": 0}
    
    for i in range(100):  # 100回対戦
        if i % 2 == 0:
            winner = play_match(best_ind, default_ind)
        else:
            winner = play_match(default_ind, best_ind)
        
        if winner == 1:
            results["best_win" if i % 2 == 0 else "default_win"] += 1
        elif winner == 2:
            results["default_win" if i % 2 == 0 else "best_win"] += 1
        else:
            results["draw"] += 1
    
    print(f"進化個体: {results['best_win']}勝")
    print(f"初期個体: {results['default_win']}勝")
    print(f"引分: {results['draw']}")
    print(f"進化個体の勝率: {results['best_win']/100*100:.1f}%")

if __name__ == "__main__":
    main()