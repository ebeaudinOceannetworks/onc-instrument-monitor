(function() {
	'use strict';

	var state = {
		tab: 'map',
		map: null,
		mapReady: false,
		locationData: {},
		markers: {},
		selectedLocationCode: null,
		baseLayers: {},
		overlayLayers: {},
		layerControl: null,
		cableLayer: null,
		cableGeoJsonLayer: null,
		cableLayerLoaded: false,
		dashboardVariant: 'internal',
		publicDetailTabs: {},
		publicDetailOrder: [],
		activeDetailCode: null
	};

	function escapeHtml(value) {
		return String(value == null ? '' : value)
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;')
			.replace(/'/g, '&#39;');
	}

	function cssEscape(value) {
		if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);
		return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
	}

	function sanitizeId(value) {
		return String(value || '').replace(/[^A-Za-z0-9_-]/g, '_');
	}

	function truncateLabel(value, maxLength) {
		var text = String(value || '');
		if (text.length <= maxLength) return text;
		return text.slice(0, Math.max(0, maxLength - 1)) + '…';
	}

	function getDashboardVariant() {
		var body = document.body;
		if (!body) return 'internal';
		return body.getAttribute('data-dashboard-variant') || 'internal';
	}

	function isPublicLandingPage() {
		return state.dashboardVariant === 'public';
	}

	function isPublicDetailPage() {
		return state.dashboardVariant === 'public_detail' || state.dashboardVariant === 'public-detail';
	}

	function deviceHasDetailView(device) {
		return !!(device && (device.detailPagePath || device.sectionId));
	}

	function statusClass(status) {
		var cleaned = String(status || 'unknown').toLowerCase();
		if (['good', 'minor', 'warning', 'critical', 'error', 'diverted'].indexOf(cleaned) !== -1) {
			return cleaned;
		}
		return 'unknown';
	}

	function statusColor(status) {
		var key = statusClass(status);
		var colors = {
			good: '#28a745',
			minor: '#ffc107',
			warning: '#fd7e14',
			critical: '#dc3545',
			error: '#dc3545',
			diverted: '#6f42c1',
			unknown: '#6c757d'
		};
		return colors[key] || colors.unknown;
	}

	function safeList(value) {
		return Array.isArray(value) ? value : [];
	}

	function parseMapData() {
		var el = document.getElementById('hydrophone-map-data');
		if (!el) return [];
		try {
			var parsed = JSON.parse(el.textContent || '[]');
			return Array.isArray(parsed) ? parsed : [];
		} catch (e) {
			return [];
		}
	}

	function toLocationIndex(data) {
		var map = {};
		data.forEach(function(item) {
			if (!item || !item.locationCode) return;
			if (!map[item.locationCode]) {
				map[item.locationCode] = item;
			}
		});
		return map;
	}

	function hasCoordinates(device) {
		if (!device) return false;
		var lat = Number(device.latitude);
		var lon = Number(device.longitude);
		if (!isFinite(lat) || !isFinite(lon)) return false;
		return Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
	}

	function coordinateKey(lat, lon) {
		return Number(lat).toFixed(6) + ',' + Number(lon).toFixed(6);
	}

	function getCableGeoJsonUrl() {
		if (typeof buildDashboardUrl === 'function') {
			return buildDashboardUrl('/assets/onc_cables.geojson');
		}
		return '/assets/onc_cables.geojson';
	}

	function cableLayerStyle() {
		var isDark = document.documentElement && document.documentElement.getAttribute('data-theme') === 'dark';
		return {
			color: isDark ? '#c2ccd6' : '#5f6973',
			weight: 1.5,
			opacity: isDark ? 0.78 : 0.72,
			lineCap: 'round',
			lineJoin: 'round'
		};
	}

	function restyleCableLayer() {
		if (state.cableGeoJsonLayer && typeof state.cableGeoJsonLayer.setStyle === 'function') {
			state.cableGeoJsonLayer.setStyle(cableLayerStyle);
		}
	}

	function loadCableLayer() {
		if (!state.cableLayer || state.cableLayerLoaded || typeof window.fetch !== 'function') return;
		state.cableLayerLoaded = true;
		window.fetch(getCableGeoJsonUrl(), { credentials: 'same-origin' })
			.then(function(response) {
				if (!response.ok) throw new Error('Cable GeoJSON request failed: ' + response.status);
				return response.json();
			})
			.then(function(cableData) {
				if (!cableData || !state.cableLayer) return;
				state.cableGeoJsonLayer = window.L.geoJSON(cableData, {
					pane: 'oncCablePane',
					interactive: false,
					style: cableLayerStyle
				});
				state.cableGeoJsonLayer.addTo(state.cableLayer);
			})
			.catch(function(error) {
				console.warn('ONC cable layer could not be loaded.', error);
			});
	}

	function createMarkerIcon(status, offset) {
		var cls = statusClass(status);
		var dx = (offset && isFinite(offset.dx)) ? Number(offset.dx) : 0;
		var dy = (offset && isFinite(offset.dy)) ? Number(offset.dy) : 0;
		return window.L.divIcon({
			className: '',
			html: '<span class="map-status-marker status-' + cls + '"></span>',
			iconSize: [16, 16],
			iconAnchor: [8 - dx, 8 - dy]
		});
	}

	function buildPopupMetaRow(label, value) {
		return [
			'<div class="map-popup-meta-row">',
			'  <span class="label">' + escapeHtml(label) + ':</span>',
			'  <span class="value">' + escapeHtml(value == null || value === '' ? 'n/a' : value) + '</span>',
			'</div>'
		].join('');
	}

	function buildPopupHtml(device) {
		var status = (device && device.status) || {};
		var title = device.displayTitle || device.locationCode || 'Unknown location';
		var subtitle = device.displaySubtitle || device.locationName || '';
		var statusText = String(status.overallStatus || 'unknown').toUpperCase();
		var actions = [];
		var metaRows = [
			buildPopupMetaRow('Hydrophone', (device.sensorLabel || device.deviceName || '') + (device.sensorCode ? ' (' + device.sensorCode + ')' : '')),
			buildPopupMetaRow('Last data', status.lastDataDate || 'Unknown'),
			buildPopupMetaRow('Missing days', status.totalMissingDays == null ? 'n/a' : status.totalMissingDays),
			buildPopupMetaRow('JIRA tickets', device.jiraTicketCount || 0)
		];

		if (deviceHasDetailView(device)) {
			actions.push(
				'<button type="button" class="quicklook-primary-action" data-open-detail-location="' +
				escapeHtml(device.locationCode) +
				'">See More Details</button>'
			);
		}
		actions.push('<a href="' + escapeHtml(device.deviceDetailsUrl || '#') + '" target="_blank" rel="noopener">Device Details</a>');
		actions.push('<a href="' + escapeHtml(device.dataSearchUrl || '#') + '" target="_blank" rel="noopener">Data Search</a>');

		return [
			'<div class="map-popup-card">',
			'  <div class="map-popup-title">' + escapeHtml(title) + '</div>',
			subtitle ? '  <div class="map-popup-subtitle">' + escapeHtml(subtitle) + '</div>' : '',
			'  <div><span class="status-pill" style="background:' + statusColor(status.overallStatus) + ';">' + escapeHtml(statusText) + '</span></div>',
			'  <div class="map-popup-message">' + escapeHtml(status.statusMessage || 'No status message available.') + '</div>',
			'  <div class="map-popup-meta">' + metaRows.join('') + '</div>',
			'  <div class="detail-action-row">' + actions.join('') + '</div>',
			'</div>'
		].join('');
	}

	function computeMarkerOffsets() {
		var groups = {};
		var offsets = {};

		Object.keys(state.locationData).forEach(function(code) {
			var device = state.locationData[code];
			if (!hasCoordinates(device)) return;
			var key = coordinateKey(device.latitude, device.longitude);
			if (!groups[key]) {
				groups[key] = { codes: [] };
			}
			groups[key].codes.push(code);
		});

		Object.keys(groups).forEach(function(key) {
			var codes = groups[key].codes.slice().sort();
			if (codes.length === 1) {
				offsets[codes[0]] = { dx: 0, dy: 0 };
				return;
			}

			var radiusPx = codes.length <= 4 ? 11 : (codes.length <= 8 ? 15 : 19);
			codes.forEach(function(code, index) {
				var angle = (2 * Math.PI * index) / codes.length;
				offsets[code] = {
					dx: Math.round(radiusPx * Math.cos(angle)),
					dy: Math.round(radiusPx * Math.sin(angle))
				};
			});
		});

		return offsets;
	}

	function removeSidebarHighlight() {
		var links = document.querySelectorAll('.sidebar-map-target.sidebar-map-active');
		links.forEach(function(link) {
			link.classList.remove('sidebar-map-active');
		});
	}

	function revealSidebarPath(locationCode) {
		if (!locationCode) return;
		var selector = '.sidebar-map-target[data-location-code="' + cssEscape(locationCode) + '"]';
		var link = document.querySelector(selector);
		if (!link) return;
		var current = link.parentElement;
		while (current) {
			if (current.tagName && current.tagName.toLowerCase() === 'details') {
				current.open = true;
			}
			current = current.parentElement;
		}
		if (typeof link.scrollIntoView === 'function') {
			link.scrollIntoView({ block: 'nearest' });
		}
	}

	function addSidebarHighlight(locationCode) {
		removeSidebarHighlight();
		if (!locationCode) return;
		var selector = '.sidebar-map-target[data-location-code="' + cssEscape(locationCode) + '"]';
		var link = document.querySelector(selector);
		if (link) {
			revealSidebarPath(locationCode);
			link.classList.add('sidebar-map-active');
		}
	}

	function clearMarkerHighlight() {
		Object.keys(state.markers).forEach(function(code) {
			var marker = state.markers[code];
			if (!marker || !marker.getElement) return;
			var node = marker.getElement();
			if (!node) return;
			var dot = node.querySelector('.map-status-marker');
			if (dot) dot.classList.remove('is-selected');
		});
	}

	function highlightMarker(locationCode) {
		clearMarkerHighlight();
		var marker = state.markers[locationCode];
		if (!marker || !marker.getElement) return;
		var node = marker.getElement();
		if (!node) return;
		var dot = node.querySelector('.map-status-marker');
		if (dot) dot.classList.add('is-selected');
	}

	function getMarkerTarget(locationCode, device) {
		var marker = state.markers[locationCode];
		var target = marker && marker.getLatLng ? marker.getLatLng() : null;
		return {
			marker: marker,
			lat: target ? target.lat : Number(device.latitude),
			lon: target ? target.lng : Number(device.longitude)
		};
	}

	function recenterSelectedMarker(locationCode, target, zoom) {
		if (!target || !state.mapReady || !state.map) return;
		if (state.selectedLocationCode !== locationCode) return;
		state.map.setView([target.lat, target.lon], zoom, { animate: false });
	}

	function renderQuickLook(device) {
		var panel = document.getElementById('map-quicklook-panel');
		if (!panel || !device) return;
		var status = device.status || {};
		var missingTypes = safeList(status.missingDataTypes);
		var mappingNames = safeList(device.mappingNames);
		var statusText = String(status.overallStatus || 'unknown').toUpperCase();
		var statusStyle = 'background:' + statusColor(status.overallStatus) + ';';
		var divertedText = status.isDiverted ? ('Yes (' + (status.divertSince || 'Unknown') + ')') : 'No';
		var title = device.displayTitle || device.locationCode || 'Unknown location';
		var subtitle = device.displaySubtitle || device.locationName || '';
		var detailActionHtml = '';
		var metaRows = [
			'<div class="meta-row"><span class="label">Device:</span><span>' + escapeHtml(device.deviceName || '') + ' (' + escapeHtml(device.deviceID) + ')</span></div>',
			'<div class="meta-row"><span class="label">Depth:</span><span>' + escapeHtml(device.depth || 'n/a') + ' m</span></div>',
			'<div class="meta-row"><span class="label">Last data:</span><span>' + escapeHtml(status.lastDataDate || 'Unknown') + '</span></div>',
			'<div class="meta-row"><span class="label">Days since data:</span><span>' + escapeHtml(status.daysSinceLastData == null ? 'n/a' : status.daysSinceLastData) + '</span></div>',
			'<div class="meta-row"><span class="label">Missing days:</span><span>' + escapeHtml(status.totalMissingDays == null ? 'n/a' : status.totalMissingDays) + '</span></div>',
			'<div class="meta-row"><span class="label">Diverted:</span><span>' + escapeHtml(divertedText) + '</span></div>',
			'<div class="meta-row"><span class="label">JIRA tickets:</span><span>' + escapeHtml(device.jiraTicketCount || 0) + '</span></div>',
			'<div class="meta-row"><span class="label">Missing types:</span><span>' + escapeHtml(missingTypes.length ? missingTypes.join(', ') : 'None') + '</span></div>'
		];

		if (device.siteName) {
			metaRows.unshift('<div class="meta-row"><span class="label">Site:</span><span>' + escapeHtml(device.siteName) + (device.siteCode ? ' (' + escapeHtml(device.siteCode) + ')' : '') + '</span></div>');
		}
		if (device.sensorLabel || device.sensorCode) {
			metaRows.splice(device.siteName ? 1 : 0, 0, '<div class="meta-row"><span class="label">Hydrophone:</span><span>' + escapeHtml(device.sensorLabel || device.deviceName || '') + (device.sensorCode ? ' (' + escapeHtml(device.sensorCode) + ')' : '') + '</span></div>');
		}
		if (mappingNames.length) {
			metaRows.push('<div class="meta-row"><span class="label">Mapped name:</span><span>' + escapeHtml(mappingNames.join(', ')) + '</span></div>');
		}

		if (deviceHasDetailView(device)) {
			detailActionHtml = '<button type="button" class="quicklook-primary-action" data-open-detail-location="' + escapeHtml(device.locationCode) + '">See More Details</button>';
		}

		panel.innerHTML = [
			'<h3>' + escapeHtml(title) + '</h3>',
			(subtitle ? '<p>' + escapeHtml(subtitle) + '</p>' : ''),
			'<div style="margin-bottom:8px;"><span class="status-pill" style="' + statusStyle + '">' + escapeHtml(statusText) + '</span></div>',
			'<p>' + escapeHtml(status.statusMessage || 'No status message available.') + '</p>',
			metaRows.join(''),
			'<div class="detail-action-row">',
			detailActionHtml,
			'  <a href="' + escapeHtml(device.deviceDetailsUrl || '#') + '" target="_blank" rel="noopener">Device Details</a>',
			'  <a href="' + escapeHtml(device.dataSearchUrl || '#') + '" target="_blank" rel="noopener">Data Search</a>',
			'  <a href="' + escapeHtml(device.searchUrl || '#') + '" target="_blank" rel="noopener">Search Hydrophone</a>',
			'</div>'
		].join('');
	}

	function getPublicDetailButtonsContainer() {
		return document.getElementById('public-detail-tab-buttons');
	}

	function getPublicDetailPanelsContainer() {
		return document.getElementById('public-detail-tab-panels');
	}

	function getInternalDetailSource() {
		return document.getElementById('internal-detail-source');
	}

	function hasPublicDetailTabs() {
		return state.publicDetailOrder.length > 0;
	}

	function getPublicDetailButtonId(locationCode) {
		return 'public-detail-tab-' + sanitizeId(locationCode);
	}

	function getPublicDetailPanelId(locationCode) {
		return 'public-detail-panel-' + sanitizeId(locationCode);
	}

	function resizePublicDetailFrame(frame) {
		if (!frame || !frame.contentWindow) return;
		try {
			var doc = frame.contentWindow.document;
			if (!doc || !doc.body) return;
			var nextHeight = Math.max(
				doc.body.scrollHeight || 0,
				doc.documentElement ? doc.documentElement.scrollHeight || 0 : 0,
				780
			);
			frame.style.height = String(nextHeight + 12) + 'px';
		} catch (e) {
			// Ignore sizing issues if same-origin access is unavailable.
		}
	}

	function resizeActivePublicDetailFrame() {
		if (!state.activeDetailCode) return;
		var entry = state.publicDetailTabs[state.activeDetailCode];
		if (entry && entry.frame) resizePublicDetailFrame(entry.frame);
	}

	function syncPublicDetailTabSelection() {
		state.publicDetailOrder.forEach(function(code) {
			var entry = state.publicDetailTabs[code];
			if (!entry) return;
			var isActive = state.tab === 'details' && state.activeDetailCode === code;
			entry.chip.classList.toggle('is-active', isActive);
			entry.selectButton.classList.toggle('active', isActive);
			entry.selectButton.setAttribute('aria-selected', String(isActive));
			entry.panel.hidden = false;
			entry.panel.classList.toggle('is-background-loading', !isActive);
		});
	}

	function createPublicDetailTab(device) {
		var code = device && device.locationCode;
		if (!code) return null;
		if (state.publicDetailTabs[code]) return state.publicDetailTabs[code];

		var buttonsContainer = getPublicDetailButtonsContainer();
		var panelsContainer = getPublicDetailPanelsContainer();
		if (!buttonsContainer || !panelsContainer) return null;

		var chip = document.createElement('div');
		chip.className = 'detail-tab-chip';
		chip.setAttribute('data-location-code', code);

		var selectButton = document.createElement('button');
		selectButton.type = 'button';
		selectButton.id = getPublicDetailButtonId(code);
		selectButton.className = 'dashboard-tab-button detail-tab-select';
		selectButton.setAttribute('role', 'tab');
		selectButton.setAttribute('aria-controls', getPublicDetailPanelId(code));
		selectButton.setAttribute('aria-selected', 'false');
		selectButton.setAttribute('data-detail-location', code);
		selectButton.title = (device.siteName || device.displayTitle || code) + ' - ' + (device.sensorLabel || code);

		var label = document.createElement('span');
		label.className = 'detail-tab-label';
		label.textContent = truncateLabel(device.sensorLabel || device.sensorCode || device.displayTitle || code, 32);
		selectButton.appendChild(label);

		var closeButton = document.createElement('button');
		closeButton.type = 'button';
		closeButton.className = 'detail-tab-close';
		closeButton.setAttribute('aria-label', 'Close ' + (device.sensorLabel || code) + ' tab');
		closeButton.setAttribute('data-close-detail-location', code);
		closeButton.textContent = '×';

		chip.appendChild(selectButton);
		chip.appendChild(closeButton);
		buttonsContainer.appendChild(chip);

		var panel = document.createElement('div');
		panel.id = getPublicDetailPanelId(code);
		panel.className = 'detail-tab-content';
		panel.setAttribute('role', 'tabpanel');
		panel.setAttribute('aria-labelledby', getPublicDetailButtonId(code));
		panel.hidden = true;
		var frame = null;
		var sourceSection = null;
		var sourceContainer = null;

		if (device.detailPagePath) {
			frame = document.createElement('iframe');
			frame.className = 'public-detail-frame';
			frame.setAttribute('title', (device.displayTitle || code) + ' details');
			frame.setAttribute('loading', 'eager');
			frame.setAttribute('referrerpolicy', 'same-origin');
			frame.setAttribute('src', typeof buildDashboardUrl === 'function' ? buildDashboardUrl(device.detailPagePath) : device.detailPagePath);
			frame.addEventListener('load', function() {
				resizePublicDetailFrame(frame);
				window.setTimeout(function() { resizePublicDetailFrame(frame); }, 250);
				window.setTimeout(function() { resizePublicDetailFrame(frame); }, 1200);
			});
			panel.appendChild(frame);
		} else if (device.sectionId) {
			sourceContainer = getInternalDetailSource();
			sourceSection = document.getElementById(device.sectionId);
			if (!sourceSection && sourceContainer) {
				var sourceTemplate = document.getElementById(device.sectionId + '_template');
				if (!sourceTemplate) {
					sourceTemplate = sourceContainer.querySelector('template[data-section-id="' + device.sectionId + '"]');
				}
				if (sourceTemplate && sourceTemplate.content && sourceTemplate.content.firstElementChild) {
					sourceSection = sourceTemplate.content.firstElementChild.cloneNode(true);
					sourceContainer = null;
				}
			}
			if (!sourceSection) return null;
			panel.appendChild(sourceSection);
		}

		panelsContainer.appendChild(panel);

		var entry = {
			device: device,
			chip: chip,
			selectButton: selectButton,
			closeButton: closeButton,
			panel: panel,
			frame: frame,
			sourceSection: sourceSection,
			sourceContainer: sourceContainer
		};
		state.publicDetailTabs[code] = entry;
		state.publicDetailOrder.push(code);
		return entry;
	}

	function activatePublicDetailTab(locationCode) {
		if (!state.publicDetailTabs[locationCode]) return;
		state.activeDetailCode = locationCode;
		showPanel('details');
	}

	function closePublicDetailTab(locationCode) {
		var entry = state.publicDetailTabs[locationCode];
		if (!entry) return;

		var nextCode = null;
		if (state.activeDetailCode === locationCode) {
			var currentIndex = state.publicDetailOrder.indexOf(locationCode);
			nextCode = state.publicDetailOrder[currentIndex + 1] || state.publicDetailOrder[currentIndex - 1] || null;
		}

		if (entry.sourceSection && entry.sourceContainer) {
			entry.sourceContainer.appendChild(entry.sourceSection);
		}
		entry.chip.remove();
		entry.panel.remove();
		delete state.publicDetailTabs[locationCode];
		state.publicDetailOrder = state.publicDetailOrder.filter(function(code) {
			return code !== locationCode;
		});

		if (!hasPublicDetailTabs()) {
			state.activeDetailCode = null;
			showPanel('map');
			return;
		}

		if (state.activeDetailCode === locationCode) {
			state.activeDetailCode = nextCode;
			showPanel('details');
			return;
		}

		syncPublicDetailTabSelection();
	}

	function loadPublicDetail(device) {
		if (!device || !deviceHasDetailView(device)) return;
		createPublicDetailTab(device);
		activatePublicDetailTab(device.locationCode);
	}

	function openLocation(locationCode, options) {
		var opts = options || {};
		var device = state.locationData[locationCode];
		if (!device) return;
		state.selectedLocationCode = locationCode;

		if (state.mapReady && hasCoordinates(device)) {
			var mapTarget = getMarkerTarget(locationCode, device);
			var marker = mapTarget.marker;
			var zoom = opts.zoom || Math.max(state.map.getZoom(), 6);
			state.map.setView([mapTarget.lat, mapTarget.lon], zoom, { animate: true });
			if (marker && marker.setPopupContent) {
				marker.setPopupContent(buildPopupHtml(device));
			}
			if (marker && marker.openPopup) marker.openPopup();
			if (opts.keepMarkerCentered) {
				window.setTimeout(function() {
					recenterSelectedMarker(locationCode, mapTarget, zoom);
				}, 0);
				window.setTimeout(function() {
					recenterSelectedMarker(locationCode, mapTarget, zoom);
				}, 220);
			}
		}

		renderQuickLook(device);
		addSidebarHighlight(locationCode);
		highlightMarker(locationCode);
	}

	function initMap() {
		if (state.mapReady) return;
		var mapEl = document.getElementById('hydrophone-status-map');
		if (!mapEl) return;

		if (!window.L) {
			mapEl.innerHTML = '<div class="hydrophone-map-empty">Leaflet could not be loaded. Map view is unavailable.</div>';
			return;
		}

		state.map = window.L.map(mapEl, {
			minZoom: 2,
			maxZoom: 13,
			worldCopyJump: false
		});

		state.map.createPane('oncCablePane');
		state.map.getPane('oncCablePane').style.zIndex = 425;
		state.map.getPane('oncCablePane').style.pointerEvents = 'none';

		var osm = window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{y}/{x}.png', {
			maxZoom: 19,
			attribution: '&copy; OpenStreetMap contributors'
		});

		var oceanBase = window.L.tileLayer(
			'https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}',
			{
				maxNativeZoom: 10,
				maxZoom: 13,
				attribution: 'Tiles &copy; Esri, GEBCO, Garmin, NaturalVue'
			}
		);

		var oceanReference = window.L.tileLayer(
			'https://services.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Reference/MapServer/tile/{z}/{y}/{x}',
			{
				maxNativeZoom: 10,
				maxZoom: 13,
				attribution: 'Labels &copy; Esri'
			}
		);

		var satellite = window.L.tileLayer(
			'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
			{
				maxZoom: 19,
				attribution: 'Tiles &copy; Esri'
			}
		);

		var placeLabels = window.L.tileLayer(
			'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
			{
				maxZoom: 19,
				attribution: 'Labels &copy; Esri'
			}
		);

		state.baseLayers = {
			'Ocean Basemap (Bathymetry)': oceanBase,
			'Satellite Imagery': satellite,
			'Street Map (OSM)': osm
		};
		state.cableLayer = window.L.layerGroup();
		state.overlayLayers = {
			'ONC Cable Routes': state.cableLayer,
			'Ocean Features / Labels': oceanReference,
			'Place Labels': placeLabels
		};

		oceanBase.addTo(state.map);
		state.cableLayer.addTo(state.map);
		oceanReference.addTo(state.map);
		loadCableLayer();

		state.layerControl = window.L.control.layers(state.baseLayers, state.overlayLayers, {
			collapsed: false,
			position: 'topleft'
		}).addTo(state.map);

		state.map.setView([70.0, -96.0], 2);
		var markerOffsets = computeMarkerOffsets();
		var markerCount = 0;

		Object.keys(state.locationData).forEach(function(code) {
			var device = state.locationData[code];
			if (!hasCoordinates(device)) return;
			var offset = markerOffsets[code] || { dx: 0, dy: 0 };

			var marker = window.L.marker([Number(device.latitude), Number(device.longitude)], {
				icon: createMarkerIcon(device.status && device.status.overallStatus, offset),
				title: code
			});
			marker.bindPopup(buildPopupHtml(device), {
				maxWidth: 340,
				className: 'hydrophone-status-popup'
			});
			marker.on('click', function() {
				openLocation(code, { zoom: Math.max(state.map.getZoom(), 6) });
			});
			marker.addTo(state.map);
			state.markers[code] = marker;
			markerCount += 1;
		});

		if (markerCount === 0) {
			mapEl.innerHTML = '<div class="hydrophone-map-empty">No hydrophone coordinates are available for the current dataset.</div>';
			return;
		}

		state.mapReady = true;
		window.setTimeout(function() {
			state.map.invalidateSize();
		}, 0);
	}

	function showPanel(tabName) {
		var isMap;
		var detailsPanel = document.getElementById('details-tab-panel');
		var mapPanel = document.getElementById('map-tab-panel');
		var mapBtn = document.getElementById('map-tab-button');
		if (tabName === 'details' && (!hasPublicDetailTabs() || !state.activeDetailCode)) {
			tabName = 'map';
		}

		state.tab = tabName === 'map' ? 'map' : 'details';
		isMap = state.tab === 'map';

		if (mapBtn) {
			mapBtn.classList.toggle('active', isMap);
			mapBtn.setAttribute('aria-selected', String(isMap));
		}
		if (detailsPanel) {
			var shouldHideDetailsPanel = !hasPublicDetailTabs();
			detailsPanel.hidden = shouldHideDetailsPanel;
			detailsPanel.classList.remove('tab-panel-collapsed');
			detailsPanel.classList.toggle('is-background-loading', !shouldHideDetailsPanel && isMap);
			detailsPanel.setAttribute('aria-hidden', String(shouldHideDetailsPanel || isMap));
		}
		if (mapPanel) {
			mapPanel.hidden = !isMap;
			mapPanel.setAttribute('aria-hidden', String(!isMap));
		}
		syncPublicDetailTabSelection();

		if (isMap) {
			initMap();
			if (state.mapReady) state.map.invalidateSize();
			if (state.selectedLocationCode) {
				openLocation(state.selectedLocationCode, { zoom: 7 });
			}
			if (hasPublicDetailTabs()) {
				window.setTimeout(resizeActivePublicDetailFrame, 40);
			}
		} else {
			resizeActivePublicDetailFrame();
			document.dispatchEvent(new CustomEvent('hydrophone:details-visible'));
		}
	}

	function bindTabButtons() {
		var mapBtn = document.getElementById('map-tab-button');
		if (mapBtn) {
			mapBtn.addEventListener('click', function() {
				showPanel('map');
			});
		}
	}

	function bindSidebarForMap() {
		var links = document.querySelectorAll('.sidebar-map-target[data-location-code]');
		links.forEach(function(link) {
			link.addEventListener('click', function(event) {
				var code = link.getAttribute('data-location-code');
				if (!code) return;
				event.preventDefault();
				showPanel('map');
				openLocation(code, { zoom: 7, keepMarkerCentered: true });
			});
		});
	}

	function bindDetailOpenActions() {
		document.addEventListener('click', function(event) {
			var target = event.target;
			var detailButton = target && target.closest ? target.closest('[data-open-detail-location]') : null;
			if (!detailButton) return;
			event.preventDefault();
			var detailCode = detailButton.getAttribute('data-open-detail-location');
			if (!detailCode) return;
			if (typeof closeNotificationsPanel === 'function') {
				closeNotificationsPanel();
			}
			openLocation(detailCode, { zoom: 7 });
			loadPublicDetail(state.locationData[detailCode]);
		});
	}

	function bindPublicDetailTabActions() {
		var buttonsContainer = getPublicDetailButtonsContainer();
		if (!buttonsContainer) return;
		buttonsContainer.addEventListener('click', function(event) {
			var target = event.target;
			var closeButton = target && target.closest ? target.closest('[data-close-detail-location]') : null;
			if (closeButton) {
				event.preventDefault();
				closePublicDetailTab(closeButton.getAttribute('data-close-detail-location'));
				return;
			}

			var selectButton = target && target.closest ? target.closest('[data-detail-location]') : null;
			if (!selectButton) return;
			event.preventDefault();
			activatePublicDetailTab(selectButton.getAttribute('data-detail-location'));
		});
	}

	function initialize() {
		state.dashboardVariant = getDashboardVariant();
		if (isPublicDetailPage()) {
			return;
		}

		var raw = parseMapData();
		state.locationData = toLocationIndex(raw);
		bindTabButtons();
		bindSidebarForMap();
		bindDetailOpenActions();
		bindPublicDetailTabActions();
		window.addEventListener('resize', function() {
			if (hasPublicDetailTabs()) {
				resizeActivePublicDetailFrame();
			}
		});

		showPanel('map');

		window.hydrophoneMapView = {
			showPanel: showPanel,
			openLocation: openLocation,
			loadPublicDetail: loadPublicDetail,
			closePublicDetailTab: closePublicDetailTab,
			restyleCableLayer: restyleCableLayer,
			getState: function() {
				var bounds = null;
				var center = null;
				if (state.mapReady && state.map) {
					var b = state.map.getBounds();
					var c = state.map.getCenter();
					bounds = {
						north: b.getNorth(),
						south: b.getSouth(),
						east: b.getEast(),
						west: b.getWest()
					};
					center = {
						lat: c.lat,
						lng: c.lng
					};
				}
				return {
					tab: state.tab,
					dashboardVariant: state.dashboardVariant,
					selectedLocationCode: state.selectedLocationCode,
					activeDetailCode: state.activeDetailCode,
					openDetailTabs: state.publicDetailOrder.slice(),
					mapReady: state.mapReady,
					markerCount: Object.keys(state.markers).length,
					activeBaseLayer: Object.keys(state.baseLayers).find(function(name) {
						var layer = state.baseLayers[name];
						return !!(layer && state.map && state.map.hasLayer(layer));
					}) || null,
					activeOverlays: Object.keys(state.overlayLayers).filter(function(name) {
						var layer = state.overlayLayers[name];
						return !!(layer && state.map && state.map.hasLayer(layer));
					}),
					cableLayerLoaded: state.cableLayerLoaded,
					cableFeatureCount: state.cableGeoJsonLayer && typeof state.cableGeoJsonLayer.getLayers === 'function' ? state.cableGeoJsonLayer.getLayers().length : 0,
					zoom: state.mapReady && state.map ? state.map.getZoom() : null,
					center: center,
					bounds: bounds
				};
			}
		};

		if (window.MutationObserver && document.documentElement) {
			var themeObserver = new MutationObserver(function(mutations) {
				mutations.forEach(function(mutation) {
					if (mutation.attributeName === 'data-theme') {
						restyleCableLayer();
					}
				});
			});
			themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
		}
	}

	document.addEventListener('DOMContentLoaded', initialize);
})();
