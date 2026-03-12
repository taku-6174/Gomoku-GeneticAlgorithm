# コード説明

## ファイル構成

```
Gomoku-GeneticAlgorithm/
├── engine.py              # ゲームエンジン・評価関数・探索アルゴリズム
├── ga_manager.py          # 遺伝的アルゴリズムの管理・実行
├── evaluate_evolution.py  # 進化個体 vs 初期個体の対戦検証
├── evaluate_numba.py      # Numba高速化評価関数
├── main.py                # PyGame UI（対局画面）
├── best_weights.txt       # GAで進化した最良個体の重み
├── weights_history.json   # 全世代の重みと勝率の記録
├── evolution_graph.png    # 進化グラフ（best/average fitness）
├── battle_results.md      # 各バージョンの対戦結果まとめ
├── changelog.md           # バージョンごとの改良履歴
└── README.md              # プロジェクト概要
```

---

## engine.py

### 概要
五目並べの全ロジックを担うコアファイル。盤面管理・評価関数・探索アルゴリズムをすべてこのファイルの`GomokuAnalyzer`クラスが担当する。

### クラス・主要メソッド

#### `GomokuAnalyzer`クラス
15×15の五目並べ盤面を管理するメインクラス。

**初期化・盤面管理**

`__init__(size=15)`
盤面（numpy配列）・現在のプレイヤー・着手履歴を初期化する。GAで最適化する評価関数の重み（`weights`辞書）もここで定義される。

```python
self.weights = {
    'five': 100000,       # 五連のスコア
    'open_four': 12000,   # 活四のスコア
    'dead_four': 5000,    # 眠四のスコア
    'open_three': 1500,   # 活三のスコア
    'dead_three': 200,    # 眠三のスコア
    'open_two': 50,       # 活二のスコア
    'defense_weight': 1.2,# 防御の重み倍率
    'def_open_four': 50000,
    'def_open_three': 2000,
    'def_dead_three': 300,
    'fork_44': 15000,     # 四四フォークのボーナス
    'fork_43': 8000,      # 四三フォークのボーナス
    'fork_33': 3000,      # 三三フォークのボーナス
    'center_bonus': 100,  # 中央付近へのボーナス
    'continuity_weight': 100, # 連続性ボーナス
}
```

`put_stone(r, c, player)` / `check_win(r, c, player)`
石を置く・勝利判定を行う基本メソッド。

**評価関数**

`evaluate_pattern(r, c, dr, dc, player)`
指定したマスに石を置いたと仮定して、1方向のパターンを文字列マッチングで評価する。五連・活四・眠四・活三（跳び三含む）・眠三・活二の順で強い順に判定し、対応する重みのスコアを返す。

`detect_forks(r, c, player)`
三三・四三・四四などのフォーク（同時に複数の脅威を作る手）を検出し、ボーナスを返す。フォークは相手が1手では防ぎきれないため、五目並べにおいて特に重要な概念。

`evaluate_board_enhanced(for_player)`
盤面全体を評価してスコアマップ（15×15のnumpy配列）を返す。各候補手について攻撃スコア・フォークボーナス・防御スコア・中央ボーナス・連続性ボーナスを計算して合計する。

`get_candidate_moves()`
探索範囲を「既存の石から2マス以内」に限定することで計算量を削減する。空の盤面では中央を候補とする。

**探索アルゴリズム**

`get_best_move(depth_limit)`
最善手を探索するメインメソッド。以下の優先順位で判断する：

1. **自分の即勝ち手**（次の1手で勝てる場合は必ずそこに打つ）
2. **相手の即勝ち手をブロック**（次の1手で相手が勝てる場合は必ずブロック）
3. **活四以上の脅威をブロック**（`detect_urgent_threats`で検出）
4. **活三の判断**（`defense_weight`の値によって判断が変わる→個体差が出る）
5. **ミニマックス探索**（αβ枝刈り付き）

`minimax(depth, alpha, beta, maximizing_player, ...)`
αβ枝刈り付きミニマックス法。指定した深さまで全探索し、最善手のスコアを返す。αβ枝刈りにより、明らかに選ばれない枝を省略して計算量を削減する。

`detect_urgent_threats(player)`
活三（スコア≧`open_three`）以上の脅威を検出してスコア順で返す。GAの重みと連動しており、`defense_weight`の値によって活三をブロックするかどうかが変わる。これにより**個体ごとに異なる戦略**が生まれる。

---

## ga_manager.py

### 概要
遺伝的アルゴリズム（GA）を管理・実行するファイル。「評価関数の重みセット」を個体として扱い、対戦の勝率を適応度（fitness）として世代を重ねながら重みを最適化していく。

### 定数

`REFERENCE_WEIGHTS`
GAの絶対的な基準となる固定の重みセット。毎世代この個体との対戦を必ず含めることで、「基準個体より強いかどうか」を一貫して測定できる。

`FIXED_DEPTH = 3`
探索深さを3に固定。深すぎると処理が遅くなり、浅すぎると重みの差がゲームに反映されにくくなるため、3が最適と判断した。

### 関数・クラス

`play_match_worker(args)`
並列処理用のワーカー関数。`(重み1, 重み2, depth, 先手番号)`を受け取り、1試合分の対局を実行して勝者番号（1 or 2 or 0）を返す。ProcessPoolExecutorから呼ばれるためトップレベルに定義されている。

#### `Individual`クラス
1つの個体（重みセット）を表すクラス。

`__init__(weights=None)`
weightsが指定された場合はそのままコピー、指定がない場合は`randomize_weights()`でランダム初期化する。

`randomize_weights()`
REFERENCE_WEIGHTSの±10%以内でランダムに初期化する。基準個体付近からスタートすることで、最初から意味のある範囲での探索が可能になる。`defense_weight`のみ0.9〜1.5の範囲で初期化する（スケールが異なるため）。

`mutate(mutation_rate=0.2, mutation_ratio=0.15)`
突然変異を適用する。各重みに対してmutation_rate（20%）の確率で変異が起き、現在の値に0.85〜1.15倍の乗算を行う（乗算方式）。加算方式と異なり重みがマイナスになることがなく、重みの大小関係を維持したまま進化できる。

#### `Generation`クラス
1世代分の個体群を管理するクラス。

`evaluate_all()`
全個体のfitnessを計算する。各個体は以下の相手と先手専用で対戦する：
- REFERENCE_WEIGHTS（固定基準個体）× 3試合
- Hall of Fame上位2体
- 同世代の仲間からランダム3体

個体は常にplayer1（先手）として対戦し、winner==1で勝利と判定する。勝利数を試合数で割って勝率（%）をfitnessとする。**先手専用GAにしたのに後手でも強い個体が育った**のは、先手で勝つために進化した攻撃的な重みが後手でも有効に機能したためと考えられる。

`update_hall_of_fame()`
歴代最強上位3体を`hall_of_fame`リストに保持する。次世代の対戦相手として使うことで、「過去の自分たちを超え続けているか」を評価できる。

`evolve()`
次世代の個体群を生成する。上位2体はエリートとしてそのまま保存し、残りはトーナメント選択+交叉+突然変異で生成する。

`_tournament_selection(k=3)`
k体をランダムに選んで最も優秀な個体を返す。ルーレット選択より計算が速く、局所最適解からの脱出が容易。

**メイン実行部**
個体数12・世代数30でGAを実行する。各世代後に`weights_history.json`を保存し、最終世代の最良重みを`best_weights.txt`に保存する。

---

## evaluate_evolution.py

### 概要
GAで進化した個体と初期個体を対戦させ、進化の効果を定量的に検証するスクリプト。

### 処理の流れ
1. `REFERENCE_WEIGHTS`から初期個体を生成
2. 指定したファイル（デフォルト: `best_weights.txt`）から進化個体を読み込む
3. 足りないキーは`REFERENCE_WEIGHTS`で自動補完（古いverの重みファイルにも対応）
4. 100試合（先手50試合・後手50試合）を並列実行
5. 先手勝率・後手勝率・合計勝率を集計して表示

### 使い方
```bash
# best_weights.txtで対戦（デフォルト）
python evaluate_evolution.py

# 特定のverの重みで対戦する場合はコード内のファイル名を変更
with open("best_weights_ver2.txt", "r") as f:
```

---

## evaluate_numba.py

### 概要
Numba（JITコンパイラ）を使って評価関数を高速化するモジュール。`@jit(nopython=True)`デコレータにより、Pythonコードがコンパイルされて高速実行される。

### `evaluate_pattern_numba(board, r, c, dr, dc, player, weights, size)`
1方向のパターンを評価する関数。引数はすべてNumbaが処理できる型（numpy配列・整数・浮動小数点）に限定されている。`engine.py`の`quick_evaluate()`メソッドから呼ばれ、ミニマックス探索中の盤面評価を高速化する。

---

## main.py

### 概要
PyGameを使った五目並べのインタラクティブUIファイル。AIの思考過程を視覚的に確認しながら対局できる。

### ゲームモード
- **人間 vs AI**：人間が先手（黒）、AIが後手（白）
- **AI vs AI**：同じエンジン同士が自動対局
- **AI vs 人間**：AIが先手（黒）、人間が後手（白）

### 主な機能
- 各マスに評価値を色と数字で重ねて表示（AIがどの手を高く評価しているかを可視化）
  - 赤（90-100）: 勝ち確定
  - 橙（70-89）: 強力
  - 黄（50-69）: 良い手
  - 緑（30-49）: 普通
  - 青（10-29）: 悪い手
- AIの最善手をハイライト表示（点滅）
- スペースキーでモード選択に戻る

---

## best_weights.txt

GAで30世代進化させた最終世代の最良個体の重みをJSON形式で保存したファイル。`evaluate_evolution.py`や`main.py`から読み込んで使用する。

### 最終的な重みの値と初期値の比較

| 重み | 初期値 | 進化後 | 変化 |
|-----|--------|--------|------|
| five | 100000 | 99421 | ほぼ変化なし |
| open_four | 12000 | 15900 | +32%（攻撃強化）|
| dead_four | 5000 | 5019 | ほぼ変化なし |
| open_three | 1500 | 1231 | -18%（やや低下）|
| dead_three | 200 | 182 | -9% |
| open_two | 50 | 37 | -26% |
| defense_weight | 1.2 | 0.894 | -25%（攻撃寄りに）|
| def_open_four | 50000 | 38191 | -24%（防御やや低下）|
| def_open_three | 2000 | 2213 | +11% |
| fork_44 | 15000 | 12411 | -17% |
| fork_43 | 8000 | 8733 | +9% |
| fork_33 | 3000 | 3703 | +23% |
| center_bonus | 100 | 93 | ほぼ変化なし |
| continuity_weight | 100 | 85 | -15% |

`open_four`が大きく上昇し、`defense_weight`が低下していることから、GAが「活四を積極的に作る攻撃的な戦略」を学習したことがわかる。

---

## weights_history.json

GAの全30世代にわたる各世代の記録ファイル。各世代ごとに以下の情報が保存されている：
- `gen`：世代番号
- `best_fitness`：最高勝率（%）
- `avg_fitness`：平均勝率（%）
- `worst_fitness`：最低勝率（%）
- `weights`：その世代の最良個体の重み

---

## evolution_graph.png

GAの進化過程を可視化したグラフ。青線がbest fitness（最高勝率）、オレンジ線がaverage fitness（平均勝率）を示す。1世代目から高い勝率を示し、平均勝率が右肩上がりで推移していることがGAの収束を示している。