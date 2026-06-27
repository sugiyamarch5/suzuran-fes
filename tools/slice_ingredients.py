# -*- coding: utf-8 -*-
"""
Geminiが生成した食材スプライトシート(4列×3行,上2行=8種)を
8個の個別アイコンPNG(背景透過・正方形・視覚サイズ統一)に分割する。

改良点:
  1. 外周background をflood透過
  2. 最大連結成分ベースで本体だけ残す（隣セルの混入物を除去）
  3. 面積基準で各アイコンの視覚サイズを統一（細長い物が大きく見える問題を解消）

使い方:
  python slice_ingredients.py <入力PNG> <出力ディレクトリ>
"""
import sys
import math
from collections import deque
from PIL import Image

# 出力する8食材のファイル名（左上→右へ、上段→下段の順）
IDS = ['ice', 'syrup', 'spoon', 'ramen', 'apple', 'yakisoba', 'takoyaki', 'sauce']

COLS = 4
GRID_ROWS = 3      # 生成画像は4×3（3行目は重複なので使わない）
USE_ROWS = 2       # 上2行=8個だけ使う
OUT_SIZE = 256     # 出力アイコンの一辺
PAD = 18           # 余白
BG_TOL = 46        # 背景とみなす色差のしきい値
CELL_INSET = 0.05  # 各セルの内側マージン比（隣セル混入を物理的に減らす）
EDGE_BAND = 0.12   # セル上下端のこの帯に触れる小成分は混入とみなす
EDGE_DROP = 0.55   # 最大成分のこの割合未満かつ端接触のblobを除去


def is_bg(px, bg):
    r, g, b = px[0], px[1], px[2]
    a = px[3] if len(px) > 3 else 255
    if a == 0:
        return True
    return abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= BG_TOL


def flood_transparent(cell):
    """四隅の背景色を基準に、外周から連結した背景だけを透過する。"""
    cell = cell.convert('RGBA')
    w, h = cell.size
    px = cell.load()
    bg = px[2, 2]
    visited = [[False] * w for _ in range(h)]
    q = deque()

    def push(x, y):
        if 0 <= x < w and 0 <= y < h and not visited[y][x]:
            visited[y][x] = True
            q.append((x, y))

    for x in range(w):
        push(x, 0); push(x, h - 1)
    for y in range(h):
        push(0, y); push(w - 1, y)

    while q:
        x, y = q.popleft()
        if not is_bg(px[x, y], bg):
            continue
        px[x, y] = (0, 0, 0, 0)
        push(x + 1, y); push(x - 1, y); push(x, y + 1); push(x, y - 1)
    return cell


def keep_main_blobs(cell):
    """不透明領域を連結成分に分け、本体（最大成分）を必ず残す。
    セル上下端の帯に触れる小成分は隣セルからの混入とみなして除去する。
    中央寄りの小成分（たこ焼きの小玉など）は残す。"""
    w, h = cell.size
    px = cell.load()
    visited = [[False] * w for _ in range(h)]
    blobs = []  # (pixels, ymin, ymax)

    for sy in range(h):
        for sx in range(w):
            if visited[sy][sx]:
                continue
            if px[sx, sy][3] <= 16:
                visited[sy][sx] = True
                continue
            comp = []
            ymin, ymax = sy, sy
            q = deque([(sx, sy)])
            visited[sy][sx] = True
            while q:
                x, y = q.popleft()
                comp.append((x, y))
                if y < ymin: ymin = y
                if y > ymax: ymax = y
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny][3] > 16:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            blobs.append((comp, ymin, ymax))

    if not blobs:
        return cell
    amax = max(len(b[0]) for b in blobs)
    top_lim = h * EDGE_BAND
    bot_lim = h * (1 - EDGE_BAND)
    keepmask = [[False] * w for _ in range(h)]
    for comp, ymin, ymax in blobs:
        is_main  = len(comp) == amax
        is_small = len(comp) < amax * EDGE_DROP
        on_edge  = (ymin < top_lim) or (ymax > bot_lim)
        if (not is_main) and is_small and on_edge:
            continue  # 端に触れる小さな破片＝混入 → 除去
        for (x, y) in comp:
            keepmask[y][x] = True
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 16 and not keepmask[y][x]:
                px[x, y] = (0, 0, 0, 0)
    return cell


def content_bbox(cell):
    w, h = cell.size
    px = cell.load()
    minx, miny, maxx, maxy = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 16:
                found = True
                if x < minx: minx = x
                if y < miny: miny = y
                if x > maxx: maxx = x
                if y > maxy: maxy = y
    if not found:
        return None
    return (minx, miny, maxx + 1, maxy + 1)


def opaque_area(cell):
    w, h = cell.size
    px = cell.load()
    n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 16:
                n += 1
    return n


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    im = Image.open(src).convert('RGBA')
    W, H = im.size
    cw = W // COLS
    ch = H // GRID_ROWS
    print('image:', (W, H), 'cell:', (cw, ch))

    # --- Pass 1: 各セルを抽出・クリーンアップして保持 ---
    items = []  # (id, cropped_cell, area)
    idx = 0
    insx = int(cw * CELL_INSET)
    insy = int(ch * CELL_INSET)
    for r in range(USE_ROWS):
        for c in range(COLS):
            box = (c * cw + insx, r * ch + insy,
                   (c + 1) * cw - insx, (r + 1) * ch - insy)
            cell = im.crop(box)
            cell = flood_transparent(cell)
            cell = keep_main_blobs(cell)
            bbox = content_bbox(cell)
            if bbox:
                cell = cell.crop(bbox)
            area = max(1, opaque_area(cell))
            items.append((IDS[idx], cell, area))
            idx += 1

    # --- 面積基準の目標視覚サイズ（中央値） ---
    visuals = sorted(math.sqrt(a) for _, _, a in items)
    target = visuals[len(visuals) // 2]
    inner = OUT_SIZE - PAD * 2

    # --- Pass 2: 視覚サイズを揃えて正方形キャンバスに中央配置 ---
    for name, cell, area in items:
        v = math.sqrt(area)
        scale = target / v
        cwi, chi = cell.size
        nw, nh = cwi * scale, chi * scale
        m = max(nw, nh)
        if m > inner:            # 枠をはみ出す場合はクランプ
            k = inner / m
            nw *= k; nh *= k
        nw = max(1, int(round(nw)))
        nh = max(1, int(round(nh)))
        resized = cell.resize((nw, nh), Image.LANCZOS)
        out = Image.new('RGBA', (OUT_SIZE, OUT_SIZE), (0, 0, 0, 0))
        out.paste(resized, ((OUT_SIZE - nw) // 2, (OUT_SIZE - nh) // 2), resized)
        path = outdir + '/' + name + '.png'
        out.save(path)
        print(f'saved: {name:10s} {nw}x{nh}  area={area}')


if __name__ == '__main__':
    main()
