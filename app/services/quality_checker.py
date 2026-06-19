import cv2
import numpy as np
from typing import Tuple
from app.config import settings


class QualityChecker:
    def __init__(self):
        self.brightness_threshold = settings.quality_brightness_threshold
        self.blur_threshold = settings.quality_blur_threshold
        self.center_tolerance = 0.15

    def check_brightness(self, gray_img: np.ndarray) -> Tuple[float, bool]:
        brightness = float(np.mean(gray_img))
        is_too_dark = brightness < self.brightness_threshold
        return brightness, is_too_dark

    def check_sharpness(self, gray_img: np.ndarray) -> Tuple[float, bool]:
        laplacian = cv2.Laplacian(gray_img, cv2.CV_64F)
        sharpness = float(np.var(laplacian))
        is_blurry = sharpness < self.blur_threshold
        return sharpness, is_blurry

    def check_centering(self, gray_img: np.ndarray) -> Tuple[float, float, bool]:
        h, w = gray_img.shape
        center_x, center_y = w // 2, h // 2

        _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = 255 - binary if np.mean(binary) > 127 else binary

        coords = np.column_stack(np.where(binary > 0))
        if len(coords) == 0:
            return 0.0, 0.0, False

        mass_center_y = float(np.mean(coords[:, 0]))
        mass_center_x = float(np.mean(coords[:, 1]))

        offset_x = (mass_center_x - center_x) / w
        offset_y = (mass_center_y - center_y) / h

        is_not_centered = abs(offset_x) > self.center_tolerance or abs(offset_y) > self.center_tolerance

        return offset_x, offset_y, is_not_centered

    def check_occlusion(self, img: np.ndarray, gray_img: np.ndarray, angle: str) -> Tuple[bool, str]:
        occlusion_notes = ""
        has_occlusion = False

        if "口内" in angle or "牙合面" in angle:
            h, w = gray_img.shape
            top_region = gray_img[:int(h * 0.2), :]
            bottom_region = gray_img[int(h * 0.8):, :]

            top_dark_ratio = float(np.mean(top_region < 50))
            bottom_dark_ratio = float(np.mean(bottom_region < 50))

            if top_dark_ratio > 0.6 or bottom_dark_ratio > 0.6:
                has_occlusion = True
                occlusion_notes = "口内镜可能存在遮挡，建议检查拍摄角度"

            if "牙合面" in angle:
                center_region = gray_img[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
                if np.std(center_region) < 20:
                    has_occlusion = True
                    occlusion_notes = "牙合面拍摄可能不完整，建议调整口内镜位置"

        elif "面相" in angle:
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lower_skin = np.array([0, 20, 40])
            upper_skin = np.array([40, 255, 255])
            skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)
            skin_ratio = float(np.sum(skin_mask > 0) / (hsv.shape[0] * hsv.shape[1]))

            if skin_ratio < 0.05:
                has_occlusion = True
                occlusion_notes = "面部未完整显示，请确保脸部居中且无遮挡"

        return has_occlusion, occlusion_notes

    def analyze(self, image_path: str, angle: str) -> dict:
        img = cv2.imread(image_path)
        if img is None:
            return {
                "brightness": 0,
                "sharpness": 0,
                "center_offset_x": 0,
                "center_offset_y": 0,
                "is_too_dark": True,
                "is_blurry": True,
                "is_not_centered": True,
                "is_occluded": False,
                "quality_passed": False,
                "notes": "无法读取图片文件"
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        brightness, is_too_dark = self.check_brightness(gray)
        sharpness, is_blurry = self.check_sharpness(gray)
        offset_x, offset_y, is_not_centered = self.check_centering(gray)
        is_occluded, occlusion_notes = self.check_occlusion(img, gray, angle)

        quality_passed = not (is_too_dark or is_blurry or is_not_centered or is_occluded)

        notes_list = []
        if is_too_dark:
            notes_list.append("照片过暗，请增加光照")
        if is_blurry:
            notes_list.append("照片模糊，请保持相机稳定")
        if is_not_centered:
            notes_list.append("主体未居中，请调整拍摄位置")
        if is_occluded:
            notes_list.append(occlusion_notes)

        notes = "；".join(notes_list) if notes_list else ""

        return {
            "brightness": round(brightness, 2),
            "sharpness": round(sharpness, 2),
            "center_offset_x": round(offset_x, 4),
            "center_offset_y": round(offset_y, 4),
            "is_too_dark": is_too_dark,
            "is_blurry": is_blurry,
            "is_not_centered": is_not_centered,
            "is_occluded": is_occluded,
            "quality_passed": quality_passed,
            "notes": notes
        }


quality_checker = QualityChecker()
