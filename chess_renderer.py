#!/usr/bin/env python3
"""
Chess Game Renderer - Professional chess diagram generator
Generates high-quality chess board diagrams with actual piece images.
"""

import chess
import chess.pgn
import os
import io
import base64
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional

# Download piece images from Wikimedia Commons (public domain)
PIECE_URLS = {
    'wK': 'https://upload.wikimedia.org/wikipedia/commons/4/42/Chess_klt45.svg',
    'wQ': 'https://upload.wikimedia.org/wikipedia/commons/1/15/Chess_qlt45.svg',
    'wR': 'https://upload.wikimedia.org/wikipedia/commons/7/72/Chess_rlt45.svg',
    'wB': 'https://upload.wikimedia.org/wikipedia/commons/b/b1/Chess_blt45.svg',
    'wN': 'https://upload.wikimedia.org/wikipedia/commons/7/70/Chess_nlt45.svg',
    'wP': 'https://upload.wikimedia.org/wikipedia/commons/4/45/Chess_plt45.svg',
    'bK': 'https://upload.wikimedia.org/wikipedia/commons/f/f0/Chess_kdt45.svg',
    'bQ': 'https://upload.wikimedia.org/wikipedia/commons/4/47/Chess_qdt45.svg',
    'bR': 'https://upload.wikimedia.org/wikipedia/commons/f/ff/Chess_rdt45.svg',
    'bB': 'https://upload.wikimedia.org/wikipedia/commons/9/98/Chess_bdt45.svg',
    'bN': 'https://upload.wikimedia.org/wikipedia/commons/e/ef/Chess_ndt45.svg',
    'bP': 'https://upload.wikimedia.org/wikipedia/commons/c/c7/Chess_pdt45.svg',
}

class ChessRenderer:
    """Professional chess board renderer with actual piece images."""
    
    def __init__(self, piece_size: int = 80, cache_dir: str = None):
        self.piece_size = piece_size
        self.square_size = piece_size
        self.board_size = piece_size * 8
        
        # Colors
        self.light_square = "#F0D9B5"
        self.dark_square = "#B58863"
        self.highlight_from = "#F7EC4F"
        self.highlight_to = "#A8D5BA"
        self.last_move = "#C8E6C9"
        self.check_highlight = "#FF8A80"
        self.bg_color = "#FFFFFF"
        
        # Cache directory
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/chess-pieces")
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load piece images
        self.pieces = {}
        self._load_pieces()
    
    def _load_pieces(self):
        """Load or download piece images."""
        import requests
        
        for key, url in PIECE_URLS.items():
            cache_path = os.path.join(self.cache_dir, f"{key}.png")
            
            if os.path.exists(cache_path):
                img = Image.open(cache_path)
            else:
                # Download from Wikimedia
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    
                    # Convert SVG to PNG using cairosvg if available
                    try:
                        import cairosvg
                        png_data = cairosvg.svg2png(bytestring=response.content, 
                                                     output_width=self.piece_size,
                                                     output_height=self.piece_size)
                        img = Image.open(io.BytesIO(png_data))
                    except ImportError:
                        # Fallback: create simple piece representation
                        img = self._create_fallback_piece(key)
                    
                    img.save(cache_path, 'PNG')
                except Exception as e:
                    print(f"Warning: Could not load {key}: {e}")
                    img = self._create_fallback_piece(key)
            
            self.pieces[key] = img.convert('RGBA')
    
    def _create_fallback_piece(self, key: str) -> Image.Image:
        """Create a simple fallback piece image."""
        img = Image.new('RGBA', (self.piece_size, self.piece_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        color = (255, 255, 255, 255) if key[0] == 'w' else (30, 30, 30, 255)
        piece_type = key[1]
        
        # Simple geometric shapes for pieces
        cx, cy = self.piece_size // 2, self.piece_size // 2
        r = self.piece_size // 3
        
        if piece_type == 'P':  # Pawn
            draw.ellipse([cx-8, cy-15, cx+8, cy+5], fill=color)
            draw.ellipse([cx-12, cy+5, cx+12, cy+18], fill=color)
        elif piece_type == 'N':  # Knight
            draw.polygon([(cx, cy-20), (cx+15, cy+10), (cx-15, cy+10)], fill=color)
            draw.ellipse([cx-12, cy+5, cx+12, cy+20], fill=color)
        elif piece_type == 'B':  # Bishop
            draw.ellipse([cx-5, cy-20, cx+5, cy-10], fill=color)
            draw.polygon([(cx, cy-15), (cx+15, cy+15), (cx-15, cy+15)], fill=color)
        elif piece_type == 'R':  # Rook
            draw.rectangle([cx-15, cy-15, cx+15, cy+15], fill=color)
            draw.rectangle([cx-12, cy-20, cx+12, cy-15], fill=color)
        elif piece_type == 'Q':  # Queen
            draw.ellipse([cx-18, cy-5, cx+18, cy+18], fill=color)
            for dx in [-12, -4, 4, 12]:
                draw.ellipse([cx+dx-4, cy-22, cx+dx+4, cy-10], fill=color)
        elif piece_type == 'K':  # King
            draw.ellipse([cx-15, cy-5, cx+15, cy+18], fill=color)
            draw.rectangle([cx-3, cy-22, cx+3, cy-10], fill=color)
            draw.rectangle([cx-10, cy-18, cx+10, cy-14], fill=color)
        
        return img
    
    def render_board(self, 
                     board: chess.Board,
                     title: str = "",
                     caption: str = "",
                     highlight_from: Optional[str] = None,
                     highlight_to: Optional[str] = None,
                     flip: bool = False,
                     show_coordinates: bool = True) -> Image.Image:
        """Render a chess board position."""
        
        # Calculate dimensions
        coord_margin = 30 if show_coordinates else 0
        title_height = 50 if title else 0
        caption_height = 30 if caption else 0
        padding = 20
        
        total_width = self.board_size + coord_margin * 2 + padding * 2
        total_height = (self.board_size + coord_margin * 2 + 
                       title_height + caption_height + padding * 2)
        
        img = Image.new('RGB', (total_width, total_height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Load fonts
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_caption = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_coord = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font_title = ImageFont.load_default()
            font_caption = ImageFont.load_default()
            font_coord = ImageFont.load_default()
        
        # Draw title
        if title:
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text(((total_width - tw) // 2, padding), title, 
                     fill='#1a1a2e', font=font_title)
        
        # Board offset
        board_x = padding + coord_margin
        board_y = padding + title_height + coord_margin
        
        # Draw squares
        for row in range(8):
            for col in range(8):
                # Determine square coordinates
                if flip:
                    file_idx = 7 - col
                    rank_idx = row
                else:
                    file_idx = col
                    rank_idx = 7 - row
                
                x = board_x + col * self.square_size
                y = board_y + row * self.square_size
                
                # Determine square color
                sq = chess.square(file_idx, rank_idx)
                sq_name = chess.square_name(sq)
                
                is_light = (row + col) % 2 == 0
                color = self.light_square if is_light else self.dark_square
                
                # Apply highlights
                if highlight_from and sq_name == highlight_from:
                    color = self.highlight_from
                elif highlight_to and sq_name == highlight_to:
                    color = self.highlight_to
                
                # Check if king is in check
                if board.is_check():
                    king_sq = board.king(board.turn)
                    if king_sq == sq:
                        color = self.check_highlight
                
                draw.rectangle([x, y, x + self.square_size, y + self.square_size], 
                              fill=color)
                
                # Draw piece
                piece = board.piece_at(sq)
                if piece:
                    color_char = 'w' if piece.color else 'b'
                    key = f"{color_char}{piece.symbol().upper()}"
                    if key in self.pieces:
                        piece_img = self.pieces[key]
                        px = x + (self.square_size - piece_img.width) // 2
                        py = y + (self.square_size - piece_img.height) // 2
                        img.paste(piece_img, (px, py), piece_img)
        
        # Draw coordinates
        if show_coordinates:
            for i in range(8):
                # File labels (a-h) at bottom
                file_label = chr(ord('a') + (7 - i if flip else i))
                x = board_x + i * self.square_size + self.square_size // 2 - 5
                y_bottom = board_y + self.board_size + 8
                is_light = i % 2 == 1
                color = '#FFFFFF' if is_light else '#555555'
                draw.text((x, y_bottom), file_label, fill=color, font=font_coord)
                
                # Rank labels (1-8) at left
                rank_label = str(i + 1 if flip else 8 - i)
                x_left = board_x - 20
                y = board_y + i * self.square_size + self.square_size // 2 - 7
                is_light = i % 2 == 0
                color = '#FFFFFF' if is_light else '#555555'
                draw.text((x_left, y), rank_label, fill=color, font=font_coord)
        
        # Draw caption
        if caption:
            y_caption = board_y + self.board_size + coord_margin + 10
            bbox = draw.textbbox((0, 0), caption, font=font_caption)
            tw = bbox[2] - bbox[0]
            draw.text(((total_width - tw) // 2, y_caption), caption,
                     fill='#555555', font=font_caption)
        
        return img
    
    def render_move(self,
                    board: chess.Board,
                    move_san: str,
                    title: str = "",
                    move_number: int = 1,
                    flip: bool = False) -> Image.Image:
        """Render a board before and after a move."""
        
        move = board.parse_san(move_san)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        
        caption = f"{move_number}. {move_san}"
        
        # Render before move
        img_before = self.render_board(
            board, 
            title=title,
            caption=f"Before: {caption}",
            highlight_from=from_sq,
            flip=flip
        )
        
        # Make move and render after
        board.push(move)
        
        img_after = self.render_board(
            board,
            title=title,
            caption=f"After: {caption}",
            highlight_to=to_sq,
            flip=flip
        )
        
        # Combine side by side
        combined = Image.new('RGB', 
                           (img_before.width * 2 + 20, img_before.height),
                           self.bg_color)
        combined.paste(img_before, (0, 0))
        
        # Draw arrow in middle
        draw = ImageDraw.Draw(combined)
        arrow_x = img_before.width + 10
        arrow_y = img_before.height // 2
        draw.polygon([(arrow_x-8, arrow_y-15), (arrow_x+8, arrow_y), 
                     (arrow_x-8, arrow_y+15)], fill='#1a1a2e')
        
        combined.paste(img_after, (img_before.width + 20, 0))
        
        return combined
    
    def render_opening(self,
                       moves: List[str],
                       title: str = "",
                       output_dir: str = "./chess-diagrams") -> List[str]:
        """Render a complete opening sequence."""
        
        os.makedirs(output_dir, exist_ok=True)
        filenames = []
        
        board = chess.Board()
        
        # Render initial position
        img = self.render_board(board, title=title, caption="Initial Position")
        fname = os.path.join(output_dir, "00_initial.jpg")
        img.save(fname, 'JPEG', quality=90)
        filenames.append(fname)
        
        # Render each move
        for i, move_san in enumerate(moves):
            move = board.parse_san(move_san)
            from_sq = chess.square_name(move.from_square)
            to_sq = chess.square_name(move.to_square)
            
            move_num = (i // 2) + 1
            color = "White" if i % 2 == 0 else "Black"
            
            # Render with highlight
            img = self.render_board(
                board,
                title=title,
                caption=f"{move_num}. {color}: {move_san}",
                highlight_from=from_sq,
                highlight_to=to_sq
            )
            
            fname = os.path.join(output_dir, f"{i+1:02d}_{move_san.replace('+', '').replace('#', '')}.jpg")
            img.save(fname, 'JPEG', quality=90)
            filenames.append(fname)
            
            board.push(move)
        
        return filenames


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Chess Game Renderer')
    parser.add_argument('--moves', '-m', help='Opening moves in SAN (e.g., "e4 e5 Nf3 Nc6 Bc4")')
    parser.add_argument('--title', '-t', default='Chess Opening', help='Diagram title')
    parser.add_argument('--output', '-o', default='./chess-diagrams', help='Output directory')
    parser.add_argument('--size', '-s', type=int, default=80, help='Piece size in pixels')
    parser.add_argument('--fen', '-f', help='FEN position to render')
    parser.add_argument('--flip', action='store_true', help='Flip board (Black perspective)')
    
    args = parser.parse_args()
    
    renderer = ChessRenderer(piece_size=args.size)
    
    if args.fen:
        board = chess.Board(args.fen)
        img = renderer.render_board(board, title=args.title, flip=args.flip)
        img.save(os.path.join(args.output, "position.jpg"), 'JPEG', quality=95)
        print(f"Saved position to {args.output}/position.jpg")
    
    elif args.moves:
        moves = args.moves.split()
        files = renderer.render_opening(moves, title=args.title, output_dir=args.output)
        print(f"Generated {len(files)} diagrams in {args.output}")
    
    else:
        # Demo: Italian Game
        print("Running demo: Italian Game")
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]
        files = renderer.render_opening(moves, title="Italian Game", 
                                        output_dir=args.output)
        print(f"Generated {len(files)} diagrams")
