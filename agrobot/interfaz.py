import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .busqueda import ALGORITMOS, REQUIERE_COSTO
from .mundo import (AVIONETA, CULTIVO, DEPOSITO, MURO, Mundo, MundoError, SIN_SUBIR)

TAM = 52  # lado de cada casilla en píxeles
COL_MURO, COL_LIBRE = "#808080", "#ffffff"
COL_ROBOT, COL_SECO, COL_TRATADO = "#2a7fff", "#c9792b", "#2e9e4f"
COL_DEPOSITO, COL_AVIONETA = "#3b8b3b", "#6ec1e4"
FLECHAS = {"Arriba": "↑", "Abajo": "↓", "Izquierda": "←", "Derecha": "→"}


class App:
    def __init__(self, raiz, ruta_inicial=None):
        self.raiz = raiz
        raiz.title("AgroBot - Proyecto 1 de Inteligencia Artificial")
        self.mundo = None
        self.resultado = None
        self.cola = queue.Queue()
        self.paso = 0
        self.job = None

        marco = ttk.Frame(raiz, padding=8)
        marco.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(marco, width=10 * TAM, height=10 * TAM,
                                bg="#dddddd", highlightthickness=1, highlightbackground="#555")
        self.canvas.grid(row=0, column=0, rowspan=2, sticky="n")

        panel = ttk.Frame(marco, padding=(10, 0))
        panel.grid(row=0, column=1, sticky="n")
        marco.columnconfigure(1, weight=1)

        ttk.Button(panel, text="Cargar mundo (.txt)", command=self.cargar).pack(fill="x", pady=2)
        self.lbl_archivo = ttk.Label(panel, text="Ningún archivo cargado", foreground="#555")
        self.lbl_archivo.pack(fill="x")

        ttk.Label(panel, text="Tipo de búsqueda").pack(anchor="w", pady=(10, 0))
        self.tipo = ttk.Combobox(panel, state="readonly", values=list(ALGORITMOS), width=30)
        self.tipo.pack(fill="x")
        self.tipo.bind("<<ComboboxSelected>>", self._cambio_tipo)

        ttk.Label(panel, text="Algoritmo").pack(anchor="w", pady=(8, 0))
        self.alg = ttk.Combobox(panel, state="readonly", width=30)
        self.alg.pack(fill="x")
        self.tipo.current(0)
        self._cambio_tipo()

        self.btn_ejecutar = ttk.Button(panel, text="Ejecutar búsqueda", command=self.ejecutar)
        self.btn_ejecutar.pack(fill="x", pady=(12, 2))
        self.btn_repetir = ttk.Button(panel, text="Repetir animación", command=self.animar,
                                      state="disabled")
        self.btn_repetir.pack(fill="x", pady=2)

        ttk.Label(panel, text="Velocidad de la animación").pack(anchor="w", pady=(8, 0))
        self.vel = tk.Scale(panel, from_=20, to=600, orient="horizontal", showvalue=False)
        self.vel.set(150)
        self.vel.pack(fill="x")
        ttk.Label(panel, text="(izquierda = rápido, derecha = lento)", foreground="#666").pack()

        self.estado_var = tk.StringVar(value="Cargue un mundo para empezar.")
        ttk.Label(marco, textvariable=self.estado_var, font=("TkDefaultFont", 10, "bold"),
                  wraplength=700).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(marco, text="Reporte").grid(row=1, column=1, sticky="sw", padx=10)
        cont = ttk.Frame(marco)
        cont.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(2, 0))
        marco.rowconfigure(3, weight=1)
        self.reporte = tk.Text(cont, height=11, width=90, state="disabled", wrap="word",
                               font=("Courier", 10))
        sb = ttk.Scrollbar(cont, command=self.reporte.yview)
        self.reporte.configure(yscrollcommand=sb.set)
        self.reporte.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._leyenda(marco).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        if ruta_inicial:
            self._abrir(ruta_inicial)
        self.raiz.after(100, self._revisar_cola)

    # ------------------------------------------------------------------
    def _leyenda(self, padre):
        f = ttk.Frame(padre)
        items = [(COL_ROBOT, "AgroBot"), (COL_SECO, "Cultivo seco"), (COL_TRATADO, "Cultivo tratado"),
                 (COL_DEPOSITO, "Depósito"), (COL_AVIONETA, "Avioneta"), (COL_MURO, "Muro")]
        for color, texto in items:
            tk.Label(f, bg=color, width=2).pack(side="left", padx=(8, 2))
            ttk.Label(f, text=texto).pack(side="left")
        return f

    def _cambio_tipo(self, _evento=None):
        nombres = list(ALGORITMOS[self.tipo.get()])
        self.alg.configure(values=nombres)
        self.alg.current(0)

    # ------------------------------------------------------------------
    # Carga del mundo
    # ------------------------------------------------------------------
    def cargar(self):
        ruta = filedialog.askopenfilename(title="Seleccione el archivo del mundo",
                                          filetypes=[("Texto", "*.txt"), ("Todos", "*.*")])
        if ruta:
            self._abrir(ruta)

    def _abrir(self, ruta):
        try:
            self.mundo = Mundo.desde_archivo(ruta)
        except (MundoError, OSError) as e:
            messagebox.showerror("Archivo no válido", str(e))
            return
        self._detener()
        self.resultado = None
        self.btn_repetir.configure(state="disabled")
        self.lbl_archivo.configure(text=ruta.replace("\\", "/").split("/")[-1])
        self.canvas.configure(width=self.mundo.cols * TAM, height=self.mundo.filas * TAM)
        self._escribir("")
        self.dibujar()
        self.estado_var.set(f"Mundo cargado: {self.mundo.filas}x{self.mundo.cols}, "
                            f"{self.mundo.n_cultivos} cultivo(s) seco(s). Estado inicial.")

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def dibujar(self, estado=None):
        m = self.mundo
        cv = self.canvas
        cv.delete("all")
        if m is None:
            return
        if estado is None:
            estado = m.estado_inicial()
        fila, col, fert, mask, fuel = estado
        for r in range(m.filas):
            for c in range(m.cols):
                x0, y0 = c * TAM, r * TAM
                x1, y1 = x0 + TAM, y0 + TAM
                v = m.matriz[r][c]
                cv.create_rectangle(x0, y0, x1, y1, fill=COL_MURO if v == MURO else COL_LIBRE,
                                    outline="#444")
                if v == DEPOSITO:
                    cv.create_rectangle(x0 + 12, y0 + 8, x1 - 12, y1 - 8, fill=COL_DEPOSITO,
                                        outline="#1f4f1f", width=2)
                    cv.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="F", fill="white",
                                   font=("TkDefaultFont", 16, "bold"))
                elif v == AVIONETA and fuel == SIN_SUBIR:
                    self._avioneta(x0, y0)
                elif v == CULTIVO:
                    tratado = (mask >> m.indice_cultivo[(r, c)]) & 1
                    color = COL_TRATADO if tratado else COL_SECO
                    cv.create_polygon(x0 + 8, y1 - 8, x1 - 8, y1 - 8, (x0 + x1) / 2, y0 + 8,
                                      fill=color, outline="#333")
                    cv.create_text((x0 + x1) / 2, y1 - 17, text="✓" if tratado else "",
                                   fill="white", font=("TkDefaultFont", 12, "bold"))
        # Robot
        x0, y0 = col * TAM, fila * TAM
        if fuel > 0:                       # va montado en la avioneta
            self._avioneta(x0, y0)
        cv.create_oval(x0 + 12, y0 + 12, x0 + TAM - 12, y0 + TAM - 12, fill=COL_ROBOT,
                       outline="#0b2d66", width=2)
        cv.create_text(x0 + TAM / 2, y0 + TAM / 2, text="R", fill="white",
                       font=("TkDefaultFont", 13, "bold"))

    def _avioneta(self, x0, y0):
        cx, cy = x0 + TAM / 2, y0 + TAM / 2
        pts = [cx - 20, cy, cx, cy - 6, cx + 20, cy, cx, cy + 6]      # fuselaje + alas
        self.canvas.create_polygon(*pts, fill=COL_AVIONETA, outline="#1b6f93", width=2)
        self.canvas.create_polygon(cx - 4, cy - 16, cx + 4, cy - 16, cx + 2, cy + 16, cx - 2, cy + 16,
                                   fill=COL_AVIONETA, outline="#1b6f93")

    # ------------------------------------------------------------------
    # Ejecución de la búsqueda (en un hilo para no congelar la ventana)
    # ------------------------------------------------------------------
    def ejecutar(self):
        if self.mundo is None:
            messagebox.showinfo("AgroBot", "Primero cargue un archivo de mundo.")
            return
        self._detener()
        nombre = self.alg.get()
        funcion = ALGORITMOS[self.tipo.get()][nombre]
        self.btn_ejecutar.configure(state="disabled")
        self.btn_repetir.configure(state="disabled")
        self.estado_var.set(f"Ejecutando {nombre}...")
        self.dibujar()
        mundo = self.mundo
        threading.Thread(target=lambda: self.cola.put(funcion(mundo)), daemon=True).start()

    def _revisar_cola(self):
        try:
            res = self.cola.get_nowait()
        except queue.Empty:
            pass
        else:
            self._mostrar_resultado(res)
        self.raiz.after(100, self._revisar_cola)

    def _mostrar_resultado(self, res):
        self.resultado = res
        self.btn_ejecutar.configure(state="normal")
        lineas = [f"Algoritmo: {res.algoritmo}",
                  f"Resultado: {res.mensaje}",
                  f"Nodos expandidos:      {res.expandidos}",
                  f"Profundidad del árbol: {res.prof_arbol}",
                  f"Tiempo de cómputo:     {res.tiempo * 1000:.2f} ms"]
        if res.encontrado:
            etiqueta = "Costo de la solución:  " if res.algoritmo in REQUIERE_COSTO \
                else "Costo de la solución (informativo): "
            lineas.append(f"{etiqueta}{res.costo:g}")
            lineas.append(f"Pasos de la solución:  {res.prof_solucion}")
            lineas.append("Movimientos: " + " ".join(FLECHAS[o] for o in res.operadores))
        self._escribir("\n".join(lineas))
        if res.encontrado:
            self.btn_repetir.configure(state="normal")
            self.animar()
        else:
            self.estado_var.set(res.mensaje)

    def _escribir(self, texto):
        self.reporte.configure(state="normal")
        self.reporte.delete("1.0", "end")
        self.reporte.insert("end", texto)
        self.reporte.configure(state="disabled")

    # ------------------------------------------------------------------
    # Animación
    # ------------------------------------------------------------------
    def _detener(self):
        if self.job is not None:
            self.raiz.after_cancel(self.job)
            self.job = None

    def animar(self):
        if not self.resultado or not self.resultado.encontrado:
            return
        self._detener()
        self.paso = 0
        self._siguiente_paso()

    def _siguiente_paso(self):
        res = self.resultado
        e = res.estados[self.paso]
        self.dibujar(e)
        fuel = e[4]
        comb = "sin abordar" if fuel == SIN_SUBIR else f"{max(fuel, 0)} mov."
        self.estado_var.set(f"{res.algoritmo} | paso {self.paso}/{len(res.estados) - 1} | "
                            f"fertilizante: {e[2]} | combustible avioneta: {comb} | "
                            f"costo acumulado: {res.costos_acum[self.paso]:g}")
        if self.paso < len(res.estados) - 1:
            self.paso += 1
            self.job = self.raiz.after(self.vel.get(), self._siguiente_paso)
        else:
            self.job = None
            self.estado_var.set(self.estado_var.get() + "  — ¡Todos los cultivos tratados!")


def iniciar(ruta_inicial=None):
    raiz = tk.Tk()
    App(raiz, ruta_inicial)
    raiz.mainloop()
