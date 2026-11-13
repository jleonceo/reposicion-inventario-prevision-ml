# La previsión de la demanda durante el plazo

El modelo se equivoca menos que el mejor método sencillo en los tres productos al medirlo en 2024, y el intervalo del
95 % de la diferencia queda entero por debajo de cero. En la prueba final de 2025 lo mantiene en B y en C; en A se
equivoca menos, pero el intervalo toca el cero.

## Qué se prevé

Desde cada día de revisión, la demanda de los días 1 al plazo medio del proveedor: 7 días en A, 8 en B y 12 en C. Es lo
que el almacén tiene que cubrir mientras llega el pedido que se lanza ese día.

## El modelo

Un Lasso por producto (alpha 0,1) que prevé la demanda de un día con:

- el día de la semana, en siete columnas de 0 y 1;
- el mes, como seno y coseno, para que diciembre quede al lado de enero;
- la demanda de los 28 días anteriores y sus medias de 7 y 28 días, escaladas.

Para varios días, la previsión es recursiva: cada día previsto se redondea a unidades, se acota en cero y entra como
historia del siguiente. Así solo se usa lo conocido al cierre del día de revisión, y las pruebas lo comprueban
cambiando la demanda posterior a ese día.

Se ajusta con los días de 2023 y se mide en 2024. Para la prueba final se reentrena con 2023 y 2024.

## Frente a qué se mide

Error absoluto medio de la demanda del plazo, en unidades, desde cada día de 2024 con el plazo entero dentro del año:

| Producto | Modelo | Mejor método sencillo | Cuál es | Intervalo del 95 % de la diferencia |
|---|---|---|---|---|
| A | 31,9 | 42,4 | media de 30 días de lo vendido, la regla actual | de −16,0 a −4,5 |
| B | 25,6 | 36,5 | media de 30 días de la demanda | de −16,3 a −5,3 |
| C | 15,9 | 24,5 | demanda del mismo día de la semana anterior | de −11,4 a −6,2 |

El intervalo se calcula remuestreando meses enteros de días de revisión, 1.000 veces, porque los errores de días
seguidos comparten días de demanda y no son independientes.

En enero a junio de 2025, con el modelo reentrenado: 32,9 frente a 39,7 en A, 22,7 frente a 32,5 en B y 17,6 frente a
25,7 en C, siempre frente a la semana anterior. En A el intervalo va de −17,4 a 1,7 y no se da por bueno.

## Límites

- Una previsión mejor no basta para pedir mejor: en la simulación del almacén, la regla con previsión y la regla
  corregida, que usa la media de 30 días, dan costes casi iguales (ver `04_simulador_y_reglas.md`).
- La demanda de los días sin stock se mide como ventas más ventas perdidas. Si un cliente que no encuentra el producto
  no lo registra, la demanda real de esos días sería mayor y no se puede saber cuánto.
