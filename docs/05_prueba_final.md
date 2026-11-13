# La prueba final: enero a junio de 2025

Con la regla con previsión en los tres productos, el sistema habría costado 31.367 € menos, en mediana, que lo que costó
de verdad el semestre: 40.707 €. Frente a la regla actual, con los mismos plazos, el sistema baja el coste en B y en C;
en A cuesta prácticamente lo mismo.

## Lo que estaba fijado antes de abrirla

Modelo, stock de seguridad, objetivo de servicio, plazos que se sortean, arranque y criterio de comparación se fijaron
con 2023 y 2024. Enero a junio de 2025 no se usó para nada de eso.

- **Arranque:** el stock al cierre del 31/12/2024 y los dos pedidos que seguían en camino, que toman el primer plazo de
  cada sorteo.
- **Previsión:** el modelo reentrenado con 2023 y 2024.
- **Criterio, producto a producto:** la regla con previsión si es buena frente a la actual y frente a la corregida; si
  no, la corregida si es buena frente a la actual; si no, la actual.

## Antes de comparar, la reproducción

Con la regla actual y los plazos reales de 2025, el simulador da lo que registró el sistema en los 181 días de los tres
productos. Su coste del semestre, 40.707 €, es lo que costó de verdad.

## La comparación de cada producto

Diferencia entre el coste del semestre de cada regla y el de la actual, con los mismos plazos. Se da la mediana de los
200 sorteos y la banda entre los percentiles 5 y 95:

| Producto | Regla con previsión | Regla corregida | Lo que elige el criterio |
|---|---|---|---|
| A | +10 € (de −841 a +35) | −55 € (de −820 a +50) | la actual: ninguna baja el coste con toda la banda |
| B | −3.715 € (de −8.277 a −746) | −3.676 € (de −8.264 a −758) | la corregida |
| C | −42.964 € (de −76.881 a −16.402) | −42.632 € (de −76.316 a −16.354) | la regla con previsión |

En B la regla con previsión baja el coste frente a la actual con toda la banda, pero no se puede afirmar que sea mejor
que la corregida. En C lo hace frente a las dos. La elección no cambia con un coste de mantener del 15 % ni del 40 %.

## Una sola regla para todos los productos

Aplicar en cada producto la regla que elige el criterio obliga a mantener una regla distinta por producto, escrita a
mano, que nada vuelve a revisar. Con muchos productos, eso no se mantiene por sí solo. Por eso, después de esta prueba,
se decidió usar en todos los productos la regla con previsión.

Es la regla que el criterio elige en C, la que más baja el coste en B y la que en A deja el coste prácticamente igual
que la regla actual. En A el proveedor tarda de media 7 días, que es lo que promete.

## El sistema frente a la regla actual

En los tres productos juntos, con los mismos plazos:

- el coste del semestre baja 47.374 € de mediana, con una banda de 19.818 € a 83.090 €;
- el fill rate sube 4,8 puntos;
- los días sin stock bajan 46, sumando los tres productos;
- el stock medio sube 17.444 €, valorado al coste.

Frente a lo que costó de verdad (40.707 €), el sistema habría costado 31.367 € menos, en mediana, con una banda de
25.933 € a 32.371 €. De ese ahorro, 25.024 € corresponden a C.

El ahorro frente a la regla actual con los mismos plazos es mayor porque, en el semestre real, la regla actual costó
menos que en la mayoría de los 200 sorteos.

## Límites

- La regla única se decidió después de ver la prueba final, así que la prueba no es una comprobación a ciegas de esa
  regla. Sí estaba fijado antes todo lo que usa la regla: el modelo, el stock de seguridad y el objetivo de cada
  producto.
- El sistema frente al coste real no es una diferencia emparejada: el coste real sale de una sola serie de plazos y se
  resta a cada uno de los 200 sorteos. Incluye el azar del plazo: en A cuesta 732 € menos que lo real, aunque comparado
  con la regla actual con los mismos plazos cuesta 10 € más.
- La banda recoge el azar del plazo, no el de la demanda.
