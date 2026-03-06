# evaluate_numba.py
from numba import jit
import numpy as np

@jit(nopython=True)
def evaluate_pattern_numba(board, r, c, dr, dc, player, weights, size):
    """
    board: 2D int array (size x size) 0=空,1=黒,2=白
    weights: 配列 [five, open_four, dead_four, open_three, dead_three, open_two]
    戻り値: スコア
    """
    # 正方向の連続石を数える
    pos_count = 0
    for i in range(1, 6):
        nr = r + dr * i
        nc = c + dc * i
        if nr < 0 or nr >= size or nc < 0 or nc >= size:
            break
        if board[nr, nc] == player:
            pos_count += 1
        elif board[nr, nc] == 0:
            break
        else:
            break

    # 負方向の連続石を数える
    neg_count = 0
    for i in range(1, 6):
        nr = r - dr * i
        nc = c - dc * i
        if nr < 0 or nr >= size or nc < 0 or nc >= size:
            break
        if board[nr, nc] == player:
            neg_count += 1
        elif board[nr, nc] == 0:
            break
        else:
            break

    total = 1 + pos_count + neg_count

    # 正方向の空き判定
    front_open = False
    nr = r + dr * (pos_count + 1)
    nc = c + dc * (pos_count + 1)
    if 0 <= nr < size and 0 <= nc < size and board[nr, nc] == 0:
        front_open = True

    # 負方向の空き判定
    back_open = False
    nr = r - dr * (neg_count + 1)
    nc = c - dc * (neg_count + 1)
    if 0 <= nr < size and 0 <= nc < size and board[nr, nc] == 0:
        back_open = True

    # 五連
    if total >= 5:
        return weights[0]

    # 活四
    if total == 4 and front_open and back_open:
        return weights[1]

    # 死四
    if total == 4:
        # 厳密には跳び四の判定も必要だが、簡易版として連続4つで死四とする
        return weights[2]

    # 活三（連続）
    if total == 3 and front_open and back_open:
        return weights[3]

    # 跳び三の簡易判定（例として .●.●●. と .●●.●. だけ）
    # 方向に沿った7マスの配列を取得
    line = np.zeros(7, dtype=np.int8) - 1  # -1で初期化
    for i in range(-3, 4):
        nr = r + dr * i
        nc = c + dc * i
        if 0 <= nr < size and 0 <= nc < size:
            line[i+3] = board[nr, nc] if i != 0 else player
        else:
            line[i+3] = -1

    # 跳び三パターン1: .●.●●. (0=空, 1=自分の石, -1=無視)
    if (line[0] == 0 and line[1] == player and line[2] == 0 and 
        line[3] == player and line[4] == player and line[5] == 0):
        return weights[3]

    # 跳び三パターン2: .●●.●.
    if (line[0] == 0 and line[1] == player and line[2] == player and 
        line[3] == 0 and line[4] == player and line[5] == 0):
        return weights[3]

    # 眠三
    if total == 3:
        return weights[4]

    # 活二
    if total == 2 and front_open and back_open:
        return weights[5]

    return 0