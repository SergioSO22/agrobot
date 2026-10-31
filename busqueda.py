"""Algoritmos de búsqueda para AgroBot.

Control de ciclos
-----------------
* Amplitud, Profundidad y Avara usan una llave reducida del estado
  (fila, col, fertilizante, máscara, fase_avioneta). No incluye el número exacto
  de pasos de combustible, de modo que ir y venir en la avioneta no es un
  estado nuevo (es un ciclo). En cambio, volver a una casilla sí se permite
  cuando algo cambió: se subió a la avioneta, recargó en el depósito o trató
  un cultivo (cambia fase, fertilizante o máscara).
* Costo uniforme y A* usan el estado completo (con combustible) porque el costo
  depende de él, así se conserva la optimalidad. Un estado se reabre solo si se
  encuentra con menor costo g.
"""
import heapq
import time
from collections import deque
from dataclasses import dataclass, field

from .heuristica import Heuristica

LIMITE_NODOS = 3_000_000


class Nodo:
    __slots__ = ("estado", "padre", "op", "g", "prof")

    def __init__(self, estado, padre, op, g, prof):
        self.estado, self.padre, self.op, self.g, self.prof = estado, padre, op, g, prof


@dataclass
class Resultado:
    algoritmo: str
    encontrado: bool = False
    mensaje: str = ""
    estados: list = field(default_factory=list)      # estados desde el inicial hasta la meta
    operadores: list = field(default_factory=list)
    costos_acum: list = field(default_factory=list)
    costo: float = 0.0
    expandidos: int = 0
    prof_arbol: int = 0
    prof_solucion: int = 0
    tiempo: float = 0.0


def clave_reducida(e):
    f = e[4]
    return (e[0], e[1], e[2], e[3], 0 if f < 0 else (1 if f > 0 else 2))


def _armar(nombre, nodo, expandidos, prof_max, t0, mensaje=""):
    res = Resultado(nombre, expandidos=expandidos, prof_arbol=prof_max,
                    tiempo=time.perf_counter() - t0, mensaje=mensaje)
    if nodo is None:
        res.mensaje = mensaje or "No existe solución."
        return res
    estados, ops, costos = [], [], []
    n = nodo
    while n is not None:
        estados.append(n.estado)
        costos.append(n.g)
        if n.op:
            ops.append(n.op)
        n = n.padre
    estados.reverse(); ops.reverse(); costos.reverse()
    base = costos[0]
    res.encontrado = True
    res.estados, res.operadores = estados, ops
    res.costos_acum = [c - base for c in costos]
    res.costo = nodo.g - base
    res.prof_solucion = nodo.prof
    res.mensaje = mensaje or "Solución encontrada."
    return res


# ----------------------------------------------------------------------
# No informadas
# ----------------------------------------------------------------------
def amplitud(mundo, inicial=None):
    t0 = time.perf_counter()
    ini = inicial or mundo.estado_inicial()
    frontera = deque([Nodo(ini, None, None, 0.0, 0)])
    vistos = {clave_reducida(ini)}
    exp = prof_max = 0
    while frontera:
        n = frontera.popleft()
        if mundo.es_meta(n.estado):
            return _armar("Amplitud", n, exp, prof_max, t0)
        exp += 1
        if exp > LIMITE_NODOS:
            return _armar("Amplitud", None, exp, prof_max, t0, "Límite de nodos excedido.")
        for op, ns, c in mundo.sucesores(n.estado):
            k = clave_reducida(ns)
            if k in vistos:
                continue
            vistos.add(k)
            frontera.append(Nodo(ns, n, op, n.g + c, n.prof + 1))
            prof_max = max(prof_max, n.prof + 1)
    return _armar("Amplitud", None, exp, prof_max, t0)


def costo_uniforme(mundo, inicial=None):
    t0 = time.perf_counter()
    ini = inicial or mundo.estado_inicial()
    cont = 0
    heap = [(0.0, cont, Nodo(ini, None, None, 0.0, 0))]
    mejor = {ini: 0.0}
    exp = prof_max = 0
    while heap:
        g, _, n = heapq.heappop(heap)
        if g > mejor.get(n.estado, float("inf")):
            continue                       # entrada obsoleta
        if mundo.es_meta(n.estado):
            return _armar("Costo uniforme", n, exp, prof_max, t0)
        exp += 1
        if exp > LIMITE_NODOS:
            return _armar("Costo uniforme", None, exp, prof_max, t0, "Límite de nodos excedido.")
        for op, ns, c in mundo.sucesores(n.estado):
            ng = g + c
            if ng < mejor.get(ns, float("inf")):
                mejor[ns] = ng
                cont += 1
                heapq.heappush(heap, (ng, cont, Nodo(ns, n, op, ng, n.prof + 1)))
                prof_max = max(prof_max, n.prof + 1)
    return _armar("Costo uniforme", None, exp, prof_max, t0)


def profundidad(mundo, inicial=None):
    """Profundidad evitando ciclos (búsqueda en grafo con lista de visitados)."""
    t0 = time.perf_counter()
    ini = inicial or mundo.estado_inicial()
    pila = [Nodo(ini, None, None, 0.0, 0)]
    vistos = set()
    exp = prof_max = 0
    while pila:
        n = pila.pop()
        k = clave_reducida(n.estado)
        if k in vistos:
            continue
        vistos.add(k)
        if mundo.es_meta(n.estado):
            return _armar("Profundidad evitando ciclos", n, exp, prof_max, t0)
        exp += 1
        if exp > LIMITE_NODOS:
            return _armar("Profundidad evitando ciclos", None, exp, prof_max, t0,
                          "Límite de nodos excedido.")
        hijos = list(mundo.sucesores(n.estado))
        for op, ns, c in reversed(hijos):      # el primer operador se explora primero
            if clave_reducida(ns) not in vistos:
                pila.append(Nodo(ns, n, op, n.g + c, n.prof + 1))
                prof_max = max(prof_max, n.prof + 1)
    return _armar("Profundidad evitando ciclos", None, exp, prof_max, t0)


# ----------------------------------------------------------------------
# Informadas
# ----------------------------------------------------------------------
def avara(mundo, inicial=None):
    t0 = time.perf_counter()
    ini = inicial or mundo.estado_inicial()
    h = Heuristica(mundo)
    cont = 0
    heap = [(h(ini), cont, Nodo(ini, None, None, 0.0, 0))]
    vistos = set()
    exp = prof_max = 0
    while heap:
        _, _, n = heapq.heappop(heap)
        k = clave_reducida(n.estado)
        if k in vistos:
            continue
        vistos.add(k)
        if mundo.es_meta(n.estado):
            return _armar("Avara", n, exp, prof_max, t0)
        exp += 1
        if exp > LIMITE_NODOS:
            return _armar("Avara", None, exp, prof_max, t0, "Límite de nodos excedido.")
        for op, ns, c in mundo.sucesores(n.estado):
            if clave_reducida(ns) in vistos:
                continue
            hn = h(ns)
            if hn == float("inf"):
                continue
            cont += 1
            heapq.heappush(heap, (hn, cont, Nodo(ns, n, op, n.g + c, n.prof + 1)))
            prof_max = max(prof_max, n.prof + 1)
    return _armar("Avara", None, exp, prof_max, t0)


def a_estrella(mundo, inicial=None):
    t0 = time.perf_counter()
    ini = inicial or mundo.estado_inicial()
    h = Heuristica(mundo)
    cont = 0
    h0 = h(ini)
    heap = [(h0, h0, cont, Nodo(ini, None, None, 0.0, 0))]
    mejor = {ini: 0.0}
    exp = prof_max = 0
    while heap:
        _, _, _, n = heapq.heappop(heap)
        if n.g > mejor.get(n.estado, float("inf")):
            continue
        if mundo.es_meta(n.estado):
            return _armar("A*", n, exp, prof_max, t0)
        exp += 1
        if exp > LIMITE_NODOS:
            return _armar("A*", None, exp, prof_max, t0, "Límite de nodos excedido.")
        for op, ns, c in mundo.sucesores(n.estado):
            ng = n.g + c
            if ng < mejor.get(ns, float("inf")):
                hn = h(ns)
                if hn == float("inf"):
                    continue
                mejor[ns] = ng
                cont += 1
                heapq.heappush(heap, (ng + hn, hn, cont, Nodo(ns, n, op, ng, n.prof + 1)))
                prof_max = max(prof_max, n.prof + 1)
    return _armar("A*", None, exp, prof_max, t0)


ALGORITMOS = {
    "No informada": {
        "Amplitud": amplitud,
        "Costo uniforme": costo_uniforme,
        "Profundidad evitando ciclos": profundidad,
    },
    "Informada": {
        "Avara": avara,
        "A*": a_estrella,
    },
}
REQUIERE_COSTO = ("Costo uniforme", "A*")   # algoritmos para los que el reporte exige el costo
