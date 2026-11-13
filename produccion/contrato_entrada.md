# Contrato de entrada del proceso diario

Cada día, al cierre, el proceso lee dos ficheros de la carpeta de entrada (`produccion/entrada/` por defecto, o la que
se le indique con `--entrada`). Tienen el mismo formato que los de `datos/`.

## `inventario_diario.csv`

Una fila por producto y día, con toda la historia hasta el día de la ejecución.

| Columna | Tipo | Qué es |
|---|---|---|
| `fecha` | fecha `AAAA-MM-DD` | el día |
| `producto` | texto | el producto |
| `stock_inicial` | entero | unidades al empezar el día |
| `unidades_recibidas` | entero | unidades que llegaron ese día |
| `ventas` | entero | unidades servidas |
| `ventas_perdidas` | entero | unidades pedidas por los clientes que no se pudieron servir |
| `stock_final` | entero | unidades al cerrar el día |

## `pedidos.csv`

Una fila por pedido al proveedor.

| Columna | Tipo | Qué es |
|---|---|---|
| `id_pedido` | texto | identificador del pedido |
| `producto` | texto | el producto |
| `fecha_pedido` | fecha | día en que se lanzó |
| `fecha_llegada` | fecha o vacío | día en que llegó; vacío si todavía no ha llegado |
| `cantidad` | entero | unidades pedidas |
| `estado` | texto | `recibido` o `pendiente` |

## Lo que se comprueba antes de decidir

Si falla cualquiera de estas comprobaciones, la ejecución para sin dejar decisión, lo anota en `ejecuciones.csv` con el
motivo y termina con error.

Al leer, sea cual sea el día:

1. Llegan los dos ficheros y se pueden leer con estas columnas y tipos.
2. Cada pedido tiene fecha de pedido, no se repite, no llega antes de pedirse y su estado es `recibido` o `pendiente`.

Después se quita todo lo posterior al día de la ejecución, para que no se pueda usar: un pedido lanzado después no
está y uno que llega después sigue pendiente. Con lo que queda:

3. Llegan exactamente los productos de `produccion/config.json`, en el inventario y en los pedidos.
4. El último día de cada producto es el día de la ejecución: un fichero del día anterior no sirve.
5. Ningún producto repite día ni tiene huecos, y cada uno trae al menos 30 días de historia.
6. Cada día empieza con el stock con que cerró la víspera.
7. Ninguna columna de unidades es negativa y el stock cuadra en todas las filas: stock inicial + recibido − ventas =
   stock final.
8. Todos los pedidos traen unidades, y el estado casa con la llegada: recibido con llegada y pendiente sin ella.

El orden de las filas no importa.
