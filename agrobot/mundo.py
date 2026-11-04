"""Modelo del problema AgroBot.

Representación del estado (tupla inmutable, apta como llave de diccionario):

    estado = (fila, columna, fertilizante, mascara, combustible)

* fila, columna : posición actual del robot.
* fertilizante  : unidades que lleva el robot (0, 1 o 2).
* mascara       : entero; el bit i vale 1 si el cultivo seco i ya fue tratado.
* combustible   : estado de la avioneta
                    -1      -> el robot aún no se ha subido a la avioneta
                    1..30   -> va en la avioneta y quedan esos movimientos baratos
                    0       -> el combustible se agotó (todo movimiento cuesta 1)
"""
from collections import deque

# Códigos del archivo de texto
LIBRE, MURO, ROBOT, CULTIVO, DEPOSITO, AVIONETA = 0, 1, 2, 3, 4, 5

CARGA_MAX = 2          # unidades de fertilizante que puede llevar
COMBUSTIBLE_INICIAL = 30
SIN_SUBIR = -1         # valor de "combustible" antes de abordar la avioneta
INF = 10 ** 9

# Operadores: (nombre, delta_fila, delta_columna). El orden fija el desempate.
OPERADORES = (
    ("Arriba", -1, 0),
    ("Abajo", 1, 0),
    ("Izquierda", 0, -1),
    ("Derecha", 0, 1),
)


class MundoError(Exception):
    """Error de formato o de contenido en el archivo del mundo."""


class Mundo:
    def __init__(self, matriz):
        self.matriz = [list(f) for f in matriz]
        self.filas = len(self.matriz)
        self.cols = len(self.matriz[0]) if self.filas else 0
        self._validar()

        self.inicio = None
        self.deposito = None
        self.avioneta = None
        self.cultivos = []                 # lista de (fila, col); índice = bit
        self.indice_cultivo = {}           # (fila, col) -> índice de bit
        for r in range(self.filas):
            for c in range(self.cols):
                v = self.matriz[r][c]
                if v == ROBOT:
                    self.inicio = (r, c)
                elif v == DEPOSITO:
                    self.deposito = (r, c)
                elif v == AVIONETA:
                    self.avioneta = (r, c)
                elif v == CULTIVO:
                    self.indice_cultivo[(r, c)] = len(self.cultivos)
                    self.cultivos.append((r, c))
        self.n_cultivos = len(self.cultivos)
        self.mascara_meta = (1 << self.n_cultivos) - 1
        self._precalcular_distancias()

    # ----------------------------
    # Carga y validación
    # ----------------------------
    @classmethod
    def desde_texto(cls, texto):
        matriz = []
        for n, linea in enumerate(texto.strip().splitlines(), start=1):
            if not linea.strip():
                continue
            try:
                fila = [int(x) for x in linea.split()]
            except ValueError:
                raise MundoError(f"Línea {n}: solo se permiten enteros separados por espacios.")
            matriz.append(fila)
        if not matriz:
            raise MundoError("El archivo está vacío.")
        return cls(matriz)

    @classmethod
    def desde_archivo(cls, ruta):
        with open(ruta, "r", encoding="utf-8-sig") as f:
            return cls.desde_texto(f.read())

    def _validar(self):
        if any(len(f) != self.cols for f in self.matriz):
            raise MundoError("Todas las filas deben tener la misma cantidad de columnas.")
        cuenta = {k: 0 for k in range(6)}
        for fila in self.matriz:
            for v in fila:
                if v not in cuenta:
                    raise MundoError(f"Valor no válido en la matriz: {v} (se permiten 0 a 5).")
                cuenta[v] += 1
        if cuenta[ROBOT] != 1:
            raise MundoError("Debe haber exactamente un AgroBot (valor 2).")
        if cuenta[DEPOSITO] > 1 or cuenta[AVIONETA] > 1:
            raise MundoError("Solo puede haber un depósito (4) y una avioneta (5).")
        if cuenta[CULTIVO] > 0 and cuenta[DEPOSITO] == 0:
            raise MundoError("Hay cultivos secos pero no hay depósito de fertilizante (4).")

    # ------------------------------------------------------------------
    # Distancias reales en la cuadrícula (se usan en la heurística)
    # ------------------------------------------------------------------
    def _bfs(self, origen):
        dist = [INF] * (self.filas * self.cols)
        dist[origen[0] * self.cols + origen[1]] = 0
        cola = deque([origen])
        while cola:
            r, c = cola.popleft()
            d = dist[r * self.cols + c]
            for _, dr, dc in OPERADORES:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.filas and 0 <= nc < self.cols and self.matriz[nr][nc] != MURO:
                    k = nr * self.cols + nc
                    if dist[k] == INF:
                        dist[k] = d + 1
                        cola.append((nr, nc))
        return dist

    def _precalcular_distancias(self):
        """dist_a[k][celda] = distancia mínima (en movimientos, ignorando
        combustible y fertilizante) entre la celda y el punto clave k.
        Puntos clave: cultivos 0..n-1, depósito (n) y avioneta (n+1)."""
        self.puntos_clave = list(self.cultivos)
        self.k_deposito = self.k_avioneta = None
        if self.deposito:
            self.k_deposito = len(self.puntos_clave)
            self.puntos_clave.append(self.deposito)
        if self.avioneta:
            self.k_avioneta = len(self.puntos_clave)
            self.puntos_clave.append(self.avioneta)
        self.dist_a = [self._bfs(p) for p in self.puntos_clave]

    # ------------------------------------------------------------------
    # Problema de búsqueda
    # ------------------------------------------------------------------
    def estado_inicial(self):
        return (self.inicio[0], self.inicio[1], 0, 0, SIN_SUBIR)

    def es_meta(self, estado):
        return estado[3] == self.mascara_meta

    @staticmethod
    def costo_movimiento(estado):
        """Costo de dar un paso estando en 'estado' (1/2 si hay combustible)."""
        return 0.5 if estado[4] > 0 else 1.0

    def sucesores(self, estado):
        """Genera (operador, nuevo_estado, costo) para cada movimiento válido."""
        r, c, fert, mask, fuel = estado
        costo = 0.5 if fuel > 0 else 1.0
        for nombre, dr, dc in OPERADORES:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < self.filas and 0 <= nc < self.cols):
                continue
            celda = self.matriz[nr][nc]
            if celda == MURO:
                continue
            nfert, nmask = fert, mask
            nfuel = fuel - 1 if fuel > 0 else fuel
            if celda == AVIONETA and fuel == SIN_SUBIR:
                nfuel = COMBUSTIBLE_INICIAL            # se sube automáticamente
            elif celda == DEPOSITO:
                nfert = CARGA_MAX                      # recarga automática
            elif celda == CULTIVO:
                i = self.indice_cultivo[(nr, nc)]
                if nfert > 0 and not (mask >> i) & 1:  # trata el cultivo seco
                    nfert -= 1
                    nmask |= 1 << i
            yield nombre, (nr, nc, nfert, nmask, nfuel), costo
