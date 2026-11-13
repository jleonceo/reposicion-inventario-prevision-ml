# El proceso diario

Cada día, al cierre, el proceso decide para cada producto si se pide o no. Simulado en los 181 días de enero a junio de
2025, da día a día lo mismo que el simulador de la prueba final con el mismo sorteo de plazos. Con la regla actual y los
plazos reales, repite lo que pasó: los mismos 181 días y los mismos 40.707 €.

## Las piezas

| Script | Qué hace |
|---|---|
| `produccion/reentrenar.py --hasta AAAA-MM-DD` | entrena el modelo de cada producto con la historia hasta esa fecha y lo guarda aparte, sin pisar el que está en uso |
| `produccion/ejecutar.py --dia AAAA-MM-DD` | lee la entrada del día, la comprueba y deja la decisión de cada producto |
| `produccion/evaluar.py --dia AAAA-MM-DD` | mide lo que pasó hasta ese día: días sin stock, unidades no servidas y coste |
| `produccion/simular_2025.py` | hace de almacén los 181 días de 2025 y lanza ejecutar y evaluar cada día |
| `produccion/volver_atras.py` | vuelve al modelo anterior |

Las rutas, las fechas y los datos de cada producto viven en `produccion/config.json`; los scripts no llevan ninguno
escrito.

## La decisión de cada día

`ejecutar.py` deja en `produccion/salidas/<día>/decision.csv` una línea por producto: la previsión de la demanda durante
el plazo, el stock de seguridad, el punto de pedido, el stock, lo que viene en camino, la posición y si se pide, con la
cantidad fija del producto. Todos los productos aplican la misma regla, la regla con previsión. Un producto nuevo solo
necesita en `produccion/config.json` su plazo medio real, su objetivo de servicio, su stock de seguridad y su cantidad.

Antes de decidir quita todo lo posterior al día, para que no se pueda usar, y comprueba la entrada con el contrato de
`produccion/contrato_entrada.md`. Si algo falla, sea la entrada, la fecha o el modelo, no deja decisión, anota el motivo
en `ejecuciones.csv` y termina con error. Si falta la decisión del día anterior, decide igual y lo anota como aviso por
ausencia. Si un día se vuelve a ejecutar, la salida anterior se archiva y no se pisa.

## El reentreno y la vuelta atrás

En los últimos 91 días de la historia se miden tres cosas en los mismos días: un modelo entrenado sin ellos, el modelo
vigente y la media de 30 días. El modelo nuevo sustituye al vigente si cumple las cuatro condiciones:

- tiene al menos la historia del vigente;
- no es un modelo que haya retirado una vuelta atrás;
- se equivoca menos que la media de 30 días;
- no se equivoca más que el vigente.

Si el vigente se entrenó con parte de esos 91 días, juega con ventaja, y el nuevo solo lo sustituye si aun así lo
mejora. El vigente pasa a `modelos/anteriores/`. Si la sustitución falla a mitad, el vigente vuelve a su sitio. Cada
modelo se guarda con un manifiesto: fecha, versiones de las librerías y huella de los datos. Si las librerías cambian,
el proceso para y pide reentrenar.

`volver_atras.py` restaura el último modelo anterior y apunta el retirado en `modelos/retirados.json`, para que el
siguiente reentreno con los mismos datos no lo vuelva a poner. Dos vueltas atrás seguidas no restauran el modelo que se
acaba de retirar.

## La simulación de 2025

`simular_2025.py` trabaja en sus propias carpetas, `produccion/salidas_simulacion/` y `modelos_simulacion/`, así que
no toca las salidas ni el modelo del proceso diario. Reentrena hasta el 31/12/2024 y, cada día del 01/01 al 30/06/2025,
hace de almacén: llegan los pedidos que tocan, se sirve la demanda real de ese día y se escriben los ficheros de
entrada. Después decide y, si toca, lanza el pedido.

Los pedidos de la regla del sistema salen otros días que los de verdad y no tienen plazo real, así que llegan con el
plazo sorteado número 0 de la prueba final. Con `--control`, los tres productos siguen la regla actual y los pedidos
llegan cuando llegaron de verdad.

Deja una carpeta por día, `registro.csv` con una fila por día e `informes/despliegue.json` con dos comprobaciones de
principio a fin: que no falta ningún día y que el resultado es el del simulador (o, con `--control`, el registrado).

## En GitHub

El flujo `produccion.yml` se lanza a mano desde la pestaña Actions: reentrena, simula los 181 días y publica el registro
como resumen de la ejecución y las salidas como artefacto. Si una ejecución falla o falta un día, el flujo falla y
GitHub avisa por correo a quien lo lanzó.

## Límites

- Enero a junio de 2025 ya se usó como prueba final: la simulación demuestra cómo funciona el proceso, no es una prueba
  nueva.
- Un solo sorteo de plazos da una de las 200 trayectorias de la prueba final; las cifras del semestre con su banda están
  en `05_prueba_final.md`.
