#!/usr/bin/env python3
import argparse
import sys

from agrobot.busqueda import ALGORITMOS, REQUIERE_COSTO
from agrobot.mundo import Mundo, MundoError

CLAVES = {
    "amplitud": "Amplitud",
    "costo": "Costo uniforme",
    "profundidad": "Profundidad evitando ciclos",
    "avara": "Avara",
    "astar": "A*",
}
FLECHAS = {"Arriba": "↑", "Abajo": "↓", "Izquierda": "←", "Derecha": "→"}


def buscar(nombre):
    for grupo in ALGORITMOS.values():
        if nombre in grupo:
            return grupo[nombre]


def reporte(res, ver_movimientos):
    print(f"Algoritmo: {res.algoritmo}")
    print(f"  Resultado:             {res.mensaje}")
    print(f"  Nodos expandidos:      {res.expandidos}")
    print(f"  Profundidad del árbol: {res.prof_arbol}")
    print(f"  Tiempo de cómputo:     {res.tiempo * 1000:.2f} ms")
    if res.encontrado:
        extra = "" if res.algoritmo in REQUIERE_COSTO else " (informativo)"
        print(f"  Costo de la solución:  {res.costo:g}{extra}")
        print(f"  Pasos de la solución:  {res.prof_solucion}")
        if ver_movimientos:
            print("  Movimientos: " + " ".join(FLECHAS[o] for o in res.operadores))
    print()


def main():
    ap = argparse.ArgumentParser(description="AgroBot - búsqueda en un terreno de cultivo")
    ap.add_argument("mundo", nargs="?", help="archivo .txt con el mundo")
    ap.add_argument("--cli", action="store_true", help="ejecutar en la terminal, sin ventana")
    ap.add_argument("--algoritmo", choices=list(CLAVES) + ["todos"], default="todos")
    ap.add_argument("--movimientos", action="store_true", help="imprimir la secuencia de movimientos")
    args = ap.parse_args()

    if not args.cli:
        from agrobot.interfaz import iniciar
        iniciar(args.mundo)
        return
    if not args.mundo:
        ap.error("con --cli debe indicar el archivo del mundo")
    try:
        mundo = Mundo.desde_archivo(args.mundo)
    except (MundoError, OSError) as e:
        sys.exit(f"Error: {e}")
    print(f"Mundo {mundo.filas}x{mundo.cols} | cultivos secos: {mundo.n_cultivos}\n")
    nombres = list(CLAVES.values()) if args.algoritmo == "todos" else [CLAVES[args.algoritmo]]
    for nombre in nombres:
        reporte(buscar(nombre)(mundo), args.movimientos)


if __name__ == "__main__":
    main()
