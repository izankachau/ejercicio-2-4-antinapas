import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import os

class AntiNapasVision:
    def __init__(self):
        # Intentar usar la nueva API de Tasks (más compatible con 3.14/lite)
        try:
            # Necesitamos un modelo .task. Por ahora usamos un detector simple o fallback
            self.use_tasks = False
            if hasattr(mp, 'solutions'):
                self.mp_pose = mp.solutions.pose
                self.pose = self.mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5)
                self.mp_draw = mp.solutions.drawing_utils
                self.use_tasks = False
            else:
                # Si no hay soluciones, intentamos configurar el landmarker (necesita archivo)
                # Como no tenemos el archivo .task a mano, usaremos un detector de personas de OpenCV como fallback
                # o intentaremos importar solutions forzadamente si es un error de path
                self.use_fallback = True
                self.hog = cv2.HOGDescriptor()
                self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception as e:
            print(f"Error inicializando Vision: {e}")
            self.use_fallback = True
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    def process_frame(self, frame, zones=[]):
        h, w, _ = frame.shape
        status = "SAFE"
        detected_points = []

        # 1. Detección de personas
        if not hasattr(self, 'use_fallback') or not self.use_fallback:
            # Usar Mediapipe Solutions (si está disponible)
            results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if results.pose_landmarks:
                mid_hip_x = (results.pose_landmarks.landmark[23].x + results.pose_landmarks.landmark[24].x) / 2 * w
                mid_hip_y = (results.pose_landmarks.landmark[23].y + results.pose_landmarks.landmark[24].y) / 2 * h
                detected_points.append((mid_hip_x, mid_hip_y))
        else:
            # Fallback a OpenCV HOG (Detector de personas estándar)
            # Esto asegura que el código ARRANQUE aunque mediapipe esté capado
            rects, weights = self.hog.detectMultiScale(frame, winStride=(8, 8), padding=(32, 32), scale=1.05)
            for (x, y, w_p, h_p) in rects:
                detected_points.append((x + w_p/2, y + h_p/2))

        # 2. Verificación de Zonas
        for px, py in detected_points:
            for zone in zones:
                poly = np.array(zone['points'], np.int32)
                is_inside = cv2.pointPolygonTest(poly, (px, py), False) >= 0
                
                if is_inside:
                    if zone['type'] == 'RED': status = "DANGER"
                    elif zone['type'] == 'AMBER' and status != "DANGER": status = "WARNING"

        # 3. Anonimización
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
        for (x, y, w_f, h_f) in faces:
            face_zone = frame[y:y+h_f, x:x+w_f]
            face_zone = cv2.GaussianBlur(face_zone, (49, 49), 30)
            frame[y:y+h_f, x:x+w_f] = face_zone

        # 4. Dibujar Zonas
        for zone in zones:
            color = (0, 0, 255) if zone['type'] == 'RED' else (0, 255, 255)
            poly = np.array(zone['points'], np.int32)
            cv2.polylines(frame, [poly], True, color, 2)
            
        return frame, status

if __name__ == "__main__":
    # Test simple con webcam
    cap = cv2.VideoCapture(0)
    vision = AntiNapasVision()
    # Zona de test fija (un cuadrado en medio)
    test_zones = [{'type': 'RED', 'points': [(100,100), (400,100), (400,400), (100,400)]}]
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        proc_frame, status = vision.process_frame(frame, test_zones)
        cv2.putText(proc_frame, f"STATUS: {status}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0) if status == "SAFE" else (0,0,255), 3)
        
        cv2.imshow("AntiNapas-Pons Eagle Eye", proc_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
        
    cap.release()
    cv2.destroyAllWindows()
