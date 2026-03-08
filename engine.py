import numpy as np
import random
import time
import math
from collections import defaultdict

# ============================================================================
# フェーズ1：パターンライブラリの定義（全基本パターンの統一）
# ============================================================================

class GomokuPatterns:
    """五目並べの全基本パターン定義"""
    
    # 攻撃パターン（強度順、GAで最適化可能）
    ATTACK_SCORES = {
        'five_or_more': 100000,          # 五連以上 = 勝利確定
        'guaranteed_four': 50000,        # 活四で次ターンに五連確定
        'fork_four_four': 20000,         # 活四×2（両見）
        'fork_four_three': 10000,        # 活四×活三（両見）
        'fork_three_three': 5000,        # 活三×2（相手がブロック不可）
        'open_four': 3000,               # 活四（相手が防ぐ必要あり）
        'open_three': 800,               # 活三（脅威）
        'dead_four': 300,                # 眠四（トビ四含む）
        'dead_three': 100,               # 眠三
        'open_two': 30,                  # 活二
        'dead_two': 5,                   # 眠二
    }
    
    # 防御パターン
    DEFENSE_SCORES = {
        'block_guaranteed_win': 50000,   # 相手の必勝を防ぐ
        'block_fork_four_four': 20000,   # 相手の活四×2を阻止
        'block_fork_four_three': 10000,  # 相手の活四×活三を阻止
        'block_open_four': 3000,         # 相手の���四を止める
        'block_open_three': 800,         # 相手の活三を止める
    }

class MCTSNode:
    """モンテカルロ木探索のノード - 改良版（盤面保存）"""
    def __init__(self, board_state, player, parent=None):
        # ✅ 盤面状態を保存
        self.board_state = board_state.copy() if board_state is not None else None
        self.player = player
        self.parent = parent
        self.children = {}  # (r, c) -> MCTSNode
        self.visits = 0
        self.value = 0.0
        self.untried_moves = None
    
    def ucb1(self, c=1.414):
        """UCB1値を計算"""
        if self.visits == 0:
            return float('inf')
        exploitation = self.value / self.visits
        exploration = c * math.sqrt(math.log(self.parent.visits) / self.visits) if self.parent and self.parent.visits > 0 else 0
        return exploitation + exploration
    
    def select_best_child(self, c=1.414):
        """UCB1値が最大の子ノードを選択"""
        if not self.children:
            return None
        return max(self.children.values(), key=lambda n: n.ucb1(c))
    
    def backpropagate(self, result):
        """探索結果をバックプロパゲート"""
        self.visits += 1
        self.value += result
        if self.parent:
            self.parent.backpropagate(result)

class GomokuAnalyzer:
    def __init__(self, size=15):
        self.size = size
        self.board = np.zeros((size, size), dtype=int)
        self.current_player = 1
        self.move_history = []
        
        # ============================================================================
        # 改良版重み定義（フェーズ1B：構造化された重み）
        # ============================================================================
        self.weights = {
            # === 基本パターン（攻撃） ===
            'five': 100000,
            'guaranteed_four': 50000,
            'open_four': 12000,
            'dead_four': 5000,
            'open_three': 1500,
            'dead_three': 200,
            'open_two': 50,
            
            # === フォーク・両見 ===
            'fork_44': 15000,
            'fork_43': 8000,
            'fork_33': 3000,
            'both_open_threats': 10000,  # 新規：両見検出ボーナス
            
            # === 防御関連 ===
            'defense_weight': 1.2,
            'def_open_four': 50000,      # 相手の活四防ぐ
            'def_open_three': 2000,      # 相手の活三防ぐ
            'def_dead_three': 300,
            'def_multiple_threats': 15000,  # 新規：複数脅威同時ブロック
            
            # === その他 ===
            'center_bonus': 100,
            'continuity_weight': 100,
            'mcts_simulation_depth': 3,  # フェーズ4：MCTS用シミュレーション深さ
        }
        
        # MCTS用キャッシュ
        self.mcts_cache = {}

    # ============================================================================
    # フェーズ1A：評価関数の「正確性」強化
    # ============================================================================
    
    def is_within_board(self, r, c):
        """盤面内かどうかを判定"""
        return 0 <= r < self.size and 0 <= c < self.size
    
    def count_stones_in_direction(self, r, c, dr, dc, player, count_empty_end=False):
        """
        指定方向に連続する自分の石をカウント
        
        Args:
            count_empty_end: True の場合、石の両端の空きマスをタプルで返す
        
        Returns:
            石の数、または (石の数, 両端空きフラグ) のタプル
        """
        count = 0
        empty_ends = []  # 両端の空きマス
        
        # 正方向
        for i in range(1, 6):
            nr, nc = r + dr * i, c + dc * i
            if not self.is_within_board(nr, nc):
                if count_empty_end:
                    empty_ends.append((nr, nc))
                break
            if self.board[nr][nc] == player:
                count += 1
            elif self.board[nr][nc] == 0:
                if count_empty_end:
                    empty_ends.append((nr, nc))
                break
            else:
                break
        
        # 負方向
        for i in range(1, 6):
            nr, nc = r - dr * i, c - dc * i
            if not self.is_within_board(nr, nc):
                if count_empty_end:
                    empty_ends.append((nr, nc))
                break
            if self.board[nr][nc] == player:
                count += 1
            elif self.board[nr][nc] == 0:
                if count_empty_end:
                    empty_ends.append((nr, nc))
                break
            else:
                break
        
        if count_empty_end:
            return count, len(empty_ends)
        return count
    
    def get_line_openness(self, r, c, dr, dc, player):
        """
        指定方向の両端の開きを正確に判定
        
        改良版：「連続石の個数」と「両端が空いているか」を正確に返す
        
        Args:
            r, c: 着手位置（ここに player の石を置いたと仮定）
            dr, dc: 判定方向
            player: プレイヤー（1 or 2）
        
        Returns:
            (front_open, back_open, pos_count, neg_count)
            - front_open: 正方向に空きマスがあるか
            - back_open: 負方向に空きマスがあるか
            - pos_count: 正方向の連続石の数（r,c は含まない）
            - neg_count: 負方向の連続石の数（r,c は含まない）
        """
        # 正方向の連続石をカウント
        pos_count = 0
        for i in range(1, 6):
            nr, nc = r + dr * i, c + dc * i
            if not self.is_within_board(nr, nc):
                break
            if self.board[nr][nc] == player:
                pos_count += 1
            elif self.board[nr][nc] == 0:
                break
            else:  # 相手石
                break
        
        # 負方向の連続石をカウント
        neg_count = 0
        for i in range(1, 6):
            nr, nc = r - dr * i, c - dc * i
            if not self.is_within_board(nr, nc):
                break
            if self.board[nr][nc] == player:
                neg_count += 1
            elif self.board[nr][nc] == 0:
                break
            else:  # 相手石
                break
        
        # 正方向の空き判定（連続石の次のマス）
        front_open = False
        next_pos = (r + dr * (pos_count + 1), c + dc * (pos_count + 1))
        if self.is_within_board(*next_pos) and self.board[next_pos] == 0:
            front_open = True
        
        # 負方向の空き判定（連続石の前のマス）
        back_open = False
        next_neg = (r - dr * (neg_count + 1), c - dc * (neg_count + 1))
        if self.is_within_board(*next_neg) and self.board[next_neg] == 0:
            back_open = True
        
        return front_open, back_open, pos_count, neg_count

    def evaluate_pattern_hierarchical(self, r, c, dr, dc, player):
        """
        改良版：9マスの文字列パターンマッチングで全パターンを統一判定
        
        跳び三（●.●●.や●●.●.）を活三として正しく評価
        五連・活四・死四の判定も正確に
        
        Args:
            r, c: 着手位置
            dr, dc: 判定方向
            player: プレイヤー（1 or 2）
        
        Returns:
            パターンのスコア
        """
        # 9マス取得（r,c を中心に前後4マス）
        line = []
        for i in range(-4, 5):
            nr, nc = r + dr * i, c + dc * i
            if self.is_within_board(nr, nc):
                val = self.board[nr][nc] if i != 0 else player
                line.append(val)
            else:
                line.append(-1)  # 盤外は -1
        
        s = "".join([str(x) if x != -1 else "X" for x in line])
        p = str(player)
        o = "0"
        opponent = 3 - player
        opp_str = str(opponent)
        
        # === 五連以上 ===
        if p * 5 in s:
            return self.weights['five']
        
        # === 活四（両端空き：.●●●●.） ===
        if f"{o}{p*4}{o}" in s:
            return self.weights['open_four']
        
        # === 死四（片端or両端塞がり） ===
        # ●●●●（盤外or相手石に隣接）
        dead_four_patterns = [
            p*4,                    # ●●●●
            f"X{p*4}",              # 盤外●●●●
            f"{p*4}X",              # ●●●●盤外
            f"{opp_str}{p*4}",      # 相手●●●●
            f"{p*4}{opp_str}",      # ●●●●相手
        ]
        if any(pat in s for pat in dead_four_patterns):
            return self.weights['dead_four']
        
        # === 活三（両端空き） ===
        # 通常: .●●●.
        if f"{o}{p*3}{o}" in s:
            return self.weights['open_three']
        
        # === 跳び三の全パターン ===
        # .●.●●. または .●●.●. などの形式
        skip_three_patterns = [
            f"{o}{p}{o}{p*2}{o}",   # .●.●●.
            f"{o}{p*2}{o}{p}{o}",   # .●●.●.
        ]
        if any(pat in s for pat in skip_three_patterns):
            return self.weights['open_three']
        
        # === 死三（片端塞がり） ===
        # ●●●（盤外or相手石に隣接）
        dead_three_patterns = [
            p*3,                    # ●●●
            f"X{p*3}",              # 盤外●●●
            f"{p*3}X",              # ●●●盤外
            f"{opp_str}{p*3}",      # 相手●●●
            f"{p*3}{opp_str}",      # ●●●相手
        ]
        if any(pat in s for pat in dead_three_patterns):
            return self.weights['dead_three']
        
        # === 活二 ===
        if f"{o}{p*2}{o}" in s:
            return self.weights['open_two']
        
        return 0
    
    def evaluate_pattern(self, r, c, dr, dc, player):
        """
        従来の文字列マッチング方式（後方互換性のため保持）
        内部的には evaluate_pattern_hierarchical を使用
        """
        return self.evaluate_pattern_hierarchical(r, c, dr, dc, player)

    # ============================================================================
    # フェーズ1A追加：「両見」（りょうけん）検出（必須）
    # ============================================================================
    
    def evaluate_both_open_threats(self, r, c, player):
        """
        【両見検出】相手が1手では両方ブロックできない複数の脅威
        
        返り値: ボーナススコア
        """
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        threats = []
        
        for dr, dc in directions:
            score = self.evaluate_pattern(r, c, dr, dc, player)
            if score >= self.weights['open_three']:  # 活三以上
                threats.append({
                    'score': score,
                    'dir': (dr, dc),
                })
        
        # 複数の脅威がある場合、両見ボーナスを追加
        if len(threats) >= 2:
            # 活四×2 > 活四×活三 > 活三×2 の順で強い
            four_count = sum(1 for t in threats if t['score'] >= self.weights['open_four'])
            three_count = sum(1 for t in threats if self.weights['open_three'] <= t['score'] < self.weights['open_four'])
            
            if four_count >= 2:
                return self.weights['fork_44'] * 1.5
            elif four_count >= 1 and three_count >= 1:
                return self.weights['fork_43'] * 1.5
            elif three_count >= 2:
                return self.weights['both_open_threats']
        
        return 0

    # ============================================================================
    # フェーズ2：VCF（連続四）検出
    # ============================================================================
    
    def has_guaranteed_four(self, r, c, player):
        """
        この着手は「次ターンで活四が確実に作れる」状態か？
        
        （つまり、相手がブロックしても、次のターンで別の場所に活四を作れる）
        """
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        four_candidates = []
        for dr, dc in directions:
            score = self.evaluate_pattern(r, c, dr, dc, player)
            if score >= self.weights['open_four']:
                # この方向で活四が成立している
                front_open, back_open, pos_count, neg_count = self.get_line_openness(r, c, dr, dc, player)
                if front_open and back_open:
                    four_candidates.append((dr, dc))
        
        # 複数方向で活四が作れる = 次ターンで確実に詰む
        return len(four_candidates) >= 2
    
    def get_block_position_for_threat(self, r, c, dr, dc, player):
        """
        活四や活三をブロックするなら、どこに置くべきか返す
        """
        front_open, back_open, pos_count, neg_count = self.get_line_openness(r, c, dr, dc, player)
        
        if front_open:
            block_r = r + dr * (pos_count + 1)
            block_c = c + dc * (pos_count + 1)
            if self.is_within_board(block_r, block_c):
                return (block_r, block_c)
        
        if back_open:
            block_r = r - dr * (neg_count + 1)
            block_c = c - dc * (neg_count + 1)
            if self.is_within_board(block_r, block_c):
                return (block_r, block_c)
        
        return None
    
    def find_vcf_move(self, player, depth=0):
        """
        VCF（連続四）探索 - 改良版
        
        改良点：
        1. 動的深さ制限
        2. 複数の四のうち、一つでもVCFになればOK
        """
        # ✅ 動的な最大深さ設定
        if len(self.move_history) < 10:
            max_depth = 2
        elif len(self.move_history) < 40:
            max_depth = 3
        else:
            max_depth = 4
        
        if depth > max_depth:
            return None
        
        candidate_moves = self.get_candidate_moves()
        
        for r, c in candidate_moves:
            if self.board[r][c] != 0:
                continue
            
            # この手で「四」が作れるか判定
            directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
            four_list = []
            
            for dr, dc in directions:
                front_open, back_open, pos_count, neg_count = self.get_line_openness(r, c, dr, dc, player)
                total = 1 + pos_count + neg_count
                
                if total == 4 and (front_open or back_open):
                    block_positions = []
                    
                    if front_open:
                        block_r = r + dr * (pos_count + 1)
                        block_c = c + dc * (pos_count + 1)
                        if self.is_within_board(block_r, block_c) and self.board[block_r][block_c] == 0:
                            block_positions.append((block_r, block_c))
                    
                    if back_open:
                        block_r = r - dr * (neg_count + 1)
                        block_c = c - dc * (neg_count + 1)
                        if self.is_within_board(block_r, block_c) and self.board[block_r][block_c] == 0:
                            block_positions.append((block_r, block_c))
                    
                    if block_positions:
                        four_list.append({
                            'dir': (dr, dc),
                            'blocks': block_positions,
                        })
            
            if not four_list:
                continue
            
            # ✅ 改良：複数の四のうち、一つでもVCFになればOK
            self.board[r][c] = player
            
            any_four_has_vcf = False
            for four_info in four_list:
                block_positions = four_info['blocks']
                four_has_vcf = False
                
                for block_r, block_c in block_positions:
                    self.board[block_r][block_c] = 3 - player
                    
                    next_vcf = self.find_vcf_move(player, depth + 1)
                    
                    self.board[block_r][block_c] = 0
                    
                    if next_vcf:
                        four_has_vcf = True
                        break
                
                if four_has_vcf:
                    any_four_has_vcf = True
                    break
            
            self.board[r][c] = 0
            
            if any_four_has_vcf:
                return (r, c)
        
        return None

    # ============================================================================
    # フェーズ2拡張：VCT（連続詰み）検出
    # ============================================================================
    
    def find_vct_move(self, player, depth=0, max_depth=6):
        """
        VCT（連続詰み）探索：脅威を連続して繰り出し、相手が受けきれない手順
        """
        if depth > max_depth:
            return None
        
        candidate_moves = self.get_candidate_moves()
        threat_moves = []
        
        # まず、自分が活三以上の脅威を作れる手を集める
        for r, c in candidate_moves:
            if self.board[r][c] != 0:
                continue
            
            directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
            max_score = 0
            
            for dr, dc in directions:
                score = self.evaluate_pattern(r, c, dr, dc, player)
                if score > max_score:
                    max_score = score
            
            # 活三以上の脅威
            if max_score >= self.weights['open_three']:
                threat_moves.append((r, c, max_score))
        
        # スコア順にソート
        threat_moves.sort(key=lambda x: -x[2])
        
        for r, c, _ in threat_moves:
            self.board[r][c] = player
            
            if self.check_win(r, c, player):
                self.board[r][c] = 0
                return (r, c)
            
            # 相手の防御選択肢を列挙
            opponent_defenses = self.get_candidate_moves()
            can_continue_threat = True
            
            for dr, dc in opponent_defenses[:3]:  # 上位3選択肢のみチェック（計算量削減）
                if self.board[dr][dc] == 0:
                    self.board[dr][dc] = 3 - player
                    
                    # 相手の防御後、再度脅威を作れるか
                    next_vct = self.find_vct_move(player, depth + 1, max_depth)
                    
                    self.board[dr][dc] = 0
                    
                    if not next_vct:
                        can_continue_threat = False
                        break
            
            self.board[r][c] = 0
            
            if can_continue_threat:
                return (r, c)
        
        return None

    # ============================================================================
    # フェーズ3/4：MCTS（モンテカルロ木探索）
    # ============================================================================
    
    def mcts_search(self, player, iterations=1000):
        """
        MCTS（モンテカルロ木探索）メイン処理 - 改良版
        
        各ノードに盤面状態を保存する方式
        """
        root_board = self.board.copy()  # ✅ ルートの盤面を保存
        root = MCTSNode(root_board, player, None)
        root.visits = 1
        
        for iteration in range(iterations):
            node = root
            board = root.board_state.copy()  # ✅ ノードから盤面を取得
            
            # === 選択フェーズ ===
            while node.children and node.visits > 10:
                node = node.select_best_child()
                board = node.board_state.copy()  # ✅ 選択したノードの盤面を使用
            
            # === 展開フェーズ ===
            if node.untried_moves is None:
                candidate_moves = []
                for i in range(self.size):
                    for j in range(self.size):
                        if board[i][j] == 0:
                            candidate_moves.append((i, j))
                node.untried_moves = candidate_moves
                random.shuffle(node.untried_moves)
            
            if node.untried_moves:
                r, c = node.untried_moves.pop()
                board[r][c] = node.player
                child_board = board.copy()  # ✅ 子ノードの盤面を保存
                child = MCTSNode(child_board, 3 - node.player, node)
                node.children[(r, c)] = child
                node = child
                current_player = 3 - node.player
            else:
                current_player = node.player
            
            # === シミュレーション フェーズ ===
            result = self._mcts_simulate_with_board(board.copy(), current_player, depth=0, max_depth=3)
            
            # === バックプロパゲーション ===
            node.backpropagate(result)
        
        # 最も訪問回数が多い子ノードを選択
        if root.children:
            best_move = max(root.children.items(), key=lambda x: x[1].visits)[0]
            return best_move
        
        return None

    def _mcts_simulate_with_board(self, board, player, depth=0, max_depth=3):
        """
        MCTSのシミュレーションを盤面コピーで実行
        """
        if depth > max_depth:
            return 0
        
        # 勝敗判定
        score_self = self._evaluate_board_mcts(board, player)
        score_opp = self._evaluate_board_mcts(board, 3 - player)
        
        if score_self > score_opp + 10000:
            return 1.0
        elif score_opp > score_self + 10000:
            return -1.0
        
        # ランダムプレイアウト
        candidate_moves = []
        for i in range(self.size):
            for j in range(self.size):
                if board[i][j] == 0:
                    candidate_moves.append((i, j))
        
        if not candidate_moves:
            return 0
        
        r, c = random.choice(candidate_moves)
        board[r][c] = player
        
        if self._check_win_board(board, r, c, player):
            return 1.0
        
        result = self._mcts_simulate_with_board(board, 3 - player, depth + 1, max_depth)
        return -result if result != 0 else 0

    def _evaluate_board_mcts(self, board, player):
        """MCTS用の軽量盤面評価 - 改良版（パターン考慮）"""
        score = 0
        opponent = 3 - player
        
        # 1. 基本スコア（石の数）
        for i in range(self.size):
            for j in range(self.size):
                if board[i][j] == player:
                    score += 10
                elif board[i][j] == opponent:
                    score -= 5
        
        # 2. 活四・活三の簡易検出
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for i in range(self.size):
            for j in range(self.size):
                if board[i][j] == 0:
                    # 自分の脅威
                    for dr, dc in directions:
                        line_str = self._get_line_string(board, i, j, dr, dc, player)
                        if "4" in line_str:  # 活四相当
                            score += 1000
                        elif "3" in line_str:  # 活三相当
                            score += 200
                    
                    # 相手の脅威（防御）
                    for dr, dc in directions:
                        line_str = self._get_line_string(board, i, j, dr, dc, opponent)
                        if "4" in line_str:
                            score -= 800
                        elif "3" in line_str:
                            score -= 150
        
        return score

    def _get_line_string(self, board, r, c, dr, dc, player):
        """簡易的なラインの文字列化"""
        line = []
        for i in range(-2, 3):
            nr, nc = r + dr * i, c + dc * i
            if 0 <= nr < self.size and 0 <= nc < self.size:
                if board[nr][nc] == player:
                    line.append('●')
                else:
                    line.append('.')
            else:
                line.append('X')
        return ''.join(line)

    def _check_win_board(self, board, r, c, player):
        """盤面コピー版の勝利判定"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            count = 1
            
            # 正方向
            for i in range(1, 5):
                nr, nc = r + dr * i, c + dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            # 負方向
            for i in range(1, 5):
                nr, nc = r - dr * i, c - dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 5:
                return True
        
        return False

    # ============================================================================
    # 従来の関数（互換性保持）
    # ============================================================================
    
    def detect_urgent_threats(self, player):
        """緊急な脅威を検出（活四・活三など）"""
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
            
            if max_score >= self.weights['open_three']:
                threats.append((r, c, max_score))
        
        threats.sort(key=lambda x: -x[2])
        return threats

    def detect_forks(self, r, c, player):
        """三三、四三などのフォークを検出"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        threats = []
        for dr, dc in directions:
            score = self.evaluate_pattern(r, c, dr, dc, player)
            
            if score >= self.weights['open_four']:
                threats.append('four')
            elif score >= self.weights['open_three']:
                threats.append('three')
            elif score >= self.weights['dead_three']:
                threats.append('half-three')
        
        bonus = 0
        three_count = threats.count('three')
        four_count = threats.count('four')
        
        if four_count >= 2:
            bonus += self.weights['fork_44']
        if four_count >= 1 and three_count >= 1:
            bonus += self.weights['fork_43']
        if three_count >= 2:
            bonus += self.weights['fork_33']
        
        return bonus

    def evaluate_board_enhanced(self, for_player=None):
        """改良版評価関数"""
        if for_player is None:
            for_player = self.current_player
        
        scores = np.zeros((self.size, self.size))
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        candidate_moves = self.get_candidate_moves()
        
        for r, c in candidate_moves:
            if self.board[r][c] != 0:
                continue
            
            # 攻撃スコア
            attack_score = 0
            for dr, dc in directions:
                attack_score += self.evaluate_pattern(r, c, dr, dc, for_player)
            
            # フォークボーナス
            fork_bonus = self.detect_forks(r, c, for_player)
            attack_score += fork_bonus
            
            # 両見ボーナス
            both_threat_bonus = self.evaluate_both_open_threats(r, c, for_player)
            attack_score += both_threat_bonus
            
            # 防御スコア
            defense_score = 0
            opponent = 3 - for_player
            
            for dr, dc in directions:
                opp_score = self.evaluate_pattern(r, c, dr, dc, opponent)
                if opp_score >= self.weights['open_four']:
                    defense_score += self.weights['def_open_four']
                elif opp_score >= self.weights['open_three']:
                    defense_score += self.weights['def_open_three']
                elif opp_score >= self.weights['dead_three']:
                    defense_score += self.weights['def_dead_three']
            
            # 中央性ボーナス
            center = self.size // 2
            distance = abs(r - center) + abs(c - center)
            center_bonus = max(0, 10 - distance) * self.weights.get('center_bonus', 100)
            
            # 継続性ボーナス
            continuity_bonus = self.continuity_bonus(r, c, for_player)
            
            # 総合スコア
            total_score = (attack_score * 1.0 + 
                          defense_score * self.weights['defense_weight'] + 
                          center_bonus + continuity_bonus)
            
            scores[r][c] = total_score
        
        return scores

    def get_candidate_moves(self):
        """探索範囲を限定"""
        candidates = set()
        board_size = self.size
        
        for i in range(board_size):
            for j in range(board_size):
                if self.board[i][j] != 0:
                    for di in range(-2, 3):
                        for dj in range(-2, 3):
                            ni, nj = i + di, j + dj
                            if 0 <= ni < board_size and 0 <= nj < board_size:
                                if self.board[ni][nj] == 0:
                                    candidates.add((ni, nj))
        
        if not candidates:
            candidates.add((board_size//2, board_size//2))
        
        return list(candidates)

    def continuity_bonus(self, r, c, player):
        """攻めの継続性ボーナス"""
        bonus = 0
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
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
        """従来の評価関数（後方互換性）"""
        return self.evaluate_board_enhanced(for_player)

    def put_stone(self, r, c, player):
        """石を置く"""
        if 0 <= r < self.size and 0 <= c < self.size and self.board[r][c] == 0:
            self.board[r][c] = player
            self.move_history.append((r, c, player))
            return True
        return False

    def check_win(self, r, c, player):
        """勝利判定"""
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            count = 1
            
            for i in range(1, 5):
                nr, nc = r + dr * i, c + dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            for i in range(1, 5):
                nr, nc = r - dr * i, c - dc * i
                if 0 <= nr < self.size and 0 <= nc < self.size and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 5:
                return True
        
        return False

    def get_best_move(self, depth_limit=None, use_mcts=False, mcts_iterations=500):
        """
        最善手探索（VCF/VCT優先 + ミニマックス + MCTS対応）
        
        Args:
            depth_limit: ミニマックスの探索深さ
            use_mcts: True の場合、MCTS を使用
            mcts_iterations: MCTS のシミュレーション回数
        """
        player = self.current_player
        opponent = 3 - self.current_player
        candidate_moves = self.get_candidate_moves()
        
        # 【優先度1：相手の即勝ち手を防ぐ】
        for r, c in candidate_moves:
            self.board[r][c] = opponent
            if self.check_win(r, c, opponent):
                self.board[r][c] = 0
                return (r, c)
            self.board[r][c] = 0
        
        # 【優先度2：自分の即勝ち手】
        for r, c in candidate_moves:
            self.board[r][c] = player
            if self.check_win(r, c, player):
                self.board[r][c] = 0
                return (r, c)
            self.board[r][c] = 0
        
        # 【優先度3：VCF（連続四）探索】
        vcf_move = self.find_vcf_move(player)
        if vcf_move:
            return vcf_move
        
        # 【優先度4：相手の活四・活三ブロック】
        urgent_opp = self.detect_urgent_threats(opponent)
        if urgent_opp:
            return (urgent_opp[0][0], urgent_opp[0][1])
        
        # 【優先度5：自分の活四・活三推進】
        urgent_self = self.detect_urgent_threats(player)
        if urgent_self:
            return (urgent_self[0][0], urgent_self[0][1])
        
        # 【優先度6：MCTS を使用する場合】
        if use_mcts and len(self.move_history) >= 4:
            return self.mcts_search(player, iterations=mcts_iterations)
        
        # 【優先度7：ミニマックス探索】
        if len(self.move_history) < 3:
            return self.get_best_move_static()
        
        if depth_limit is None:
            depth_limit = 2  # デフォルト探索深さ
        
        start_time = time.time()
        time_limit = 1.0
        best_move = None
        best_score = -float('inf')
        
        moves = self.get_ordered_moves(player)
        for r, c in moves:
            if time.time() - start_time > time_limit:
                break
            
            self.board[r][c] = player
            score = self.minimax(depth_limit - 1, -float('inf'), float('inf'), False, (r, c))
            self.board[r][c] = 0
            
            if score > best_score:
                best_score = score
                best_move = (r, c)
        
        return best_move if best_move else self.get_best_move_static()

    def get_best_move_static(self):
        """静的評価関数のみを使用"""
        candidate_moves = self.get_candidate_moves()
        
        opponent = 3 - self.current_player
        for r, c in candidate_moves:
            self.board[r][c] = opponent
            if self.check_win(r, c, opponent):
                self.board[r][c] = 0
                return (r, c)
            self.board[r][c] = 0
        
        for r, c in candidate_moves:
            self.board[r][c] = self.current_player
            if self.check_win(r, c, self.current_player):
                self.board[r][c] = 0
                return (r, c)
            self.board[r][c] = 0
        
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
        
        center = self.size // 2
        for dr in range(self.size):
            for dc in range(self.size):
                r = (center + dr) % self.size
                c = (center + dc) % self.size
                if self.board[r][c] == 0:
                    return (r, c)
        
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
        """αβ枝切り付きミニマックス法"""
        if ai_player is None:
            ai_player = self.current_player
        
        if last_move:
            r, c = last_move
            moving_player = ai_player if maximizing_player else (3 - ai_player)
            if self.check_win(r, c, moving_player):
                return 1000000 if moving_player == ai_player else -1000000
        
        if depth == 0:
            return self.quick_evaluate(ai_player)
        
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
        """評価値の高い順に手をソート"""
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
        """手の簡易位置評価"""
        score = 0
        
        center = self.size // 2
        distance = abs(r - center) + abs(c - center)
        score += max(0, 10 - distance) * 10
        
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
        """軽量評価関数"""
        if self.check_win_anywhere(player):
            return 100000
        if self.check_win_anywhere(3 - player):
            return -100000
        
        score = 0
        opponent = 3 - player
        
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == player:
                    score += self.evaluate_single_stone(r, c, player)
                elif self.board[r][c] == opponent:
                    score -= self.evaluate_single_stone(r, c, opponent)
        
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