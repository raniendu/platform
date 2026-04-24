function createMarkerStyle(type) {
  const base = {
    radius: 6,
    weight: 1.5,
    opacity: 1,
    fillOpacity: 1,
    color: '#111111',
  };

  if (type === 'from') {
    return { ...base, radius: 8, fillColor: '#ffffff' };
  }
  if (type === 'lived') {
    return { ...base, radius: 6, fillColor: '#ffffff' };
  }
  return { ...base, radius: 5, fillColor: '#444444' };
}

document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('travel-map');
  if (!container || typeof L === 'undefined') {
    return;
  }

  container.setAttribute('role', 'application');
  container.setAttribute('aria-label', 'Map of places lived and visited');

  let pins = [];
  try {
    pins = JSON.parse(container.dataset.pins || '[]');
  } catch (error) {
    pins = [];
  }

  const map = L.map(container, {
    zoomControl: true,
    scrollWheelZoom: false,
    keyboard: true,
  });

  const lightTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors',
  });

  const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors',
  });

  function applyThemeLayer(theme) {
    if (theme === 'dark') {
      if (map.hasLayer(lightTiles)) map.removeLayer(lightTiles);
      darkTiles.addTo(map);
    } else {
      if (map.hasLayer(darkTiles)) map.removeLayer(darkTiles);
      lightTiles.addTo(map);
    }
  }

  applyThemeLayer(document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');

  const markers = [];
  pins.forEach((pin) => {
    if (typeof pin.lat !== 'number' || typeof pin.lng !== 'number') {
      return;
    }
    const marker = L.circleMarker([pin.lat, pin.lng], createMarkerStyle(pin.type));
    const title = pin.name || 'Travel pin';
    const lines = [title];
    if (pin.type) {
      lines.push(pin.type.charAt(0).toUpperCase() + pin.type.slice(1));
    }
    if (pin.date) {
      lines.push(pin.date);
    }
    marker.bindPopup(lines.join('<br>'));
    marker.addTo(map);
    markers.push(marker);
  });

  if (markers.length) {
    const group = L.featureGroup(markers);
    map.fitBounds(group.getBounds(), { padding: [24, 24] });
  } else {
    map.setView([20, 0], 2);
  }

  let zoomTimer = null;
  container.addEventListener(
    'wheel',
    (event) => {
      if (event.ctrlKey || event.metaKey) {
        map.scrollWheelZoom.enable();
        if (zoomTimer) {
          clearTimeout(zoomTimer);
        }
        zoomTimer = setTimeout(() => map.scrollWheelZoom.disable(), 1000);
      } else {
        map.scrollWheelZoom.disable();
        event.preventDefault();
      }
    },
    { passive: false }
  );

  window.addEventListener('resize', () => {
    map.invalidateSize();
  });

  document.addEventListener('themechange', (event) => {
    applyThemeLayer(event.detail?.theme === 'dark' ? 'dark' : 'light');
  });
});
