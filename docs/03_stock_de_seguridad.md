# El stock de seguridad

El stock de seguridad de las reglas nuevas sale del error medido en 2024 con los plazos reales del proveedor. No supone
ninguna distribución. En el objetivo de servicio de cada producto, con la regla con previsión, queda en 131 unidades en
A, 205 en B y 422 en C.

## Cómo se calcula

Se parte de cada día de revisión de 2024 y de cada plazo real L de los pedidos recibidos en 2023 y 2024. Para cada par,
se resta la demanda real de los días 1 a L menos la previsión sobre el plazo medio. El stock de seguridad de un
objetivo del 95 % es el percentil 95 de esos valores.

Así un solo número recoge las dos fuentes de riesgo. Una es que la demanda se desvíe de la previsión. La otra, que el
pedido tarde más que el plazo medio. Todos los pares día × plazo pesan igual, y los plazos repetidos cuentan las veces
que ocurrieron. En C son 345 días por 41 plazos, de 7 a 21 días.

## Las cuatro reglas que llevan stock de seguridad

- La regla con previsión usa el error de la previsión del modelo, calculado como arriba.
- La regla corregida hace lo mismo con la media de 30 días de la demanda × plazo medio real.
- La oscilación de la media toma el percentil del objetivo de la media × plazo medio en los días de 2024, menos su
  media. No lleva la variación del plazo.
- La fórmula de manual es z × √(L × σ² + d² × σL²). Supone demanda y plazo normales e independientes, con σ y d de la
  demanda diaria de 2024 y σL del plazo real (4,5 días en C).

## El objetivo de servicio

El objetivo de cada producto es el que da menor coste total medio a la regla con previsión en la simulación de 2024. Se
recorre del 80 % al 99,5 %, de medio en medio punto. Sale el 93 % en A, el 94,5 % en B y el 97,5 % en C.

Las reglas corregida y oscilación de la media usan ese mismo objetivo. La fórmula de manual tiene el suyo, elegido
igual: 98 % en A y B y 99 % en C.

| Producto | Objetivo | Regla con previsión | Regla corregida |
|---|---|---|---|
| A | 93 % | 131 | 141 |
| B | 94,5 % | 205 | 209 |
| C | 97,5 % | 422 | 437 |

## Límites

- El stock de seguridad y el objetivo se fijan con 2024, así que la comparación de ese año es orientativa. La mide la
  prueba final de 2025, que no se usó para nada de esto.
- En C la cola del error descansa en pocos pedidos de plazo largo. Su stock de seguridad depende de unos pocos pedidos.
