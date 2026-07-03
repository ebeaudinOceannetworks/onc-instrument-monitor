/**
 * Robust scalar plot rendering with universal data format parsing.
 */
(function() {
	'use strict';

	// 🚀 THE UNIVERSAL PARSER: Maps any incoming python serialization format safely
	function parseRow(r) {
		if (!r) return null;
		var tStr = null;
		var vVal = null;

		if (r.t !== undefined && r.v !== undefined) {
			// Handles explicit {"t": ..., "v": ...}
			tStr = r.t;
			vVal = r.v;
		} else if (Array.isArray(r) && r.length >= 2) {
			// Handles flat pairs ["2026-07-01...", 9.22]
			tStr = r[0];
			vVal = r[1];
		} else if (typeof r === 'object') {
			var keys = Object.keys(r);
			if (keys.length === 1) {
				// Handles timestamp keys {"2026-07-01...": 9.22}
				tStr = keys[0];
				vVal = r[keys[0]];
			} else if (r.datetime !== undefined && r.value !== undefined) {
				// Handles full database keys {"datetime": ..., "value": ...}
				tStr = r.datetime;
				vVal = r.value;
			}
		}

		if (!tStr) return null;
		var ts = Math.floor(Date.parse(tStr) / 1000);
		if (isNaN(ts)) return null;

		return { t: ts, v: (vVal !== null && vVal !== undefined) ? Number(vVal) : null };
	}

	function toSeries(rows) {
		if (!rows || !rows.length) return [[], []];
		var parsed = [];
		rows.forEach(function(row) {
			var p = parseRow(row);
			if (p) parsed.push(p);
		});
		parsed.sort(function(a, b) { return a.t - b.t; });
		return [parsed.map(function(r) { return r.t; }), parsed.map(function(r) { return r.v; })];
	}

	function toUnifiedSeries(cleanRows, rawRows) {
		var cleanMap = {};
		var rawMap = {};
		var allTimestampsSet = new Set();

		if (cleanRows) {
			cleanRows.forEach(function(row) {
				var p = parseRow(row);
				if (p) {
					cleanMap[p.t] = p.v;
					allTimestampsSet.add(p.t);
				}
			});
		}

		if (rawRows) {
			rawRows.forEach(function(row) {
				var p = parseRow(row);
				if (p) {
					rawMap[p.t] = p.v;
					allTimestampsSet.add(p.t);
				}
			});
		}

		var unifiedX = Array.from(allTimestampsSet).sort(function(a, b) { return a - b; });
		var unifiedYClean = [];
		var unifiedYRaw = [];

		unifiedX.forEach(function(ts) {
			unifiedYClean.push(cleanMap[ts] !== undefined ? cleanMap[ts] : null);
			unifiedYRaw.push(rawMap[ts] !== undefined ? rawMap[ts] : null);
		});

		return [unifiedX, unifiedYClean, unifiedYRaw];
	}

	function currentMode(card) {
		var checked = card.querySelector('input[type=radio]:checked');
		return checked ? checked.value : 'clean';
	}

	function renderCard(card) {
		var canvas = card.querySelector('.scalar-plot-canvas');
		if (!canvas || typeof uPlot === 'undefined') return true;

		var width = canvas.clientWidth || card.clientWidth || 0;
		if (!width) return false;

		var clean = [], raw = [];
		try { clean = JSON.parse(canvas.getAttribute('data-clean') || '[]'); } catch (e) { clean = []; }
		try { raw = JSON.parse(canvas.getAttribute('data-raw') || '[]'); } catch (e) { raw = []; }

		// Safe time bounds parsing logic
		var updatedEl = document.getElementById('last-updated-indicator');
		var maxTime = Math.floor(Date.now() / 1000);
		if (updatedEl) {
			var attrTime = Date.parse(updatedEl.getAttribute('data-updated-at')) / 1000;
			if (!isNaN(attrTime)) { maxTime = attrTime; }
		}
		
		var lookbackAttr = canvas.getAttribute('data-lookback-hours');
		var lookbackHours = lookbackAttr ? parseInt(lookbackAttr, 10) : 24;
		var minTime = maxTime - (lookbackHours * 3600);

		function draw(mode) {
			canvas.innerHTML = '';
			var w = canvas.clientWidth || card.clientWidth || 640;
			
			var scaleConfiguration = { x: {} };
			if (!isNaN(minTime) && !isNaN(maxTime) && minTime < maxTime) {
				scaleConfiguration.x.auto = false;
				scaleConfiguration.x.min = minTime;
				scaleConfiguration.x.max = maxTime;
			}

			try {
				if (mode === 'both') {
					var unifiedData = toUnifiedSeries(clean, raw);
					new uPlot({
						width: w,
						height: 220,
						scales: scaleConfiguration,
						series: [
							{},
							{ label: 'clean', stroke: '#0b6aa8', spanGaps: true },
							{ label: 'raw', stroke: '#fd7e14', spanGaps: true }
						]
					}, unifiedData, canvas);
				} else {
					var data = mode === 'raw' ? toSeries(raw) : toSeries(clean);
					new uPlot({
						width: w,
						height: 220,
						scales: scaleConfiguration,
						series: [
							{},
							{ label: mode, stroke: '#0b6aa8', spanGaps: true }
						]
					}, data, canvas);
				}
			} catch (err) {
				console.error("uPlot initialization aborted:", err);
				canvas.innerHTML = '<div class="scalar-plot-empty" style="color:#d9534f; padding-top:80px;">Render Error</div>';
			}
		}

		if (!card.dataset.bound) {
			card.querySelectorAll('input[type=radio]').forEach(function(input) {
				input.addEventListener('change', function() { draw(currentMode(card)); });
			});
			card.dataset.bound = '1';
		}

		if (!clean.length && !raw.length) {
			canvas.innerHTML = '<div class="scalar-plot-empty">No data in the last ' + lookbackHours + 'h.</div>';
		} else {
			draw(currentMode(card));
		}
		card.dataset.rendered = '1';
		return true;
	}

	var observer = null;

	// ... rest of the file (IntersectionObserver and Resize triggers) stays exactly identical ...
	function observeCard(card) {
		if (observer) observer.observe(card);
		else renderCard(card);
	}

	function scanForCards() {
		document.querySelectorAll('.scalar-plot-card:not([data-rendered])').forEach(observeCard);
	}

	document.addEventListener('DOMContentLoaded', function() {
		if ('IntersectionObserver' in window) {
			observer = new IntersectionObserver(function(entries) {
				entries.forEach(function(entry) {
					if (entry.isIntersecting && renderCard(entry.target)) {
						observer.unobserve(entry.target);
					}
				});
			}, { threshold: 0.01 });
		}
		scanForCards();

		document.addEventListener('hydrophone:details-visible', function() {
			window.setTimeout(scanForCards, 50);
		});

		if (window.MutationObserver) {
			var panels = document.getElementById('public-detail-tab-panels');
			if (panels) {
				new MutationObserver(function() { window.setTimeout(scanForCards, 30); })
					.observe(panels, { childList: true, subtree: true });
			}
		}

		var resizeTimer;
		window.addEventListener('resize', function() {
			window.clearTimeout(resizeTimer);
			resizeTimer = window.setTimeout(function() {
				document.querySelectorAll('.scalar-plot-card[data-rendered]').forEach(function(card) {
					card.dataset.rendered = '';
					renderCard(card);
				});
			}, 200);
		});
	});
})();