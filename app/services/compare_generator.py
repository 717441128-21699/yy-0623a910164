import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import List, Tuple, Dict
import os

from app.config import COMPARE_DIR
from app.services.image_utils import imread_unicode, imwrite_unicode


class CompareGenerator:
    def __init__(self):
        self.output_dir = COMPARE_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resize_and_pad(self, img: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
        target_w, target_h = target_size
        h, w = img.shape[:2]

        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        resized = cv2.resize(img, (new_w, new_h))

        padded = np.ones((target_h, target_w, 3), dtype=np.uint8) * 255

        x_offset = (target_w - new_w) // 2
        y_offset = (target_h - new_h) // 2

        padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

        return padded

    def add_label(self, img: np.ndarray, label: str, position: str = "top") -> np.ndarray:
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        try:
            font = ImageFont.truetype("simhei.ttf", 24)
        except:
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        img_w, img_h = pil_img.size

        if position == "top":
            x = (img_w - text_w) // 2
            y = 10
            draw.rectangle([x - 10, y - 5, x + text_w + 10, y + text_h + 10], fill=(255, 255, 255))
            draw.text((x, y), label, fill=(0, 0, 0), font=font)
        elif position == "bottom":
            x = (img_w - text_w) // 2
            y = img_h - text_h - 15
            draw.rectangle([x - 10, y - 5, x + text_w + 10, y + text_h + 10], fill=(255, 255, 255))
            draw.text((x, y), label, fill=(0, 0, 0), font=font)

        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    def create_pair_comparison(self, before_path: str, after_path: str, angle: str,
                                before_label: str, after_label: str) -> np.ndarray:
        before_img = imread_unicode(before_path)
        after_img = imread_unicode(after_path)

        if before_img is None or after_img is None:
            return None

        target_h = 300
        h1, w1 = before_img.shape[:2]
        h2, w2 = after_img.shape[:2]

        scale1 = target_h / h1
        scale2 = target_h / h2

        before_resized = cv2.resize(before_img, (int(w1 * scale1), target_h))
        after_resized = cv2.resize(after_img, (int(w2 * scale2), target_h))

        before_labeled = self.add_label(before_resized, before_label, "top")
        after_labeled = self.add_label(after_resized, after_label, "top")

        pair_img = np.hstack([before_labeled, after_labeled])

        pair_img = self.add_label(pair_img, angle, "bottom")

        return pair_img

    def generate_comparison_grid(self, photo_pairs: List[Dict], patient_no: str,
                                  before_date: str, after_date: str,
                                  compare_mode: str) -> str:
        pair_images = []
        angles = []

        before_label = "初诊" if compare_mode == "initial_vs_current" else "上次"
        after_label = "本次"

        for pair in photo_pairs:
            pair_img = self.create_pair_comparison(
                pair["before_path"],
                pair["after_path"],
                pair["angle"],
                before_label,
                after_label
            )
            if pair_img is not None:
                pair_images.append(pair_img)
                angles.append(pair["angle"])

        if not pair_images:
            return ""

        cols = 2
        rows = (len(pair_images) + cols - 1) // cols

        max_width = max(img.shape[1] for img in pair_images)
        max_height = max(img.shape[0] for img in pair_images)

        header_h = 60
        total_w = max_width * cols
        total_h = header_h + max_height * rows

        result = np.ones((total_h, total_w, 3), dtype=np.uint8) * 245

        header_pil = Image.fromarray(np.ones((header_h, total_w, 3), dtype=np.uint8) * 255)
        draw = ImageDraw.Draw(header_pil)
        try:
            font_title = ImageFont.truetype("simhei.ttf", 28)
            font_sub = ImageFont.truetype("simhei.ttf", 18)
        except:
            font_title = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        title = f"正畸复诊对比 - 患者 {patient_no}"
        subtitle = f"{before_label}({before_date})  vs  {after_label}({after_date})"

        draw.text((20, 10), title, fill=(0, 0, 0), font=font_title)
        draw.text((20, 35), subtitle, fill=(80, 80, 80), font=font_sub)

        result[:header_h, :] = cv2.cvtColor(np.array(header_pil), cv2.COLOR_RGB2BGR)

        for idx, pair_img in enumerate(pair_images):
            row = idx // cols
            col = idx % cols

            x = col * max_width
            y = header_h + row * max_height

            p_h, p_w = pair_img.shape[:2]
            x_offset = (max_width - p_w) // 2
            y_offset = (max_height - p_h) // 2

            result[y + y_offset:y + y_offset + p_h, x + x_offset:x + x_offset + p_w] = pair_img

        output_filename = f"compare_{patient_no}_{compare_mode}_{before_date}_{after_date}.jpg"
        output_path = self.output_dir / output_filename

        imwrite_unicode(str(output_path), result)

        return str(output_path)


compare_generator = CompareGenerator()
