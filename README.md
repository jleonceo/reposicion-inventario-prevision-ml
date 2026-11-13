English version: [README.en.md](README.en.md)

# Reposición de inventario con previsión de demanda

[![pruebas](https://github.com/jleonceo/reposicion-inventario-prevision-ml/actions/workflows/ci.yml/badge.svg)](https://github.com/jleonceo/reposicion-inventario-prevision-ml/actions/workflows/ci.yml)

**Qué es.** Un sistema automatizado que decide diariamente si es necesario realizar un pedido de reposición al
proveedor para tres productos de un almacén, con datos sintéticos.

**Cómo funciona.** Estima la demanda esperada durante el tiempo de entrega y calcula un stock de seguridad basado en
los plazos reales de recepción, en lugar de depender de los tiempos teóricos prometidos por el proveedor.

**Resultado.** Simulado con la demanda registrada del primer semestre de 2025, reservado para la prueba final, nuestro
método reduce el coste de 40.707 € a 9.340 €: un 77 % menos, 31.367 € de ahorro.

El coste es la suma de lo que cuesta mantener el stock, el margen de las ventas perdidas y el coste de cada pedido. Los
40.707 € son lo que costó el semestre con la regla de pedido que usa hoy la empresa. Los 9.340 € son la mediana del
coste en 200 sorteos del plazo de entrega de cada pedido.

## Cómo se ejecuta

Con Python 3.13:

```bash
git clone https://github.com/jleonceo/reposicion-inventario-prevision-ml.git && cd reposicion-inventario-prevision-ml
pip install -r requirements.txt
python ejecutar_todo.py --rapido
```

`ejecutar_todo.py` rehace el proyecto a partir de los CSV de `datos/`. Prepara los datos, entrena los modelos, calcula
el stock de seguridad, hace la prueba final y simula el proceso diario. Por último, comprueba que cada cifra de esta
página sale de lo que acaba de calcular.

## Un día del proceso

Al cierre de cada día, el proceso calcula el punto de pedido de cada producto, que es la demanda que prevé el modelo
durante el plazo de entrega más el stock de seguridad. Después lo compara con el stock, contando lo que ya viene en
camino. Si el stock está en ese punto o por debajo, pide la cantidad fija del producto.

Así quedó la decisión del 26/02/2025 en la simulación del semestre:

<!-- ejemplo 2025-02-26 -->
| Producto | Demanda prevista en el plazo | Stock de seguridad | Punto de pedido | Stock más lo que viene | Decisión |
|---|---|---|---|---|---|
| A | 905 | 131 | 1.036 | 918 | pide 1.500 unidades |
| B | 693 | 205 | 898 | 1.005 | no pide |
| C | 569 | 422 | 991 | 971 | pide 600 unidades |
<!-- /ejemplo -->

La regla es la misma en todos los productos. Un producto nuevo solo necesita su plazo medio real, su objetivo de
servicio, su stock de seguridad y su cantidad de pedido.

## Qué cambia frente a la regla actual

Con los mismos plazos sorteados para las dos reglas y sumando los tres productos, el sistema:

- sube 4,8 puntos el fill rate (unidades servidas entre unidades pedidas por los clientes);
- reduce en 46 los días sin stock;
- aumenta el stock medio en 17.444 €, valorado al coste.

Por producto, el sistema baja el coste en B y en C. En A cuesta prácticamente lo mismo que la regla actual; el
proveedor de A tarda de media lo que promete.

## Cómo está hecho

| Documento | Qué cuenta |
|---|---|
| [Los datos](docs/01_datos.md) | las tres tablas y cómo se preparan |
| [La previsión](docs/02_prevision.md) | un modelo Lasso por producto y cómo se mide frente a las medias |
| [El stock de seguridad](docs/03_stock_de_seguridad.md) | cómo se calcula con los plazos reales y el error medido |
| [El simulador y las reglas](docs/04_simulador_y_reglas.md) | cómo se comparan las cinco reglas de pedido |
| [La prueba final](docs/05_prueba_final.md) | la comparación de cada producto y el resultado del sistema, con sus bandas |
| [El proceso diario](docs/06_produccion.md) | la decisión de cada día, el reentreno y la vuelta atrás |
| [Ficha del modelo](docs/ficha_del_modelo.md) | para qué sirve el modelo y para qué no |

## Limitaciones

**Del modelo.** La mayor parte del ahorro proviene de ajustar el cálculo a los plazos reales de entrega y a la demanda
real (en lugar de guiarse solo por las ventas registradas). La capacidad predictiva del modelo aporta un margen de
mejora reducido y solo resulta relevante en el producto C.

**De los datos.** El estudio se ha realizado con datos sintéticos, limitados a tres referencias y evaluados únicamente
durante un semestre.

**De la simulación.** El ahorro depende de lo que tarde en llegar cada pedido. En el 90 % central de los 200 sorteos, el
ahorro va de 25.933 € a 32.371 €. Como la demanda es la registrada, esa banda no recoge el azar de la demanda.

**De la decisión.** La regla única para todos los productos se decidió después de ver la prueba final. Todo lo que usa
la regla (el modelo, el stock de seguridad y el objetivo de cada producto) estaba fijado antes.

## Datos y licencia

Los datos son sintéticos: recogen tres productos de un almacén, de enero de 2023 a junio de 2025, y no hay ninguna
empresa real detrás.

El código y los datos se publican con licencia [MIT](LICENSE).

## Repositorios relacionados

- [store-sales-forecasting-ml](https://github.com/jleonceo/store-sales-forecasting-ml): previsión diaria de ventas por
  tienda y producto, con un modelo por serie y validación temporal.
- [tesoreria-forecast-ia](https://github.com/jleonceo/tesoreria-forecast-ia): previsión de caja validada con
  backtesting.
- [de-datos-en-bruto-a-decisiones](https://github.com/jleonceo/de-datos-en-bruto-a-decisiones): de un fichero de
  ventas en bruto a un cuadro de mando, con cada cifra recalculada.
