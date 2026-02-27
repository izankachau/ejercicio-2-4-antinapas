import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import cv2
import threading
import time
import os
import numpy as np
import winsound
import json

# Configuración de estilo
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AntiNapasApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AntiÑapas-Pons | AI Precision Watcher")
        self.geometry("1100x800")

        # Variables de estado
        self.mode = "STOP" 
        self.roi_zone = None # (x1, y1, x2, y2) en color azul
        self.red_zones = [] # [(x1, y1, x2, y2), ...]
        self.amber_zones = []
        self.last_status = "SAFE"
        self.grid_visible = False
        self.drawing_type = None # "ROI", "RED" or "AMBER"
        self.camera_source = 0 # Por defecto webcam 0
        self.last_capture_path = None # Ruta de la última foto tomada
        
        # Detector de Anomalías (Fondo sustraído)
        self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
        self.anomaly_threshold = 1200 # Umbral de sensibilidad inicial
        self.confirmed_anomalies = 0
        self.false_alarms = 0
        
        # Detector de Caras
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        self.setup_ui()
        # Cargar configuración tras inicializar la UI (consola)
        self.load_settings()
        self.start_camera()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Barra lateral Compacta
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        ctk.CTkLabel(self.sidebar, text="AntiÑapas", font=("Orbitron", 22, "bold")).pack(pady=20)

        # Control
        ctk.CTkLabel(self.sidebar, text="MODO VIGILANCIA", font=("Arial", 10, "bold")).pack(anchor="w", padx=15)
        self.mode_selector = ctk.CTkOptionMenu(self.sidebar, values=["AUTOMATICO", "CALIBRACION", "STOP"], 
                                               command=self.change_mode, height=30)
        self.mode_selector.set("STOP")
        self.mode_selector.pack(pady=5, padx=15, fill="x")

        # Selector de Cámara
        ctk.CTkLabel(self.sidebar, text="FUENTE DE VIDEO", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(10, 0))
        self.cam_selector = ctk.CTkComboBox(self.sidebar, values=["Cámara 0", "Cámara 1", "Cámara 2", "IP / URL"], 
                                            command=self.change_camera, height=28)
        self.cam_selector.set("Cámara 0")
        self.cam_selector.pack(pady=5, padx=15, fill="x")

        # Botón de Rearme (Inicialmente deshabilitado)
        self.btn_reset = ctk.CTkButton(self.sidebar, text="REARME DE SEGURIDAD", fg_color="#27AE60", state="disabled", 
                                       command=self.safety_reset, height=40, font=("Arial", 13, "bold"))
        self.btn_reset.pack(pady=10, padx=15, fill="x")

        # Herramientas de Dibujo
        ctk.CTkLabel(self.sidebar, text="CONFIGURAR ÁREAS", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(20, 5))
        
        self.btn_roi = ctk.CTkButton(self.sidebar, text="1. DIBUJAR ROI (AZUL)", fg_color="#1F6FEB", height=32, command=lambda: self.set_tool("ROI"))
        self.btn_roi.pack(pady=4, padx=15, fill="x")

        self.btn_red = ctk.CTkButton(self.sidebar, text="2. ZONA ROJA", fg_color="#C0392B", hover_color="#E74C3C", height=32, command=lambda: self.set_tool("RED"))
        self.btn_red.pack(pady=4, padx=15, fill="x")
        
        self.btn_amber = ctk.CTkButton(self.sidebar, text="3. ZONA ÁMBAR", fg_color="#D4AC0D", height=32, text_color="black", command=lambda: self.set_tool("AMBER"))
        self.btn_amber.pack(pady=4, padx=15, fill="x")

        ctk.CTkButton(self.sidebar, text="Limpiar Todo", fg_color="#34495E", height=30, command=self.clear_all).pack(pady=(15, 5), padx=15, fill="x")
        
        ctk.CTkButton(self.sidebar, text="EXPORTAR INFORME CSV", fg_color="#1F6FEB", height=35, command=self.export_report).pack(pady=10, padx=15, fill="x")
        
        self.grid_switch = ctk.CTkSwitch(self.sidebar, text="Guía de Alineación", command=self.toggle_grid, font=("Arial", 11))
        self.grid_switch.pack(pady=10, padx=15, anchor="w")

        # Monitor de Alerta
        ctk.CTkLabel(self.sidebar, text="ÚLTIMA INTRUSIÓN", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        self.last_capture_label = ctk.CTkLabel(self.sidebar, text="Sistema OK", fg_color="#1a1a1a", height=120, corner_radius=10)
        self.last_capture_label.pack(pady=5, padx=15, fill="x")

        # Área Principal
        self.main_content = ctk.CTkFrame(self, corner_radius=12, fg_color="#0D1117")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.main_content.grid_rowconfigure(0, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.main_content, bg="#000", highlightthickness=0, cursor="cross")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.console = ctk.CTkTextbox(self.main_content, height=100, font=("Consolas", 10), fg_color="#161B22")
        self.console.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        # Eventos de Ratón (Pull & Drag)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        self.video_bg_id = self.canvas.create_image(0, 0, anchor="nw", tags="bg_video")
        self.rect_id = None
        self.start_x = None
        self.start_y = None

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        self.video_running = True
        self.video_thread = threading.Thread(target=self.update_video, daemon=True)
        self.video_thread.start()

    def apply_chimp_face(self, frame, x, y, w, h):
        # Reducimos un poco el tamaño total para que no sea tan invasivo
        s_w = int(w * 0.75)
        s_h = int(h * 0.75)
        cx, cy = x + w // 2, y + h // 2
        
        # Cara base (marrón oscuro chimpancé)
        cv2.ellipse(frame, (cx, cy), (s_w // 2, int(s_h // 1.6)), 0, 0, 360, (42, 72, 122), -1)
        # Orejas (más pequeñas y mejor posicionadas)
        cv2.circle(frame, (cx - s_w // 2, cy), s_w // 6, (42, 72, 122), -1)
        cv2.circle(frame, (cx + s_w // 2, cy), s_w // 6, (42, 72, 122), -1)
        # Hocico (color piel clara)
        cv2.ellipse(frame, (cx, cy + int(s_h // 5)), (int(s_w // 2.6), int(s_h // 4)), 0, 0, 360, (140, 180, 210), -1)
        # Ojos (puntos minimalistas)
        cv2.circle(frame, (cx - s_w // 6, cy), 2, (0, 0, 0), -1)
        cv2.circle(frame, (cx + s_w // 6, cy), 2, (0, 0, 0), -1)
        # Sonrisa pequeña
        cv2.ellipse(frame, (cx, cy + int(s_h // 4)), (int(s_w // 6), int(s_h // 15)), 0, 0, 180, (0, 0, 0), 1)

    def update_video(self):
        while self.video_running:
            ret, frame = self.cap.read()
            if not ret: continue

            frame = cv2.resize(frame, (860, 484))
            
            # 1. Detección de Caras (Más estricta para evitar que el mono parpadee o sea gigante)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.2, 6, minSize=(60, 60))
            for (x, y, w, h) in faces:
                self.apply_chimp_face(frame, x, y, w, h)
            
            # 2. Lógica de Seguridad (ROI / Anomalías)
            current_status = "SAFE"
            rects = []
            if self.mode == "AUTOMATICO":
                current_status, rects = self.process_security(frame)
            elif self.mode == "CALIBRACION":
                self.back_sub.apply(frame) # Aprender fondo habitual
            else:
                self.back_sub.apply(frame, learningRate=0.005)
            
            self.handle_security_logic(current_status, frame)

            # 3. Dibujar Zonas y Seguimiento
            if self.roi_zone:
                cv2.rectangle(frame, (self.roi_zone[0], self.roi_zone[1]), (self.roi_zone[2], self.roi_zone[3]), (255, 0, 0), 2)
            
            # Dibujar recuadros verdes de movimiento
            for (rx, ry, rw, rh) in rects:
                cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
                cv2.putText(frame, "MOTION", (rx, ry-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

            for z in self.amber_zones:
                cv2.rectangle(frame, (z[0], z[1]), (z[2], z[3]), (0, 165, 255), 2)
            for z in self.red_zones:
                cv2.rectangle(frame, (z[0], z[1]), (z[2], z[3]), (0, 0, 255), 2)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))

            self.after(0, self.draw_frame)
            time.sleep(0.01)

    def draw_frame(self):
        self.canvas.itemconfig(self.video_bg_id, image=self.photo)
        self.canvas.tag_lower("bg_video")
        
        if self.last_status == "DANGER":
            self.canvas.delete("danger_overlay")
            self.canvas.create_rectangle(0, 0, 860, 484, fill="red", stipple="gray25", tags="danger_overlay")
        else:
            self.canvas.delete("danger_overlay")

    def process_security(self, frame):
        # Sustracción de fondo
        fg_mask = self.back_sub.apply(frame)
        _, fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
        
        # Encontrar contornos de movimiento
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rects = []
        final_status = "SAFE"
        
        # Filtrar movimiento dentro de la ROI
        if self.roi_zone:
            rx1, ry1, rx2, ry2 = self.roi_zone
            for cnt in contours:
                if cv2.contourArea(cnt) > 500: # Ignorar ruidos muy pequeños
                    mx, my, mw, mh = cv2.boundingRect(cnt)
                    # Solo añadir si el centro del movimiento está en la ROI
                    if rx1 < mx + mw/2 < rx2 and ry1 < my + mh/2 < ry2:
                        rects.append((mx, my, mw, mh))
                        
                        # Verificar si el movimiento toca zonas críticas
                        for z in self.red_zones:
                            if self.intersect((mx,my,mx+mw,my+mh), z):
                                return "DANGER", rects
                        
                        for z in self.amber_zones:
                            if self.intersect((mx,my,mx+mw,my+mh), z):
                                final_status = "WARNING"
                
        return final_status, rects

    def intersect(self, r1, r2):
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    def handle_security_logic(self, status, frame):
        if self.mode != "AUTOMATICO": return

        if status == "DANGER":
            self.mode = "EMERGENCIA"
            self.mode_selector.set("STOP")
            self.mode_selector.configure(state="disabled") # Bloquear selección de modo
            self.btn_reset.configure(state="normal", fg_color="#27AE60") # Habilitar rearme
            
            self.trigger_photo(frame)
            self.play_sound("EMERGENCY")
            self.log_event("!!! INTRUSIÓN CRÍTICA - SISTEMA BLOQUEADO !!!")
            # Preguntar al usuario para aprendizaje
            self.after(500, self.ask_feedback)
        elif status == "WARNING" and self.last_status != "WARNING":
            self.play_sound("WARNING")
            self.log_event("Alerta: Movimiento detectado en zona ÁMBAR")
            
        self.last_status = status

    def ask_feedback(self):
        # Mostrar diálogo de confirmación
        respuesta = tk.messagebox.askyesno("Confirmación de IA", 
            "Se ha detectado una intrusión y se ha parado el sistema.\n\n"
            "¿Es esto una anomalía REAL?\n\n"
            "(Si seleccionas NO, el sistema aprenderá que este nivel de movimiento es tolerable)")
        
        if respuesta: # SI es anomalía
            self.confirmed_anomalies += 1
            self.log_event(f"Feedback: Anomalía confirmada. Foto guardada en captures/")
        else: # NO es anomalía (Falsa alarma)
            self.false_alarms += 1
            # Eliminar la foto si no es una alarma real
            if self.last_capture_path and os.path.exists(self.last_capture_path):
                try:
                    os.remove(self.last_capture_path)
                    self.log_event("Limpieza: Foto descartada eliminada de captures/")
                except Exception as e:
                    print(f"Error al eliminar foto: {e}")
            
            # Ajuste dinámico (aprendizaje): subimos el umbral un 15%
            old_threshold = self.anomaly_threshold
            self.anomaly_threshold = int(self.anomaly_threshold * 1.15)
            self.save_settings() # Guardar aprendizaje
            self.log_event(f"Aprendizaje: Falsa alarma detectada. Sensibilidad ajustada.")
            tk.messagebox.showinfo("IA Actualizada", "Entendido. He descartado la captura y ajustado mi sensibilidad.")

    def safety_reset(self):
        self.mode = "STOP"
        self.mode_selector.configure(state="normal")
        self.mode_selector.set("STOP")
        self.btn_reset.configure(state="disabled")
        self.last_status = "SAFE"
        self.log_event("Rearme completado. Sistema en espera.")
        tk.messagebox.showinfo("Rearme", "Seguridad rearmada. Ya puede volver al modo AUTOMÁTICO.")

    def save_settings(self):
        settings = {
            "threshold": self.anomaly_threshold,
            "roi": self.roi_zone,
            "red_zones": self.red_zones,
            "amber_zones": self.amber_zones
        }
        if not os.path.exists("logs"): os.makedirs("logs")
        with open("logs/factory_settings.json", "w") as f:
            json.dump(settings, f)
        self.log_event("Configuración guardada en disco.")

    def load_settings(self):
        path = "logs/factory_settings.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    self.anomaly_threshold = data.get("threshold", 1200)
                    self.roi_zone = data.get("roi")
                    self.red_zones = data.get("red_zones", [])
                    self.amber_zones = data.get("amber_zones", [])
                    self.log_event(f"IA iniciada con umbral aprendido: {self.anomaly_threshold}")
                    # Re-dibujar zonas al cargar si el canvas ya existe (aquí es pronto, se hará en draw_frame la primera vez)
            except Exception as e:
                self.log_event(f"Error al cargar ajustes: {e}")

    def play_sound(self, type):
        def _job():
            if type == "EMERGENCY":
                for _ in range(5): winsound.Beep(1200, 200); time.sleep(0.05)
            else:
                winsound.Beep(600, 400); winsound.Beep(400, 400)
        threading.Thread(target=_job, daemon=True).start()

    def set_tool(self, tool):
        self.drawing_type = tool
        color_map = {"ROI": "Azul (ROI)", "RED": "Roja", "AMBER": "Ámbar"}
        self.log_event(f"Herramienta activa: Arrastra para dibujar Zona {color_map[tool]}.")

    def on_press(self, event):
        if self.drawing_type and self.mode == "STOP":
            self.start_x = event.x
            self.start_y = event.y
            color_map = {"RED": "#E74C3C", "AMBER": "#F1C40F", "ROI": "#1F6FEB"}
            self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, 
                                                        outline=color_map[self.drawing_type], width=2, dash=(4,4), tags="temp_rect")

    def change_camera(self, choice):
        if choice == "IP / URL":
            url = tk.simpledialog.askstring("Cámara IP", "Introduce la URL de la cámara (rtsp://...):")
            if url: self.camera_source = url
        else:
            self.camera_source = int(choice.split()[-1])
        
        self.video_running = False
        time.sleep(0.2)
        self.cap.release()
        self.start_camera()
        self.log_event(f"Cambiando a fuente: {self.camera_source}")

    def on_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        if self.rect_id:
            end_x, end_y = event.x, event.y
            # Normalizar coordenadas
            x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
            y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)
            
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                # Validar si está dentro de la ROI si estamos dibujando zonas de seguridad
                is_valid = True
                if self.drawing_type in ["RED", "AMBER"]:
                    if not self.roi_zone:
                        tk.messagebox.showwarning("Falta ROI", "Primero debes dibujar el ROI (Zona Azul) para delimitar el área de trabajo.")
                        is_valid = False
                    else:
                        rx1, ry1, rx2, ry2 = self.roi_zone
                        if not (x1 >= rx1 and y1 >= ry1 and x2 <= rx2 and y2 <= ry2):
                            tk.messagebox.showwarning("Fuera de ROI", "Estás dibujando fuera de la Zona Azul (ROI). Esto puede dar fallos en la detección.")
                            is_valid = False
                
                if is_valid:
                    if self.drawing_type == "RED":
                        self.red_zones.append((x1, y1, x2, y2))
                    elif self.drawing_type == "AMBER":
                        self.amber_zones.append((x1, y1, x2, y2))
                    elif self.drawing_type == "ROI":
                        self.roi_zone = (x1, y1, x2, y2)
                        # Al cambiar ROI, mejor limpiar zonas antiguas que queden fuera
                        self.red_zones = []
                        self.amber_zones = []
                        self.canvas.delete("fixed_zone")
                        self.log_event("Nuevo ROI definido. Zonas de seguridad reseteadas por seguridad.")
                        
                    color_map = {"RED": "#C0392B", "AMBER": "#D4AC0D", "ROI": "#1F6FEB"}
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline=color_map[self.drawing_type], width=2, tags="fixed_zone")
                    self.log_event(f"Zona {self.drawing_type} creada.")
                    self.save_settings()
            
            self.canvas.delete("temp_rect")
            self.rect_id = None
            self.drawing_type = None

    def toggle_grid(self):
        self.grid_visible = not self.grid_visible
        if self.grid_visible:
            for x in range(0, 860, 50):
                self.canvas.create_line(x, 0, x, 484, fill="#1c1c1c", tags="grid_line")
            for y in range(0, 484, 50):
                self.canvas.create_line(0, y, 860, y, fill="#1c1c1c", tags="grid_line")
            self.canvas.tag_lower("grid_line", "bg_video")
        else:
            self.canvas.delete("grid_line")

    def trigger_photo(self, frame):
        if not os.path.exists("captures"): os.makedirs("captures")
        self.last_capture_path = f"captures/EMERGENCIA_{int(time.time())}.jpg"
        # Guardar la captura inicialmente
        cv2.imwrite(self.last_capture_path, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        # Actualizar miniatura
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((200, 112))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(200, 112))
        self.last_capture_label.configure(image=ctk_img, text="")

    def change_mode(self, mode):
        self.mode = mode
        if mode == "CALIBRACION":
            self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
            self.log_event("Aprendiendo patrones de fondo normales...")
        self.log_event(f"Sistema: {mode}")

    def log_event(self, msg):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.console.insert("end", f"[{timestamp.split()[-1]}] {msg}\n")
        self.console.see("end")
        
        # Mantener registro para exportación
        if not hasattr(self, 'event_history'): self.event_history = []
        self.event_history.append([timestamp, msg])

    def export_report(self):
        if not hasattr(self, 'event_history') or not self.event_history:
            tk.messagebox.showwarning("Informe", "No hay eventos registrados para exportar.")
            return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", 
                                                 filetypes=[("CSV Files", "*.csv")],
                                                 initialfile=f"Informe_AntiNapas_{int(time.time())}.csv")
        if file_path:
            try:
                import csv
                with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Fecha y Hora", "Evento"])
                    writer.writerows(self.event_history)
                tk.messagebox.showinfo("Éxito", f"Informe exportado correctamente a:\n{file_path}")
            except Exception as e:
                tk.messagebox.showerror("Error", f"No se pudo exportar el informe: {e}")

    def clear_all(self):
        self.red_zones = []
        self.amber_zones = []
        self.roi_zone = None
        self.canvas.delete("fixed_zone")
        self.save_settings() # Limpiar también en el archivo
        self.log_event("Todas las zonas (incluyendo ROI) han sido eliminadas.")

if __name__ == "__main__":
    app = AntiNapasApp()
    app.mainloop()
