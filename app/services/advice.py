"""Recomendaciones sencillas según el nivel de calidad del aire y de polen."""

_AIR = (
    "Aire excelente: disfruta de actividades al aire libre sin restricciones.",
    "Calidad aceptable: apta para todos; las personas muy sensibles pueden notar molestias leves.",
    "Calidad moderada: si eres sensible (asma, alergias), reduce el esfuerzo intenso al aire libre.",
    "Calidad mala: evita el deporte intenso al aire libre y prefiere espacios interiores.",
    "Calidad muy mala: limita las salidas, ventila a primera hora o por la noche y evita hacer ejercicio fuera.",
    "Calidad extrema: permanece en interiores y evita cualquier esfuerzo físico en la calle.",
)
_POLLEN = (
    None,
    "Polen moderado: si eres alérgico, ten a mano tu medicación.",
    "Polen alto: evita el deporte al aire libre en las horas centrales y ventila de noche.",
    "Polen muy alto: si eres alérgico, limita las salidas, usa gafas de sol y date una ducha al volver.",
)


def advice(aqi_idx: int | None, pollen_idx: int | None) -> list[str]:
    """Lista de consejos; `pollen_idx` es el nivel más alto entre todos los tipos."""
    out = []
    if aqi_idx is not None:
        out.append(_AIR[aqi_idx])
    if pollen_idx is not None and _POLLEN[pollen_idx]:
        out.append(_POLLEN[pollen_idx])
    return out
