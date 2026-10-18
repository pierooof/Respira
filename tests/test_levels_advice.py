from app.services import advice, levels


def test_aqi_level_boundaries():
    assert levels.aqi_level(None) is None
    assert levels.aqi_level(20) == 0
    assert levels.aqi_level(21) == 1
    assert levels.aqi_level(100) == 4
    assert levels.aqi_level(150) == 5
    assert levels.AQI_LABELS[levels.aqi_level(45)] == "Moderada"


def test_pollen_level_labels():
    assert levels.pollen_level("grass", None) is None
    assert levels.POLLEN_LABELS[levels.pollen_level("grass", 0)] == "Bajo"
    assert levels.POLLEN_LABELS[levels.pollen_level("grass", 10)] == "Moderado"
    assert levels.POLLEN_LABELS[levels.pollen_level("grass", 60)] == "Alto"
    assert levels.POLLEN_LABELS[levels.pollen_level("grass", 999)] == "Muy alto"


def test_dominant_pollutant():
    assert levels.dominant_pollutant({"pm10": 10, "no2": 55, "o3": None}) == "no2"
    assert levels.dominant_pollutant({"pm10": None}) is None


def test_advice_by_level():
    assert "evita el deporte" in advice.advice(3, None)[0].lower()
    out = advice.advice(0, 3)
    assert len(out) == 2 and "alérgico" in out[1]
    assert advice.advice(None, 0) == []
