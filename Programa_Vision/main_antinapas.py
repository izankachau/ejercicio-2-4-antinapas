# =============================================================================
# AntiÑapas-Pons: Sistema de Seguridad Industrial - Ejercicio 2.4
# Autor  : Izan Kachau
# Fecha  : Febrero 2026
# Desc.  : Sistema de vigilancia con visión artificial (OpenCV) para detección
#          de intrusiones en zonas peligrosas con privacidad y alertas en tiempo real.
# =============================================================================

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import threading
import time
import os
import numpy as np
import winsound
import json
import csv
import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AntiNapasApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AntiÑapas-Pons | AI Precision Watcher")
        self.geometry("1200x820")

        # Estado
        self.mode = "STOP"
        self.roi_zone = None
        self.red_zones = []
        self.amber_zones = []
        self.last_status = "SAFE"
        self.grid_visible = False
        self.drawing_type = None
        self.camera_source = 0
        self.last_capture_path = None
        self.event_history = []

        # Grabación de vídeo
        self.video_writer = None
        self.is_recording = False
        self.recording_path = None
        self.recording_start_time = None
        self.MAX_RECORDING_SECONDS = 10

        # Detector de anomalías
        self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
        self.anomaly_threshold = 1200

        # Estadísticas
        self.confirmed_anomalies = 0
        self.false_alarms = 0
        self.last_intrusion_time = None  # Hora de la última intrusión real

        # Detector de caras
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        self.setup_ui()
        self.load_settings()
        self.start_camera()

    # ─────────────────────────────── UI ──────────────────────────────────────

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── SIDEBAR ──
        self.sidebar = ctk.CTkScrollableFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="AntiÑapas", font=("Orbitron", 22, "bold")).pack(pady=15)
        self._sep()

        # Modo vigilancia
        ctk.CTkLabel(self.sidebar, text="MODO VIGILANCIA", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", padx=15)
        self.mode_selector = ctk.CTkOptionMenu(
            self.sidebar, values=["AUTOMATICO", "CALIBRACION", "STOP"],
            command=self.change_mode, height=30
        )
        self.mode_selector.set("STOP")
        self.mode_selector.pack(pady=5, padx=15, fill="x")

        self.status_indicator = ctk.CTkLabel(
            self.sidebar, text="⚪ SISTEMA PARADO",
            font=("Arial", 11, "bold"), text_color="#888888"
        )
        self.status_indicator.pack(pady=3, padx=15, anchor="w")

        # Cámara
        ctk.CTkLabel(self.sidebar, text="FUENTE DE VIDEO", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", padx=15, pady=(10, 0))
        self.cam_selector = ctk.CTkComboBox(
            self.sidebar, values=["Cámara 0", "Cámara 1", "Cámara 2", "IP / URL"],
            command=self.change_camera, height=28
        )
        self.cam_selector.set("Cámara 0")
        self.cam_selector.pack(pady=5, padx=15, fill="x")

        # Rearme
        self.btn_reset = ctk.CTkButton(
            self.sidebar, text="⚡ REARME DE SEGURIDAD",
            fg_color="#27AE60", state="disabled",
            command=self.safety_reset, height=40, font=("Arial", 12, "bold")
        )
        self.btn_reset.pack(pady=10, padx=15, fill="x")
        self._sep()

        # Herramientas de dibujo
        ctk.CTkLabel(self.sidebar, text="CONFIGURAR ÁREAS", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", padx=15, pady=(5, 5))
        ctk.CTkButton(self.sidebar, text="1. DIBUJAR ROI (AZUL)", fg_color="#1F6FEB", height=32, command=lambda: self.set_tool("ROI")).pack(pady=3, padx=15, fill="x")
        ctk.CTkButton(self.sidebar, text="2. ZONA ROJA", fg_color="#C0392B", hover_color="#E74C3C", height=32, command=lambda: self.set_tool("RED")).pack(pady=3, padx=15, fill="x")
        ctk.CTkButton(self.sidebar, text="3. ZONA ÁMBAR", fg_color="#D4AC0D", height=32, text_color="black", command=lambda: self.set_tool("AMBER")).pack(pady=3, padx=15, fill="x")
        ctk.CTkButton(self.sidebar, text="🗑 Limpiar Todo", fg_color="#34495E", height=30, command=self.clear_all).pack(pady=(8, 3), padx=15, fill="x")
        ctk.CTkButton(self.sidebar, text="💾 Guardar Config", fg_color="#1F6FEB", height=30, command=self.save_settings_manual).pack(pady=3, padx=15, fill="x")
        ctk.CTkButton(self.sidebar, text="📊 Exportar CSV", fg_color="#34495E", height=30, command=self.export_report).pack(pady=3, padx=15, fill="x")
        self.grid_switch = ctk.CTkSwitch(self.sidebar, text="Guía de Alineación", command=self.toggle_grid, font=("Arial", 11))
        self.grid_switch.pack(pady=10, padx=15, anchor="w")
        self._sep()

        # ── ESTADÍSTICAS IA ──
        ctk.CTkLabel(self.sidebar, text="ESTADÍSTICAS IA", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", padx=15, pady=(5, 5))
        stats = ctk.CTkFrame(self.sidebar, fg_color="#1a1a2e", corner_radius=8)
        stats.pack(pady=5, padx=15, fill="x")

        for label, attr, color, row in [
            ("Anomalías confirmadas", "lbl_anomalies", "#E74C3C", 0),
            ("Falsas alarmas",        "lbl_false",     "#F39C12", 1),
            ("Sensibilidad actual",   "lbl_sens",      "#3498DB", 2),
        ]:
            ctk.CTkLabel(stats, text=label, font=("Arial", 9), text_color="#aaa").pack(anchor="w", padx=10, pady=(8 if row == 0 else 5, 0))
            lbl = ctk.CTkLabel(stats, text="0" if row < 2 else "1200", font=("Arial", 22, "bold"), text_color=color)
            lbl.pack(anchor="w", padx=10, pady=(0, 8 if row == 2 else 0))
            setattr(self, attr, lbl)

        # Tasa de acierto
        ctk.CTkLabel(stats, text="Tasa de acierto", font=("Arial", 9), text_color="#aaa").pack(anchor="w", padx=10, pady=(5, 0))
        self.lbl_accuracy = ctk.CTkLabel(stats, text="--", font=("Arial", 16, "bold"), text_color="#2ECC71")
        self.lbl_accuracy.pack(anchor="w", padx=10)

        # Última intrusión real
        ctk.CTkLabel(stats, text="Última intrusión real", font=("Arial", 9), text_color="#aaa").pack(anchor="w", padx=10, pady=(5, 0))
        self.lbl_last_time = ctk.CTkLabel(stats, text="Ninguna aún", font=("Arial", 11), text_color="#aaa")
        self.lbl_last_time.pack(anchor="w", padx=10, pady=(0, 8))

        # Botón Reset diario
        ctk.CTkButton(
            self.sidebar, text="🔄 Reset Estadísticas del Día",
            fg_color="#6C3483", hover_color="#8E44AD", height=32,
            command=self.reset_daily_stats
        ).pack(pady=8, padx=15, fill="x")

        self._sep()

        # Última intrusión
        ctk.CTkLabel(self.sidebar, text="ÚLTIMA INTRUSIÓN", font=("Arial", 10, "bold"), text_color="#888").pack(anchor="w", padx=15, pady=(5, 5))
        self.last_capture_label = ctk.CTkLabel(self.sidebar, text="Sistema OK", fg_color="#0d1117", height=120, corner_radius=8)
        self.last_capture_label.pack(pady=5, padx=15, fill="x")
        self.lbl_rec_status = ctk.CTkLabel(self.sidebar, text="", font=("Arial", 9), text_color="#E74C3C")
        self.lbl_rec_status.pack(padx=15, anchor="w")

        # ── ÁREA PRINCIPAL ──
        self.main_content = ctk.CTkFrame(self, corner_radius=12, fg_color="#0D1117")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.main_content, bg="#000", highlightthickness=0, cursor="cross")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.console = ctk.CTkTextbox(self.main_content, height=100, font=("Consolas", 10), fg_color="#161B22")
        self.console.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.video_bg_id = self.canvas.create_image(0, 0, anchor="nw", tags="bg_video")
        self.rect_id = self.start_x = self.start_y = None

    def _sep(self):
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2d2d2d").pack(fill="x", padx=15, pady=6)

    # ─────────────────────────────── CÁMARA ──────────────────────────────────

    def start_camera(self):
        self.cap = cv2.VideoCapture(self.camera_source)
        self.video_running = True
        threading.Thread(target=self.update_video, daemon=True).start()

    def update_video(self):
        while self.video_running:
            ret, frame = self.cap.read()
            if not ret:
                continue
            frame = cv2.resize(frame, (860, 484))

            # Privacidad: cara de chimpancé
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 6, minSize=(60, 60))
            for (x, y, w, h) in faces:
                self.apply_chimp_face(frame, x, y, w, h)

            # Lógica de seguridad
            current_status, rects = "SAFE", []
            if self.mode == "AUTOMATICO":
                current_status, rects = self.process_security(frame)
            elif self.mode == "CALIBRACION":
                self.back_sub.apply(frame)
            else:
                self.back_sub.apply(frame, learningRate=0.005)

            self.handle_security_logic(current_status, frame)

            # Grabación de vídeo
            if self.is_recording and self.video_writer:
                if time.time() - self.recording_start_time <= self.MAX_RECORDING_SECONDS:
                    self.video_writer.write(frame)
                else:
                    self.stop_recording()

            # ── HUD sobre el frame ──
            if self.grid_visible:
                for x in range(0, 860, 50):
                    cv2.line(frame, (x, 0), (x, 484), (40, 40, 40), 1)
                for y in range(0, 484, 50):
                    cv2.line(frame, (0, y), (860, y), (40, 40, 40), 1)

            if self.roi_zone:
                cv2.rectangle(frame, (self.roi_zone[0], self.roi_zone[1]), (self.roi_zone[2], self.roi_zone[3]), (255, 120, 0), 2)
            for rx, ry, rw, rh in rects:
                cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
                cv2.putText(frame, "MOTION", (rx, ry - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            for z in self.amber_zones:
                cv2.rectangle(frame, (z[0], z[1]), (z[2], z[3]), (0, 165, 255), 2)
            for z in self.red_zones:
                cv2.rectangle(frame, (z[0], z[1]), (z[2], z[3]), (0, 0, 255), 2)

            # Timestamp en esquina superior derecha
            ts = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
            cv2.putText(frame, ts, (860 - 230, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)

            # Indicador de modo
            mode_color = {"AUTOMATICO": (0, 200, 0), "CALIBRACION": (0, 165, 255), "STOP": (100, 100, 100), "EMERGENCIA": (0, 0, 255)}.get(self.mode, (100, 100, 100))
            cv2.putText(frame, f"  {self.mode}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, mode_color, 2, cv2.LINE_AA)

            if self.is_recording:
                cv2.putText(frame, "REC", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))
            self.after(0, self.draw_frame)
            time.sleep(0.01)

    def draw_frame(self):
        self.canvas.itemconfig(self.video_bg_id, image=self.photo)
        self.canvas.tag_lower("bg_video")
        if self.last_status == "DANGER" or self.mode == "EMERGENCIA":
            self.canvas.delete("danger_overlay")
            self.canvas.create_rectangle(0, 0, 860, 484, fill="red", stipple="gray25", tags="danger_overlay")
        else:
            self.canvas.delete("danger_overlay")

    # ─────────────────────────────── SEGURIDAD ───────────────────────────────

    def process_security(self, frame):
        fg_mask = self.back_sub.apply(frame)
        _, fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rects, final_status = [], "SAFE"

        if self.roi_zone:
            rx1, ry1, rx2, ry2 = self.roi_zone
            for cnt in contours:
                if cv2.contourArea(cnt) > 500:
                    mx, my, mw, mh = cv2.boundingRect(cnt)
                    if rx1 < mx + mw / 2 < rx2 and ry1 < my + mh / 2 < ry2:
                        rects.append((mx, my, mw, mh))
                        for z in self.red_zones:
                            if self.intersect((mx, my, mx + mw, my + mh), z):
                                return "DANGER", rects
                        for z in self.amber_zones:
                            if self.intersect((mx, my, mx + mw, my + mh), z):
                                final_status = "WARNING"
        return final_status, rects

    def intersect(self, r1, r2):
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    def handle_security_logic(self, status, frame):
        if self.mode != "AUTOMATICO":
            return
        if status == "DANGER":
            self.mode = "EMERGENCIA"
            self.mode_selector.set("STOP")
            self.mode_selector.configure(state="disabled")
            self.btn_reset.configure(state="normal", fg_color="#E74C3C")
            self.after(0, lambda: self.status_indicator.configure(text="🔴 EMERGENCIA ACTIVA", text_color="#E74C3C"))
            self.trigger_recording(frame)
            self.play_siren("EMERGENCY")
            self.log_event("!!! INTRUSIÓN CRÍTICA - SISTEMA BLOQUEADO !!!")
            self.after(500, self.ask_feedback)
        elif status == "WARNING" and self.last_status != "WARNING":
            self.play_siren("WARNING")
            self.log_event("⚠ Alerta: Movimiento en zona ÁMBAR")
            self.after(0, lambda: self.status_indicator.configure(text="🟡 ALERTA - ZONA ÁMBAR", text_color="#F39C12"))
        elif status == "SAFE" and self.last_status != "SAFE":
            self.after(0, lambda: self.status_indicator.configure(text="🟢 VIGILANDO", text_color="#27AE60"))
        self.last_status = status

    def ask_feedback(self):
        respuesta = messagebox.askyesno(
            "Confirmación de IA",
            "Se ha detectado una intrusión y el sistema se ha bloqueado.\n\n"
            "¿Es esto una anomalía REAL?\n\n"
            "(Si seleccionas NO, el sistema aprenderá que este nivel de movimiento es tolerable)"
        )
        if respuesta:
            self.confirmed_anomalies += 1
            self.last_intrusion_time = datetime.datetime.now().strftime("%H:%M:%S del %d/%m/%Y")
            self.log_event(f"✔ Anomalía confirmada (Total: {self.confirmed_anomalies})")
        else:
            self.false_alarms += 1
            for path in [self.last_capture_path, self.recording_path]:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            old = self.anomaly_threshold
            self.anomaly_threshold = int(self.anomaly_threshold * 1.15)
            self.log_event(f"🧠 Aprendizaje: umbral {old} → {self.anomaly_threshold}")
            messagebox.showinfo("IA Actualizada", "Entendido. He ajustado mi sensibilidad.")

        self.event_history.append([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"Intrusión - {'Confirmada' if respuesta else 'Falsa alarma'}"
        ])
        self.update_stats_display()
        self.save_settings()

    def update_stats_display(self):
        self.lbl_anomalies.configure(text=str(self.confirmed_anomalies))
        self.lbl_false.configure(text=str(self.false_alarms))
        self.lbl_sens.configure(text=str(self.anomaly_threshold))
        # Tasa de acierto
        total = self.confirmed_anomalies + self.false_alarms
        if total > 0:
            pct = int((self.confirmed_anomalies / total) * 100)
            color = "#2ECC71" if pct >= 80 else "#F39C12" if pct >= 50 else "#E74C3C"
            self.lbl_accuracy.configure(text=f"{pct}%", text_color=color)
        else:
            self.lbl_accuracy.configure(text="--", text_color="#aaa")
        # Última intrusión real
        if self.last_intrusion_time:
            self.lbl_last_time.configure(text=self.last_intrusion_time, text_color="#E74C3C")

    def reset_daily_stats(self):
        """Resetea solo los contadores del día. NO toca sensibilidad ni zonas."""
        confirm = messagebox.askyesno(
            "Resetear estadísticas",
            "¿Resetear los contadores de anomalías y falsas alarmas?\n\n"
            "(La sensibilidad aprendida y las zonas NO se modifican)"
        )
        if confirm:
            self.confirmed_anomalies = 0
            self.false_alarms = 0
            self.last_intrusion_time = None
            self.update_stats_display()
            self.lbl_last_time.configure(text="Ninguna aún", text_color="#aaa")
            self.save_settings()
            self.log_event("🔄 Estadísticas del día reseteadas. Sensibilidad y zonas intactas.")

    def safety_reset(self):
        self.mode = "AUTOMATICO"
        self.last_status = "SAFE"
        self.mode_selector.configure(state="normal")
        self.mode_selector.set("AUTOMATICO")
        self.btn_reset.configure(state="disabled", fg_color="#27AE60")
        self.status_indicator.configure(text="🟢 VIGILANDO", text_color="#27AE60")
        self.log_event("✅ Rearme completado. Sistema en modo AUTOMÁTICO.")
        messagebox.showinfo("Rearme", "Seguridad rearmada. Sistema activo en modo AUTOMÁTICO.")

    # ─────────────────────────── GRABACIÓN / AUDIO ───────────────────────────

    def trigger_recording(self, frame):
        timestamp = int(time.time())
        if not os.path.exists("captures"):
            os.makedirs("captures")

        # Foto de captura
        self.last_capture_path = f"captures/EMERGENCIA_{timestamp}.jpg"
        cv2.imwrite(self.last_capture_path, frame)

        # Grabación de vídeo (10 s)
        self.recording_path = f"captures/GRABACION_{timestamp}.avi"
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        self.video_writer = cv2.VideoWriter(self.recording_path, fourcc, 20.0, (860, 484))
        self.is_recording = True
        self.recording_start_time = time.time()
        self.after(0, lambda: self.lbl_rec_status.configure(text="⬤ Grabando emergencia..."))

        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((200, 112))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 112))
        self.last_capture_label.configure(image=ctk_img, text="")
        self.log_event(f"📸 Foto: {self.last_capture_path}")
        self.log_event(f"🎥 Grabando vídeo: {self.recording_path}")

    def stop_recording(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        self.is_recording = False
        self.after(0, lambda: self.lbl_rec_status.configure(text="✅ Grabación finalizada"))
        self.log_event(f"🎥 Vídeo guardado: {self.recording_path}")

    def play_siren(self, siren_type):
        """Sirena realista con patrón ascendente/descendente."""
        def _emergency():
            for _ in range(3):
                for freq in range(600, 1400, 40):
                    winsound.Beep(freq, 25)
                for freq in range(1400, 600, -40):
                    winsound.Beep(freq, 25)

        def _warning():
            winsound.Beep(800, 250)
            time.sleep(0.05)
            winsound.Beep(600, 250)

        threading.Thread(target=_emergency if siren_type == "EMERGENCY" else _warning, daemon=True).start()

    # ─────────────────────────────── CONFIG ──────────────────────────────────

    def save_settings(self):
        settings = {
            "threshold": self.anomaly_threshold,
            "roi": self.roi_zone,
            "red_zones": self.red_zones,
            "amber_zones": self.amber_zones,
            "confirmed_anomalies": self.confirmed_anomalies,
            "false_alarms": self.false_alarms,
        }
        if not os.path.exists("logs"):
            os.makedirs("logs")
        with open("logs/factory_settings.json", "w") as f:
            json.dump(settings, f, indent=2)

    def save_settings_manual(self):
        self.save_settings()
        self.log_event("💾 Configuración guardada.")

    def load_settings(self):
        path = "logs/factory_settings.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    d = json.load(f)
                self.anomaly_threshold = d.get("threshold", 1200)
                self.roi_zone = d.get("roi")
                self.red_zones = d.get("red_zones", [])
                self.amber_zones = d.get("amber_zones", [])
                self.confirmed_anomalies = d.get("confirmed_anomalies", 0)
                self.false_alarms = d.get("false_alarms", 0)
                self.log_event(f"⚙ Config cargada: umbral={self.anomaly_threshold}, anomalías={self.confirmed_anomalies}, falsas={self.false_alarms}")
                self.after(150, self.update_stats_display)
            except Exception as e:
                self.log_event(f"Error al cargar ajustes: {e}")

    # ─────────────────────────── HERRAMIENTAS ────────────────────────────────

    def apply_chimp_face(self, frame, x, y, w, h):
        s_w, s_h = int(w * 0.75), int(h * 0.75)
        cx, cy = x + w // 2, y + h // 2
        cv2.ellipse(frame, (cx, cy), (s_w // 2, int(s_h // 1.6)), 0, 0, 360, (42, 72, 122), -1)
        cv2.circle(frame, (cx - s_w // 2, cy), s_w // 6, (42, 72, 122), -1)
        cv2.circle(frame, (cx + s_w // 2, cy), s_w // 6, (42, 72, 122), -1)
        cv2.ellipse(frame, (cx, cy + int(s_h // 5)), (int(s_w // 2.6), int(s_h // 4)), 0, 0, 360, (140, 180, 210), -1)
        cv2.circle(frame, (cx - s_w // 6, cy), 2, (0, 0, 0), -1)
        cv2.circle(frame, (cx + s_w // 6, cy), 2, (0, 0, 0), -1)
        cv2.ellipse(frame, (cx, cy + int(s_h // 4)), (int(s_w // 6), int(s_h // 15)), 0, 0, 180, (0, 0, 0), 1)

    def set_tool(self, tool):
        self.drawing_type = tool
        self.log_event(f"🖊 Herramienta: Zona {tool}")

    def change_camera(self, choice):
        if choice == "IP / URL":
            url = simpledialog.askstring("Cámara IP", "Introduce la URL (rtsp://...):")
            if url:
                self.camera_source = url
        else:
            self.camera_source = int(choice.split()[-1])
        self.video_running = False
        time.sleep(0.3)
        self.cap.release()
        self.start_camera()
        self.log_event(f"📷 Fuente: {self.camera_source}")

    def on_press(self, event):
        if self.drawing_type and self.mode == "STOP":
            self.start_x, self.start_y = event.x, event.y
            color_map = {"RED": "#E74C3C", "AMBER": "#F1C40F", "ROI": "#1F6FEB"}
            self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline=color_map[self.drawing_type], width=2, dash=(4, 4), tags="temp_rect"
            )

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if not self.rect_id:
            return
        x1, x2 = sorted([self.start_x, event.x])
        y1, y2 = sorted([self.start_y, event.y])
        if (x2 - x1) > 10 and (y2 - y1) > 10:
            is_valid = True
            if self.drawing_type in ["RED", "AMBER"]:
                if not self.roi_zone:
                    messagebox.showwarning("Falta ROI", "Primero dibuja el ROI (Zona Azul).")
                    is_valid = False
                else:
                    rx1, ry1, rx2, ry2 = self.roi_zone
                    if not (x1 >= rx1 and y1 >= ry1 and x2 <= rx2 and y2 <= ry2):
                        messagebox.showwarning("Fuera de ROI", "La zona debe estar dentro del ROI.")
                        is_valid = False
            if is_valid:
                if self.drawing_type == "RED":
                    self.red_zones.append((x1, y1, x2, y2))
                elif self.drawing_type == "AMBER":
                    self.amber_zones.append((x1, y1, x2, y2))
                elif self.drawing_type == "ROI":
                    self.roi_zone = (x1, y1, x2, y2)
                    self.red_zones, self.amber_zones = [], []
                    self.canvas.delete("fixed_zone")
                    self.log_event("Nuevo ROI. Zonas anteriores eliminadas.")
                color_map = {"RED": "#C0392B", "AMBER": "#D4AC0D", "ROI": "#1F6FEB"}
                self.canvas.create_rectangle(x1, y1, x2, y2, outline=color_map[self.drawing_type], width=2, tags="fixed_zone")
                self.log_event(f"✅ Zona {self.drawing_type} creada.")
                self.save_settings()
        self.canvas.delete("temp_rect")
        self.rect_id = self.drawing_type = None

    def toggle_grid(self):
        self.grid_visible = not self.grid_visible

    def change_mode(self, mode):
        self.mode = mode
        colors = {"AUTOMATICO": ("🟢 VIGILANDO", "#27AE60"), "CALIBRACION": ("🔵 CALIBRANDO", "#3498DB"), "STOP": ("⚪ SISTEMA PARADO", "#888888")}
        text, color = colors.get(mode, ("⚪ SISTEMA PARADO", "#888888"))
        self.status_indicator.configure(text=text, text_color=color)
        if mode == "CALIBRACION":
            self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
            self.log_event("📷 Calibrando fondo... (mantén la escena vacía 10s)")
        self.log_event(f"Sistema → {mode}")

    def log_event(self, msg):
        ts = time.strftime('%H:%M:%S')
        self.console.insert("end", f"[{ts}] {msg}\n")
        self.console.see("end")
        self.event_history.append([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg])

    def export_report(self):
        if not self.event_history:
            messagebox.showwarning("Informe", "No hay eventos para exportar.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"Informe_AntiNapas_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if file_path:
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                    csv.writer(f).writerows([["Fecha y Hora", "Evento"]] + self.event_history)
                messagebox.showinfo("Éxito", f"Informe exportado:\n{file_path}")
                self.log_event(f"📊 Informe exportado.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def clear_all(self):
        self.red_zones, self.amber_zones, self.roi_zone = [], [], None
        self.canvas.delete("fixed_zone")
        self.save_settings()
        self.log_event("🗑 Todas las zonas eliminadas.")

    def on_closing(self):
        self.video_running = False
        if self.is_recording:
            self.stop_recording()
        time.sleep(0.3)
        if hasattr(self, 'cap'):
            self.cap.release()
        self.save_settings()
        self.destroy()


if __name__ == "__main__":
    app = AntiNapasApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
