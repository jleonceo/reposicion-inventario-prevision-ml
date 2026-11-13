# Los datos

Tres tablas sintéticas de un almacén con tres productos, de enero de 2023 a junio de 2025. Los dos primeros años sirven
para construir y medir el método; enero a junio de 2025 queda apartado en `datos/prueba_final/` y solo se abre en la
prueba final.

## Las tres tablas

- **`inventario_diario.csv`**: una fila por producto y día, con el stock al empezar y al cerrar, las unidades recibidas,
  las ventas y las ventas perdidas por falta de stock. 2.193 filas en 2023 y 2024.
- **`pedidos.csv`**: un pedido al proveedor por fila, con su fecha, su llegada y su cantidad. 146 pedidos hasta el
  31/12/2024; dos seguían en camino ese día y llegaron en enero de 2025.
- **`productos.csv`**: precio, coste unitario, coste anual de mantener el stock (25 %), coste de cada pedido, plazo
  prometido por el proveedor (7 días en los tres) y la regla de pedido que usa hoy la empresa.

## Lo que se construye con ellas

La **demanda** de un día es lo que pidieron los clientes: ventas más ventas perdidas. Se usa la demanda y no las ventas
porque un día sin stock vende menos de lo que se pidió, y prever las ventas de esos días repetiría la rotura.

El **plazo real** de un pedido son los días naturales entre el pedido y la llegada. El proveedor promete 7 días y tarda
de media 6,9 en el producto A, 7,8 en el B y 11,7 en el C, con pedidos de C que llegan a tardar 21 días. C es también
el que más días se quedó sin stock en 2023 y 2024: 125, frente a 37 del B y 3 del A.

La **posición de stock** de un día es el stock al cerrar más lo que viene en camino; es lo que se compara con el punto
de pedido.

## Comprobaciones

`pipeline/01_transformacion.py` para si alguna falla:

- el calendario de cada producto va de día en día, sin huecos;
- el stock cuadra todos los días: stock inicial más lo recibido menos lo vendido es el stock final;
- hay como mucho un pedido por producto y día, y todos con la cantidad fija de la ficha;
- el plazo medio de cada producto, redondeado a días enteros, es el que usa el método: 7, 8 y 12.

No se quita ni se corrige ningún registro.
