# El simulador del almacén y las cinco reglas

Las reglas se comparan en un simulador que repite día a día lo que hace el almacén. Antes de comparar nada, el
simulador reproduce lo registrado: con la regla actual y los plazos reales, da el mismo stock, las mismas ventas, las
mismas ventas perdidas y los mismos días de pedido que el sistema en los 731 días de 2023 y 2024, y en los 181 de la
prueba final.

## El día a día

Cada día, en este orden:

1. llegan los pedidos que tocan y entran en el stock;
2. se sirve la demanda hasta donde llega el stock y lo que falta se pierde;
3. al cierre, si la posición de stock (stock más lo que viene en camino) está en el punto de pedido o por debajo, se
   lanza un pedido de la cantidad fija del producto.

## Las cinco reglas de pedido

El punto de pedido de cada una:

- **Regla actual:** media de lo vendido en 30 días × plazo prometido (7 días) + un stock de seguridad fijo de la ficha.
  Cuenta lo vendido, que en los días sin stock es menos que lo pedido, y el plazo prometido, que en C es 5 días menos
  que el real.
- **Regla corregida:** media de la demanda en 30 días × plazo medio real + el stock de seguridad del error medido.
- **Regla con previsión:** previsión del modelo sobre el plazo medio + el stock de seguridad del error medido.
- **Oscilación de la media** y **fórmula de manual:** dos referencias de libro, con la misma previsión que la regla
  corregida (ver `03_stock_de_seguridad.md`).

## Cómo se comparan

El plazo de cada pedido se sortea de los plazos reales del proveedor, 200 veces, con semilla fija. En cada sorteo, el
pedido número k de cada regla recibe el mismo plazo, así que la diferencia entre dos reglas no la pone el azar del
plazo. Cada cifra se da con la mediana de los 200 sorteos y la banda del 5 al 95.

El coste total del periodo suma tres partes: mantener el stock (stock medio × coste unitario × 25 % anual × días / 365),
el margen de las ventas perdidas y el coste de cada pedido. Para ver si la conclusión depende del 25 %, se repite con el
15 % y el 40 %.

Una regla es **buena** frente a otra si baja el coste total con toda la banda de la diferencia por debajo de cero y sin
bajar el fill rate (unidades servidas entre unidades pedidas). Si la mediana baja pero la banda cruza el cero, no se
puede afirmar.

## En 2024, orientativo

Con el stock de seguridad fijado con 2024, la regla con previsión baja el coste del año frente a la actual en 164 € en
A, 5.972 € en B y 67.239 € en C (medianas). La regla corregida da casi lo mismo: 147 €, 5.941 € y 67.128 €. Es
orientativo porque el stock de seguridad se calculó con ese mismo año; la medida que cuenta es la de la prueba final
(`05_prueba_final.md`).

## Límites

- La banda recoge el azar del plazo, no el de la demanda, que es la registrada tal cual.
- El margen perdido supone que la venta no servida se pierde entera; no incluye clientes que dejan de comprar.
- El coste de mantener es una estimación de la empresa; por eso se da también con el 15 % y el 40 %.
- El punto de pedido cubre un día de más. Un pedido que tarda L días llega antes de servir el día L, así que basta con
  cubrir L − 1 días, y el punto de pedido cubre L. El objetivo se elige por coste y absorbe esa diferencia, pero por eso
  el objetivo nominal no es el servicio que se obtiene: en C, con un objetivo del 97,5 %, el fill rate sale 1,0 de
  mediana.
- El criterio que compara producto a producto tiene un hueco: si la regla con previsión es buena frente a la actual,
  no se puede afirmar que mejore a la corregida y la corregida no es buena frente a la actual, elige la actual. No
  ocurre con estos datos, y el sistema no depende de él: usa la regla con previsión en todos los productos.
