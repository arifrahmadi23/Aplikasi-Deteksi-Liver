"""
Pipeline Hybrid Deteksi Histopatologi Liver
YOLOv11 (Object Detection) → ResNet50 (Feature Extraction) → XGBoost (Classification)
"""

import pickle
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from ultralytics import YOLO
from PIL import Image


# Label kelas deteksi
CLASS_NAMES = ["Ballooning", "Fibrosis", "Inflammation", "Steatosis"]

# Deskripsi klinis untuk setiap kelas
CLASS_DESCRIPTIONS = {
    "Ballooning": "Pembengkakan hepatosit yang menandakan kerusakan sel hati. "
                  "Sering ditemukan pada penyakit hati berlemak non-alkoholik (NAFLD/NASH).",
    "Fibrosis": "Pembentukan jaringan parut di hati akibat peradangan kronis. "
                "Dapat berkembang menjadi sirosis jika tidak ditangani.",
    "Inflammation": "Peradangan pada jaringan hati yang menunjukkan respons imun aktif. "
                    "Dapat disebabkan oleh infeksi virus, alkohol, atau penyakit autoimun.",
    "Steatosis": "Penumpukan lemak berlebih dalam sel hati (perlemakan hati). "
                 "Tahap awal penyakit hati berlemak yang umumnya reversibel.",
}

# Warna untuk setiap kelas (BGR untuk OpenCV)
CLASS_COLORS_BGR = {
    "Ballooning": (0, 100, 255),      # Oranye
    "Fibrosis": (255, 50, 50),        # Biru
    "Inflammation": (0, 0, 230),      # Merah
    "Steatosis": (0, 200, 100),       # Hijau
}

# Warna untuk setiap kelas (HEX untuk Plotly/Streamlit)
CLASS_COLORS_HEX = {
    "Ballooning": "#FF6400",
    "Fibrosis": "#3232FF",
    "Inflammation": "#E60000",
    "Steatosis": "#64C800",
}


class HybridDetector:
    """
    Pipeline hybrid untuk deteksi dan klasifikasi histopatologi liver.

    Alur:
    1. YOLOv11 mendeteksi region of interest (ROI) pada gambar
    2. Setiap ROI di-crop dan di-preprocess
    3. ResNet50 mengekstrak 2048 fitur dari setiap crop
    4. XGBoost mengklasifikasikan berdasarkan fitur ResNet50
    """

    def __init__(self, yolo_path: str, xgb_path: str, device: str = None):
        """
        Args:
            yolo_path: Path ke model YOLO (.pt)
            xgb_path: Path ke model XGBoost (.pkl)
            device: Device untuk inferensi ('cpu' atau 'cuda')
        """
        # Tentukan device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # Load YOLO model
        self.yolo_model = YOLO(yolo_path)

        # Load XGBoost model
        with open(xgb_path, "rb") as f:
            self.xgb_model = pickle.load(f)

        # Setup ResNet50 sebagai feature extractor (tanpa FC layer terakhir)
        resnet = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        # Hapus fully connected layer terakhir → output = 2048 features
        self.resnet_extractor = nn.Sequential(*list(resnet.children())[:-1])
        self.resnet_extractor = self.resnet_extractor.to(self.device)
        self.resnet_extractor.eval()

        # Transform untuk preprocessing crop sebelum masuk ResNet50
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

    def detect(self, image: Image.Image, conf_threshold: float = 0.25):
        """
        Jalankan pipeline deteksi lengkap.

        Args:
            image: Gambar input (PIL Image, RGB)
            conf_threshold: Confidence threshold untuk YOLO

        Returns:
            list of dict, setiap dict berisi:
                - 'bbox': [x1, y1, x2, y2]
                - 'yolo_class': Kelas dari YOLO
                - 'yolo_conf': Confidence YOLO
                - 'xgb_class': Kelas dari XGBoost
                - 'xgb_conf': Confidence XGBoost (probability)
                - 'crop': PIL Image crop region
                - 'features': numpy array 2048 features (opsional)
        """
        results = []

        # ==========================================
        # TAHAP 1: YOLO Object Detection
        # ==========================================
        yolo_results = self.yolo_model.predict(
            source=image,
            conf=conf_threshold,
            verbose=False,
        )

        if len(yolo_results) == 0 or yolo_results[0].boxes is None:
            return results

        boxes = yolo_results[0].boxes
        img_width, img_height = image.size

        for i in range(len(boxes)):
            # Ambil bounding box
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy().astype(int)
            yolo_conf = float(boxes.conf[i].cpu().numpy())
            yolo_cls_id = int(boxes.cls[i].cpu().numpy())

            # Pastikan bounding box valid
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(img_width, x2)
            y2 = min(img_height, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            # Dapatkan nama kelas YOLO
            yolo_class_name = self.yolo_model.names.get(yolo_cls_id, f"class_{yolo_cls_id}")

            # ==========================================
            # TAHAP 2: Crop Region
            # ==========================================
            crop = image.crop((x1, y1, x2, y2))

            # ==========================================
            # TAHAP 3: ResNet50 Feature Extraction
            # ==========================================
            features = self._extract_features(crop)

            # ==========================================
            # TAHAP 4: XGBoost Classification
            # ==========================================
            xgb_class, xgb_conf = self._classify(features)

            results.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "yolo_class": yolo_class_name,
                "yolo_conf": round(yolo_conf, 4),
                "xgb_class": xgb_class,
                "xgb_conf": round(xgb_conf, 4),
                "crop": crop,
                "features": features,
            })

        return results

    def _extract_features(self, crop: Image.Image) -> np.ndarray:
        """
        Ekstrak fitur 2048-dim dari crop menggunakan ResNet50.

        Args:
            crop: PIL Image (RGB) hasil cropping YOLO

        Returns:
            numpy array shape (2048,)
        """
        # Preprocess
        input_tensor = self.transform(crop).unsqueeze(0).to(self.device)

        # Forward pass (tanpa gradient)
        with torch.no_grad():
            features = self.resnet_extractor(input_tensor)

        # Flatten: (1, 2048, 1, 1) → (2048,)
        features = features.squeeze().cpu().numpy()

        return features

    def _classify(self, features: np.ndarray):
        """
        Klasifikasikan fitur menggunakan XGBoost.

        Args:
            features: numpy array shape (2048,)

        Returns:
            (class_name, confidence)
        """
        features_2d = features.reshape(1, -1)

        # Prediksi kelas
        pred_id = self.xgb_model.predict(features_2d)[0]

        # Prediksi probabilitas
        try:
            proba = self.xgb_model.predict_proba(features_2d)[0]
            confidence = float(proba[int(pred_id)])
        except AttributeError:
            # Jika model tidak support predict_proba
            confidence = 1.0

        # Map ID ke nama kelas
        pred_id = int(pred_id)
        if pred_id < len(CLASS_NAMES):
            class_name = CLASS_NAMES[pred_id]
        else:
            class_name = f"Unknown_{pred_id}"

        return class_name, confidence
