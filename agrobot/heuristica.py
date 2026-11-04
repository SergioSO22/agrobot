"""Heurística de AgroBot (admisible).

Idea: se relaja el problema quitando muros "dinámicos" de costo, es decir, se
ignora cuánto fertilizante hay que repartir y se acota por abajo el NÚMERO de
movimientos que faltan; luego ese número se convierte en costo según la
situación de la avioneta.

1. Conjunto obligatorio S de puntos que el robot debe visitar todavía:
     * cada cultivo seco sin tratar
     * el depósito, si el fertilizante que lleva es menor que el número de
       cultivos pendientes (tiene que reabastecerse al menos una vez)
2. Cota de movimientos LB(p, S), con d = distancia real en la cuadrícula
   (BFS que respeta los muros):
       LB = max( max_{x in S} d(p, x),
                 max_{a,b in S} [ min(d(p,a), d(p,b)) + d(a,b) ] )
3. Conversión a costo (cada movimiento cuesta como mínimo 1/2):
     * va en la avioneta con k pasos de combustible:
           h = 0.5 * min(LB, k) + (LB - min(LB, k))
     * combustible agotado:               h = LB
     * aún no abordó la avioneta:
           h = min( LB(S),  0.5 * LB(S U {avioneta}) )
"""
from .mundo import INF, SIN_SUBIR


class Heuristica:
    def __init__(self, mundo):
        self.m = mundo
        self._cache = {}

    # Cota inferior del número de movimientos para visitar todos los destinos
    def _cota_movimientos(self, celda, destinos):
        m = self.m
        d = [m.dist_a[k][celda] for k in destinos]
        if any(x >= INF for x in d):
            return INF
        mejor = max(d)
        n = len(destinos)
        for i in range(n):
            ki = destinos[i]
            for j in range(i + 1, n):
                kj = destinos[j]
                dij = m.dist_a[ki][m.puntos_clave[kj][0] * m.cols + m.puntos_clave[kj][1]]
                if dij >= INF:
                    return INF
                v = (d[i] if d[i] < d[j] else d[j]) + dij
                if v > mejor:
                    mejor = v
        return mejor

    def __call__(self, estado):
        h = self._cache.get(estado)
        if h is not None:
            return h
        m = self.m
        r, c, fert, mask, fuel = estado
        pendientes = [i for i in range(m.n_cultivos) if not (mask >> i) & 1]
        if not pendientes:
            self._cache[estado] = 0.0
            return 0.0
        destinos = list(pendientes)
        if fert < len(pendientes) and m.k_deposito is not None:
            destinos.append(m.k_deposito)
        celda = r * m.cols + c
        lb = self._cota_movimientos(celda, destinos)
        if lb >= INF:
            h = float("inf")
        elif fuel > 0:
            baratos = min(lb, fuel)
            h = 0.5 * baratos + (lb - baratos)
        elif fuel == SIN_SUBIR and m.k_avioneta is not None:
            lb_av = self._cota_movimientos(celda, destinos + [m.k_avioneta])
            h = min(float(lb), 0.5 * lb_av)
        else:
            h = float(lb)
        self._cache[estado] = h
        return h
