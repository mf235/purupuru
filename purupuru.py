# 必要なライブラリのインストールはこちらを実行してね！
# pip install Pillow numpy scipy opencv-python tkinterdnd2

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter
import math
import os
import cv2
import datetime

# D&D対応
try:
    from tkinterdnd2 import *
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

class PurupuruPaintGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ぷるぷるGIF＆MP4メーカー")
        self.root.geometry("1280x720")
        
        self.image = None
        self.img_array = None
        self.mask_image = None
        self.centers = []
        self.h, self.w = 0, 0
        self.canvas_photo = None
        self.drawing = False
        self.erasing = False
        self.center_mode = False
        self.last_x = self.last_y = None
        
        # パラメータ
        self.brush_size = tk.IntVar(value=18)
        self.amp = tk.DoubleVar(value=12.0)
        self.freq = tk.DoubleVar(value=2.5)
        self.horiz = tk.DoubleVar(value=0.4)
        self.damping = tk.DoubleVar(value=0.3)
        self.falloff = tk.DoubleVar(value=1.8)
        self.mode = tk.StringVar(value='bounce')
        self.frames = tk.IntVar(value=36)
        self.fps = tk.IntVar(value=24)
        
        self.create_ui()
    
    def create_ui(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # 1. 画像列 (一番幅が広い - weightを大きめに設定)
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=5)
        
        self.canvas = tk.Canvas(left_frame, bg="#222", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        v_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll = ttk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")
        
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        # 2. ボタン列 (縦に並べて配置)
        mid_frame = ttk.Frame(paned)
        paned.add(mid_frame, weight=1)
        
        btn_frame = ttk.Frame(mid_frame)
        btn_frame.pack(pady=10, fill=tk.X, padx=10)
        
        ttk.Button(btn_frame, text="📂 画像を選択", command=self.load_image).pack(side=tk.TOP, fill=tk.X, pady=4)
        self.draw_btn = ttk.Button(btn_frame, text="✏️ 描画モード", command=self.toggle_draw)
        self.draw_btn.pack(side=tk.TOP, fill=tk.X, pady=4)
        self.erase_btn = ttk.Button(btn_frame, text="🧼 消しゴム", command=self.toggle_erase)
        self.erase_btn.pack(side=tk.TOP, fill=tk.X, pady=4)
        self.center_btn = ttk.Button(btn_frame, text="📍 中心配置", command=self.toggle_center_mode)
        self.center_btn.pack(side=tk.TOP, fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="🔍 肌全体マスク", command=self.auto_detect_skin).pack(side=tk.TOP, fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="🗑️ マスククリア", command=self.clear_mask).pack(side=tk.TOP, fill=tk.X, pady=4)
        ttk.Button(btn_frame, text="📍 中心クリア", command=self.clear_centers).pack(side=tk.TOP, fill=tk.X, pady=4)
        
        # ブラシサイズをボタン列に追加
        ttk.Label(btn_frame, text="🖌️ ブラシサイズ").pack(side=tk.TOP, pady=(15, 2))
        tk.Scale(btn_frame, from_=5, to=40, variable=self.brush_size, orient=tk.HORIZONTAL, resolution=1).pack(side=tk.TOP, fill=tk.X)
        
        # ▼ここを変更！GIFとMP4の出力ボタンを分けたぞ
        ttk.Button(btn_frame, text="🎉 GIF生成！", command=lambda: self.generate_animation('gif')).pack(side=tk.TOP, fill=tk.X, pady=(20, 4))
        ttk.Button(btn_frame, text="🎥 MP4生成！", command=lambda: self.generate_animation('mp4')).pack(side=tk.TOP, fill=tk.X, pady=4)
        
        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
        
        # 3. プルプル調整列
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        jiggle_frame = ttk.LabelFrame(right_frame, text="💖 ぷるぷる調整")
        jiggle_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        params = [
            ("揺れの大きさ (amp):", self.amp, 5, 25, 0.5),
            ("速さ (freq):", self.freq, 1, 5, 0.1),
            ("横揺れ比率:", self.horiz, 0, 1, 0.1),
            ("減衰 (damping):", self.damping, 0, 1, 0.1),
            ("柔らかさ (falloff):", self.falloff, 0.5, 5.0, 0.1),
            ("フレーム数:", self.frames, 20, 60, 1),
            ("FPS:", self.fps, 12, 30, 1)
        ]
        
        for i, (label, var, mn, mx, res) in enumerate(params):
            ttk.Label(jiggle_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=8)
            tk.Scale(jiggle_frame, from_=mn, to=mx, resolution=res, variable=var, orient=tk.HORIZONTAL).grid(row=i, column=1, sticky="ew", padx=5, pady=8)
        
        ttk.Label(jiggle_frame, text="モード:").grid(row=len(params), column=0, sticky="w", padx=5, pady=10)
        ttk.OptionMenu(jiggle_frame, self.mode, 'bounce', 'bounce', 'sine').grid(row=len(params), column=1, sticky="w", padx=5)
        
        jiggle_frame.grid_columnconfigure(1, weight=1)
        
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)
    
    def toggle_draw(self):
        self.drawing = not self.drawing
        self.erasing = False
        self.center_mode = False
        self.draw_btn.config(text="✏️ 描画中…" if self.drawing else "✏️ 描画モード")
        self.erase_btn.config(text="🧼 消しゴム")
    
    def toggle_erase(self):
        self.erasing = not self.erasing
        self.drawing = False
        self.center_mode = False
        self.erase_btn.config(text="🧼 消しゴム中…" if self.erasing else "🧼 消しゴム")
        self.draw_btn.config(text="✏️ 描画モード")
    
    def toggle_center_mode(self):
        self.center_mode = not self.center_mode
        self.drawing = False
        self.erasing = False
        self.center_btn.config(text="📍 中心配置中…" if self.center_mode else "📍 中心配置")
        self.draw_btn.config(text="✏️ 描画モード")
        self.erase_btn.config(text="🧼 消しゴム")
    
    def on_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        if files:
            path = files[0]
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                self.load_image_from_path(path)
    
    def load_image_from_path(self, path):
        self.image = Image.open(path).convert('RGBA')
        self.img_array = np.array(self.image)
        self.h, self.w = self.img_array.shape[:2]
        self.mask_image = Image.new('L', (self.w, self.h), 0)
        self.centers = []
        self.update_preview()
    
    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")])
        if path:
            self.load_image_from_path(path)
    
    def canvas_click(self, event):
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        if self.center_mode and self.image:
            self.centers.append((x, y))
            self.update_preview()
            return
        if self.drawing or self.erasing:
            self.start_draw(x, y)
    
    def paint(self, event):
        if not (self.drawing or self.erasing) or self.mask_image is None: return
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        draw = ImageDraw.Draw(self.mask_image)
        r = self.brush_size.get()
        color = 0 if self.erasing else 255
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color)
        if self.last_x is not None:
            draw.line([self.last_x, self.last_y, x, y], fill=color, width=r*2)
        self.last_x, self.last_y = x, y
        self.update_preview()
    
    def start_draw(self, x, y):
        self.last_x, self.last_y = x, y
        self.paint_from_coord(x, y)
    
    def paint_from_coord(self, x, y):
        if self.mask_image is None: return
        draw = ImageDraw.Draw(self.mask_image)
        r = self.brush_size.get()
        color = 0 if self.erasing else 255
        draw.ellipse([x-r, y-r, x+r, y+r], fill=color)
        self.update_preview()
    
    def stop_draw(self, event):
        self.last_x = self.last_y = None
    
    def clear_mask(self):
        if self.mask_image:
            self.mask_image = Image.new('L', (self.w, self.h), 0)
            self.update_preview()
    
    def clear_centers(self):
        self.centers = []
        self.update_preview()
    
    def update_preview(self):
        if self.image is None: return
        preview = self.image.copy()
        mask_rgba = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        mask_colored = Image.new('RGBA', self.image.size, (255, 105, 180, 140))
        mask_rgba.paste(mask_colored, (0, 0), self.mask_image)
        preview = Image.alpha_composite(preview, mask_rgba)
        
        draw = ImageDraw.Draw(preview)
        for cx, cy in self.centers:
            draw.ellipse([cx-8, cy-8, cx+8, cy+8], fill=(255, 0, 0, 220), outline="white", width=2)
        
        self.canvas_photo = ImageTk.PhotoImage(preview)
        self.canvas.image = self.canvas_photo
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.canvas_photo)
        self.canvas.config(scrollregion=(0, 0, self.w, self.h))
    
    def auto_detect_skin(self):
        if self.image is None:
            messagebox.showwarning("注意", "まず画像を読み込んでね！")
            return
        cv_img = cv2.cvtColor(np.array(self.image), cv2.COLOR_RGBA2BGR)
        hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 20, 80])
        upper_skin = np.array([20, 255, 255])
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (8, 8))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel)
        
        self.mask_image = Image.fromarray(skin_mask)
        self.update_preview()
        messagebox.showinfo("肌全体マスク完了！", "上半身の肌領域を全部マスクしたよ♡\n微妙なところは消しゴムで調整してね")
    
    # ▼関数名を変更し、引数でフォーマットを受け取るようにしたぞ！
    def generate_animation(self, file_type='gif'):
        if self.img_array is None or self.mask_image is None:
            messagebox.showwarning("注意", "画像とマスクを準備してね！")
            return
        
        binary_mask = np.array(self.mask_image) > 128
        smoothed = gaussian_filter(binary_mask.astype(float), sigma=6)
        mask_array = smoothed > 0.2
        weight_map = np.zeros((self.h, self.w), dtype=float)
        
        if self.centers and np.any(binary_mask):
            yy, xx = np.mgrid[0:self.h, 0:self.w].astype(float)
            for cx, cy in self.centers:
                dist = np.sqrt((xx - cx)**2 + (yy - cy)**2)
                influence = np.exp(- (dist / (self.falloff.get() * 25)) ** 2)
                weight_map = np.maximum(weight_map, influence)
            weight_map *= mask_array.astype(float)
            if weight_map.max() > 0:
                weight_map /= weight_map.max()
        else:
            if np.any(binary_mask):
                from scipy.ndimage import distance_transform_edt
                dist = distance_transform_edt(binary_mask)
                max_d = dist.max() or 1
                weight_map = (dist / max_d) ** self.falloff.get()
                weight_map *= mask_array.astype(float)
        
        now_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        output_path = f"purupuru-{now_str}.{file_type}"
        
        frames = []
        num_frames = self.frames.get()
        fps = self.fps.get()
        amp = self.amp.get()
        freq = self.freq.get()
        horiz_ratio = self.horiz.get()
        damping = self.damping.get()
        mode = self.mode.get()
        
        # フレーム生成ループ
        for i in range(num_frames):
            t = i / num_frames * 2 * math.pi * freq
            if mode == 'bounce':
                phase = t % (2 * math.pi)
                y_disp = amp * (-abs(np.sin(phase * 1.5)) * np.exp(-0.3 * (i / num_frames * 4)))
                x_disp = amp * horiz_ratio * np.cos(phase * 2.5) * 0.6
            else:
                y_disp = amp * np.sin(t)
                x_disp = amp * horiz_ratio * np.sin(t * 1.8)
            if damping > 0:
                decay = np.exp(-damping * i / num_frames * 4)
                y_disp *= decay
                x_disp *= decay
            
            y_disp_weighted = y_disp * weight_map
            x_disp_weighted = x_disp * weight_map
            
            yy, xx = np.mgrid[0:self.h, 0:self.w].astype(float)
            yy_disp = yy.copy() + y_disp_weighted
            xx_disp = xx.copy() + x_disp_weighted
            yy_disp = np.clip(yy_disp, 0, self.h-1)
            xx_disp = np.clip(xx_disp, 0, self.w-1)
            coords = [yy_disp.ravel(), xx_disp.ravel()]
            
            warped = []
            for c in range(4):
                channel = map_coordinates(self.img_array[:, :, c], coords, order=1, mode='reflect', prefilter=False)
                warped.append(channel.reshape(self.h, self.w))
            warped_array = np.stack(warped, axis=-1).astype(np.uint8)
            frames.append(Image.fromarray(warped_array))
        
        # ▼拡張子に応じた書き出し処理
        if file_type == 'gif':
            frames[0].save(output_path, save_all=True, append_images=frames[1:],
                           duration=1000//fps, loop=0, optimize=True, disposal=2)
        elif file_type == 'mp4':
            # OpenCVを使ってMP4に書き出し
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # 一般的で互換性の高いコーデック
            out = cv2.VideoWriter(output_path, fourcc, fps, (self.w, self.h))
            for frame in frames:
                # PILのRGBA画像を、OpenCV用のBGR画像に変換
                cv_img = cv2.cvtColor(np.array(frame), cv2.COLOR_RGBA2BGR)
                out.write(cv_img)
            out.release()
            
        messagebox.showinfo("完成！", f"🎉 ぷるぷる完成！\n{output_path}")
        try:
            os.startfile(output_path)
        except:
            pass

if __name__ == "__main__":
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = PurupuruPaintGUI(root)
    root.mainloop()