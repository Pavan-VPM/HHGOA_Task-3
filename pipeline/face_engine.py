"""
Face Identification & Encoding Engine.
Detects faces from image files or URLs, normalizes facial crops, extracts 128-dimensional
feature descriptors, perceptual hashes, and deterministic cryptographic fingerprints.
"""

import io
import os
from typing import Dict, Any, List, Optional, Tuple, Union
import cv2
import numpy as np
import requests
from PIL import Image

from blockchain.hasher import hash_face_array, sha256_hex


class FaceEngine:
    def __init__(self, target_size: Tuple[int, int] = (160, 160)):
        self.target_size = target_size

        # Load OpenCV Haar cascade for face detection
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        if not os.path.exists(cascade_path):
            raise FileNotFoundError(f"OpenCV Haar cascade not found at {cascade_path}")
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        # Also load eye cascade for facial alignment verification
        eye_cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_eye.xml")
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade_path) if os.path.exists(eye_cascade_path) else None

    def load_image(self, source: Union[str, bytes, np.ndarray, Image.Image]) -> np.ndarray:
        """Loads an image from a file path, URL, bytes, PIL Image, or numpy array."""
        if isinstance(source, np.ndarray):
            if len(source.shape) == 2:
                return cv2.cvtColor(source, cv2.COLOR_GRAY2BGR)
            return source

        if isinstance(source, Image.Image):
            rgb = source.convert("RGB")
            return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)

        if isinstance(source, bytes):
            arr = np.frombuffer(source, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image bytes")
            return img

        if isinstance(source, str):
            if source.startswith("http://") or source.startswith("https://"):
                resp = requests.get(source, timeout=15, headers={"User-Agent": "FacePipeline/1.0"})
                resp.raise_for_status()
                arr = np.frombuffer(resp.content, np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ValueError(f"Could not decode image from URL: {source}")
                return img
            elif os.path.exists(source):
                img = cv2.imread(source)
                if img is None:
                    raise ValueError(f"Could not load image from path: {source}")
                return img
            else:
                raise FileNotFoundError(f"Image source not found: {source}")

        raise TypeError(f"Unsupported image source type: {type(source)}")

    def detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects all faces in an image.
        Returns a list of detected face dictionaries sorted by area descending (largest face first).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Apply histogram equalization for robust detection under variable lighting
        equalized = cv2.equalizeHist(gray)

        # Detect faces with tuned scaleFactor and minNeighbors
        boxes = self.face_cascade.detectMultiScale(
            equalized,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        detected = []
        img_h, img_w = image.shape[:2]

        for (x, y, w, h) in boxes:
            # Expand bounding box slightly (15% padding) for full facial outline
            pad_x = int(w * 0.15)
            pad_y = int(h * 0.15)
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(img_w, x + w + pad_x)
            y2 = min(img_h, y + h + pad_y)

            crop = image[y1:y2, x1:x2]
            area = w * h

            detected.append({
                "bbox": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                "padded_box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "area": int(area),
                "crop": crop,
            })

        # Sort by largest face first
        detected.sort(key=lambda f: f["area"], reverse=True)
        return detected

    def normalize_face(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Normalizes face crop: resizes to standard target size, converts to grayscale,
        and applies contrast normalization.
        """
        resized = cv2.resize(face_crop, self.target_size, interpolation=cv2.INTER_AREA)
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized
        norm = cv2.equalizeHist(gray)
        return norm

    def compute_dhash(self, face_gray_160: np.ndarray, hash_size: int = 8) -> str:
        """Computes difference hash (dHash) for perceptual visual similarity."""
        resized = cv2.resize(face_gray_160, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        bits = diff.flatten()
        hex_str = "".join(f"{b:02x}" for b in np.packbits(bits))
        return hex_str

    def extract_feature_vector(self, normalized_face: np.ndarray) -> np.ndarray:
        """
        Extracts a deterministic 128-dimensional normalized facial feature vector
        based on spatial gradient blocks and frequency decomposition.
        """
        h, w = normalized_face.shape
        block_h, block_w = h // 4, w // 4  # 4x4 grid = 16 blocks

        features = []
        for i in range(4):
            for j in range(4):
                block = normalized_face[i * block_h:(i + 1) * block_h, j * block_w:(j + 1) * block_w]
                # Mean intensity
                mean_val = float(np.mean(block)) / 255.0
                # Standard deviation (texture complexity)
                std_val = float(np.std(block)) / 128.0
                # Gradients
                gx = cv2.Sobel(block, cv2.CV_32F, 1, 0, ksize=3)
                gy = cv2.Sobel(block, cv2.CV_32F, 0, 1, ksize=3)
                mag, _ = cv2.cartToPolar(gx, gy)
                grad_mean = float(np.mean(mag)) / 255.0
                grad_std = float(np.std(mag)) / 128.0
                grad_max = float(np.max(mag)) / 512.0
                grad_q75 = float(np.percentile(mag, 75)) / 255.0
                # Symmetry comparison
                left_half = block[:, :block_w // 2]
                right_half = cv2.flip(block[:, block_w // 2:], 1)
                sym_diff = float(np.mean(np.abs(left_half.astype(float) - right_half.astype(float)))) / 255.0
                # Contrast energy
                energy = float(np.sum(block.astype(float) ** 2)) / (block_h * block_w * (255.0 ** 2))

                features.extend([mean_val, std_val, grad_mean, grad_std, grad_max, grad_q75, sym_diff, energy])

        vec = np.array(features, dtype=np.float32)
        # L2-normalize feature vector
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def process_face(self, image_source: Union[str, bytes, np.ndarray, Image.Image]) -> Dict[str, Any]:
        """
        Executes end-to-end face processing on an image:
        1. Loads image.
        2. Detects face(s).
        3. Normalizes primary face crop.
        4. Computes 128-d feature descriptor, dHash, and cryptographic SHA-256 fingerprint.
        """
        img = self.load_image(image_source)
        faces = self.detect_faces(img)

        if not faces:
            # If face detector finds no frontal face with strict params, fall back to center crop
            h, w = img.shape[:2]
            cx, cy = w // 2, h // 2
            side = min(w, h) // 2
            crop = img[max(0, cy - side):min(h, cy + side), max(0, cx - side):min(w, cx + side)]
            primary = {
                "bbox": {"x": cx - side, "y": cy - side, "w": side * 2, "h": side * 2},
                "crop": crop,
                "confidence": 0.5,
                "detected": False
            }
        else:
            primary = faces[0]
            primary["confidence"] = 0.95
            primary["detected"] = True

        norm_crop = self.normalize_face(primary["crop"])
        dhash = self.compute_dhash(norm_crop)
        vector = self.extract_feature_vector(norm_crop)
        face_hash = hash_face_array(norm_crop)

        return {
            "face_detected": primary["detected"],
            "confidence": primary["confidence"],
            "bbox": primary["bbox"],
            "face_hash": face_hash,
            "dhash": dhash,
            "feature_vector": vector.tolist(),
            "normalized_crop": norm_crop,
            "original_shape": list(img.shape[:2]),
        }

    def compare_faces(self, face_a: Dict[str, Any], face_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compares two processed face encodings using cosine similarity and perceptual distance.
        Returns match verdict and confidence score.
        """
        vec_a = np.array(face_a["feature_vector"], dtype=np.float32)
        vec_b = np.array(face_b["feature_vector"], dtype=np.float32)

        cosine_sim = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b) + 1e-9))

        # Hamming distance between perceptual dhashes
        dhash_a = face_a["dhash"]
        dhash_b = face_b["dhash"]
        bin_a = bin(int(dhash_a, 16))[2:].zfill(64)
        bin_b = bin(int(dhash_b, 16))[2:].zfill(64)
        hamming_dist = sum(c1 != c2 for c1, c2 in zip(bin_a, bin_b))

        # Normalize score
        dhash_similarity = max(0.0, 1.0 - (hamming_dist / 64.0))
        composite_score = 0.7 * cosine_sim + 0.3 * dhash_similarity

        # Cryptographic exact match check
        exact_match = (face_a["face_hash"] == face_b["face_hash"])

        return {
            "is_match": composite_score >= 0.75 or exact_match,
            "composite_score": round(composite_score, 4),
            "cosine_similarity": round(cosine_sim, 4),
            "hamming_distance": hamming_dist,
            "exact_cryptographic_match": exact_match,
        }
