import asyncio, aiohttp, os, logging
from github_bot.git_client import get_git_client
from ruamel.yaml import YAML

CONCEPTOS = {
    # ── TEORÍA MUSICAL (Néstor Crespo / Armonía) ──
    "escala-menor": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [escala, modo-menor, armonía]
---
# Escala Menor

La **escala menor** es una estructura diatónica de siete notas caracterizada fundamentalmente por la distancia de **tercera menor** (un tono y medio) entre su primer grado ([[tonica]]) y su tercer grado ([[mediante]]). Constituye uno de los dos polos del sistema tonal occidental (junto con la [[escala-mayor]]).

En la teoría musical, el modo menor se manifiesta principalmente en tres variantes fundamentales para resolver necesidades melódicas y armónicas:
1. **[[escala-menor-natural]]** (o [[escala-eolica]]): Estructura original sin notas sensibles alteradas (`T - S - T - T - S - T - T`). Carece de tensión de dominante.
2. **[[escala-menor-armonica]]**: Introduce una alteración ascendente en el VII grado para crear una [[sensible]] artificial (`T - S - T - T - S - T y medio - S`), permitiendo la formación de un acorde de [[dominante]] mayor.
3. **[[escala-menor-melodica]]**: Asciende el VI y VII grado al subir para evitar el intervalo de segunda aumentada, y desciende como la menor natural.

## Relaciones interválicas básicas
- Fundamental a III grado: Tercera menor (1,5 tonos).
- Fundamental a VI e VII grados: Varían según sea natural, armónica o melódica.
""",

    "escala-mayor": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [escala, modo-mayor, armonía]
---
# Escala Mayor

La **escala mayor** (o modo jónico) es la escala diatónica fundamental del sistema tonal occidental. Se compone de siete grados con la siguiente distribución interválica de tonos y semitonos:

`Tono - Tono - Semitono - Tono - Tono - Tono - Semitono`

## Características principales
- **Tercera mayor**: Su característica distintiva es la distancia de dos tonos entre el I grado ([[tonica]]) y el III grado ([[mediante]]).
- **[[sensible]] natural**: El VII grado se encuentra a solo un semitono de la tónica superior, generando una fuerte atracción melódica y armónica de resolución.
- **Armonización básica**: Al superponer terceras diatónicas sobre cada grado, genera los acordes principales de la [[armonia-funcional]]:
  - **I, IV, V**: Acordes mayores (Tónica, [[subdominante]], [[dominante]]).
  - **II, III, VI**: Acordes menores.
  - **VII**: Acorde disminuido.
""",

    "escala-menor-antigua": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [escala, modo-menor, eólico]
---
# Escala Menor Antigua

La **escala menor antigua** es una denominación tradicional para la [[escala-menor-natural]] o modo eólico (`I - II - bIII - IV - V - bVI - bVII`).

Se caracteriza por mantener la armadura de clave de su [[escala-menor-relativa]] mayor sin ninguna alteración accidental. Al poseer una séptima menor ([[subtonica]]) en lugar de una [[sensible]], carece de una tensión resolutiva fuerte hacia la tónica, motivo por el cual evolucionó en la música occidental hacia la [[escala-menor-armonica]].
""",

    "escala-eolica": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [modo, escala, eólico]
---
# Escala Eólica (Modo Eólico)

La **escala eólica** corresponde al sexto modo de la escala diatónica mayor (comenzando sobre el VI grado). Es el equivalente modal exacto de la [[escala-menor-natural]].

Su estructura interválica es:
`Tono - Semitono - Tono - Tono - Semitono - Tono - Tono`

En la armonía modal, el modo eólico destaca por su sonoridad melancólica y natural, careciendo del tritono resolutivo en su acorde de dominante diatónico (el cual es menor, `Vm`).
""",

    "sensible": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía, resolución]
---
# Sensible (VII Grado)

En teoría musical, la **sensible** es el **séptimo grado (VII)** de una escala diatónica cuando se encuentra a una distancia exacta de **un semitono diatónico** por debajo de la [[tonica]].

## Función melódica y armónica
- **Atracción gravitacional**: Por su proximidad melódica, posee un impulso casi ineludible de resolver de forma ascendente hacia la tónica (grado I).
- **En el acorde de [[dominante]]**: Es la tercera del acorde de dominante (`V` o `V7`), y junto con la séptima del acorde forma el intervalo de [[tritono]], cuya inestabilidad define la resolución armónica del sistema tonal.
- **En el modo menor**: Como el VII grado diatónico natural está a un tono de distancia ([[subtonica]]), la sensible debe generarse artificialmente alterando el VII grado medio tono hacia arriba (dando lugar a la [[escala-menor-armonica]]).
""",

    "tonica": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía, centro-tonal]
---
# Tónica (I Grado)

La **tónica** es el **primer grado (I)** de una escala o tonalidad, constituyendo el centro de gravedad del sistema tonal en la [[armonia-funcional]].

## Propiedades fundamentales
- **Reposo y estabilidad**: Representa el punto de máxima relajación, reposo y conclusión dentro de una obra musical.
- **Acorde de Tónica**: El acorde construido sobre este grado establece la identidad de la [[tonalidad]] (mayor o menor). Todos los demás grados y funciones armónicas ([[dominante]], [[subdominante]]) se definen por la tensión que generan respecto a la tónica y su necesidad de resolver en ella.
""",

    "dominante": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía, función]
---
# Dominante (V Grado)

La **dominante** es el **quinto grado (V)** de una escala tonal, situado una quinta justa por encima de la [[tonica]].

## Función en la Armonía Funcional
- **Máxima tensión**: La función armónica de dominante genera la mayor expectación e inestabilidad en el discurso musical, exigiendo una resolución inminente hacia la tónica.
- **Acorde de Dominante (`V` o `V7`)**: Contiene la [[sensible]] de la escala (como tercera del acorde). Al añadir la séptima menor, incorpora el [[tritono]] tonal (entre la sensible y la séptima del acorde), que resuelve por movimiento contrario hacia la fundamental y la tercera de la tónica.
""",

    "subdominante": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía, función]
---
# Subdominante (IV Grado)

La **subdominante** es el **cuarto grado (IV)** de una escala diatónica, situado una quinta justa por debajo de la tónica o una cuarta justa por encima.

## Función Armónica
En la [[armonia-funcional]], la función de subdominante representa una tensión moderada o de alejamiento del reposo. Tradicionalmente prepara la llegada de la [[dominante]] en la progresión de cadencia completa (`I - IV - V - I`), o bien resuelve directamente a la tónica en la cadencia plagal (`IV - I`).
""",

    "mediante": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía, modalidad]
---
# Mediante (III Grado)

La **mediante** es el **tercer grado (III)** de la escala diatónica, situado exactamente a mitad de camino entre la [[tonica]] (I) y la [[dominante]] (V).

Su papel es definitorio en la música, ya que determina el modo o carácter modal de la tonalidad según el intervalo que forme con la tónica:
- Si está a dos tonos (tercera mayor), define el modo de [[escala-mayor]].
- Si está a tono y medio (tercera menor), define el modo de [[escala-menor]].
""",

    "supertonica": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía]
---
# Supertónica (II Grado)

La **supertónica** es el **segundo grado (II)** de una escala, situado un tono diatónico por encima de la [[tonica]].

En la [[armonia-funcional]], el acorde construido sobre la supertónica (`IIm` en el modo mayor o `IIm7b5` en el modo menor) cumple una importante función de **[[subdominante]]** o preparación de la [[dominante]], siendo el primer acorde en la conocida progresión `II - V - I`.
""",

    "superdominante": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [grados, armonía]
---
# Superdominante o Submediante (VI Grado)

La **superdominante** (o **submediante**) es el **sexto grado (VI)** de la escala diatónica, situado un tono por encima de la [[dominante]] (o una tercera por debajo de la tónica superior).

En el modo mayor, el VI grado alberga la fundamental de la [[escala-menor-relativa]]. Armónicamente, el acorde del VI grado suele compartir notas tanto con la tónica como con la subdominante, lo que le permite actuar en cadencias rotas o evictivas (`V - VI`).
""",

    "armadura-de-clave": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [notación, tonalidad]
---
# Armadura de Clave

La **armadura de clave** es el conjunto de alteraciones accidentales (sostenidos o bemoles) situadas al comienzo del pentagrama, justo después de la clave musical.

Indica la [[tonalidad]] de la obra (tanto su modo mayor como su [[escala-menor-relativa]]) y define las notas que deberán interpretarse alteradas sistemáticamente a lo largo de la pieza, salvo indicación expresa en contra mediante becuadros. Sigue el orden fijo de alteraciones:
- **[[orden-de-sostenidos]]**: Fa, Do, Sol, Re, La, Mi, Si.
- **[[orden-de-bemoles]]**: Si, Mi, La, Re, Sol, Do, Fa.
""",

    "tetracordio-superior": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [estructura, escalas]
---
# Tetracordio Superior

En la teoría de formación de escalas diatónicas, el **tetracordio superior** corresponde al grupo de las cuatro notas más agudas de una escala diatónica (grados V, VI, VII y VIII).

Se complementa con el tetracordio inferior (grados I a IV), estando ambos separados por un intervalo de un tono entero llamado [[tono-de-enlace]]. En la [[escala-mayor]], el tetracordio superior y el inferior son de estructura idéntica (`Tono - Tono - Semitono`).
""",

    "octava": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [intervalo, acústica]
---
# Octava (Intervalo)

La **octava** es el intervalo musical que abarca ocho grados diatónicos (incluyendo las notas de partida y llegada).

Acústicamente corresponde a una relación de frecuencias de $2:1$, lo que genera el fenómeno de equivalencia de octava: dos notas separadas por una octava comparten el mismo nombre y se perciben cromáticamente como equivalentes en distintas alturas.
""",

    "escala-diatonica": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [escalas, sistema-tonal]
---
# Escala Diatónica

Una **escala diatónica** es una sucesión heptáfona (de siete sonidos) que progresa por grados conjuntos, en la cual las distancias interválicas se distribuyen exactamente en cinco tonos y dos semitonos diatónicos.

Esta distribución asimétrica permite definir un centro tonal claro. Los modos principales de la escala diatónica son la [[escala-mayor]] y la [[escala-menor-natural]].
""",

    "armonia-funcional": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [armonía, análisis]
---
# Armonía Funcional

La **armonía funcional** es el sistema analítico y constructivo de la música tonal en el cual cada acorde cumple una función específica de tensión o reposo en relación con un centro tonal (`[[tonica]]`).

Se estructura en tres funciones arquetípicas primarias:
1. **[[tonica]] (`T`)**: Reposo, resolución y centro de gravedad.
2. **[[subdominante]] (`S` o `SD`)**: Tensión media, desarrollo, alejamiento y preparación.
3. **[[dominante]] (`D`)**: Máxima tensión armónica y direccionalidad de resolución hacia la tónica.
""",

    "atonalidad": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [siglo-xx, vanguardia]
---
# Atonalidad

La **atonalidad** es un lenguaje o sistema compositivo del siglo XX caracterizado por la ausencia intencionada de un centro tonal dominante (`[[tonica]]`) y la jerarquía de funciones tradicionales de la [[armonia-funcional]].

En la música atonal (como el dodecafonismo de Arnold Schoenberg o las obras de la Segunda Escuela de Viena), los doce tonos de la escala cromática reciben un tratamiento de igualdad absoluta, evitando progresiones que generen cadencias tonales convencionales.
""",

    "politonalidad": """---
tipo: concepto
dominio: teoria-musical
etiquetas: [armonía, siglo-xx]
---
# Politonalidad

La **politonalidad** es el uso simultáneo de dos o más tonalidades diferentes dentro de una misma textura compositiva musical.

Cuando se emplean exactamente dos tonalidades simultáneas se denomina habitualmente *bitonalidad* (ejemplo célebre en la obra de Igor Stravinsky o Darius Milhaud). Cada capa o instrumento mantiene su propia estructura diatónica y centro resolutivo de manera concurrente.
""",

    # ── ECUACIONES DIFERENCIALES II (Matemáticas / Los del DGIIM) ──
    "condicion-inicial": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [pvi, análisis]
---
# Condición Inicial

En el estudio de ecuaciones diferenciales ordinarias, una **condición inicial** es el valor especificado del estado del sistema $(t_0, x_0)$ en un instante inicial $t_0$, exigiendo que la solución $x(t)$ cumpla exactamente:
$$x(t_0) = x_0$$

La combinación de una ecuación diferencial con una condición inicial define formalmente un [[problema-de-valores-iniciales]] (PVI o problema de Cauchy).
""",

    "convergencia-puntual": """---
tipo: concepto
dominio: analisis-matematico
etiquetas: [convergencia, funciones]
---
# Convergencia Puntual

Dada una sucesión de funciones $f_n: I \to \mathbb{R}^d$, se dice que $\{f_n\}$ presenta **convergencia puntual** hacia una función límite $f: I \to \mathbb{R}^d$ en un intervalo $I$ si, para cada punto individual $t \in I$ fijado, la sucesión numérica de valores evaluados converge:
$$\lim_{n \to \infty} f_n(t) = f(t) \quad \forall t \in I$$

A diferencia de la [[convergencia-uniforme]], la convergencia puntual no garantiza en general que el límite de funciones continuas siga siendo continuo si la velocidad de convergencia depende de cada punto $t$.
""",

    "dependencia-continua-condiciones-iniciales": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [continuidad, pvi]
---
# Dependencia Continua respecto a Condiciones Iniciales

El teorema de **dependencia continua respecto a condiciones iniciales** establece que las soluciones de un [[problema-de-valores-iniciales]] varían de forma continua y suave ante perturbaciones infinitesimales en el punto de partida $(t_0, x_0)$.

Si el campo vectorial $f(t, x)$ es continuo y localmente Lipschitz respecto a $x$, dos soluciones $x(t)$ e $y(t)$ que parten de condiciones iniciales cercanas se mantendrán acotadas en su divergencia de acuerdo con el [[lema-de-gronwall]]:
$$\|x(t) - y(t)\| \le \|x(t_0) - y(t_0)\| e^{L|t - t_0|}$$
""",

    "dependencia-continua-parametros": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [parámetros, continuidad]
---
# Dependencia Continua respecto a Parámetros

Cuando un sistema de ecuaciones diferenciales depende explícitamente de un parámetro o vector de parámetros $\mu \in \mathbb{R}^k$:
$$\dot{x} = f(t, x, \mu)$$
bajo condiciones adecuadas de continuidad y Lipschitzianidad del campo respecto al conjunto $(x, \mu)$, la solución $x(t; t_0, x_0, \mu)$ resulta ser una función continua de dicho parámetro $\mu$. Esto permite aproximar sistemas perturbados estudiando el caso no perturbado $\mu = 0$.
""",

    "diferenciabilidad-parametros": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [parámetros, derivadas]
---
# Diferenciabilidad respecto a Parámetros

Si el campo de una ecuación diferencial dependiente de parámetros $\dot{x} = f(t, x, \mu)$ posee derivadas parciales continuas de clase $C^1$ respecto a $(x, \mu)$, entonces la solución $x(t; \mu)$ es diferenciable de clase $C^1$ respecto a $\mu$. Su derivada respecto a los parámetros satisface un sistema lineal asociado no homogéneo derivado a partir de la [[ecuacion-variacional]].
""",

    "ecuacion-variacional": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [sistemas-lineales, variacional]
---
# Ecuación Variacional

La **ecuación variacional** es el sistema lineal matricial de ecuaciones diferenciales que gobierna la evolución y el comportamiento de las derivadas parciales de una solución con respecto a las condiciones iniciales o parámetros.

Dada la solución de referencia $\phi(t; t_0, x_0)$ del sistema $\dot{x} = f(t, x)$, la matriz jacobiana $Y(t) = \frac{\partial \phi}{\partial x_0}(t; t_0, x_0)$ satisface la ecuación variacional lineal:
$$\dot{Y}(t) = \frac{\partial f}{\partial x}\left(t, \phi(t; t_0, x_0)\right) Y(t), \quad Y(t_0) = I$$
""",

    "espacio-de-fases": """---
tipo: concepto
dominio: sistemas-dinamicos
etiquetas: [geometría, fases]
---
# Espacio de Fases

El **espacio de fases** es el espacio matemático geométrico en el que cada punto representa de forma unívoca un estado completo e instantáneo de un sistema dinámico.

En sistemas mecánicos como el [[problema-de-n-cuerpos]], el espacio de fases está conformado por las variables de posición y velocidad (o momentos generalizados) de todas las partículas. Las trayectorias en este espacio representan las curvas integrales generadas por el flujo del campo vectorial de la ecuación diferencial.
""",

    "estabilidad-asintotica": """---
tipo: concepto
dominio: sistemas-dinamicos
etiquetas: [estabilidad, lyapunov]
---
# Estabilidad Asintótica

Un punto de equilibrio $x^*$ de un sistema dinámico $\dot{x} = f(x)$ es **asintóticamente estable** si cumple simultáneamente dos condiciones en el sentido del análisis de [[estabilidad-lyapunov]]:
1. **Estabilidad de Lyapunov**: Las soluciones que parten suficientemente cerca de $x^*$ permanecen cerca para todo tiempo futuro $t \ge t_0$.
2. **Atracción**: Existe una vecindad alrededor del equilibrio tal que cualquier solución $x(t)$ que inicie en ella converge al equilibrio en el límite temporal:
$$\lim_{t \to \infty} x(t) = x^*$$
""",

    "existencia-de-soluciones": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [teoremas, existencia]
---
# Existencia de Soluciones

El problema fundamental de la **existencia de soluciones** indaga bajo qué condiciones analíticas un [[problema-de-valores-iniciales]] admite al menos una curva integral diferenciable en un entorno del punto inicial.

El resultado clásico más general es el [[teorema-de-cauchy-peano]], que garantiza la existencia local de solución con la sola exigencia de la continuidad del campo $f(t, x)$. Si se busca además la [[unicidad-de-soluciones]], se requiere la condición adicional de Lipschitz.
""",

    "ley-de-gravitacion-universal": """---
tipo: concepto
dominio: fisica-matematica
etiquetas: [mecánica, gravitación]
---
# Ley de Gravitación Universal

Formulada por Isaac Newton, la **ley de gravitación universal** postula que dos cuerpos con masas $m_i$ y $m_j$ se atraen mutuamente con una fuerza central directamente proporcional al producto de sus masas e inversamente proporcional al cuadrado de la distancia que los separa:
$$F_{ij} = -G \frac{m_i m_j}{\|r_i - r_j\|^3}(r_i - r_j)$$

Constituye la base fundamental para el modelado del [[problema-de-n-cuerpos]] en sistemas dinámicos celestes.
""",

    "leyes-de-newton": """---
tipo: concepto
dominio: fisica-matematica
etiquetas: [mecánica, newton]
---
# Leyes de Newton

Las tres **leyes de la dinámica de Newton** establecen los principios axiomáticos de la mecánica clásica:
1. **Inercia**: Un cuerpo conserva su estado de reposo o movimiento rectilíneo uniforme si no actúan fuerzas sobre él.
2. **Fundamental de la dinámica**: La tasa de variación del momento lineal es igual a la fuerza neta aplicada ($\vec{F} = m\ddot{\vec{x}}$).
3. **Acción y reacción**: Por cada fuerza de acción existe una reacción igual y opuesta sobre el otro cuerpo ($\vec{F}_{ij} = -\vec{F}_{ji}$).
""",

    "movimiento-armonico-simple": """---
tipo: concepto
dominio: fisica-matematica
etiquetas: [oscilaciones, lineal]
---
# Movimiento Armónico Simple (MAS)

El **movimiento armónico simple** es el movimiento oscilatorio periódico gobernado por una ecuación diferencial lineal de segundo orden con coeficientes constantes sin amortiguamiento, del tipo:
$$\ddot{x} + \omega^2 x = 0$$

Su solución general es una combinación de senos y cosenos ($x(t) = A \cos(\omega t + \phi)$), representando oscilaciones puras y estables alrededor de un punto de equilibrio, constituyendo la aproximación lineal de orden 1 para la [[ecuacion-del-pendulo]] en ángulos pequeños.
""",

    "prolongacion-de-soluciones-y-soluciones-maximales": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [maximal, prolongación]
---
# Prolongación de Soluciones y Soluciones Maximales

Este concepto engloba la extensión del intervalo de definición de una solución local de un [[problema-de-valores-iniciales]].

Una solución es **maximal** ([[solucion-maximal]]) si no puede extenderse a un intervalo temporal más amplio. El teorema de prolongación ([[teorema-de-prolongacion]]) asegura que si una solución maximal definida en $(\alpha, \omega)$ no alcanza todo $\mathbb{R}$, cuando $t \to \omega^-$ la trayectoria inevitablemente se aproxima al borde del dominio o su norma explota hacia el infinito ($\|x(t)\| \to \infty$).
""",

    "teorema-de-diferenciabilidad-condiciones-iniciales": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [diferenciabilidad, pvi]
---
# Teorema de Diferenciabilidad respecto a Condiciones Iniciales

Establece que si el campo vectorial $f(t, x)$ de la ecuación $\dot{x} = f(t, x)$ posee derivadas parciales respecto a $x$ continuas en el dominio (es de clase $C^1$), entonces la solución general $\phi(t; t_0, x_0)$ es diferenciable de clase $C^1$ como función de la condición inicial $x_0$.

Las derivadas parciales jacobianas asociadas evolucionan y se calculan resolviendo exactamente la [[ecuacion-variacional]] del sistema.
""",

    "teorema-de-painleve": """---
tipo: concepto
dominio: sistemas-dinamicos
etiquetas: [singularidades, n-cuerpos]
---
# Teorema de Painlevé

En el estudio analítico del [[problema-de-n-cuerpos]], el **Teorema de Painlevé** (1895) caracteriza formalmente las singularidades en las soluciones maximales.

Establece que si el intervalo maximal de definición de una solución del problema de los $N$ cuerpos es acotado por la derecha en $t^* < \infty$ (existencia de una singularidad), entonces la distancia mínima entre al menos un par de las partículas tiende inevitablemente a cero cuando $t \to t^*$:
$$\lim_{t \to t^*-} \min_{i \ne j} \|r_i(t) - r_j(t)\| = 0$$
Es decir, toda singularidad en el problema de los tres cuerpos ($N=3$) corresponde necesariamente a una colisión física entre partículas.
""",

    "teorema-funcion-implicita": """---
tipo: concepto
dominio: analisis-matematico
etiquetas: [análisis, implícita]
---
# Teorema de la Función Implícita

El **teorema de la función implícita** es un resultado fundamental del análisis multivariable que establece condiciones suficientes para que una ecuación o sistema de ecuaciones $F(x, y) = 0$ defina localmente a la variable $y$ como una función diferenciable de $x$ ($y = g(x)$).

Para un punto $(x_0, y_0)$ donde $F(x_0, y_0) = 0$, si las derivadas parciales son continuas y la matriz jacobiana respecto a las variables dependientes $\frac{\partial F}{\partial y}(x_0, y_0)$ es inversible (determinante no nulo), se garantiza la existencia y diferenciabilidad de la función implícita.
""",

    "ecuacion-del-muelle": """---
tipo: concepto
dominio: fisica-matematica
etiquetas: [mecánica, oscilaciones]
---
# Ecuación del Muelle

La **ecuación del muelle** modela el movimiento mecánico de una masa unida a un resorte elástico que obedece la ley de Hooke, posiblemente con fricción lineal o fuerzas externas.

En su forma canónica clásica de segundo orden:
$$m \ddot{x} + c \dot{x} + k x = F(t)$$
donde $m$ es la masa, $c$ el coeficiente de amortiguamiento viscoso, $k$ la constante de rigidez elástica y $F(t)$ la excitación exterior. Cuando $c=0$ y $F(t)=0$, se reduce a un [[movimiento-armonico-simple]].
""",

    "ecuaciones-con-crecimiento-lineal": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [cota-lineal, existencia-global]
---
# Ecuaciones con Crecimiento Lineal

Se dice que un campo vectorial $f(t, x)$ satisface una condición de **crecimiento lineal** en $x$ si existen funciones continuas $a(t), b(t) \ge 0$ tales que:
$$\|f(t, x)\| \le a(t)\|x\| + b(t) \quad \forall (t, x) \in I \times \mathbb{R}^d$$

Por aplicación del [[teorema-de-prolongacion]] junto con el [[lema-de-gronwall]], esta condición acota la velocidad con la que puede crecer una solución impidiendo que su norma explote en un tiempo finito, garantizando así la **[[unicidad-global]]** y existencia global en todo el intervalo $I$.
""",

    "forma-canonica-de-jordan": """---
tipo: concepto
dominio: algebra-lineal
etiquetas: [matrices, sistemas-lineales]
---
# Forma Canónica de Jordan

La **forma canónica de Jordan** es la representación matricial casi diagonal más simplificada que se puede obtener para cualquier matriz cuadrada mediante transformaciones de semejanza $J = P^{-1} A P$.

En el estudio de un [[sistema-lineal-coeficientes-constantes]] $\dot{x} = A x$, la reducción de la matriz $A$ a bloques de Jordan permite calcular explícitamente la matriz exponencial $e^{At}$ y determinar el comportamiento y la [[estabilidad-lyapunov]] de las soluciones.
""",

    "lema-de-caratheodory": """---
tipo: concepto
dominio: analisis-matematico
etiquetas: [medida, existencia]
---
# Lema o Condiciones de Carathéodory

Las condiciones de **Carathéodory** generalizan el [[teorema-de-cauchy-peano]] para campos vectoriales $f(t, x)$ que no son necesariamente continuos respecto al tiempo $t$, permitiendo estudiar ecuaciones con saltos o excitaciones discontinuas.

Exige que $f(t, x)$ sea medible respecto a $t$, continua respecto a $x$, y que esté acotada por una función integrable Lebesgue $\ell(t)$. Bajo estas condiciones, se garantiza la existencia local de soluciones absolutamente continuas casi en todas partes.
""",

    "acotacion-uniforme": """---
tipo: concepto
dominio: analisis-matematico
etiquetas: [acotación, ascoli-arzela]
---
# Acotación Uniforme

Una familia o sucesión de funciones $\mathcal{F} = \{f_n: I \to \mathbb{R}^d\}$ está **uniformemente acotada** en un intervalo $I$ si existe una constante global fija $M > 0$ tal que para todas las funciones de la familia y todos los puntos del dominio:
$$\|f_n(t)\| \le M \quad \forall n \in \mathbb{N}, \;\forall t \in I$$

Junto con la equicontinuidad, constituye la hipótesis central exigida en el [[teorema-de-ascoli-arzela]] para garantizar compacidad y subconvergencia uniforme.
""",

    "aproximacion-oscilador-armonico": """---
tipo: concepto
dominio: fisica-matematica
etiquetas: [linealización, oscilaciones]
---
# Aproximación de Oscilador Armónico

La **aproximación de oscilador armónico** consiste en linealizar un sistema dinámico no lineal alrededor de un punto de equilibrio estable mínimo de potencial, mediante el desarrollo en serie de Taylor de primer orden.

Por ejemplo, para la [[ecuacion-del-pendulo]] $\ddot{\theta} + \frac{g}{l}\sin\theta = 0$, en torno al equilibrio $\theta = 0$, la aproximación $\sin\theta \approx \theta$ reduce el sistema no lineal al oscilador linealizado $\ddot{\theta} + \frac{g}{l}\theta = 0$.
""",

    "sistema-lineal-coeficientes-constantes": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [sistemas-lineales, jordan]
---
# Sistema Lineal con Coeficientes Constantes

Un **sistema lineal con coeficientes constantes** es un sistema autónomo vectorial governed by una matriz constante $A \in \mathbb{R}^{d \times d}$:
$$\dot{x} = A x$$

Su solución general analítica global para la [[condicion-inicial]] $x(0) = x_0$ viene dada exactamente por la exponencial matricial $x(t) = e^{At} x_0$, cuyo cálculo práctico se realiza simplificando los bloques propios a través de la [[forma-canonica-de-jordan]].
""",

    "solucion-general-ecuacion-diferencial": """---
tipo: concepto
dominio: ecuaciones-diferenciales
etiquetas: [soluciones, teoría-general]
---
# Solución General de una Ecuación Diferencial

La **solución general** de una ecuación diferencial de orden $n$ (o sistema vectorial de orden $d$) es una familia o conjunto completo de soluciones que contiene un número suficiente de constantes arbitrarias libres de integración (exactamente igual al orden o dimensión del sistema).

Permite recuperar cualquier solución particular del problema al especificar una [[condicion-inicial]] admisible única en su dominio de definición.
"""
}

async def upload_missing():
    config = {}
    db_path = "/data/maubot.db"
    if os.path.exists(db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT config FROM instance WHERE id='dev.julia.githubbot'").fetchone()
        if row and row[0]:
            yaml = YAML()
            config = yaml.load(row[0])
        conn.close()

    git = get_git_client(config)
    sem = asyncio.Semaphore(5)
    owner = config["default_owner"]
    repo = config["default_repo"]
    token = config["gitlab_token"]
    branch = config.get("default_branch", "main")

    async with aiohttp.ClientSession() as s:
        print(f"Subiendo {len(CONCEPTOS)} conceptos importantes faltantes a GitLab...")
        for slug, contenido in CONCEPTOS.items():
            path = f"okf/concepts/{slug}.md"
            msg = f"Crear concepto de teoría y matemáticas: {slug}"
            res = await git.subir_archivo(owner, repo, token, path, contenido, branch, msg, sem, lambda: None)
            print(f" [OK] {path}")

if __name__ == "__main__":
    asyncio.run(upload_missing())
