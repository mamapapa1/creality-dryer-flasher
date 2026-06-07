[Русский](README.md) · [English](README.en.md) · [Deutsch](README.de.md) · **Español** · [中文](README.zh.md)

# Creality Space Pi X4 Lite - flasheador de firmware (mod 90 °C)

Flasheador multiplataforma (Windows / macOS / Linux) para el secador de filamento
**Creality Space Pi X4 Lite**. Permite:

- **subir la temperatura máxima de 75 a 90 °C** (167 → 194 °F, el mínimo baja a 1 °C / 33.8 °F),
- **calibrar** la lectura del sensor para tu unidad,
- **volver al firmware de fábrica** en cualquier momento.

Es **un único archivo autónomo `flash.py`** - todos los firmwares están incrustados en él,
no hay nada más que descargar. La interfaz está en **5 idiomas** (RU / EN / DE / ES / 中文),
manejada solo con dígitos, tras escribir, el flasheador **vuelve a leer el firmware y lo
verifica byte a byte**, y muestra el cableado del ST-Link en la consola. El flasheo va por SWD
mediante [pyOCD](https://pyocd.io/) (`pip install pyocd`, por defecto) o
[OpenOCD](https://openocd.org/). El MCU de la placa es **GD32F303CBT6** (Cortex-M4, compatible
por software con STM32F303).

<p align="center">
  <img src="images/proof.JPG" alt="La pantalla del secador muestra 90 °C" width="380">
  <img src="images/proof2.JPG" alt="Termómetro en la salida del calentador - 102 °C" width="380"><br>
  <em>La pantalla muestra los 90 °C de trabajo (frente de la cámara). Justo en la salida del calentador hay 102 °C, los calentadores PTC dan como máximo unos 120 °C (según el offset de calibración) y luego empiezan a cortar (chasquidos).</em>
</p>

---

## ⚠️ SEGURIDAD - léelo antes de conectar

> **Lo más simple y seguro es alimentar la placa desde el pin de 3.3 V del ST-Link, sin 220 V y
> sin una fuente de 5 V aparte.** Así no hay red eléctrica en absoluto. La revisión actual de
> la placa tiene aislamiento galvánico, por lo que el ST-Link puede conectarse incluso con 220 V aplicados
> (ver [«Flasheo bajo 220 V»](#flasheo-bajo-220-v-avanzado-bajo-tu-propio-riesgo)), pero para un
> flasheo normal no hace falta.

**Cómo abrir y cablear (forma recomendada, sin 220 V):**

1. Quita los pies adhesivos de la base para llegar a los tornillos de la carcasa. **Usa secador y alcohol** para despegar el adhesivo sin residuos, y pega los pies sobre cinta para que no se les acumule polvo.
2. Cuatro cables ST-Link → placa: **SWDIO, SWCLK, GND** y **3.3V → el riel de 3.3 V de la placa (VDD del MCU)**.
3. **RST** no hace falta (provocaría reinicios sin fin) - el reset es por software.
4. **No apliques 220 V.** Con solo 3.3 V la **pantalla queda apagada - es normal**
   (su alimentación/retroiluminación no está en el riel de 3.3 V), no se necesita para flashear por SWD.

**Importante sobre los 3.3 V:**

- el pin `3.3V` del ST-Link debe ser una **salida** - en los clones baratos lo es, en un ST-Link
  original ese mismo pin es `VTREF` (una entrada de medición) y no entrega corriente,
- aplícalo estrictamente al **riel de 3.3 V (VDD del MCU)** - **5 V ahí matan el chip** (máx. ~3.6 V),
- si la placa no se detecta o la tensión cae, el clon no da suficiente corriente, entonces alimenta
  **5 V en la entrada de 5 V** de la placa (alimenta el regulador de 3.3 V de a bordo).

El mod quita el límite de temperatura de fábrica, uso bajo tu propio riesgo. **La garantía del
fabricante/vendedor queda anulada sin duda.** La carcasa de plástico del secador soporta esta
temperatura sin problema, está construida para ello. No dejes el secador sin vigilancia en las primeras pasadas.

### Flasheo bajo 220 V (avanzado, bajo tu propio riesgo)

A veces es cómodo flashear/depurar **sin desconectar los 220 V** (p. ej. para leer la temperatura
en vivo durante el calentamiento). Esto es seguro **solo si la parte digital está galvánicamente
aislada de la red**.

**Esta placa tiene aislamiento galvánico:**

- la alimentación viene de un **módulo AC-DC aislado con transformador** (condensadores de 35 V en el secundario),
- los calentadores se conmutan mediante **optoacopladores** (EL3063 → triac) - un optoacoplador
  existe precisamente para romper el enlace «red ↔ MCU»,
- hay un **condensador Y** que cruza la barrera de aislamiento cerca del módulo.

Por eso el ST-Link puede conectarse directamente bajo 220 V. Si tu placa es de otra revisión,
el aislamiento se vuelve a comprobar fácilmente con un multímetro:

1. **Red apagada:** continuidad entre **GND (en SWD)** y ambos pines de entrada de red (L y N) →
   debe leer **abierto / megaohmios** (sin camino de baja impedancia = aislado).
2. **(con cuidado) red encendida:** tensión alterna entre el GND de la placa y la tierra del enchufe →
   una placa aislada muestra **~0 a unos pocos voltios** (fuga del Y-cap), una no aislada decenas/cientos de voltios.

El flasheo en vivo bajo 220 V es posible. Margen extra de seguridad: un **portátil con batería**
(cargador desenchufado). Si tu revisión resultara no tener aislamiento, el coste de un error es un
portátil/placa muertos o una descarga eléctrica, así que ante la duda alimenta **3.3 V desde el
ST-Link** (o 5 V en la entrada de 5 V para encender la pantalla) **sin 220 V** - como se describe al inicio de la sección de seguridad.

---

## Qué necesitas

- **Depurador SWD:** ST-Link V2 (el más barato y común), o CMSIS-DAP, o J-Link.
- **Cables** a los pads SWD de la placa (busca el pad `J25`/SWD: SWDIO, SWCLK, GND).
- **Python 3.7+** y una herramienta de flasheo - **pyOCD** (recomendado) u OpenOCD.

### Instalar la herramienta de flasheo

**Recomendado - pyOCD** (un comando, sin binario aparte):

```bash
pip install pyocd
```

Listo. El pack CMSIS del chip GD32F303 se **instala automáticamente** en el primer flasheo
(necesita internet una vez). Nada más que descargar ni añadir al PATH.

**Alternativa - OpenOCD** (si ya está instalado): pasa `--backend openocd`. Instalación:
macOS `brew install open-ocd`, Linux `sudo apt install openocd`,
Windows - [xpack-openocd](https://github.com/xpack-dev-tools/openocd-xpack/releases) en el PATH
(o `--openocd C:\ruta\openocd.exe`).

> **Windows + ST-Link:** tanto pyOCD como OpenOCD hablan con el ST-Link vía libusb - si no se ve la
> sonda, necesita el driver WinUSB (con [Zadig](https://zadig.akeo.ie/)).

Por defecto el flasheador elige el backend solo: pyOCD si está, si no OpenOCD. Si no encuentra
ninguno, **ofrece instalar pyOCD** (`pip install pyocd`) desde el propio menú.

---

## Cableado (fotos)

Forma recomendada - alimentar la placa con **3.3 V en el pin del ST-Link** (sin 220 V). Cuatro cables:
**SWDIO, SWCLK, GND** y **3.3V → el riel de 3.3 V de la placa (VDD del MCU)**, RST no hace falta.

<p align="center">
  <img src="images/board.JPG" alt="ST-Link conectado a la placa por SWD" width="520"><br>
  <em>ST-Link V2 → SWD (SWDIO / SWCLK / GND) y 3.3 V al riel de 3.3 V de la placa.</em>
</p>

**Los 5 V USB externos NO hacen falta para flashear** - el chip se flashea desde los 3.3 V del ST-Link.
La pantalla queda apagada con esa alimentación, y está bien: no se necesita para escribir el firmware por SWD.

Los 5 V hacen falta **solo si desarrollas el firmware** y quieres que la **pantalla se encienda**
(ver la UI en vivo). En ese caso aplica además 5 V, como en la foto:

<p align="center">
  <img src="images/board-5v.JPG" alt="Aplicar 5 V externos para encender la pantalla" width="520"><br>
  <em>Opcional: 5 V USB externos - para que la pantalla cobre vida (solo hace falta para el desarrollo del firmware).</em>
</p>

---

## Uso

Los firmwares están **incrustados dentro de `flash.py`** - es un único archivo autónomo, la carpeta
`firmware/` no hace falta para ejecutarlo (está en el repo solo para verificación/transparencia).

Modo simple - ejecuta y pulsa dígitos:

```bash
python3 flash.py        # o ./flash.py (el archivo es ejecutable)
```

Pasos (todo con dígitos):

```
1. Idioma:  1) Русский  2) English  3) Deutsch  4) Español  5) 中文

2. ¿Qué flashear?
     1) 90 °C / 194 °F (subir el máximo)
     2) Volver a fábrica (75 °C / 167 °F)
     0) salir

3. Calibración (se pregunta SOLO para 90 °C, no para volver a fábrica):
     Offset, °C [Enter=+11 / 0 / p. ej. 9.5]      (+11 °C ≈ +20 °F)

4. Seguridad:  1=sí (flashear)  0=cancelar
```

Secuencia `Enter, Enter, Enter, 1` (idioma → 90 °C → calibración +11 → confirmar) - y listo.

Sin menú (CLI):

```bash
python3 flash.py --lang en                 # idioma de la UI (ru|en|de|es|zh)
python3 flash.py --firmware mod90c --calibrate 11   # mod 90 °C
python3 flash.py --firmware stock          # volver a fábrica 75 °C
python3 flash.py --firmware my_dump.bin    # un firmware arbitrario por ruta
```

Opciones útiles:

```bash
python3 flash.py --list                    # mostrar los firmwares disponibles
python3 flash.py --speed 300               # bajar la velocidad SWD ante errores de enlace
python3 flash.py --dump backup.bin         # ¡PRIMERO haz copia del firmware actual!
python3 flash.py --build-only out.bin      # construir el .bin sin flashear (prueba sin placa)
python3 flash.py --backend openocd         # usar OpenOCD en vez de pyOCD
```

**Consejo:** antes del primer flasheo conviene respaldar el firmware de fábrica de tu placa concreta:
`python3 flash.py --dump my_factory_backup.bin`. Las revisiones difieren - tu propia copia siempre lo restaura todo.

### Probar el flasheador sin placa

Puedes comprobar que todo funciona sin conectar nada:

```bash
python3 flash.py --list                                  # ¿ve los firmwares?
python3 flash.py --help                                  # todas las opciones
# construir un .bin calibrado y comprobar que cambia exactamente 1 byte:
python3 flash.py --firmware mod90c --calibrate 11 --build-only /tmp/t.bin
cmp -l firmware/mod_90c.bin /tmp/t.bin                   # debería ser 1 línea (la dirección C1)
```

`--build-only` no toca la placa. El flasheo real solo es posible con un depurador conectado y los
**220 V retirados** (ver la sección de seguridad).

---

## Calibración de temperatura

El sensor es **no lineal**: en frío lee casi bien, pero **al calentar lee de menos** - cuanto más
caliente, más. La calibración añade un offset constante que conviene ajustar al **punto de trabajo (~90 °C)**.

**Offset recomendado `+11 °C` (≈ +20 °F)** - por qué así:

| | sin calibración | con `+11 °C` |
|---|---|---|
| en frío (sala ~23 °C) | pantalla ~23 °C (correcto) | pantalla ~34 °C (lee de más) |
| al calentar a 90 °C reales | pantalla solo ~79 °C | pantalla ~90 °C (correcto) |

Sin el offset la pantalla se queda en ~79 °C, el regulador cree que «no ha calentado» y sigue
empujando los calentadores PTC → salta el corte térmico, lo que provoca **chasquidos constantes** y
lecturas bajas/falsas. Con `+11` los 90 °C reales se muestran y regulan correctamente - `90 = 90` (a
costa de la precisión en frío, lo cual da igual - se seca en caliente).

En el menú interactivo basta con pulsar **Enter** (aplica +11). Puedes poner tu propio número - pero
para 90 °C suele hacer falta cerca de **+11**. El offset acepta valores **decimales** (p. ej. `10.5` o
`11.3`) y **negativos** - si la pantalla, al revés, lee de más (p. ej. `-3`, límite ±30 °C).

> El offset es en **°C** (unidad interna del firmware). Para un termómetro en °F: convierte la
> diferencia a °C (divide por 1.8). P. ej. pantalla 174 °F, termómetro 194 °F → diferencia 20 °F →
> `20 / 1.8 ≈ 11` → offset **11**.

**Si oyes chasquidos cerca de ~90 °C** - aumenta el offset un par de grados (p. ej. a `+12…+13`).
Cuanto mayor el offset, antes corta el regulador el calentador, así que la salida del calentador no
alcanza los ~120 °C reales y el corte bimetálico deja de chasquear. El coste: la temperatura real de
la cámara queda un par de grados por debajo de la consigna (suele ser aceptable).

**Cómo medir el offset de tu unidad:**

1. Mete un termómetro (termopar) en el **orificio frontal del tubo PTFE**.
2. Calienta la cámara y deja que la temperatura se estabilice.
3. Compara lo que muestra el **secador** y lo que muestra el **termómetro**.
4. Offset = `termómetro − pantalla`. Ejemplo: pantalla 79, termómetro 90 → offset **+11**.

**Cómo aplicar:**

```bash
python3 flash.py --firmware mod90c --calibrate 11    # +11 °C (recomendado)
python3 flash.py --firmware mod90c --calibrate 0     # sin calibración (fábrica)
```

o simplemente `python3 flash.py` - el menú interactivo pregunta el offset por separado
(Enter = +11 recomendados, `0` = sin calibración, o tu propio número).

El offset es común a **ambas cámaras** (se usa una constante de sensor compartida). Tras flashear
conviene volver a comprobar con el termómetro y reflashear con un valor afinado si hace falta.

> Técnicamente la calibración cambia una constante float `C1` (`T = ADC·K − C1`, fábrica `C1 = 50.0`)
> a `50.0 − offset`. Detalles - en [`docs/PATCHES.md`](docs/PATCHES.md) (en ruso).

---

## Chasquidos y el gradiente de temperatura - es normal

Al secar oirás **chasquidos** cerca del calentador, y la temperatura en la pared trasera y al frente
diferirá notablemente. Es **comportamiento normal**, no una avería:

- **Pared trasera (salida de aire caliente):** ~**120 °C / 248 °F**. Es el propio límite térmico del
  calentador - al llegar a ~120 °C (248 °F) se apaga, baja a ~115 °C (239 °F) y vuelve a encenderse.
  De ahí los chasquidos (un ciclo 120 ↔ 115) - la protección térmica del calentador, no un fallo del firmware.
- **Frente de la cámara (donde está el termómetro / el filamento):** ~**90 °C / 194 °F**. Es la
  temperatura de trabajo, por ella regula - y es lo que muestra la pantalla (correcto tras calibrar).
- **Diferencia frente/trasera:** unos **30 °C (54 °F)**, es decir el aire en la pared trasera es
  aprox. **~33 % más caliente** que al frente (equivalente: el frente ~25 % más frío que la salida).
  Un gradiente de temperatura normal de una cámara de flujo.

Dicho de otro modo: no chasquea un «bug del firmware», sino el calentador en su límite cerca de la
salida, mientras el frente mantiene los 90 °C (194 °F) fijados.

**Si los chasquidos molestan** - se pueden eliminar **aumentando el offset de calibración** (p. ej.
`+12…+13` en vez de `+11`): el regulador corta el calentador un poco antes, la salida no llega a
~120 °C y el corte bimetálico no salta. La temperatura real quedará entonces un par de grados por
debajo de la consigna. Ver [«Calibración de temperatura»](#calibración-de-temperatura).

---

## Dos firmwares - la diferencia

| Archivo | t máx. | Para quién |
|------|:------:|------|
| `firmware/mod_90c.bin` | 90 °C / 194 °F | subir el límite a 90 °C |
| `firmware/stock_factory_75c.bin` | 75 °C / 167 °F | volver a fábrica |

### Sobre E4 y la seguridad

**E4** es un código de fallo de sensor/calentador. El mod **no elimina la protección E4 por completo**:
si realmente desconectas/cortocircuitas el sensor de temperatura - **E4 sigue saltando** y se corta el
calentamiento (verificado: desconecta el sensor → aparece el error).

Lo que el mod sí relaja es el **watchdog de subcalentamiento**: el firmware de fábrica daba E4 si la
temperatura no llegaba al **85 % de la consigna** (`0.85 × 90 = 76.5 °C`), y el calentamiento limitado
a 75 °C nunca alcanzaba ese umbral → **E4 perpetuo**. El mod quita exactamente ese disparo falso para
poder llegar a 90 °C. La protección de hardware también permanece - los calentadores PTC se
autolimitan por su temperatura constructiva.

---

## Qué cambia exactamente el mod (para curiosos)

El mod son parches de bytes del firmware de fábrica (128 KB, cargado en `0x08000000`). El mapa completo
está en [`docs/PATCHES.md`](docs/PATCHES.md) (en ruso). En resumen:

- límites de temperatura objetivo `75 → 90 °C` y `45 → 1 °C` (zonas 1 y 2),
- ampliar el rango de consigna en el menú a 90,
- quitar el límite de la temperatura mostrada/regulada en 80.0 °C,
- redirigir el watchdog de subcalentamiento esquivando el manejador E4 (el E4 por fallo de sensor sigue intacto).

La función del sensor y la regulación por consigna están **intactas** - el calentamiento se apaga al
alcanzar el objetivo como siempre.

> ¿Quieres profundizar / desarrollar el firmware (calibración propia, velocidad de ventiladores, UI)?
> Las notas sobre la placa y la ingeniería inversa están en [`docs/REVERSE.md`](docs/REVERSE.md) (en ruso).

---

## Si algo sale mal

- **Sonda no visible / `No available debug probes`** → revisa el cable y el driver
  (Windows: WinUSB con [Zadig](https://zadig.akeo.ie/)), baja `--speed` a `300` o `200`.
- **`unable to connect` / `init mode failed`** → la placa no recibe 5 V/3.3 V, mal contacto en
  SWDIO/SWCLK/GND, o la velocidad es demasiado alta.
- **pyOCD: `Target type ... not found`** → el pack no se instaló a tiempo, manualmente
  `pyocd pack install gd32f303cb` (necesita internet), luego reintenta.
- **pyOCD se resiste en una placa concreta** → cambia a OpenOCD: `--backend openocd`.
- **Firmware equivocado / la placa se comporta raro** → flashea `stock` (o tu copia). El flasheo no
  deja la placa inservible - SWD siempre está disponible.

---

## Aviso legal

Un proyecto aficionado, no afiliado a Creality. Quitar el límite de temperatura y cualquier
modificación son **bajo tu propio riesgo**. Los autores no se responsabilizan de daños a equipos,
propiedad o lesiones. Sigue las reglas de seguridad eléctrica de la sección de arriba.

---

## Licencia

El flasheador se distribuye bajo la **[GNU GPL v3](LICENSE)** © 2026 Alexey Verhogladov.
Los firmwares son modificaciones de bytes de la imagen de fábrica de Creality, provistos «tal cual»
para reparación/investigación, la responsabilidad de su uso es del usuario.

---

## 💚 Apoyar

El proyecto es gratis y hecho por entusiasmo. Si te sirvió - gracias por el apoyo (USDT):

| Red | Dirección |
|------|-------|
| USDT · **TRC20** | `TYLmBvdxL8t9ziyZiFp3jcHwQbAsZR5haZ` |
| USDT · **TON** | `UQCnVND-uBgkWIAD1UP14tsN8239KE5BTOfKSJmg-0XqrN-k` |
| USDT · **ERC20** | `0xa61dcA98A86D84883Ddb3d62aA7F008f157c8eFF` |
