import cv2
import numpy as np
from typing import Optional


def imread_unicode(file_path: str) -> Optional[np.ndarray]:
    try:
        with open(file_path, "rb") as f:
            img_array = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def imread_unicode_gray(file_path: str) -> Optional[np.ndarray]:
    try:
        with open(file_path, "rb") as f:
            img_array = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
        return img
    except Exception:
        return None


def imwrite_unicode(file_path: str, img: np.ndarray, params: list = None) -> bool:
    try:
        ext = "." + file_path.rsplit(".", 1)[-1]
        if params is None:
            if ext.lower() in [".jpg", ".jpeg"]:
                params = [cv2.IMWRITE_JPEG_QUALITY, 90]
            else:
                params = []
        success, encoded_img = cv2.imencode(ext, img, params)
        if success:
            with open(file_path, "wb") as f:
                f.write(encoded_img.tobytes())
            return True
        return False
    except Exception:
        return False
