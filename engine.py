import numpy as np
import random
import time
from evaluate_numba import evaluate_pattern_numba

class GomokuAnalyzer:
    def __init__(self, size=15):
        self.size = size
        self.board = np.zeros((size, size), dtype=int)
        self.current_player = 1
        self.move_history = []
        # GAで調整したいスコアを辞書にまとめる
        self.weights = {
            'five': 100000,
            'open_four': 12000,
            'dead_four': 5000,
            'open_three': 1500,
            'dead_three': 200,
            'open_two': 50,
            'defense_weight': 1.2,
            # --- 守備専用の重み ---
            'def_open_four': 50000,
            'def_open_three': 2000,
            'def_dead_three': 300,
            # --- その他の重み ---
            'fork_44': 15000, 
            'fork_43': 8000, 
            'fork_33': 3000, 
            'center_bonus': 100,
            'continuity_weight': 100 
        }

    def put_stone(self, r, c, player):
        if 0 <= r < self.size and 0 <= c < self.size and self.board[r][c] == 0:
            self.board[r][c] = player
            self.move_history.append((r, c, player))
            return True
        return False

    def is_within_board(self, r, c):
        """盤面内かどうかを判定"""
        return 0 <= r < self.size and 0 <= c < self.size
    
    def get_line_openness(self, r, c, dr, dc, player):
        """両端の開きを正確に判定"""
        # 正方向の連続石を数える
        pos_count = 0
        for i in range(1, 6):
            nr, nc = r + dr * i, c + dc * i
            if not self.is_within_board(nr, nc):
                break
            if self.board[nr][nc] == player:
                pos_count += 1
            elif self.board[nr][nc] == 0:
                break
            else:
                break
        
        # 負方向の連続石を数える
        neg_count = 0
        for i in range(1, 6):
            nr, nc = r - dr * i, c - dc * i
            if not self.is_within_board(nr, nc):
                break
            if self.board[nr][nc] == player:
                neg_count += 1
            elif self.board[nr][nc] == 0:
                break
            else:
                break
        
        # 両端の空き判定
        front_open = False
        back_open = False
        
        # 正方向の空き判定（連続石の次のマス）
        next_pos = (r + dr * (pos_count + 1), c + dc * (pos_count + 1))
        if self.is_within_board(*next_pos) and self.board[next_pos] == 0:
            front_open = True
        
        # 負方向の空き判定（連続石の前のマス）
        next_neg = (r - dr * (neg_count + 1), c - dc * (neg_count + 1))
        if self.is_within_board(*next_neg) and self.board[next_neg] == 0:
            back_open = True
        
        return front_open, back_open
    
    def detect_urgent_threats(self, player):
        """緊急な脅威を検出（活四・活三など）。活三(>=1000)以上を返す"""
        threats = []
        candidate_moves = self.get_candidate_moves()
        
        for r, c in candidate_moves:
            if self.board[r][c] != 0:
                continue
            
            directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
            max_score = 0
            for dr, dc in directions:
                score = self.evaluate_pattern(r, c, dr, dc, player)
                if score > max_score:
                    max_score = score
            
            # 活三(>=1000)以上を緊急脅威として扱う（活四=12000, 五連=100000等）
            if max_score >= self.weights['open_three']:
                threats.append((r, c, max_score))
        
        # スコア順（降順）にして返す
        threats.sort(key=lambda x: -x[2])
        return threats


    def evaluate_pattern(self, r, c, dr, dc, player):
        """1方向のパターンを文字列マッチングで詳細に評価"""
        # 1. 注目しているマスの前後4マス、計9マスの状態を取得
        line = []
        for i in range(-4, 5):
            nr, nc = r + dr * i, c + dc * i
            if self.is_within_board(nr, nc):
                # (r, c) の位置にはこれから石を置くので、player の石として扱う
                val = self.board[nr][nc] if i != 0 else player
                line.append(val)
            else:
                line.append(-1)  # 盤外は -1
                
        # 文字列に変換（例: "0110110"）
        # 0:空き, 1:黒, 2:白, -1:盤外(X)
        s = "".join([str(x) if x != -1 else "X" for x in line])
        p = str(player)
        o = "0"

        # --- 2. パターンマッチング（強い順に判定） ---
        # 【五連】
        if p * 5 in s:
            return self.weights['five']

        # 【活四】 . ● ● ● ● .
        if f"{o}{p*4}{o}" in s:
            return self.weights['open_four']

        # 【眠四】 (トビ四を含む)
        # 例: ● ● . ● ●  や  ● . ● ● ● など
        dead_four_patterns = [
            p*4,          # ●●●●
            f"{p}{o}{p*3}", # ●.●●●
            f"{p*3}{o}{p}", # ●●●.●
            f"{p*2}{o}{p*2}" # ●●.●●
        ]
        if any(pat in s for pat in dead_four_patterns):
            # 両端のどちらかが空いていれば眠四 (活四は上で除外済み)
            return self.weights['dead_four']

        # 【活三】 (トビ活三を含む)
        # 通常の活三: .●●●.
        # トビ三の例: .●.●●. や .●●.●. など
        open_three_patterns = [
            f"{o}{p*3}{o}",      # .●●●.
            f"{o}{p}{o}{p*2}{o}",  # .●.●●.
            f"{o}{p*2}{o}{p}{o}",  # .●●.●.
            # さらにトビ三のバリエーション (7マス中に3つの石が2グループ)
            f"{o}{p}{o}{p}{o}{p}{o}",  # .●.●.●. (飛び三連続の一種)
            f"{o}{p*2}{o}{p}{o}{p}{o}", # .●●.●.●. (やや長いが部分一致で検出)
        ]
        if any(pat in s for pat in open_three_patterns):
            return self.weights['open_three']

        # 【眠三】
        # 片方が塞がった三連 (例えば先頭が盤外や相手石)
        if p * 3 in s:
            return self.weights['dead_three']

        # 【活二】
        if f"{o}{p*2}{o}" in s:
            return self.weights['open_two']

        return 0

    def detect_forks(self, r, c, player):
        """三三、四三などのフォークを検出"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        # 各方向の脅しの強さを評価
        threats = []
        for dr, dc in directions:
            score = self.evaluate_pattern(r, c, dr, dc, player)
            
            # ここも本当は weights を参照するとより進化しやすくなります
            if score >= self.weights['open_four']: # 10000の代わりに
                threats.append('four')
            elif score >= self.weights['open_three']: # 1000の代わりに
                threats.append('three')
            elif score >= self.weights['dead_three']: # 200の代わりに
                threats.append('half-three')
        
        # フォークのボーナス計算
        bonus = 0
        three_count = threats.count('three')
        four_count = threats.count('four')
        
        # --- 直接の数字を self.weights の項目名に変更 ---
        if four_count >= 2:
            bonus += self.weights['fork_44']  # 15000の代わり
        if four_count >= 1 and three_count >= 1:
            bonus += self.weights['fork_43']  # 8000の代わり
        if three_count >= 2:
            bonus += self.weights['fork_33']  # 3000の代わり
        
        return bonus

    def evaluate_board_enhanced(self, for_player=None):
        """改良版評価関数 - メインで使用する"""
        if for_player is None:
            for_player = self.current_player
        
        scores = np.zeros((self.size, self.size))
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        # 候補手の限定（既存の石から2マス以内）
        candidate_moves = self.get_candidate_moves()
        
        for r, c in candidate_moves:
            if self.board[r][c] != 0:
                continue
            
            # 攻撃スコア（自分の石の評価）
            attack_score = 0
            for dr, dc in directions:
                attack_score += self.evaluate_pattern(r, c, dr, dc, for_player)
            
            # フォークボーナス
            fork_bonus = self.detect_forks(r, c, for_player)
            attack_score += fork_bonus
            
            # 防御スコア（相手の石の評価を阻止する価値）
            defense_score = 0
            opponent = 3 - for_player
            
            for dr, dc in directions:
                opp_score = self.evaluate_pattern(r, c, dr, dc, opponent)
                # 相手の脅威レベルに応じた防御ボーナス（防御用重みを使用）
                if opp_score >= self.weights['open_four']:
                    defense_score += self.weights['def_open_four']
                elif opp_score >= self.weights['open_three']:
                    defense_score += self.weights['def_open_three']
                elif opp_score >= self.weights['dead_three']:
                    defense_score += self.weights['def_dead_three']
                # 必要に応じてさらに低い脅威（dead_twoなど）も追加可能
            
            # 中央性ボーナス
            center = self.size // 2
            distance = abs(r - center) + abs(c - center)
            center_bonus = max(0, 10 - distance) * self.weights.get('center_bonus', 100)
            
            # 既存の脅しを活かすボーナス
            continuity_bonus = self.continuity_bonus(r, c, for_player)
            
            # 総合スコア（攻撃:1.0, 防御:weights['defense_weight']の重み）
            total_score = (attack_score * 1.0 + defense_score * self.weights['defense_weight'] + 
                          center_bonus + continuity_bonus)
            
            scores[r][c] = total_score
        
        return scores
    
    def get_candidate_moves(self):
        """探索範囲を限定（石の周囲2マスのみ）"""
        candidates = set()
        board_size = self.size
        
        # すべての石の周囲を候補に追加
        for i in range(board_size):
            for j in range(board_size):
                if self.board[i][j] != 0:
                    for di in range(-2, 3):
                        for dj in range(-2, 3):
                            ni, nj = i + di, j + dj
                            if 0 <= ni < board_size and 0 <= nj < board_size:
                                if self.board[ni][nj] == 0:
                                    candidates.add((ni, nj))
        
        # 空の盤面の場合、中央を候補に
        if not candidates:
            candidates.add((board_size//2, board_size//2))
        
        return list(candidates)
    
    def continuity_bonus(self, r, c, player):
        """攻めの継続性ボーナス（既存の攻撃ラインを活かす手）"""
        bonus = 0
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            # この方向に既に並んでいる自分の石の数を数える
            count = 0
            for i in range(1, 4):
                nr, nc = r + dr * i, c + dc * i
                if self.is_within_board(nr, nc) and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            for i in range(1, 4):
                nr, nc = r - dr * i, c - dc * i
                if self.is_within_board(nr, nc) and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 2:
                bonus += self.weights.get('continuity_weight', 100) * count
        
        return bonus
        
    def evaluate_board(self, for_player=None):
        """従来の評価関数（後方互換性のため保持）"""
        return self.evaluate_board_enhanced(for_player)

    def check_win(self, r, c, player):
        """勝利判定"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            count = 1
            
            # 正方向
            for i in range(1, 5):
                nr, nc = r + dr * i, c + dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            # 負方向
            for i in range(1, 5):
                nr, nc = r - dr * i, c - dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 5:
                return True
        
        return False
    
    def get_best_move(self, depth_limit=None):
        """最善手探索（反復深化付き＋急所検出）"""
        # 【最優先：相手の即勝ち手を防ぐ】
        player = self.current_player
        opponent = 3 - self.current_player
        candidate_moves = self.get_candidate_moves()
        
        for r, c in candidate_moves:
            self.board[r][c] = opponent
            if self.check_win(r, c, opponent):
                self.board[r][c] = 0
                #print(f"  → 防御急所！({r}, {c}) に着手してブロック")
                return (r, c)
            self.board[r][c] = 0
        
        # 【自分の即勝ち手があれば指す】
        for r, c in candidate_moves:
            self.board[r][c] = self.current_player
            if self.check_win(r, c, self.current_player):
                self.board[r][c] = 0
                #print(f"  → 勝利急所！({r}, {c}) に着手して勝利")
                return (r, c)
            self.board[r][c] = 0

        # 【追加】相手の活三・活四などの緊急脅威を検出してブロック
        urgent = self.detect_urgent_threats(opponent)
        if urgent:
            ur = urgent[0]
            #print(f"  → 防御急所(urgent)！({ur[0]}, {ur[1]}) に着手して阻止 (score={ur[2]})")
            return (ur[0], ur[1])
        
         # 【追加】自分の活三・活四を優先して攻める
        my_urgent = self.detect_urgent_threats(player)
        if my_urgent:
            ur = my_urgent[0]
            #print(f"  → 攻撃急所！({ur[0]}, {ur[1]}) に着手 (score={ur[2]})")
            return (ur[0], ur[1])

        # 最初の数手は静的評価
        if len(self.move_history) < 3:
            return self.get_best_move_static()
        
        # 反復深化探索（時間制限付き）
        start_time = time.time()
        time_limit = 1.0  # 1秒制限
        best_move = None
        best_score = -float('inf')
        
        # 深さ1から徐々に深く
        start_depth = 1
        end_depth = 4
        
        if depth_limit is not None:
            start_depth = depth_limit
            end_depth = depth_limit + 1
            time_limit = 5.0  # GA用：1手最大5秒
        else:
            time_limit = 1.0  # 通常プレイ時は1秒制限

        # 反復深化探索
        for depth in range(start_depth, end_depth):
            if time.time() - start_time > time_limit:
                break
            
            moves = self.get_ordered_moves(self.current_player)
            current_best = None
            current_score = -float('inf')
            
            for r, c in moves:
                if time.time() - start_time > time_limit:
                    break
                
                self.board[r][c] = self.current_player
                score = self.minimax(depth - 1, -float('inf'), float('inf'), False, (r, c))
                self.board[r][c] = 0
                
                if score > current_score:
                    current_score = score
                    current_best = (r, c)
            
            if current_best and current_score > best_score:
                best_move = current_best
                best_score = current_score
        
        return best_move if best_move else self.get_best_move_static()

    def get_best_move_static(self):
        """静的評価関数のみを使用（急所検出付き）"""
        candidate_moves = self.get_candidate_moves()
        
        # 【最優先：相手の即勝ち手を防ぐ】
        opponent = 3 - self.current_player
        for r, c in candidate_moves:
            self.board[r][c] = opponent
            if self.check_win(r, c, opponent):
                self.board[r][c] = 0
                #print(f"  → 防御急所（static）！({r}, {c}) に着手してブロック")
                return (r, c)
            self.board[r][c] = 0
        
        # 【自分の即勝ち手があれば指す】
        for r, c in candidate_moves:
            self.board[r][c] = self.current_player
            if self.check_win(r, c, self.current_player):
                self.board[r][c] = 0
                #print(f"  → 勝利急所（static）！({r}, {c}) に着手して勝利")
                return (r, c)
            self.board[r][c] = 0
        
        # 通常の評価で決める
        scores = self.evaluate_board_enhanced(self.current_player)
        max_score = -float('inf')
        best_moves = []
        
        for r, c in candidate_moves:
            score = scores[r][c]
            if score > max_score:
                max_score = score
                best_moves = [(r, c)]
            elif abs(score - max_score) < 1e-9:
                best_moves.append((r, c))
        
        if best_moves:
            return random.choice(best_moves)
        
        # フォールバック
        center = self.size // 2
        for dr in range(self.size):
            for dc in range(self.size):
                r = (center + dr) % self.size
                c = (center + dc) % self.size
                if self.board[r][c] == 0:
                    return r, c
        
        return None

    def get_game_state(self):
        """ゲーム状態を文字列で返す"""
        state = []
        for r in range(self.size):
            row = []
            for c in range(self.size):
                if self.board[r][c] == 0:
                    row.append('.')
                elif self.board[r][c] == 1:
                    row.append('B')
                else:
                    row.append('W')
            state.append(''.join(row))
        return '\n'.join(state)
    
    def minimax(self, depth, alpha, beta, maximizing_player, last_move=None, ai_player=None):
        """αβ枝切り付きミニマックス法（修正版）"""
        if ai_player is None:
            ai_player = self.current_player
        
        # 勝利判定（シンプル化）
        if last_move:
            r, c = last_move
            moving_player = ai_player if maximizing_player else (3 - ai_player)
            if self.check_win(r, c, moving_player):
                return 1000000 if moving_player == ai_player else -1000000
        
        # 深さ0で評価
        if depth == 0:
            return self.quick_evaluate(ai_player)
        
        # 手の候補を評価値順にソート
        moves = self.get_ordered_moves(ai_player if maximizing_player else (3 - ai_player))
        
        if maximizing_player:
            val = -float('inf')
            for r, c in moves:
                self.board[r][c] = ai_player
                res = self.minimax(depth - 1, alpha, beta, False, (r, c), ai_player)
                self.board[r][c] = 0
                val = max(val, res)
                alpha = max(alpha, val)
                if beta <= alpha:
                    break
            return val
        else:
            val = float('inf')
            opponent = 3 - ai_player
            for r, c in moves:
                self.board[r][c] = opponent
                res = self.minimax(depth - 1, alpha, beta, True, (r, c), ai_player)
                self.board[r][c] = 0
                val = min(val, res)
                beta = min(beta, val)
                if beta <= alpha:
                    break
            return val
    
    def get_ordered_moves(self, player):
        """評価値の高い順に手をソート（αβ枝刈りの効率化）"""
        moves = self.get_candidate_moves()
        if not moves:
            return []
        
        scored_moves = []
        for r, c in moves:
            if self.board[r][c] == 0:
                self.board[r][c] = player
                score = self.quick_positional_score(r, c, player)
                self.board[r][c] = 0
                scored_moves.append((-score, r, c))
        
        scored_moves.sort()
        return [(r, c) for _, r, c in scored_moves]

    def quick_positional_score(self, r, c, player):
        """手の簡易位置評価（ソート用）"""
        score = 0
        
        # 中央に近いほど高評価
        center = self.size // 2
        distance = abs(r - center) + abs(c - center)
        score += max(0, 10 - distance) * 10
        
        # 既存の石の近くは高評価
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.size and 0 <= nc < self.size:
                    if self.board[nr][nc] == player:
                        score += 50
                    elif self.board[nr][nc] == (3 - player):
                        score += 30
        
        return score
    
    def quick_evaluate(self, player):
        """
        軽量評価関数（ミニマックス用）
        ★ numba高速化 + self.weights使用 → GAの重みが読みに直結する
        """
        if self.check_win_anywhere(player):
            return 100000
        if self.check_win_anywhere(3 - player):
            return -100000

        # numba用にweightsを配列化
        w = np.array([
            self.weights['five'],
            self.weights['open_four'],
            self.weights['dead_four'],
            self.weights['open_three'],
            self.weights['dead_three'],
            self.weights['open_two'],
        ], dtype=np.float64)

        score = 0.0
        opponent = 3 - player
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]

        for r, c in self.get_candidate_moves():
            if self.board[r][c] != 0:
                continue
            for dr, dc in directions:
                score += evaluate_pattern_numba(self.board, r, c, dr, dc, player, w, self.size)
                opp = evaluate_pattern_numba(self.board, r, c, dr, dc, opponent, w, self.size)
                score -= opp * self.weights['defense_weight']

        return score

    def evaluate_single_stone(self, r, c, player):
        """単一の石の影響力を評価"""
        if self.board[r][c] != player:
            return 0
        
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        stone_value = 0
        
        for dr, dc in directions:
            count = 1
            for i in range(1, 5):
                nr, nc = r + dr * i, c + dc * i
                if not self.is_within_board(nr, nc):
                    break
                if self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            for i in range(1, 5):
                nr, nc = r - dr * i, c - dc * i
                if not self.is_within_board(nr, nc):
                    break
                if self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 5:
                stone_value += 10000
            elif count == 4:
                stone_value += 1000
            elif count == 3:
                stone_value += 100
            elif count == 2:
                stone_value += 10
        
        return stone_value

    def check_win_anywhere(self, player):
        """盤面全体で勝利判定"""
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == player:
                    if self.check_win(r, c, player):
                        return True
        return False