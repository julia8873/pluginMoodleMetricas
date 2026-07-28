from .mensajes import MensajesMixin
from .pregunta import PreguntaMixin
from .ficheros import FicherosMixin
from .estadisticas import EstadisticasMixin
from .trazabilidad import TrazabilidadMixin
from .documento import DocumentoMixin
from .borrar import BorrarMixin
from .mover import MoverMixin
from .carpeta import CarpetaMixin
from .flashcard import FlashcardMixin
from .ejercicio import EjercicioMixin
from .concepto import ConceptoMixin
from .feynman import FeynmanMixin
from .repasartema import RepasarTemaMixin
from .ejerciciostema import EjerciciosTemaMixin
from .resumen import ResumenMixin
from .mapa import MapaMixin
from .ayuda import AyudaMixin
from .stop import StopMixin


class ComandosMixin(
    MensajesMixin, PreguntaMixin, FicherosMixin, EstadisticasMixin, TrazabilidadMixin, DocumentoMixin, BorrarMixin, MoverMixin, CarpetaMixin, FlashcardMixin, EjercicioMixin, ConceptoMixin, FeynmanMixin, RepasarTemaMixin, EjerciciosTemaMixin, ResumenMixin, MapaMixin, AyudaMixin, StopMixin
):
    """Punto de composición: agrega todos los mixins de comandos individuales."""
    pass
