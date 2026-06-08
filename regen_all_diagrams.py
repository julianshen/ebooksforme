#!/usr/bin/env python3
"""Regenerate all chess opening diagrams with professional piece images."""

import sys
sys.path.insert(0, '/home/julianshen/projects/ebooksforme')

from chess_renderer_v2 import ChessRenderer

renderer = ChessRenderer(piece_size=100)

openings = [
    (["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"], "Italian Game", "italian"),
    (["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"], "Ruy Lopez (Spanish)", "spanish"),
    (["e4", "c5", "Nf3", "d6", "d4", "cxd4"], "Sicilian Defense", "sicilian"),
    (["d4", "d5", "c4", "e6", "Nc3", "Nf6"], "Queen's Gambit", "queens_gambit"),
    (["e4", "e5", "f4", "exf4", "Nf3", "d5"], "King's Gambit", "kings_gambit"),
    (["e4", "e6", "d4", "d5", "Nc3", "Nf6"], "French Defense", "french"),
    (["c4", "e5", "Nc3", "Nf6", "Nf3", "Nc6"], "English Opening", "english"),
]

output_dir = '/home/julianshen/projects/ebooksforme/chess-openings/EPUB/images'

for moves, title, prefix in openings:
    files = renderer.render_opening(moves, title=title, output_dir=output_dir)
    # Rename to match expected pattern
    import os
    for i, f in enumerate(files):
        old_name = os.path.basename(f)
        if i == 0:
            new_name = f"{prefix}_00.jpg"
        else:
            new_name = f"{prefix}_{i:02d}.jpg"
        if old_name != new_name:
            os.rename(f, os.path.join(output_dir, new_name))
    print(f"{title}: {len(files)} diagrams")

print("\nAll diagrams regenerated!")
