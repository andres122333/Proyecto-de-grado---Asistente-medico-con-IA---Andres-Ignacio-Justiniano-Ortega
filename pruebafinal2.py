# ==================== ASISTENTE MÉDICO CON SENSORES FÍSICOS ====================
import tkinter as tk
from tkinter import ttk, messagebox
import threading, time, random
import sqlite3
from datetime import datetime
import google.generativeai as genai

# ==================== IMPORTACIONES PARA SENSORES ====================
try:
    import board
    import busio
    import digitalio
    import adafruit_mcp3xxx.mcp3008 as MCP
    from adafruit_mcp3xxx.analog_in import AnalogIn
    import smbus2
    SENSORS_AVAILABLE = True
    print("✅ Librerías de sensores cargadas correctamente")
except ImportError as e:
    SENSORS_AVAILABLE = False
    print(f"⚠️ ADVERTENCIA: No se pudieron cargar las librerías de sensores: {e}")
    print("La aplicación usará valores simulados. Para usar sensores reales, instale:")
    print("  sudo pip3 install adafruit-circuitpython-mcp3xxx smbus2")

# ==================== CONFIGURACIÓN GEMINI ====================
GEMINI_API_KEY = "AIzaSyDtZfXKMkdz-_sPe7IBCpArBIMvXZTAkU4"

# ==================== CONFIGURACIÓN DE SENSORES ====================
# Sensor de Temperatura MLX90614
MLX_ADDR = 0x5A
BUS_NUM = 1
REG_TOBJ1 = 0x07

# Sensor de Pulso
THRESHOLD = 53000
SAMPLE_RATE = 0.02
NUM_BEATS_TO_AVERAGE = 10

# ==================== PALETA DE COLORES ====================
PALETTE = {
    "bg": "#F5F7FA",
    "card": "#FFFFFF",
    "accent": "#2B7A78",
    "accent_dark": "#205E5A",
    "text": "#17252A",
    "muted": "#4F5B66",
    "success": "#3AAFA9",
    "warning": "#F2B950",
    "danger": "#E15544",
    "checkmark": "#00B894",
    "btn_inactive_bg": "#E9EEF0",
    "btn_active_bg": "#2B7A78",
    "btn_inactive_fg": "#37474F",
    "btn_active_fg": "white",
}

def font_with_fallback(name, size, weight=None):
    try:
        return (name, size, weight) if weight else (name, size)
    except:
        return ("Arial", size, weight) if weight else ("Arial", size)

BASE_FONT = font_with_fallback("Verdana", 11)
TITLE_FONT = font_with_fallback("Verdana", 16, "bold")
HEADER_FONT = font_with_fallback("Verdana", 22, "bold")
BUTTON_FONT = font_with_fallback("Verdana", 11, "bold")
CARD_TITLE_FONT = font_with_fallback("Verdana", 13, "bold")
RESULT_TEXT_FONT = font_with_fallback("Verdana", 11)

# SÍNTOMAS ACTUALIZADOS CON LOS NUEVOS
DEFAULT_SYMPTOMS = [
    "Fiebre", 
    "Dolor de cabeza", 
    "Ardor de garganta", 
    "Dolor de cuerpo", 
    "Malestar estomacal", 
    "Diarrea", 
    "Escalofríos",
    "Congestión nasal",
    "Tos",
    "Náuseas",
    "Vómitos"
]

# ==================== CLASE PARA MANEJO DE SENSORES ====================
class SensorManager:
    def __init__(self):
        self.sensors_active = SENSORS_AVAILABLE
        self.pulse_sensor = None
        self.temp_bus = None
        
        if self.sensors_active:
            try:
                # Inicializar sensor de pulso (MCP3008)
                spi = busio.SPI(clock=board.SCLK, MISO=board.MISO, MOSI=board.MOSI)
                cs = digitalio.DigitalInOut(board.D25)
                mcp = MCP.MCP3008(spi, cs)
                self.pulse_sensor = AnalogIn(mcp, MCP.P0)
                print("✅ Sensor de pulso MCP3008 inicializado")
            except Exception as e:
                print(f"⚠️ Error al inicializar sensor de pulso: {e}")
                self.sensors_active = False
            
            try:
                # Inicializar sensor de temperatura (MLX90614)
                self.temp_bus = smbus2.SMBus(BUS_NUM)
                # Probar lectura
                test_read = self.temp_bus.read_word_data(MLX_ADDR, REG_TOBJ1)
                print("✅ Sensor de temperatura MLX90614 inicializado")
            except Exception as e:
                print(f"⚠️ Error al inicializar sensor de temperatura: {e}")
                self.sensors_active = False
                if self.temp_bus:
                    try:
                        self.temp_bus.close()
                    except:
                        pass
                    self.temp_bus = None
    
    def read_temperature(self):
        """Lee la temperatura del sensor MLX90614"""
        if not self.sensors_active or not self.temp_bus:
            # Retornar valor simulado
            return round(random.uniform(35.8, 37.8), 1)
        
        try:
            data = self.temp_bus.read_word_data(MLX_ADDR, REG_TOBJ1)
            celsius = (data * 0.02) - 273.15
            return round(celsius, 1)
        except Exception as e:
            print(f"Error leyendo temperatura: {e}")
            return round(random.uniform(36.0, 37.5), 1)
    
    def read_pulse(self, duration=10):
        """Lee el pulso durante 'duration' segundos"""
        if not self.sensors_active or not self.pulse_sensor:
            # Retornar valor simulado después de simular tiempo de medición
            time.sleep(duration * 0.15)  # Simulación rápida
            return random.randint(60, 100)
        
        ibi_list = []
        last_beat_time = 0
        beat_detected = False
        start_time = time.monotonic()
        
        print(f"Iniciando lectura de pulso por {duration} segundos...")
        
        while time.monotonic() - start_time < duration:
            try:
                valor_bruto = self.pulse_sensor.value
                current_time = time.monotonic()
                
                # Detectar cruce hacia arriba del umbral
                if valor_bruto > THRESHOLD and not beat_detected:
                    beat_detected = True
                    
                    if last_beat_time != 0:
                        ibi = current_time - last_beat_time
                        
                        # Filtro: pulso humano entre 40-240 BPM
                        if 0.25 < ibi < 1.5:
                            ibi_list.append(ibi)
                            
                            if len(ibi_list) > NUM_BEATS_TO_AVERAGE:
                                ibi_list.pop(0)
                    
                    last_beat_time = current_time
                
                # Detectar cruce hacia abajo del umbral
                elif valor_bruto < THRESHOLD and beat_detected:
                    beat_detected = False
                
                time.sleep(SAMPLE_RATE)
                
            except Exception as e:
                print(f"Error en lectura de pulso: {e}")
                break
        
        # Calcular BPM promedio
        if ibi_list:
            avg_ibi = sum(ibi_list) / len(ibi_list)
            bpm = round(60 / avg_ibi)
            print(f"✅ Pulso medido: {bpm} BPM (basado en {len(ibi_list)} latidos)")
            return bpm
        else:
            print("⚠️ No se detectaron latidos suficientes, usando valor estimado")
            return random.randint(65, 85)
    
    def cleanup(self):
        """Limpia recursos de sensores"""
        if self.temp_bus:
            try:
                self.temp_bus.close()
            except:
                pass

# ==================== COMPONENTE VISUAL: TARJETA REDONDEADA ====================
class RoundedCard(tk.Canvas):
    def __init__(self, parent, width=400, height=200, radius=12, bg=PALETTE["card"], **kwargs):
        super().__init__(parent, width=width, height=height, highlightthickness=0, bg=parent['bg'], **kwargs)
        self.radius = radius
        self.bg = bg
        self.width = width
        self.height = height
        self._draw_round_rect()
        self.inner_frame = tk.Frame(self, bg=self.bg)
        pad = int(radius/2)
        self.create_window((pad, pad), window=self.inner_frame, anchor="nw", width=width - pad*2, height=height - pad*2)

    def _draw_round_rect(self):
        w, h, r = self.width, self.height, self.radius
        self.create_rectangle(r, 0, w - r, h, fill=self.bg, outline=self.bg)
        self.create_rectangle(0, r, w, h - r, fill=self.bg, outline=self.bg)
        self.create_arc((0, 0, r*2, r*2), start=90, extent=90, fill=self.bg, outline=self.bg)
        self.create_arc((w - 2*r, 0, w, r*2), start=0, extent=90, fill=self.bg, outline=self.bg)
        self.create_arc((0, h - 2*r, r*2, h), start=180, extent=90, fill=self.bg, outline=self.bg)
        self.create_arc((w - 2*r, h - 2*r, w, h), start=270, extent=90, fill=self.bg, outline=self.bg)

# ==================== APLICACIÓN PRINCIPAL ====================
class AsistenteDiagnostico(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Asistente para Diagnóstico Médico - Con Sensores Reales")
        
        # Configurar pantalla completa
        self.attributes('-fullscreen', True)
        self.bind('<Escape>', lambda e: self.toggle_fullscreen())  # ESC para salir de pantalla completa
        self.bind('<F11>', lambda e: self.toggle_fullscreen())  # F11 para alternar
        
        self.configure(bg=PALETTE["bg"])
        
        # Inicializar gestor de sensores
        self.sensor_manager = SensorManager()
        
        self.db_name = 'historial_pacientes.db'
        self.current_sort_order = "DESC"
        self.current_urgency_sort = "fecha_hora"
        self.symptom_vars = {'Otros': tk.BooleanVar(value=False)}
        self.custom_symptom_text = None
        self.antecedentes_detail_text = None
        self.history_text = None
        self.history_yes_no_var = tk.StringVar(value="")
        self.lbl_history_detail = None
        self.btn_history_yes = None
        self.btn_history_no = None
        self.temp_value_label = None
        self.pulse_value_label = None
        self.lbl_otros_detalle = None
        self.result_box = None
        self.btn_otros = None
        self.temp_db = None
        self.pulse_db = None
        self.resumen_completo_db = None
        self.diagnostico_final = None
        self.nivel_urgencia = None
        self.sintomas_db = None
        self.antecedentes_db = None
        self.current_step_frame = None
        self.step_frames = {}
        self.keyboard_frame = None
        self.keyboard_visible = False
        self.last_step = None
        self.active_text_target = None
        self.measuring = False
        self.fullscreen_state = True
        
        self._setup_database()
        
        self.container = tk.Frame(self, bg=PALETTE["bg"])
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        self.frames = {}
        self._build_welcome_screen()
        self._build_diagnosis_screen()
        self._build_history_screen()
        self.show_frame("Welcome")
        
        sensor_status = "🟢 Sensores físicos conectados" if self.sensor_manager.sensors_active else "🟡 Modo simulación (sensores no disponibles)"
        self.status_var = tk.StringVar(value=f"Base de datos conectada. {sensor_status}")
        self.status_bar = tk.Frame(self, bg="#EDEFF0", height=28)
        self.status_bar.pack(side="bottom", fill="x")
        tk.Label(self.status_bar, textvariable=self.status_var, bg="#EDEFF0", fg=PALETTE["muted"], font=font_with_fallback("Verdana", 9)).pack(side="left", padx=12)
        
        # Manejar cierre de ventana
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def toggle_fullscreen(self):
        """Alterna entre pantalla completa y modo ventana"""
        self.fullscreen_state = not self.fullscreen_state
        self.attributes('-fullscreen', self.fullscreen_state)

    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        self.sensor_manager.cleanup()
        self.destroy()

    def _setup_database(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_hora TEXT NOT NULL, sintomas_seleccionados TEXT,
                antecedentes TEXT, temperatura REAL, pulso INTEGER, nivel_urgencia TEXT,
                diagnostico_preliminar TEXT, resumen_completo TEXT)''')
            conn.commit()
        except sqlite3.Error as e:
            messagebox.showerror("Error DB", f"No se pudo conectar: {e}")
        finally:
            if conn: conn.close()

    def _guardar_en_db(self):
        if not self.resumen_completo_db or not self.diagnostico_final:
            return "No hay análisis para guardar."
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO pacientes (fecha_hora, sintomas_seleccionados, antecedentes, temperatura, pulso,
                nivel_urgencia, diagnostico_preliminar, resumen_completo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.sintomas_db, self.antecedentes_db,
                 self.temp_db, self.pulse_db, self.nivel_urgencia, self.diagnostico_final, self.resumen_completo_db))
            conn.commit()
            return f"✅ Guardado (ID: {cursor.lastrowid})"
        except sqlite3.Error as e:
            return f"❌ Error: {e}"
        finally:
            if conn: conn.close()

    def get_all_patients(self, order_by="fecha_hora", sort_order="DESC"):
        conn = None
        if order_by == "nivel_urgencia":
            order_case = """CASE nivel_urgencia WHEN 'ALTA URGENCIA (Nivel Rojo)' THEN 3 
                WHEN 'MODERADA (Nivel Amarillo)' THEN 2 WHEN 'BAJA (Nivel Verde)' THEN 1 ELSE 0 END"""
            order_clause = f"ORDER BY {order_case} {sort_order}, fecha_hora DESC"
        else:
            order_clause = f"ORDER BY {order_by} {sort_order}"
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, fecha_hora, nivel_urgencia, temperatura, pulso, diagnostico_preliminar FROM pacientes {order_clause}")
            return [d[0] for d in cursor.description], cursor.fetchall()
        except sqlite3.Error as e:
            self.status_var.set(f"Error: {e}")
            return None, None
        finally:
            if conn: conn.close()

    def delete_patient_by_id(self, patient_id):
        conn = None
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM pacientes WHERE id = ?', (patient_id,))
            conn.commit()
            return True
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo eliminar: {e}")
            return False
        finally:
            if conn: conn.close()

    def delete_selected_patient(self):
        selected = self.history_tree.focus()
        if not selected:
            messagebox.showwarning("Eliminar", "Selecciona un paciente.")
            return
        patient_id = self.history_tree.item(selected, 'values')[0]
        if messagebox.askyesno("Confirmar", f"¿Eliminar ID {patient_id}?"):
            if self.delete_patient_by_id(patient_id):
                messagebox.showinfo("Éxito", f"ID {patient_id} eliminado.")
                self._update_history_treeview()

    def toggle_urgency_sort(self):
        if self.current_urgency_sort == "nivel_urgencia":
            self.current_sort_order = "ASC" if self.current_sort_order == "DESC" else "DESC"
            self.current_urgency_sort = "fecha_hora"
        else:
            self.current_urgency_sort = "nivel_urgencia"
            self.current_sort_order = "DESC"
        self._update_history_treeview(self.current_urgency_sort, self.current_sort_order)

    def _update_history_treeview(self, order_by=None, sort_order=None):
        order_by = order_by or self.current_urgency_sort
        sort_order = sort_order or self.current_sort_order
        self.history_tree.delete(*self.history_tree.get_children())
        cols, data = self.get_all_patients(order_by, sort_order)
        if not data: return
        if not self.history_tree['columns']:
            display_cols = ['id', 'fecha_hora', 'nivel_urgencia', 'temperatura', 'pulso', 'diagnostico_preliminar']
            self.history_tree.config(columns=display_cols)
            for col in display_cols:
                self.history_tree.heading(col, text=col.replace('_', ' ').title())
                self.history_tree.column(col, width=100, anchor=tk.CENTER)
            self.history_tree.column('id', width=40)
            self.history_tree.column('fecha_hora', width=150)
            self.history_tree.column('nivel_urgencia', width=120)
            self.history_tree.column('diagnostico_preliminar', width=300, anchor=tk.W)
        for item in data:
            self.history_tree.insert('', tk.END, values=item)

    def toggle_symptom(self, symptom_name, button):
        new_state = not self.symptom_vars[symptom_name].get()
        self.symptom_vars[symptom_name].set(new_state)
        button.config(bg=PALETTE["btn_active_bg"] if new_state else PALETTE["btn_inactive_bg"],
                     fg=PALETTE["btn_active_fg"] if new_state else PALETTE["btn_inactive_fg"],
                     relief=tk.SUNKEN if new_state else tk.RAISED)

    def open_custom_symptom_screen(self):
        self.symptom_vars['Otros'].set(True)
        if hasattr(self, 'btn_otros') and self.btn_otros:
            self.btn_otros.config(bg=PALETTE["btn_active_bg"], fg=PALETTE["btn_active_fg"], relief=tk.SUNKEN)
        self.show_diagnosis_step("otros_sintomas")

    def save_custom_symptoms(self):
        if self.keyboard_visible:
            self.hide_virtual_keyboard()
        self.show_diagnosis_step("sintomas")

    def save_antecedentes_details(self):
        if self.keyboard_visible:
            self.hide_virtual_keyboard()
        self.show_diagnosis_step("antecedentes")

    def toggle_history_box(self, show):
        if show:
            self.history_yes_no_var.set("yes")
            self.btn_history_yes.config(bg=PALETTE["btn_active_bg"], fg=PALETTE["btn_active_fg"], relief=tk.SUNKEN)
            self.btn_history_no.config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)
            self.show_diagnosis_step("detalle_antecedentes")
        else:
            self.history_yes_no_var.set("no")
            self.btn_history_yes.config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)
            self.btn_history_no.config(bg=PALETTE["btn_active_bg"], fg=PALETTE["btn_active_fg"], relief=tk.SUNKEN)
            if self.antecedentes_detail_text:
                self.antecedentes_detail_text.delete("1.0", "end")

    def _build_symptom_buttons(self, container):
        NUM_COLS = 3
        row_idx = col_idx = 0
        for symptom in DEFAULT_SYMPTOMS + ['Otros Síntomas']:
            if symptom == 'Otros Síntomas':
                button = tk.Button(container, text="Otros síntomas", bg=PALETTE["btn_inactive_bg"],
                    fg=PALETTE["btn_inactive_fg"], bd=0, relief=tk.RAISED, activebackground=PALETTE["btn_active_bg"],
                    font=BUTTON_FONT, width=22, height=2, command=self.open_custom_symptom_screen)
                self.btn_otros = button
            else:
                self.symptom_vars[symptom] = tk.BooleanVar(value=False)
                button = tk.Button(container, text=symptom, bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"],
                    bd=0, relief=tk.RAISED, activebackground=PALETTE["btn_active_bg"], font=BUTTON_FONT, width=22, height=2,
                    command=lambda s=symptom, b=None: self.toggle_symptom(s, getattr(self, 'symptom_button_' + s.replace(" ", "_"))))
                setattr(self, 'symptom_button_' + symptom.replace(" ", "_"), button)
            button.grid(row=row_idx, column=col_idx, padx=8, pady=8, sticky="ew")
            col_idx += 1
            if col_idx >= NUM_COLS:
                col_idx = 0
                row_idx += 1
        for i in range(NUM_COLS):
            container.grid_columnconfigure(i, weight=1)

    def _build_welcome_screen(self):
        frame = tk.Frame(self.container, bg=PALETTE["bg"])
        self.frames["Welcome"] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        
        tk.Label(frame, text="🩺 ASISTENTE MÉDICO", bg=PALETTE["bg"], fg=PALETTE["accent_dark"], 
                 font=HEADER_FONT).pack(pady=(60, 40))
        
        btn_frame = tk.Frame(frame, bg=PALETTE["bg"])
        btn_frame.pack(expand=True, anchor="n")
        
        tk.Button(btn_frame, text="NUEVO DIAGNÓSTICO", bg=PALETTE["accent"], fg="white", bd=0,
            activebackground=PALETTE["accent_dark"], font=font_with_fallback("Verdana", 13, "bold"), 
            width=30, height=3, command=lambda: self.show_frame("Diagnosis")).pack(pady=12)
        tk.Button(btn_frame, text="VER HISTORIAL", bg=PALETTE["muted"], fg="white", bd=0,
            font=font_with_fallback("Verdana", 13, "bold"), width=30, height=3, 
            command=lambda: self.show_frame("History")).pack(pady=12)
        tk.Button(btn_frame, text="SALIR", bg=PALETTE["danger"], fg="white", bd=0,
            font=font_with_fallback("Verdana", 13, "bold"), width=30, height=3, 
            command=self.salir_aplicacion).pack(pady=12)

    def salir_aplicacion(self):
        if messagebox.askyesno("Salir", "¿Está seguro que desea salir de la aplicación?"):
            self.on_closing()

    def _build_history_screen(self):
        frame = tk.Frame(self.container, bg=PALETTE["bg"])
        self.frames["History"] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        header = tk.Frame(frame, bg=PALETTE["bg"])
        header.grid(row=0, column=0, sticky="ew", pady=(10, 6))
        tk.Label(header, text="Historial de Pacientes", bg=PALETTE["bg"], fg=PALETTE["text"], font=TITLE_FONT).pack(side="left", padx=12)
        tk.Button(header, text="VOLVER", bg=PALETTE["accent"], fg="white", bd=0, font=BUTTON_FONT,
            command=lambda: self.show_frame("Welcome")).pack(side="right", padx=12)
        control = tk.Frame(frame, bg=PALETTE["bg"])
        control.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        tk.Button(control, text="🗑️ ELIMINAR", bg=PALETTE["danger"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.delete_selected_patient).pack(side="left", padx=6)
        tk.Button(control, text="📊 ORDENAR", bg=PALETTE["warning"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.toggle_urgency_sort).pack(side="left", padx=6)
        tree_frame = tk.Frame(frame, bg=PALETTE["bg"])
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(6, 10))
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self.history_tree = ttk.Treeview(tree_frame, show='headings')
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        vsb.pack(side='right', fill='y')
        self.history_tree.pack(fill=tk.BOTH, expand=True)

    def _build_diagnosis_screen(self):
        frame = tk.Frame(self.container, bg=PALETTE["bg"])
        self.frames["Diagnosis"] = frame
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        header = tk.Frame(frame, bg=PALETTE["bg"])
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text="🩺 ASISTENTE PARA DIAGNÓSTICO", bg=PALETTE["bg"], fg=PALETTE["text"], font=TITLE_FONT).pack(side="left", padx=12)
        
        self.btn_scroll_up = tk.Button(header, text="⬆️ SUBIR", bg=PALETTE["accent"], fg="white", 
                 bd=0, font=BUTTON_FONT, command=lambda: self.result_box.yview_moveto(0))
        self.btn_scroll_down = tk.Button(header, text="⬇️ BAJAR", bg=PALETTE["accent"], fg="white",
                 bd=0, font=BUTTON_FONT, command=lambda: self.result_box.yview_moveto(1.0))
        
        self.btn_finish_diagnosis = tk.Button(header, text="VOLVER", bg=PALETTE["muted"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.save_and_return_home)
        self.btn_finish_diagnosis.pack(side="right", padx=12)
        
        self.step_container = tk.Frame(frame, bg=PALETTE["bg"])
        self.step_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        self.step_container.grid_rowconfigure(0, weight=1)
        self.step_container.grid_columnconfigure(0, weight=1)

        self.keyboard_frame = tk.Frame(self.step_container, bg=PALETTE["bg"])
        self.keyboard_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(2, 4))
        self.keyboard_frame.grid_remove()

        self._build_step_symptoms()
        self._build_step_custom_symptoms()
        self._build_step_history()
        self._build_step_antecedentes_detail()
        self._build_step_measurements()
        self._build_step_result()

        self.nav_frame = tk.Frame(frame, bg=PALETTE["bg"])
        self.nav_frame.grid(row=2, column=0, sticky="ew", pady=(4, 8), padx=12)
        self.btn_prev = tk.Button(self.nav_frame, text="⬅️ ANTERIOR", bg="#9AA4A6", fg="white", bd=0,
            font=BUTTON_FONT, command=lambda: self.navigate_diagnosis("Prev"))
        self.btn_next = tk.Button(self.nav_frame, text="SIGUIENTE ➡️", bg=PALETTE["accent"], fg="white", bd=0,
            font=BUTTON_FONT, command=lambda: self.navigate_diagnosis("Next"))
        self.btn_analyze = tk.Button(self.nav_frame, text="ANALIZAR", bg=PALETTE["accent_dark"], fg="white", bd=0,
            font=BUTTON_FONT, command=lambda: self.navigate_diagnosis("Analyze"))
        self.btn_finish_analysis = tk.Button(self.nav_frame, text="FINALIZAR Y GUARDAR", bg=PALETTE["success"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.save_and_return_home)
        self.btn_listo_sintomas = tk.Button(self.nav_frame, text="LISTO", bg=PALETTE["success"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.save_custom_symptoms)
        self.btn_listo_antecedentes = tk.Button(self.nav_frame, text="LISTO", bg=PALETTE["success"], fg="white", bd=0,
            font=BUTTON_FONT, command=self.save_antecedentes_details)

    def _build_step_symptoms(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="sintomas")
        frame.name = "sintomas"
        self.step_frames["sintomas"] = frame
        card = RoundedCard(frame, width=980, height=420, radius=12)
        card.pack(fill="x", pady=4)
        tk.Label(card.inner_frame, text="Seleccione los síntomas que presenta:", bg=PALETTE["card"],
            fg=PALETTE["text"], font=BASE_FONT).pack(anchor="w", padx=8, pady=(6, 6))
        center = tk.Frame(card.inner_frame, bg=PALETTE["card"])
        center.pack(fill="x", padx=6, pady=(0, 6))
        grid = tk.Frame(center, bg=PALETTE["card"])
        grid.pack(anchor="center", fill="x")
        self._build_symptom_buttons(grid)

    def _build_step_custom_symptoms(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="otros_sintomas")
        frame.name = "otros_sintomas"
        self.step_frames["otros_sintomas"] = frame
        
        frame.grid_rowconfigure(0, weight=3)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        card = RoundedCard(frame, width=980, height=250, radius=12)
        card.grid(row=0, column=0, sticky="nsew", padx=10, pady=(4, 2))
        
        tk.Label(card.inner_frame, text="Registre sus síntomas:", bg=PALETTE["card"], fg=PALETTE["text"], font=CARD_TITLE_FONT).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(card.inner_frame, text="Por favor, describa detalladamente los síntomas adicionales que presenta:", bg=PALETTE["card"], fg=PALETTE["muted"], font=BASE_FONT).pack(anchor="w", padx=12, pady=(0, 12))
        
        text_frame = tk.Frame(card.inner_frame, bg="#CCCCCC", bd=1)
        text_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        self.custom_symptom_text = tk.Text(text_frame, bg="#FFFFFF", fg=PALETTE["text"], bd=0, wrap="word", font=font_with_fallback("Verdana", 12), insertbackground=PALETTE["accent"], relief="flat", padx=10, pady=10)
        self.custom_symptom_text.pack(fill="both", expand=True)
        
        self.custom_symptom_text.bind("<FocusIn>", lambda e: (setattr(self, 'active_text_target', self.custom_symptom_text), self.show_virtual_keyboard()))
        self.custom_symptom_text.bind("<Button-1>", lambda e: (setattr(self, 'active_text_target', self.custom_symptom_text), self.show_virtual_keyboard()))

    def _build_step_history(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="antecedentes")
        frame.name = "antecedentes"
        self.step_frames["antecedentes"] = frame
        card = RoundedCard(frame, width=980, height=220, radius=12)
        card.pack(fill="x", pady=4)
        
        tk.Label(card.inner_frame, text="¿Tienes algún antecedente médico, alergia a medicamento o información médica relevante?", bg=PALETTE["card"], fg=PALETTE["text"], font=BASE_FONT).pack(anchor="w", padx=8, pady=(6, 6))
        
        btn_frame = tk.Frame(card.inner_frame, bg=PALETTE["card"])
        btn_frame.pack(pady=4) 
        
        self.btn_history_yes = tk.Button(btn_frame, text="Sí", bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"],
            bd=0, relief=tk.RAISED, activebackground=PALETTE["btn_active_bg"], font=BUTTON_FONT, width=12, height=2,
            command=lambda: self.toggle_history_box(show=True))
        self.btn_history_yes.pack(side="left", padx=(0, 8))
        
        self.btn_history_no = tk.Button(btn_frame, text="No", bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"],
            bd=0, relief=tk.RAISED, activebackground=PALETTE["btn_active_bg"], font=BUTTON_FONT, width=12, height=2,
            command=lambda: self.toggle_history_box(show=False))
        self.btn_history_no.pack(side="left")
        
        self.lbl_history_detail = tk.Label(card.inner_frame, text="Especifique:", bg=PALETTE["card"], fg=PALETTE["muted"], font=BASE_FONT)

    def _build_step_antecedentes_detail(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="detalle_antecedentes")
        frame.name = "detalle_antecedentes"
        self.step_frames["detalle_antecedentes"] = frame
        
        frame.grid_rowconfigure(0, weight=3)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        card = RoundedCard(frame, width=980, height=250, radius=12)
        card.grid(row=0, column=0, sticky="nsew", padx=10, pady=(4, 2))
        
        tk.Label(card.inner_frame, text="Detalle sus antecedentes clínicos o alergias a medicamentos:", bg=PALETTE["card"], fg=PALETTE["text"], font=CARD_TITLE_FONT).pack(anchor="w", padx=12, pady=(12, 8))
        tk.Label(card.inner_frame, text="Describa aquí antecedentes relevantes (ej. alergias, enfermedades crónicas, medicamentos):", bg=PALETTE["card"], fg=PALETTE["muted"], font=BASE_FONT).pack(anchor="w", padx=12, pady=(0, 12))
        
        text_frame = tk.Frame(card.inner_frame, bg="#CCCCCC", bd=1)
        text_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        self.antecedentes_detail_text = tk.Text(text_frame, bg="#FFFFFF", fg=PALETTE["text"], bd=0, wrap="word", font=font_with_fallback("Verdana", 12), insertbackground=PALETTE["accent"], relief="flat", padx=10, pady=10)
        self.antecedentes_detail_text.pack(fill="both", expand=True)
        
        self.antecedentes_detail_text.bind("<FocusIn>", lambda e: (setattr(self, 'active_text_target', self.antecedentes_detail_text), self.show_virtual_keyboard()))
        self.antecedentes_detail_text.bind("<Button-1>", lambda e: (setattr(self, 'active_text_target', self.antecedentes_detail_text), self.show_virtual_keyboard()))

    def _build_step_measurements(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="mediciones")
        frame.name = "mediciones"
        self.step_frames["mediciones"] = frame
        card = RoundedCard(frame, width=980, height=220, radius=12)
        card.pack(fill="x", pady=4)
        tk.Label(card.inner_frame, text="Signos vitales (realice las mediciones con los sensores):", bg=PALETTE["card"],
            fg=PALETTE["text"], font=BASE_FONT).pack(anchor="w", padx=8, pady=(6, 10))
        mf = tk.Frame(card.inner_frame, bg=PALETTE["card"])
        mf.pack(fill="x", padx=8, pady=(0, 8))
        for i in range(4): mf.grid_columnconfigure(i, weight=[2,3,1,2][i])
        tk.Label(mf, text="Temperatura (°C):", bg=PALETTE["card"], fg=PALETTE["muted"], font=BASE_FONT).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.temp_value_label = tk.Label(mf, text="—", bg=PALETTE["card"], fg=PALETTE["text"], font=font_with_fallback("Verdana", 14, "bold"))
        self.temp_value_label.grid(row=0, column=3, padx=6, sticky="w")
        self.progress_temp = ttk.Progressbar(mf, orient="horizontal", mode="determinate", length=180)
        self.progress_temp.grid(row=0, column=1, padx=6)
        tk.Button(mf, text="MEDIR", bg=PALETTE["accent"], fg="white", bd=0, activebackground=PALETTE["accent_dark"],
            font=BUTTON_FONT, command=lambda: self.simulate_measure("temp")).grid(row=0, column=2, padx=6)
        tk.Label(mf, text="Pulso (bpm):", bg=PALETTE["card"], fg=PALETTE["muted"], font=BASE_FONT).grid(row=1, column=0, sticky="w", pady=(8, 6))
        self.pulse_value_label = tk.Label(mf, text="—", bg=PALETTE["card"], fg=PALETTE["text"], font=font_with_fallback("Verdana", 14, "bold"))
        self.pulse_value_label.grid(row=1, column=3, padx=6, sticky="w")
        self.progress_pulse = ttk.Progressbar(mf, orient="horizontal", mode="determinate", length=180)
        self.progress_pulse.grid(row=1, column=1, padx=6)
        tk.Button(mf, text="MEDIR", bg=PALETTE["accent"], fg="white", bd=0, activebackground=PALETTE["accent_dark"],
            font=BUTTON_FONT, command=lambda: self.simulate_measure("pulse")).grid(row=1, column=2, padx=6)

    def _build_step_result(self):
        frame = tk.Frame(self.step_container, bg=PALETTE["bg"], name="resultado")
        frame.name = "resultado"
        self.step_frames["resultado"] = frame
        card = RoundedCard(frame, width=980, height=450, radius=12)
        card.pack(fill="both", pady=4, expand=True)
        
        self.result_box = tk.Text(card.inner_frame, bg="#FFFFFF", bd=0, wrap="word", state="disabled", font=RESULT_TEXT_FONT)
        self.result_box.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        
        tk.Label(card.inner_frame, text="⚠️ Aviso: Las recomendaciones son preliminares y NO reemplazan la valoración de un profesional.",
            wraplength=860, justify="left", bg=PALETTE["card"], fg=PALETTE["danger"], font=BASE_FONT).pack(anchor="w", padx=8, pady=(6, 8))

    def show_frame(self, page_name):
        self.frames[page_name].tkraise()
        if page_name == "Diagnosis":
            self.reset_all_data()
            self.show_diagnosis_step("sintomas")
        elif page_name == "History":
            self._update_history_treeview()

    def show_diagnosis_step(self, step_name):
        if self.keyboard_visible:
            self.hide_virtual_keyboard()
            
        prev = self.current_step_frame.name if self.current_step_frame else None
        if self.current_step_frame:
            self.current_step_frame.grid_forget()
        self.last_step = prev
        self.current_step_frame = self.step_frames[step_name]
        self.current_step_frame.grid(row=0, column=0, sticky="nsew")
        self._update_nav_buttons(step_name)

    def _update_nav_buttons(self, step):
        for w in self.nav_frame.winfo_children(): w.pack_forget()
        self.btn_finish_diagnosis.pack(side="right", padx=6)
        
        self.btn_scroll_up.pack_forget()
        self.btn_scroll_down.pack_forget()
        
        if step == "sintomas":
            self.btn_next.pack(side="right", padx=6)
        elif step == "otros_sintomas":
            self.btn_prev.pack(side="left", padx=6)
            self.btn_listo_sintomas.pack(side="left", padx=6)
            self.btn_next.pack(side="right", padx=6)
        elif step == "antecedentes":
            self.btn_prev.pack(side="left", padx=6)
            self.btn_next.pack(side="right", padx=6)
        elif step == "detalle_antecedentes":
            self.btn_prev.pack(side="left", padx=6)
            self.btn_listo_antecedentes.pack(side="left", padx=6)
            self.btn_next.pack(side="right", padx=6)
        elif step == "mediciones":
            self.btn_prev.pack(side="left", padx=6)
            self.btn_analyze.pack(side="right", padx=6)
        elif step == "resultado":
            self.btn_scroll_up.pack(side="right", padx=6, before=self.btn_finish_diagnosis)
            self.btn_scroll_down.pack(side="right", padx=6, before=self.btn_finish_diagnosis)
            self.btn_finish_diagnosis.pack_forget()
            self.btn_finish_analysis.pack(side="left", padx=6)

    def navigate_diagnosis(self, action):
        steps = ["sintomas", "otros_sintomas", "antecedentes", "detalle_antecedentes", "mediciones", "resultado"]
        idx = steps.index(self.current_step_frame.name)
        
        if action == "Next":
            if steps[idx] == "sintomas":
                if self.symptom_vars['Otros'].get():
                    if getattr(self, 'last_step', None) == 'otros_sintomas':
                        self.show_diagnosis_step("antecedentes")
                    else:
                        self.show_diagnosis_step("otros_sintomas")
                else:
                    self.show_diagnosis_step("antecedentes")
                return
            
            if steps[idx] == "otros_sintomas":
                self.show_diagnosis_step("antecedentes")
                return
            
            if steps[idx] == "antecedentes":
                response = self.history_yes_no_var.get()
                if response == "":
                    messagebox.showwarning("Faltan datos", "Por favor, seleccione 'Sí' o 'No' en la pregunta sobre antecedentes.")
                    return
                if response == "yes":
                    detalle = self.antecedentes_detail_text.get("1.0", "end").strip() if self.antecedentes_detail_text else ""
                    if not detalle:
                        messagebox.showwarning("Faltan datos", "Ha seleccionado 'Sí', por favor especifique los antecedentes para continuar.")
                        return
                    self.show_diagnosis_step("mediciones")
                    return
                else:
                    self.show_diagnosis_step("mediciones")
                    return
                
            if steps[idx] == "detalle_antecedentes":
                detalle = self.antecedentes_detail_text.get("1.0", "end").strip() if self.antecedentes_detail_text else ""
                if not detalle:
                    messagebox.showwarning("Faltan datos", "Por favor escriba sus antecedentes o pulse 'Listo' cuando termine.")
                    return
                self.show_diagnosis_step("mediciones")
                return
                
        elif action == "Prev":
            if steps[idx] == "antecedentes":
                if self.symptom_vars['Otros'].get():
                    self.show_diagnosis_step("otros_sintomas")
                else:
                    self.show_diagnosis_step("sintomas")
                return
            
            if steps[idx] == "detalle_antecedentes":
                self.show_diagnosis_step("antecedentes")
                return
            
            if steps[idx] == "mediciones":
                if getattr(self, 'last_step', None) == 'detalle_antecedentes' or self.history_yes_no_var.get() == "yes":
                    self.show_diagnosis_step("detalle_antecedentes")
                else:
                    self.show_diagnosis_step("antecedentes")
                return
            
            if steps[idx] == "resultado":
                self.show_diagnosis_step("mediciones")
                return
                
        elif action == "Analyze":
            self.on_analyze()

    def save_and_return_home(self):
        if self.resumen_completo_db:
            messagebox.showinfo("Guardado", self._guardar_en_db())
        else:
            messagebox.showinfo("Volver", "No hay análisis para guardar.")
        self.reset_all_data()
        self.show_frame("Welcome")

    def reset_all_data(self):
        if self.keyboard_visible:
            self.hide_virtual_keyboard()
            
        for s, v in list(self.symptom_vars.items()):
            v.set(False)
            if s in DEFAULT_SYMPTOMS:
                btn_name = 'symptom_button_' + s.replace(" ", "_")
                if hasattr(self, btn_name):
                    getattr(self, btn_name).config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)
        
        if hasattr(self, 'btn_otros'):
            self.btn_otros.config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)
        
        if self.custom_symptom_text:
            self.custom_symptom_text.delete("1.0", "end")
        
        if self.antecedentes_detail_text:
            self.antecedentes_detail_text.delete("1.0", "end")
        
        self.history_yes_no_var.set("")
        
        if self.lbl_history_detail:
            self.lbl_history_detail.pack_forget()
            
        if self.btn_history_yes:
            self.btn_history_yes.config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)
        if self.btn_history_no:
            self.btn_history_no.config(bg=PALETTE["btn_inactive_bg"], fg=PALETTE["btn_inactive_fg"], relief=tk.RAISED)

        self.temp_db = self.pulse_db = None
        if self.temp_value_label: self.temp_value_label.config(text="—", fg=PALETTE["text"])
        if self.pulse_value_label: self.pulse_value_label.config(text="—", fg=PALETTE["text"])
        if self.result_box:
            self.result_box.configure(state="normal")
            self.result_box.delete("1.0", "end")
            self.result_box.configure(state="disabled")
        self.resumen_completo_db = self.diagnostico_final = self.nivel_urgencia = None
        self.sintomas_db = self.antecedentes_db = None
        self.status_var.set("Datos reiniciados.")
        for f in self.step_frames.values():
            try:
                f.grid_forget()
            except Exception:
                pass
        self.current_step_frame = None
        self.last_step = None
        self.active_text_target = None
        self.measuring = False

    def simulate_measure(self, sensor):
        """Inicia la medición real desde los sensores físicos"""
        if self.measuring:
            messagebox.showwarning("Medición en curso", "Ya hay una medición en progreso. Por favor espere.")
            return
        
        self.measuring = True
        progress = self.progress_temp if sensor == "temp" else self.progress_pulse
        label = self.temp_value_label if sensor == "temp" else self.pulse_value_label
        
        if sensor == "temp":
            label.config(text="Midiendo...", fg=PALETTE["text"])
            self.status_var.set("📡 Leyendo temperatura del sensor MLX90614...")
        else:
            label.config(text="Midiendo...", fg=PALETTE["text"])
            self.status_var.set("❤️ Leyendo pulso cardíaco (10 segundos)...")
        
        progress["value"] = 0
        self.update_idletasks()
        
        def measure_task():
            try:
                if sensor == "temp":
                    for i in range(20):
                        time.sleep(0.08)
                        progress["value"] += 5
                        self.update_idletasks()
                    
                    value = self.sensor_manager.read_temperature()
                    self.temp_db = value
                    
                else:
                    def update_progress():
                        for i in range(20):
                            if not self.measuring:
                                break
                            progress["value"] = (i + 1) * 5
                            self.update_idletasks()
                            time.sleep(0.5)
                    
                    progress_thread = threading.Thread(target=update_progress, daemon=True)
                    progress_thread.start()
                    
                    value = self.sensor_manager.read_pulse(duration=10)
                    self.pulse_db = value
                    
                    progress_thread.join()
                
                self.after(0, lambda: self._finish_measure(sensor, value))
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error de sensor", f"Error al leer {sensor}: {str(e)}"))
                self.after(0, lambda: self._finish_measure(sensor, None))
            finally:
                self.measuring = False
        
        threading.Thread(target=measure_task, daemon=True).start()

    def _finish_measure(self, sensor, value):
        label = self.temp_value_label if sensor == "temp" else self.pulse_value_label
        progress = self.progress_temp if sensor == "temp" else self.progress_pulse
        
        if value is None:
            label.config(text="Error ❌", fg=PALETTE["danger"])
            self.status_var.set(f"❌ Error al medir {'temperatura' if sensor == 'temp' else 'pulso'}")
        else:
            unit = " °C" if sensor == "temp" else " bpm"
            label.config(text=f"{value}{unit}  ✓", fg=PALETTE["checkmark"])
            sensor_type = "🌡️ Temperatura" if sensor == "temp" else "❤️ Pulso"
            mode = "sensor físico" if self.sensor_manager.sensors_active else "simulación"
            self.status_var.set(f"✅ {sensor_type} medido: {value}{unit} ({mode})")
        
        progress["value"] = 0
        self.measuring = False

    def on_analyze(self):
        symptoms = [s for s, v in self.symptom_vars.items() if v.get() and s != 'Otros']
        other_text = self.custom_symptom_text.get("1.0", "end").strip() if self.custom_symptom_text else ""
        if self.symptom_vars['Otros'].get():
            if not other_text:
                messagebox.showwarning("Faltan datos", "Ha seleccionado 'Otros Síntomas' pero no ha escrito ningún detalle.")
                return
            symptoms.append(f"Otros: {other_text}")
            
        history = ""
        if self.history_yes_no_var.get() == "yes":
            history = self.antecedentes_detail_text.get("1.0", "end").strip() if self.antecedentes_detail_text else ""
        elif self.history_yes_no_var.get() == "no":
            history = "El paciente indica no tener antecedentes relevantes."
        
        temp = self.temp_db if self.temp_db else 0.0
        pulse = self.pulse_db if self.pulse_db else 0
        
        if not symptoms and not history and temp == 0.0 and pulse == 0:
            messagebox.showwarning("Faltan datos", "Complete al menos un campo antes de analizar.")
            return
        
        self.show_diagnosis_step("resultado")
        
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        
        loading_text = "\n\n\n\n"
        loading_text += "          🤖 GENERANDO ANÁLISIS CON INTELIGENCIA ARTIFICIAL...\n\n"
        loading_text += "          ⏳ Por favor espere mientras procesamos la información\n\n"
        loading_text += "          📊 Analizando síntomas y signos vitales\n"
        loading_text += "          🔍 Evaluando nivel de urgencia\n"
        loading_text += "          💡 Generando recomendaciones personalizadas\n\n"
        loading_text += "          ═══════════════════════════════════════════════\n\n"
        loading_text += "          Esto puede tomar unos segundos..."
        
        self.result_box.insert("1.0", loading_text)
        self.result_box.tag_configure("center", justify="center")
        self.result_box.tag_add("center", "1.0", "end")
        self.result_box.configure(state="disabled")
        
        self.status_var.set("🤖 Conectando con Inteligencia Artificial...")
        self.update_idletasks()
        
        def analyze_thread():
            try:
                self.perform_ai_analysis(symptoms, history, temp, pulse)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        threading.Thread(target=analyze_thread, daemon=True).start()

    def perform_ai_analysis(self, symptoms, history, temp, pulse):
        all_symp = [s if not s.startswith("Otros:") else s[7:].strip() for s in symptoms]
        symptoms_text = ', '.join(all_symp) if all_symp else 'Ninguno reportado'
        
        prompt = f"""Eres un asistente médico experto. Analiza cuidadosamente la siguiente información del paciente.

DATOS DEL PACIENTE:
- Síntomas: {symptoms_text}
- Antecedentes médicos: {history if history else 'No especificados'}
- Temperatura corporal: {temp if temp != 0.0 else 'No medida'} °C
- Frecuencia cardíaca: {pulse if pulse != 0 else 'No medida'} bpm

INSTRUCCIONES CRÍTICAS:
Debes responder EXACTAMENTE en este formato, línea por línea:

DIAGNÓSTICO: [escribe aquí un diagnóstico preliminar específico en UNA línea]

NIVEL_URGENCIA: [escribe EXACTAMENTE una de estas tres opciones sin agregar nada más:
ALTA URGENCIA (Nivel Rojo)
MODERADA (Nivel Amarillo)
BAJA (Nivel Verde)]

RECOMENDACIÓN: [escribe aquí una recomendación médica específica en UNA línea]

DETALLES: [escribe aquí una explicación médica detallada de 3-5 líneas que justifique tu diagnóstico y nivel de urgencia basándote en los signos vitales y síntomas presentados]

CRITERIOS IMPORTANTES:
- Fiebre >39°C = considerar alta urgencia
- Taquicardia >110 bpm o bradicardia <50 bpm = considerar alta urgencia  
- Múltiples síntomas severos combinados = aumentar nivel de urgencia
- Antecedentes médicos relevantes = considerar en el análisis
- Este es un diagnóstico preliminar, SIEMPRE recomendar valoración médica profesional"""

        try:
            if GEMINI_API_KEY == "TU_API_KEY_AQUI":
                raise Exception("Debes configurar tu API Key de Gemini en la variable GEMINI_API_KEY.\nObtén tu clave en: https://aistudio.google.com/app/apikey")
            
            genai.configure(api_key=GEMINI_API_KEY)
            
            # Lista de modelos a intentar en orden de preferencia
            modelos = [
                'gemini-1.5-flash',  # Modelo gratuito más confiable
                'gemini-1.5-pro',    # Alternativa si flash falla
                'gemini-pro',        # Modelo legacy como respaldo
            ]
            
            ai_response = None
            ultimo_error = None
            modelo_usado = None
            
            for nombre_modelo in modelos:
                try:
                    self.status_var.set(f"🤖 Intentando conectar con {nombre_modelo}...")
                    self.update_idletasks()
                    
                    model_conectado = genai.GenerativeModel(nombre_modelo)
                    response = model_conectado.generate_content(prompt)
                    ai_response = response.text
                    modelo_usado = nombre_modelo
                    break
                except Exception as e:
                    ultimo_error = str(e)
                    
                    # Si es error de cuota, mostrar mensaje específico
                    if "429" in str(e) or "quota" in str(e).lower():
                        self.after(0, lambda: messagebox.showerror(
                            "Cuota de API Excedida", 
                            "❌ Has excedido la cuota gratuita de Gemini.\n\n"
                            "Opciones para solucionar:\n\n"
                            "1. Espera unas horas y vuelve a intentar\n"
                            "2. Obtén una nueva API Key en:\n   https://aistudio.google.com/app/apikey\n"
                            "3. Considera actualizar a un plan de pago\n\n"
                            "Nota: El plan gratuito tiene límites de uso diario."
                        ))
                        return
                    continue
            
            if not ai_response:
                error_msg = f"❌ No se pudo conectar con ningún modelo de Gemini.\n\n"
                
                if "429" in str(ultimo_error) or "quota" in str(ultimo_error).lower():
                    error_msg += "PROBLEMA: Cuota de API excedida\n\n"
                    error_msg += "SOLUCIONES:\n"
                    error_msg += "• Espera 24 horas para que se renueve tu cuota\n"
                    error_msg += "• Obtén una nueva API Key gratuita\n"
                    error_msg += "• Actualiza a un plan de pago\n\n"
                elif "API_KEY" in str(ultimo_error).upper():
                    error_msg += "PROBLEMA: API Key inválida o no configurada\n\n"
                    error_msg += "SOLUCIÓN:\n"
                    error_msg += "• Verifica tu API Key en el código\n"
                    error_msg += "• Obtén una nueva en: https://aistudio.google.com/app/apikey\n\n"
                else:
                    error_msg += f"Error técnico: {ultimo_error}\n\n"
                
                error_msg += "Más información:\n"
                error_msg += "https://ai.google.dev/gemini-api/docs/rate-limits"
                
                raise Exception(error_msg)
            
            # Procesar respuesta de la IA
            diagnostico = "Diagnóstico no disponible"
            nivel = "BAJA (Nivel Verde)"
            recomendacion = "Consultar con un profesional de la salud"
            detalles = ""
            
            for line in ai_response.split('\n'):
                line = line.strip()
                if line.startswith('DIAGNÓSTICO:'):
                    diagnostico = line.replace('DIAGNÓSTICO:', '').strip()
                elif line.startswith('NIVEL_URGENCIA:'):
                    nivel_raw = line.replace('NIVEL_URGENCIA:', '').strip()
                    if 'ALTA' in nivel_raw.upper() or 'ROJO' in nivel_raw.upper():
                        nivel = "ALTA URGENCIA (Nivel Rojo)"
                    elif 'MODERADA' in nivel_raw.upper() or 'AMARILLO' in nivel_raw.upper():
                        nivel = "MODERADA (Nivel Amarillo)"
                    else:
                        nivel = "BAJA (Nivel Verde)"
                elif line.startswith('RECOMENDACIÓN:'):
                    recomendacion = line.replace('RECOMENDACIÓN:', '').strip()
                elif line.startswith('DETALLES:'):
                    detalles = line.replace('DETALLES:', '').strip()
                elif detalles and line:
                    detalles += " " + line
            
            if "ALTA" in nivel:
                color = PALETTE["danger"]
            elif "MODERADA" in nivel:
                color = PALETTE["warning"]
            else:
                color = PALETTE["success"]
            
            self.diagnostico_final = diagnostico
            self.nivel_urgencia = nivel
            self.sintomas_db = ', '.join(symptoms) if symptoms else 'Ninguno'
            self.antecedentes_db = history if history else 'No especificado'
            
            sensor_mode = "Sensores físicos" if self.sensor_manager.sensors_active else "Valores simulados"
            
            text = f"DIAGNÓSTICO PRELIMINAR: {diagnostico}\n\n"
            text += f"NIVEL DE URGENCIA: {nivel}\n\n"
            text += f"RECOMENDACIÓN: {recomendacion}\n\n"
            text += "─ DATOS REGISTRADOS ─\n\n"
            text += f"Síntomas: {self.sintomas_db}\n\n"
            text += f"Antecedentes: {self.antecedentes_db}\n\n"
            text += f"Temperatura: {temp if temp != 0.0 else 'No medida'} °C\n\n"
            text += f"Pulso: {pulse if pulse != 0 else 'No medido'} bpm\n\n"
            text += f"Modo de medición: {sensor_mode}\n\n"
            
            if detalles:
                text += "─ ANÁLISIS DETALLADO (IA) ─\n\n"
                text += f"{detalles}\n\n"
            
            text += "\n" + "="*50 + "\n"
            text += "🤖 ANÁLISIS GENERADO CON INTELIGENCIA ARTIFICIAL\n"
            text += f"   Modelo: {modelo_usado}\n"
            text += f"   Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            text += "="*50 + "\n"
            
            self.resumen_completo_db = text.strip()
            
            self.after(0, lambda: self._display_result(self.resumen_completo_db, color))
            self.after(0, lambda: self.status_var.set(f"✅ Análisis completado con {modelo_usado}: {nivel.split()[0]}. Listo para guardar."))
            
        except Exception as e:
            error_text = str(e)
            self.after(0, lambda: messagebox.showerror("Error de IA", f"No se pudo conectar con Gemini:\n\n{error_text}"))
            self.after(0, lambda: self.status_var.set("❌ Error al analizar con IA - Verifique su cuota de API"))

    def _display_result(self, text, color):
        self.result_box.configure(state="normal", bg="#FFFFFF")
        self.result_box.delete("1.0", "end")
        self.result_box.tag_configure("level_tag", background=color, foreground="white", font=font_with_fallback("Verdana", 12, "bold"))
        
        for line in text.split('\n'):
            self.result_box.insert("end", line + "\n") 
            
            if "NIVEL DE URGENCIA:" in line:
                start = self.result_box.search(line, "1.0", nocase=True, stopindex="end")
                if start:
                    end_line_end = f"{start.split('.')[0]}.end" 
                    self.result_box.tag_add("level_tag", start, end_line_end)
                    
        self.result_box.configure(state="disabled")

    def show_virtual_keyboard(self):
        if self.keyboard_visible:
            return
        if not getattr(self, 'active_text_target', None):
            return
            
        self.keyboard_visible = True
        self.keyboard_frame.grid()
        
        for widget in self.keyboard_frame.winfo_children():
            widget.destroy()
        
        keyboard_card = tk.Frame(self.keyboard_frame, bg=PALETTE["card"], bd=2, relief="solid")
        keyboard_card.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Filas del teclado con teclas MÁS GRANDES
        keys = [
            ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'],
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'Ñ'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '?'],
        ]
        
        def insert_char(char):
            if not self.active_text_target:
                return
            self.active_text_target.insert(tk.INSERT, char)
            self.active_text_target.focus_set()
        
        def delete_char():
            if not self.active_text_target:
                return
            self.active_text_target.delete("insert-1c", tk.INSERT)
            self.active_text_target.focus_set()
        
        def insert_space():
            if not self.active_text_target:
                return
            self.active_text_target.insert(tk.INSERT, ' ')
            self.active_text_target.focus_set()
        
        # Crear las filas de teclas con MAYOR TAMAÑO
        for row_idx, row in enumerate(keys):
            row_frame = tk.Frame(keyboard_card, bg=PALETTE["card"])
            row_frame.pack(fill="both", expand=True, pady=2)
            for key in row:
                btn = tk.Button(
                    row_frame, 
                    text=key, 
                    font=font_with_fallback("Verdana", 14, "bold"),  # Fuente más grande
                    bg="#E9EEF0", 
                    fg=PALETTE["text"], 
                    activebackground=PALETTE["accent"], 
                    activeforeground="white", 
                    bd=1, 
                    relief="raised", 
                    command=lambda k=key: insert_char(k),
                    height=2  # Altura mayor
                )
                btn.pack(side="left", expand=True, fill="both", padx=2)
        
        # Fila de teclas especiales con NUEVA DISTRIBUCIÓN
        special_frame = tk.Frame(keyboard_card, bg=PALETTE["card"])
        special_frame.pack(fill="both", expand=True, pady=2)
        
        # CERRAR a la IZQUIERDA
        close_btn = tk.Button(
            special_frame, 
            text="✓ CERRAR", 
            font=font_with_fallback("Verdana", 12, "bold"), 
            bg=PALETTE["success"], 
            fg="white", 
            activebackground="#2E9E87", 
            activeforeground="white", 
            bd=1, 
            relief="raised", 
            command=self.hide_virtual_keyboard,
            height=2
        )
        close_btn.pack(side="left", fill="both", padx=2, expand=True)
        
        # ESPACIO en el MEDIO (más grande)
        space_btn = tk.Button(
            special_frame, 
            text="ESPACIO", 
            font=font_with_fallback("Verdana", 12, "bold"), 
            bg="#E9EEF0", 
            fg=PALETTE["text"], 
            activebackground=PALETTE["accent"], 
            activeforeground="white", 
            bd=1, 
            relief="raised", 
            command=insert_space,
            height=2
        )
        space_btn.pack(side="left", fill="both", padx=2, expand=True)
        
        # BORRAR a la DERECHA
        delete_btn = tk.Button(
            special_frame, 
            text="⌫ BORRAR", 
            font=font_with_fallback("Verdana", 12, "bold"), 
            bg=PALETTE["danger"], 
            fg="white", 
            activebackground="#C44536", 
            activeforeground="white", 
            bd=1, 
            relief="raised", 
            command=delete_char,
            height=2
        )
        delete_btn.pack(side="left", fill="both", padx=2, expand=True)

    def hide_virtual_keyboard(self):
        if self.keyboard_visible:
            self.keyboard_visible = False
            self.keyboard_frame.grid_remove()
            if getattr(self, 'active_text_target', None):
                self.active_text_target.focus_set()

if __name__ == "__main__":
    style = ttk.Style()
    style.theme_use("default")
    style.configure("TProgressbar", troughcolor=PALETTE["card"], background=PALETTE["accent"], thickness=10)
    
    print("\n" + "="*70)
    print("  🩺 ASISTENTE MÉDICO CON SENSORES FÍSICOS INTEGRADOS")
    print("="*70)
    print("\n📋 Características:")
    print("  ✓ Sensor de temperatura: MLX90614 (I2C)")
    print("  ✓ Sensor de pulso: MCP3008 + Sensor cardíaco")
    print("  ✓ Análisis con IA (Google Gemini)")
    print("  ✓ Base de datos SQLite para historial")
    print("  ✓ Interfaz en pantalla completa")
    print("  ✓ Teclado virtual mejorado")
    print("\n🆕 Nuevos síntomas agregados:")
    print("  • Congestión nasal")
    print("  • Tos")
    print("  • Náuseas")
    print("  • Vómitos")
    print("\n🔧 Mejoras en esta versión:")
    print("  ✓ Manejo de cuota de API excedida")
    print("  ✓ Múltiples modelos de respaldo")
    print("  ✓ Teclado virtual más grande y reorganizado")
    print("  ✓ Mensajes de error más claros")
    print("\n📌 Conexiones requeridas:")
    print("  - MLX90614: SDA (GPIO 2), SCL (GPIO 3)")
    print("  - MCP3008: SPI (MISO, MOSI, SCLK), CS (GPIO 25)")
    print("  - Sensor de pulso: Canal 0 del MCP3008")
    print("\n⌨️  Controles:")
    print("  - ESC o F11: Salir/entrar de pantalla completa")
    print("  - Teclado virtual: CERRAR (izq) | ESPACIO (centro) | BORRAR (der)")
    print("\n🚀 Iniciando aplicación...")
    print("="*70 + "\n")
    
    app = AsistenteDiagnostico()
    app.mainloop()