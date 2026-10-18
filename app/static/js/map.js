(function () {
  const el = document.getElementById("map");
  const map = L.map(el, { scrollWheelZoom: false }).setView([39.4699, -0.3763], 12);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap · © CARTO", maxZoom: 18, subdomains: "abcd",
  }).addTo(map);

  const status = document.getElementById("map-status");
  const list = document.getElementById("rank-list");

  fetch(el.dataset.url).then((r) => r.json()).then((data) => {
    if (!data.available) status.textContent = "Datos no disponibles ahora mismo. Reintenta en unos minutos.";
    else status.textContent = "Índice europeo de calidad del aire (EAQI) por distrito.";
    const items = data.districts.slice().sort((a, b) => (b.eaqi ?? -1) - (a.eaqi ?? -1));
    const group = [];
    items.forEach((d) => {
      const url = el.dataset.base + d.slug;
      const color = d.eaqi == null ? "#b9b4a8" : d.color;
      const circle = L.circle([d.lat, d.lon], {
        radius: 1100, color: color, weight: 2, fillColor: color, fillOpacity: 0.5,
      }).addTo(map);
      const tip = d.name + " · " + (d.eaqi ?? "—") + " (" + d.label + ")";
      circle.bindTooltip(tip, { className: "tip" });
      circle.on("click", () => (window.location.href = url));
      group.push(circle);

      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = url;
      a.style.setProperty("--c", color);
      const dot = Object.assign(document.createElement("span"), { className: "dot" });
      const name = Object.assign(document.createElement("span"), { textContent: d.name });
      const val = Object.assign(document.createElement("b"), { textContent: d.eaqi ?? "—" });
      a.append(dot, name, val);
      li.append(a);
      list.append(li);
    });
    if (group.length) map.fitBounds(L.featureGroup(group).getBounds().pad(0.1));
  }).catch(() => (status.textContent = "No se pudieron cargar los datos."));
})();
