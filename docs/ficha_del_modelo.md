# Ficha del modelo

| | |
|---|---|
| **Qué prevé** | la demanda de un producto durante el plazo medio de su proveedor (7, 8 o 12 días), desde el día de revisión |
| **Para qué se usa** | el punto de pedido de la regla con previsión, la regla del sistema en todos los productos |
| **Algoritmo** | Lasso, alpha 0,1, uno por producto |
| **Variables** | día de la semana, mes (seno y coseno), demanda de los 28 días anteriores y sus medias de 7 y 28 días |
| **Cómo prevé varios días** | de forma recursiva: cada día previsto, redondeado y acotado en cero, entra como historia del siguiente |
| **Entrenamiento** | 2023 para medirlo en 2024; 2023 y 2024 para la prueba final y la producción |
| **Medida** | error absoluto medio de la demanda del plazo, frente a cuatro métodos sencillos |
| **Resultado en 2024** | menos error que el mejor método sencillo en los tres productos, con el intervalo del 95 % bajo cero |
| **Resultado en 2025** | lo mismo en B y C; en A el intervalo toca el cero |

## Uso previsto

Calcular cada día el punto de pedido de un producto cuyo proveedor tarda de forma variable. El modelo no decide nada
por sí solo: la decisión de pedir la toma la regla, con el stock de seguridad calculado sobre su error.

## Lo que no hace

- No prevé la demanda de productos nuevos sin 28 días de historia.
- No tiene en cuenta precios, promociones ni festivos: no están en los datos.
- No prevé el plazo del proveedor; el plazo entra en el stock de seguridad.

## Límites

- Los datos son sintéticos: tres productos de un almacén, sin empresa real detrás.
- En la simulación del almacén, la regla con previsión y la corregida, que usa la media de 30 días, dan costes casi
  iguales: casi todo el ahorro frente a la regla actual lo da ya la regla corregida, que no usa el modelo.
- La demanda de los días sin stock se mide como ventas más ventas perdidas.
