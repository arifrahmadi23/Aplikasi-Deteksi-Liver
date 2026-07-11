"""
Utility functions untuk visualisasi dan preprocessing
Aplikasi Deteksi Histopatologi Liver
"""

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from pipeline import CLASS_COLORS_BGR, CLASS_COLORS_HEX, CLASS_NAMES


def draw_detections(image: Image.Image, detections: list, use_xgb_label: bool = True,
                    line_thickness: int = 2, font_scale: float = 0.6) -> Image.Image:
    """
    Gambar bounding box dan label pada gambar.

    Args:
        image: PIL Image (RGB)
        detections: List hasil dari HybridDetector.detect()
        use_xgb_label: Gunakan label XGBoost (True) atau YOLO (False)
        line_thickness: Ketebalan garis bbox
        font_scale: Skala font label

    Returns:
        PIL Image dengan annotasi
    """
    # Konversi PIL → OpenCV (RGB → BGR)
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]

        if use_xgb_label:
            label = det["xgb_class"]
            conf = det["xgb_conf"]
        else:
            label = det["yolo_class"]
            conf = det["yolo_conf"]

        # Warna berdasarkan kelas
        color = CLASS_COLORS_BGR.get(label, (200, 200, 200))

        # Gambar bounding box
        cv2.rectangle(img_cv, (x1, y1), (x2, y2), color, line_thickness)

        # Label text
        text = f"{label} {conf:.0%}"
        (text_w, text_h), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1
        )

        # Background untuk label
        cv2.rectangle(
            img_cv,
            (x1, y1 - text_h - baseline - 6),
            (x1 + text_w + 6, y1),
            color,
            -1  # filled
        )

        # Text label (putih)
        cv2.putText(
            img_cv, text,
            (x1 + 3, y1 - baseline - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    # Konversi kembali ke PIL (BGR → RGB)
    img_result = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
    return img_result


def create_results_dataframe(detections: list) -> pd.DataFrame:
    """
    Buat DataFrame dari hasil deteksi untuk ditampilkan di tabel.

    Args:
        detections: List hasil dari HybridDetector.detect()

    Returns:
        pandas DataFrame
    """
    if not detections:
        return pd.DataFrame()

    rows = []
    for i, det in enumerate(detections, 1):
        x1, y1, x2, y2 = det["bbox"]
        rows.append({
            "No.": i,
            "Kelas (YOLO)": det["yolo_class"],
            "Confidence YOLO": f"{det['yolo_conf']:.2%}",
            "Kelas (XGBoost)": det["xgb_class"],
            "Confidence XGBoost": f"{det['xgb_conf']:.2%}",
            "Lokasi (x1,y1)": f"({x1}, {y1})",
            "Lokasi (x2,y2)": f"({x2}, {y2})",
            "Ukuran (px)": f"{x2 - x1} × {y2 - y1}",
        })

    return pd.DataFrame(rows)


def get_class_distribution(detections: list, use_xgb: bool = True) -> dict:
    """
    Hitung distribusi kelas dari deteksi.

    Args:
        detections: List hasil deteksi
        use_xgb: Gunakan label XGBoost (True) atau YOLO (False)

    Returns:
        dict {class_name: count}
    """
    distribution = {name: 0 for name in CLASS_NAMES}
    key = "xgb_class" if use_xgb else "yolo_class"

    for det in detections:
        cls_name = det[key]
        if cls_name in distribution:
            distribution[cls_name] += 1
        else:
            distribution[cls_name] = 1

    return distribution


def calculate_summary_metrics(detections: list) -> dict:
    """
    Hitung metrik ringkasan dari hasil deteksi.

    Returns:
        dict dengan metrik seperti total deteksi, rata-rata confidence, dll
    """
    if not detections:
        return {
            "total_deteksi": 0,
            "rata_conf_yolo": 0.0,
            "rata_conf_xgb": 0.0,
            "kelas_dominan": "-",
            "agreement_rate": 0.0,
        }

    total = len(detections)
    avg_yolo_conf = np.mean([d["yolo_conf"] for d in detections])
    avg_xgb_conf = np.mean([d["xgb_conf"] for d in detections])

    # Kelas dominan (dari XGBoost)
    dist = get_class_distribution(detections, use_xgb=True)
    dominant_class = max(dist, key=dist.get) if any(v > 0 for v in dist.values()) else "-"

    # Agreement rate antara YOLO dan XGBoost
    agreements = sum(
        1 for d in detections
        if d["yolo_class"].lower() == d["xgb_class"].lower()
    )
    agreement_rate = agreements / total if total > 0 else 0.0

    return {
        "total_deteksi": total,
        "rata_conf_yolo": round(avg_yolo_conf, 4),
        "rata_conf_xgb": round(avg_xgb_conf, 4),
        "kelas_dominan": dominant_class,
        "agreement_rate": round(agreement_rate, 4),
    }
