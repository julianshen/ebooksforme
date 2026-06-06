import chess
from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('/tmp/ebooksforme/chess-openings/EPUB/images', exist_ok=True)

LIGHT_SQUARE = "#F0D9B5"
DARK_SQUARE = "#B58863"
HIGHLIGHT_FROM = "#F7EC4F"
HIGHLIGHT_TO = "#A8D5BA"
BG = "#FFFFFF"

PIECES = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
}

def draw_chessboard(board, size=600, highlight_from=None, highlight_to=None, title="", caption=""):
    img = Image.new('RGB', (size, size + 90), BG)
    draw = ImageDraw.Draw(img)
    sq_size = size // 8
    
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_piece = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(sq_size * 0.62))
        font_coord = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_piece = ImageFont.load_default()
        font_coord = ImageFont.load_default()
    
    if title:
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((size - tw) // 2, 8), title, fill='#1a1a2e', font=font_title)
    
    if caption:
        bbox = draw.textbbox((0, 0), caption, font=font_sub)
        tw = bbox[2] - bbox[0]
        draw.text(((size - tw) // 2, 42), caption, fill='#555555', font=font_sub)
    
    offset_y = 68
    
    for row in range(8):
        for col in range(8):
            x = col * sq_size
            y = offset_y + row * sq_size
            color = LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE
            sq = chess.square(col, 7 - row)
            sq_name = chess.square_name(sq)
            
            if highlight_from and sq_name == highlight_from:
                color = HIGHLIGHT_FROM
            elif highlight_to and sq_name == highlight_to:
                color = HIGHLIGHT_TO
            
            draw.rectangle([x, y, x + sq_size, y + sq_size], fill=color)
            
            piece = board.piece_at(sq)
            if piece:
                p = PIECES[piece.symbol()]
                bbox = draw.textbbox((0, 0), p, font=font_piece)
                pw = bbox[2] - bbox[0]
                ph = bbox[3] - bbox[1]
                px = x + (sq_size - pw) // 2
                py = y + (sq_size - ph) // 2
                piece_color = '#FFFFFF' if piece.color else '#1a1a2e'
                draw.text((px, py), p, fill=piece_color, font=font_piece)
    
    for i in range(8):
        file_label = chr(ord('a') + i)
        color = '#FFFFFF' if i % 2 == 1 else '#555555'
        draw.text((i * sq_size + sq_size // 2 - 5, offset_y + size + 5), file_label, fill=color, font=font_coord)
        rank_label = str(8 - i)
        color = '#FFFFFF' if i % 2 == 0 else '#555555'
        draw.text((5, offset_y + i * sq_size + sq_size // 2 - 7), rank_label, fill=color, font=font_coord)
    
    return img

def generate_opening_diagrams(moves, filename_prefix, title):
    board = chess.Board()
    images = []
    
    img = draw_chessboard(board, title=title, caption="Initial Position")
    img.save(f'/tmp/ebooksforme/chess-openings/EPUB/images/{filename_prefix}_00.png')
    images.append(f'{filename_prefix}_00.png')
    
    for i, move_san in enumerate(moves):
        move = board.parse_san(move_san)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        board.push(move)
        
        move_num = (i // 2) + 1
        color = "White" if i % 2 == 0 else "Black"
        caption = f"{move_num}. {color}: {move_san}"
        
        img = draw_chessboard(board, title=title, caption=caption, highlight_from=from_sq, highlight_to=to_sq)
        img.save(f'/tmp/ebooksforme/chess-openings/EPUB/images/{filename_prefix}_{i+1:02d}.png')
        images.append(f'{filename_prefix}_{i+1:02d}.png')
    
    return images

openings = [
    (["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"], "italian", "Italian Game"),
    (["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"], "spanish", "Ruy Lopez (Spanish)"),
    (["e4", "c5", "Nf3", "d6", "d4", "cxd4"], "sicilian", "Sicilian Defense"),
    (["d4", "d5", "c4", "e6", "Nc3", "Nf6"], "queens_gambit", "Queen's Gambit"),
    (["e4", "e5", "f4", "exf4", "Nf3", "d5"], "kings_gambit", "King's Gambit"),
    (["e4", "e6", "d4", "d5", "Nc3", "Nf6"], "french", "French Defense"),
    (["c4", "e5", "Nc3", "Nf6", "Nf3", "Nc6"], "english", "English Opening"),
]

all_images = []
for moves, prefix, title in openings:
    imgs = generate_opening_diagrams(moves, prefix, title)
    all_images.extend(imgs)
    print(f"{title}: {len(imgs)} diagrams")

print(f"\nTotal: {len(all_images)} diagrams")
