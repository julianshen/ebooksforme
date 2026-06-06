#!/usr/bin/env python3
"""
Chess Game Renderer v2 - Professional chess diagram generator
Uses embedded SVG piece data (no network required)
"""

import chess
import os
import io
import base64
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional

# Embedded SVG piece data (Wikimedia Commons, public domain, Cburnett)
# These are the standard CBurnett chess pieces used in most chess software
PIECE_SVGS = {
    'wK': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path fill="#fff" stroke-linecap="butt" stroke-linejoin="miter" d="M22.5 11.63V6M20 8h5"/><path fill="#fff" stroke="#000" d="M22.5 25s4.5-7.5 3-10.5c0 0-1-2.5-3-2.5s-3 2.5-3 2.5c-1.5 3 3 10.5 3 10.5"/><path fill="#fff" stroke="#000" d="M11.5 37c5.5 3.5 15.5 3.5 21 0v-7s9-4.5 6-10.5c-4-1-5 5-8 6.5-3 1.5-7 1.5-10 0-3-1.5-4-7.5-8-6.5-3 6 6 10.5 6 10.5v7"/><path fill="#fff" stroke="#000" d="M11.5 30c5.5-3 15.5-3 21 0"/><path fill="#fff" stroke="#000" d="M11.5 33.5c5.5-3 15.5-3 21 0"/><path fill="#fff" stroke="#000" d="M11.5 37c5.5-3 15.5-3 21 0"/></g></svg>''',
    'wQ': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="#fff" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path d="M8 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM24.5 7.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM41 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM16 8.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM33 9a2 2 0 1 1-4 0 2 2 0 1 1 4 0z"/><path stroke-linecap="butt" d="M9 26c8.5-1.5 21-1.5 27 0l2-12-7 11V11l-5.5 13.5-3-15-3 15-5.5-13.5V25l-7-11 2 12z"/><path stroke-linecap="butt" d="M9 26c0 2 1.5 2 2.5 4 1 2 1 1 .5 3.5-1.5 1-1.5 2.5-1.5 2.5-1.5 1.5.5 2.5.5 2.5 6.5 1 16.5 1 23 0 0 0 1.5-1 0-2.5 0 0 .5-1.5-1-2.5-.5-2.5-.5-1.5.5-3.5 1-2 2.5-2 2.5-4-8.5-1.5-18.5-1.5-27 0z"/><path fill="none" d="M11.5 30c3.5-1 18.5-1 22 0"/><path fill="none" d="M12 33.5c6-1 15-1 21 0"/></g></svg>''',
    'wR': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="#fff" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path stroke-linecap="butt" d="M9 39h27v-3H9v3zM12 36v-4h21v4H12zM11 14V9h4v2h5V9h5v2h5V9h4v5"/><path d="M34 14l-3 3H14l-3-3"/><path stroke-linecap="butt" stroke-linejoin="miter" d="M31 17v12.5H14V17"/><path d="M31 29.5l1.5 2.5h-20l1.5-2.5"/><path fill="none" stroke-linejoin="miter" d="M11 14h23"/></g></svg>''',
    'wB': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><g fill="#fff" stroke-linecap="butt"><path d="M9 36c3.39-.97 10.11.43 13.5-2 3.39 2.43 10.11 1.03 13.5 2 0 0 1.65.54 3 2-.68.97-1.65.99-3 .5-3.39-.97-10.11.46-13.5-1-3.39 1.46-10.11.03-13.5 1-1.35.49-2.32.47-3-.5 1.36-1.46 3-2 3-2z"/><path d="M15 32c2.5 2.5 12.5 2.5 15 0 .5-1.5 0-2 0-2 0-2.5-2.5-4-2.5-4 5.5-1.5 6-11.5-5-15.5-11 4-10.5 14-5 15.5 0 0-2.5 1.5-2.5 4 0 0-.5.5 0 2z"/><path d="M25 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0z"/></g><path d="M17.5 26h10M15 30h15M22.5 15.5v5M20 18h5" stroke-linejoin="miter"/></g></svg>''',
    'wN': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path fill="#fff" d="M22 10c10.5 1 16.5 8 16 29H15c0-9 10-6.5 8-21"/><path fill="#fff" d="M24 18c.38 2.91-5.55 7.37-8 9-3 2-2.82 4.34-5 4-1.042-.94 1.41-3.04 0-3-1 0 .19 1.23-1 2-1 0-4.003 1-4-4 0-2 6-12 6-12s1.89-1.9 2-3.5c-.73-.994-.5-2-.5-3 1-1 3 2.5 3 2.5h2s.78-1.992 2.5-3c1 0 1 3 1 3"/><path fill="#fff" d="M9.5 25.5A.5.5 0 1 1 9 25a.5.5 0 0 1 .5.5z"/><path fill="#fff" stroke="#000" d="M14.933 15.055a4.25 4.25 0 0 1 4.058-2.993 4.25 4.25 0 0 1 3.976 2.978"/><path fill="none" d="M24.55 10.4l-3.95 3.95"/><path fill="none" d="M28.7 13.1l-2.25 3.65"/><path fill="none" d="M16.4 11.8l-2.65 2.15"/></g></svg>''',
    'wP': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><path fill="#fff" stroke="#000" stroke-linecap="round" stroke-width="1.5" d="M22.5 9c-2.21 0-4 1.79-4 4 0 .89.29 1.71.78 2.38C17.33 16.5 16 18.59 16 21c0 2.03.94 3.84 2.41 5.03-3 1.06-7.41 5.55-7.41 13.47h23c0-7.92-4.41-12.41-7.41-13.47 1.47-1.19 2.41-3 2.41-5.03 0-2.41-1.33-4.5-3.28-5.62.49-.67.78-1.49.78-2.38 0-2.21-1.79-4-4-4z"/></svg>''',
    'bK': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path stroke-linecap="butt" stroke-linejoin="miter" d="M22.5 11.63V6M20 8h5"/><path fill="#000" stroke="#000" d="M22.5 25s4.5-7.5 3-10.5c0 0-1-2.5-3-2.5s-3 2.5-3 2.5c-1.5 3 3 10.5 3 10.5"/><path fill="#000" stroke="#000" d="M11.5 37c5.5 3.5 15.5 3.5 21 0v-7s9-4.5 6-10.5c-4-1-5 5-8 6.5-3 1.5-7 1.5-10 0-3-1.5-4-7.5-8-6.5-3 6 6 10.5 6 10.5v7"/><path fill="#000" stroke="#000" d="M11.5 30c5.5-3 15.5-3 21 0"/><path fill="#000" stroke="#000" d="M11.5 33.5c5.5-3 15.5-3 21 0"/><path fill="#000" stroke="#000" d="M11.5 37c5.5-3 15.5-3 21 0"/></g></svg>''',
    'bQ': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><g fill="#000" stroke="none"><circle cx="6" cy="12" r="2.75"/><circle cx="14" cy="9" r="2.75"/><circle cx="22.5" cy="8" r="2.75"/><circle cx="31" cy="9" r="2.75"/><circle cx="39" cy="12" r="2.75"/></g><path fill="#000" stroke="#000" stroke-linecap="butt" stroke-linejoin="miter" d="M9 26c8.5-1.5 21-1.5 27 0l2-12-7 11V11l-5.5 13.5-3-15-3 15-5.5-13.5V25l-7-11 2 12z"/><path fill="#000" stroke="#000" stroke-linecap="butt" d="M9 26c0 2 1.5 2 2.5 4 1 2 1 1 .5 3.5-1.5 1-1.5 2.5-1.5 2.5-1.5 1.5.5 2.5.5 2.5 6.5 1 16.5 1 23 0 0 0 1.5-1 0-2.5 0 0 .5-1.5-1-2.5-.5-2.5-.5-1.5.5-3.5 1-2 2.5-2 2.5-4-8.5-1.5-18.5-1.5-27 0z"/><path fill="none" stroke="#fff" d="M11.5 30c3.5-1 18.5-1 22 0"/><path fill="none" stroke="#fff" d="M12 33.5c6-1 15-1 21 0"/></g></svg>''',
    'bR': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="#000" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path stroke-linecap="butt" d="M9 39h27v-3H9v3zM12.5 32l1.5-2.5h17l1.5 2.5h-20zM12 36v-4h21v4H12z"/><path stroke-linecap="butt" d="M14 29.5v-13h17v13H14z"/><path stroke-linecap="butt" d="M14 16.5L11 14h23l-3 2.5H14zM11 14V9h4v2h5V9h5v2h5V9h4v5H11z"/><path fill="none" stroke="#fff" stroke-linejoin="miter" stroke-width="1" d="M12 35.5h21"/></g></svg>''',
    'bB': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><g fill="#000" stroke-linecap="butt"><path d="M9 36c3.39-.97 10.11.43 13.5-2 3.39 2.43 10.11 1.03 13.5 2 0 0 1.65.54 3 2-.68.97-1.65.99-3 .5-3.39-.97-10.11.46-13.5-1-3.39 1.46-10.11.03-13.5 1-1.35.49-2.32.47-3-.5 1.36-1.46 3-2 3-2z"/><path d="M15 32c2.5 2.5 12.5 2.5 15 0 .5-1.5 0-2 0-2 0-2.5-2.5-4-2.5-4 5.5-1.5 6-11.5-5-15.5-11 4-10.5 14-5 15.5 0 0-2.5 1.5-2.5 4 0 0-.5.5 0 2z"/><path d="M25 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0z"/></g><path d="M17.5 26h10M15 30h15M22.5 15.5v5M20 18h5" stroke-linejoin="miter" stroke="#fff"/></g></svg>''',
    'bN': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path fill="#000" d="M22 10c10.5 1 16.5 8 16 29H15c0-9 10-6.5 8-21"/><path fill="#000" d="M24 18c.38 2.91-5.55 7.37-8 9-3 2-2.82 4.34-5 4-1.042-.94 1.41-3.04 0-3-1 0 .19 1.23-1 2-1 0-4.003 1-4-4 0-2 6-12 6-12s1.89-1.9 2-3.5c-.73-.994-.5-2-.5-3 1-1 3 2.5 3 2.5h2s.78-1.992 2.5-3c1 0 1 3 1 3"/><path fill="#000" d="M9.5 25.5A.5.5 0 1 1 9 25a.5.5 0 0 1 .5.5z"/><path fill="#000" stroke="#fff" d="M14.933 15.055a4.25 4.25 0 0 1 4.058-2.993 4.25 4.25 0 0 1 3.976 2.978"/><path fill="none" stroke="#fff" d="M24.55 10.4l-3.95 3.95"/><path fill="none" stroke="#fff" d="M28.7 13.1l-2.25 3.65"/><path fill="none" stroke="#fff" d="M16.4 11.8l-2.65 2.15"/></g></svg>''',
    'bP': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 45 45"><path fill="#000" stroke="#000" stroke-linecap="round" stroke-width="1.5" d="M22.5 9c-2.21 0-4 1.79-4 4 0 .89.29 1.71.78 2.38C17.33 16.5 16 18.59 16 21c0 2.03.94 3.84 2.41 5.03-3 1.06-7.41 5.55-7.41 13.47h23c0-7.92-4.41-12.41-7.41-13.47 1.47-1.19 2.41-3 2.41-5.03 0-2.41-1.33-4.5-3.28-5.62.49-.67.78-1.49.78-2.38 0-2.21-1.79-4-4-4z"/></svg>''',
}


class ChessRenderer:
    """Professional chess board renderer with actual piece images."""
    
    def __init__(self, piece_size: int = 80):
        self.piece_size = piece_size
        self.square_size = piece_size
        self.board_size = piece_size * 8
        
        # Colors
        self.light_square = "#F0D9B5"
        self.dark_square = "#B58863"
        self.highlight_from = "#F7EC4F"  # Yellow
        self.highlight_to = "#A8D5BA"    # Green
        self.last_move = "#C8E6C9"
        self.check_highlight = "#FF8A80"  # Red for check
        self.bg_color = "#FFFFFF"
        
        # Load piece images
        self.pieces = {}
        self._load_pieces()
    
    def _load_pieces(self):
        """Load piece images from embedded SVG data."""
        try:
            import cairosvg
            has_cairosvg = True
        except ImportError:
            has_cairosvg = False
        
        for key, svg_data in PIECE_SVGS.items():
            if has_cairosvg:
                png_data = cairosvg.svg2png(bytestring=svg_data.encode(),
                                             output_width=self.piece_size,
                                             output_height=self.piece_size)
                img = Image.open(io.BytesIO(png_data))
            else:
                img = self._create_fallback_piece(key)
            
            self.pieces[key] = img.convert('RGBA')
    
    def _create_fallback_piece(self, key: str) -> Image.Image:
        """Create a simple fallback piece image."""
        img = Image.new('RGBA', (self.piece_size, self.piece_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        is_white = key[0] == 'w'
        color = (255, 255, 255, 255) if is_white else (30, 30, 30, 255)
        outline = (30, 30, 30, 255) if is_white else (200, 200, 200, 255)
        piece_type = key[1]
        
        cx, cy = self.piece_size // 2, self.piece_size // 2
        
        if piece_type == 'P':
            draw.ellipse([cx-10, cy-18, cx+10, cy+2], fill=color, outline=outline, width=2)
            draw.ellipse([cx-14, cy+2, cx+14, cy+18], fill=color, outline=outline, width=2)
        elif piece_type == 'N':
            draw.polygon([(cx, cy-22), (cx+18, cy+8), (cx-12, cy+12)], fill=color, outline=outline, width=2)
            draw.ellipse([cx-14, cy+5, cx+14, cy+22], fill=color, outline=outline, width=2)
        elif piece_type == 'B':
            draw.ellipse([cx-6, cy-22, cx+6, cy-10], fill=color, outline=outline, width=2)
            draw.polygon([(cx, cy-12), (cx+16, cy+18), (cx-16, cy+18)], fill=color, outline=outline, width=2)
        elif piece_type == 'R':
            draw.rectangle([cx-16, cy-12, cx+16, cy+16], fill=color, outline=outline, width=2)
            draw.rectangle([cx-13, cy-20, cx+13, cy-12], fill=color, outline=outline, width=2)
        elif piece_type == 'Q':
            draw.ellipse([cx-18, cy-5, cx+18, cy+18], fill=color, outline=outline, width=2)
            for dx in [-14, -5, 5, 14]:
                draw.ellipse([cx+dx-5, cy-24, cx+dx+5, cy-10], fill=color, outline=outline, width=2)
        elif piece_type == 'K':
            draw.ellipse([cx-16, cy-5, cx+16, cy+18], fill=color, outline=outline, width=2)
            draw.rectangle([cx-4, cy-24, cx+4, cy-10], fill=color, outline=outline, width=2)
            draw.rectangle([cx-12, cy-20, cx+12, cy-16], fill=color, outline=outline, width=2)
        
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
        
        coord_margin = 30 if show_coordinates else 0
        title_height = 50 if title else 0
        caption_height = 30 if caption else 0
        padding = 20
        
        total_width = self.board_size + coord_margin * 2 + padding * 2
        total_height = (self.board_size + coord_margin * 2 +
                       title_height + caption_height + padding * 2)
        
        img = Image.new('RGB', (total_width, total_height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_caption = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            font_coord = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font_title = ImageFont.load_default()
            font_caption = ImageFont.load_default()
            font_coord = ImageFont.load_default()
        
        # Title
        if title:
            bbox = draw.textbbox((0, 0), title, font=font_title)
            tw = bbox[2] - bbox[0]
            draw.text(((total_width - tw) // 2, padding), title,
                     fill='#1a1a2e', font=font_title)
        
        board_x = padding + coord_margin
        board_y = padding + title_height + coord_margin
        
        # Draw squares
        for row in range(8):
            for col in range(8):
                if flip:
                    file_idx = 7 - col
                    rank_idx = row
                else:
                    file_idx = col
                    rank_idx = 7 - row
                
                x = board_x + col * self.square_size
                y = board_y + row * self.square_size
                
                sq = chess.square(file_idx, rank_idx)
                sq_name = chess.square_name(sq)
                
                is_light = (row + col) % 2 == 0
                color = self.light_square if is_light else self.dark_square
                
                if highlight_from and sq_name == highlight_from:
                    color = self.highlight_from
                elif highlight_to and sq_name == highlight_to:
                    color = self.highlight_to
                
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
        
        # Coordinates
        if show_coordinates:
            for i in range(8):
                file_label = chr(ord('a') + (7 - i if flip else i))
                x = board_x + i * self.square_size + self.square_size // 2 - 5
                y_bottom = board_y + self.board_size + 8
                is_light = i % 2 == 1
                color = '#FFFFFF' if is_light else '#555555'
                draw.text((x, y_bottom), file_label, fill=color, font=font_coord)
                
                rank_label = str(i + 1 if flip else 8 - i)
                x_left = board_x - 20
                y = board_y + i * self.square_size + self.square_size // 2 - 7
                is_light = i % 2 == 0
                color = '#FFFFFF' if is_light else '#555555'
                draw.text((x_left, y), rank_label, fill=color, font=font_coord)
        
        # Caption
        if caption:
            y_caption = board_y + self.board_size + coord_margin + 10
            bbox = draw.textbbox((0, 0), caption, font=font_caption)
            tw = bbox[2] - bbox[0]
            draw.text(((total_width - tw) // 2, y_caption), caption,
                     fill='#555555', font=font_caption)
        
        return img
    
    def render_opening(self,
                       moves: List[str],
                       title: str = "",
                       output_dir: str = "./chess-diagrams") -> List[str]:
        """Render a complete opening sequence."""
        
        os.makedirs(output_dir, exist_ok=True)
        filenames = []
        
        board = chess.Board()
        
        # Initial position
        img = self.render_board(board, title=title, caption="Initial Position")
        fname = os.path.join(output_dir, "00_initial.jpg")
        img.save(fname, 'JPEG', quality=95)
        filenames.append(fname)
        
        # Each move
        for i, move_san in enumerate(moves):
            move = board.parse_san(move_san)
            from_sq = chess.square_name(move.from_square)
            to_sq = chess.square_name(move.to_square)
            
            move_num = (i // 2) + 1
            color = "White" if i % 2 == 0 else "Black"
            
            img = self.render_board(
                board,
                title=title,
                caption=f"{move_num}. {color}: {move_san}",
                highlight_from=from_sq,
                highlight_to=to_sq
            )
            
            safe_name = move_san.replace('+', '').replace('#', '').replace('=', '')
            fname = os.path.join(output_dir, f"{i+1:02d}_{safe_name}.jpg")
            img.save(fname, 'JPEG', quality=95)
            filenames.append(fname)
            
            board.push(move)
        
        return filenames


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Chess Game Renderer v2')
    parser.add_argument('--moves', '-m', help='Opening moves in SAN')
    parser.add_argument('--title', '-t', default='Chess Opening', help='Diagram title')
    parser.add_argument('--output', '-o', default='./chess-diagrams', help='Output directory')
    parser.add_argument('--size', '-s', type=int, default=80, help='Piece size')
    parser.add_argument('--fen', '-f', help='FEN position')
    parser.add_argument('--flip', action='store_true', help='Flip board')
    
    args = parser.parse_args()
    
    renderer = ChessRenderer(piece_size=args.size)
    
    if args.fen:
        board = chess.Board(args.fen)
        img = renderer.render_board(board, title=args.title, flip=args.flip)
        os.makedirs(args.output, exist_ok=True)
        img.save(os.path.join(args.output, "position.jpg"), 'JPEG', quality=95)
        print(f"Saved to {args.output}/position.jpg")
    
    elif args.moves:
        moves = args.moves.split()
        files = renderer.render_opening(moves, title=args.title, output_dir=args.output)
        print(f"Generated {len(files)} diagrams in {args.output}")
    
    else:
        print("Running demo: Italian Game")
        moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]
        files = renderer.render_opening(moves, title="Italian Game",
                                        output_dir=args.output)
        print(f"Generated {len(files)} diagrams")
