# El stock de seguridad

El stock de seguridad de las reglas nuevas sale del error medido en 2024 con los plazos reales del proveedor, sin
suponer ninguna distribución. En el objetivo de servicio de cada producto queda en 131 unidades en A, 205 en B y 422
en C con la regla con previsión.

## Cómo se calcula

Para cada día de revisión de 2024 y cada plazo real L de los pedidos recibidos en 2023 y 2024, se resta la demanda real
de los días 1 a L menos la previsión sobre el plazo medio. El stock de seguridad de un objetivo del 95 % es el
percentil 95 de esos valores.

Así un solo número recoge las dos fuentes de riesgo: que la demanda se desvíe de la previsión y que el pedido tarde más
que el plazo medio. Todos los pares día × plazo pesan igual, y los plazos repetidos cuentan las veces que ocurrieron.
En C son 345 días por 41 plazos, de 7 a 21 días.

## Las cuatro reglas que llevan stock de seguridad

- **Regla con previsión:** el error de la previsión del modelo, calculado como arriba.
- **Regla corregida:** lo mismo con la previsión de la media de 30 días de la demanda × plazo medio real.
- **Oscilación de la media:** el percentil del objetivo de la media × plazo medio de los días de 2024, menos su media.
  No lleva la variación del plazo.
- **Fórmula de manual:** z × √(L × σ² + d² × σL²), que supone demanda y plazo normales e independientes, con σ y d de
  la demanda diaria de 2024 y σL del plazo real (4,5 días en C).

## El objetivo de servicio

El objetivo de cada producto es el que da menor coste total medio a la regla con previsión en la simulación de 2024,
recorriendo del 80 % al 99,5 % de medio en medio punto: 93 % en A, 94,5 % en B y 97,5 % en C. Las reglas corregida y
oscilación de la media usan ese mismo objetivo. La fórmula de manual tiene el suyo, elegido igual: 98 % en A y B y 99 %
en C.

| Producto | Objetivo | Regla con previsión | Regla corregida |
|---|---|---|---|
| A | 93 % | 131 | 141 |
| B | 94,5 % | 205 | 209 |
| C | 97,5 % | 422 | 437 |

## Límites

- El stock de seguridad se fija con 2024 y se elige el objetivo con 2024: la comparación de ese año es orientativa. La
  mide la prueba final de 2025, que no se usó para nada de esto.
- En C la cola del error descansa en pocos pedidos de plazo largo, así que su stock de seguridad depende de unos pocos
  pedidos.
