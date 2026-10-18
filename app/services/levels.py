"""Traduce valores numéricos a niveles legibles (EAQI y polen)."""

# Índice europeo de calidad del aire (EEA): límite superior de cada tramo.
AQI_BOUNDS = (20, 40, 60, 80, 100)
AQI_LABELS = ("Buena", "Aceptable", "Moderada", "Mala", "Muy mala", "Extremadamente mala")
AQI_COLORS = ("#3fd0c4", "#7bc96f", "#f2c94c", "#f2994a", "#c0392b", "#7b2d8e")

POLLEN_LABELS = ("Bajo", "Moderado", "Alto", "Muy alto")
POLLEN_COLORS = ("#7bc96f", "#f2c94c", "#f2994a", "#c0392b")
POLLEN_NAMES = {
    "grass": "Gramíneas",
    "olive": "Olivo",
    "birch": "Abedul",
    "alder": "Aliso",
    "mugwort": "Artemisa",
    "ragweed": "Ambrosía",
}
# Umbrales orientativos (granos/m³): fin de "bajo", de "moderado" y de "alto".
# ponytail: umbrales fijos aproximados; ajustar con los de la red aerobiológica local si se necesita rigor clínico.
POLLEN_THRESHOLDS = {
    "grass": (10, 50, 150),
    "olive": (20, 100, 300),
    "birch": (30, 100, 500),
    "alder": (30, 100, 500),
    "mugwort": (10, 30, 100),
    "ragweed": (5, 20, 50),
}

POLLUTANT_NAMES = {"pm10": "PM10", "pm2_5": "PM2.5", "no2": "NO₂", "o3": "O₃"}


def aqi_level(value) -> int | None:
    """Índice 0..5 o None si no hay dato."""
    if value is None:
        return None
    for i, bound in enumerate(AQI_BOUNDS):
        if value <= bound:
            return i
    return len(AQI_BOUNDS)


def pollen_level(kind: str, value) -> int | None:
    """Índice 0..3 o None si no hay dato (fuera de temporada la API devuelve null)."""
    if value is None:
        return None
    for i, bound in enumerate(POLLEN_THRESHOLDS[kind]):
        if value < bound:
            return i
    return len(POLLEN_LABELS) - 1


def dominant_pollutant(sub_indexes: dict) -> str | None:
    """Contaminante con el sub-índice EAQI más alto. `sub_indexes`: {'pm10': 23, ...}."""
    valid = {k: v for k, v in sub_indexes.items() if v is not None}
    return max(valid, key=valid.get) if valid else None
