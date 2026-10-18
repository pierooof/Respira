(function () {
  const box = document.getElementById("history");
  const metric = document.getElementById("metric");
  const note = document.getElementById("history-note");
  const css = getComputedStyle(document.documentElement);
  const teal = css.getPropertyValue("--teal").trim();
  const PALETTE = ["#d9542b", "#0f3d3a", "#c9a227", "#6b8e23", "#7b2d8e", "#2a7fb8"];
  const LABELS = { eaqi: "EAQI", pm10: "PM10 (µg/m³)", pm2_5: "PM2.5 (µg/m³)", no2: "NO₂ (µg/m³)", o3: "O₃ (µg/m³)" };
  let airChart, pollenChart, data;

  const fmt = (iso) => { const [, m, d] = iso.split("-"); return d + "/" + m; };

  function draw() {
    const key = metric.value;
    airChart && airChart.destroy();
    airChart = new Chart(document.getElementById("chart-air"), {
      type: "line",
      data: { labels: data.dates.map(fmt), datasets: [{
        label: LABELS[key], data: data[key], borderColor: teal, backgroundColor: teal + "22",
        fill: true, tension: 0.3, pointRadius: 3,
        pointBackgroundColor: key === "eaqi" ? data[key].map((v) => data.aqi_colors[data.aqi_bounds.findIndex((b) => v <= b) < 0 ? 5 : data.aqi_bounds.findIndex((b) => v <= b)]) : teal,
      }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
    });
  }

  fetch(box.dataset.url).then((r) => r.json()).then((d) => {
    data = d;
    if (d.dates.length < 2) note.textContent = "El histórico se va guardando cada día; vuelve en unos días para ver la evolución completa.";
    draw();
    const kinds = Object.keys(d.pollen).filter((k) => d.pollen[k].some((v) => v != null));
    pollenChart = new Chart(document.getElementById("chart-pollen"), {
      type: "line",
      data: { labels: d.dates.map(fmt), datasets: kinds.map((k, i) => ({
        label: d.pollen_names[k], data: d.pollen[k], borderColor: PALETTE[i % PALETTE.length], tension: 0.3, pointRadius: 2,
      })) },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } },
    });
    metric.addEventListener("change", draw);
  });
})();
