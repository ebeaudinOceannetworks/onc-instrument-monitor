/**
 * Robust scalar plot rendering.
 *
 * Detail sections live hidden in #internal-detail-source and are moved into
 * tabs on demand. Rendering uPlot while a card has zero width (hidden) produces
 * an empty/blank plot — which is why the per-site view sometimes showed no data
 * even though the per-instrument view did. This renders each card lazily, only
 * once it is actually visible with a real width, and re-renders on resize.
 */
(function() {
	'use strict';

	function toSeries(rows) {
		if (!rows || !rows.length) return [[], []];
		return [rows.map(function(r) { return Date.parse(r.t) / 1000; }), rows.map(function(r) { return r.v; })];
	}

	function currentMode(card) {
		var checked = card.querySelector('input[type=radio]:checked');
		return checked ? checked.value : 'clean';
	}

	function renderCard(card) {
		var canvas = card.querySelector('.scalar-plot-canvas');
		if (!canvas || typeof uPlot === 'undefined') return true;

		var width = canvas.clientWidth || card.clientWidth || 0;
		if (!width) return false; // not visible yet; try again later

		var clean = [];
		var raw = [];
		try { clean = JSON.parse(canvas.getAttribute('data-clean') || '[]'); } catch (e) { clean = []; }
		try { raw = JSON.parse(canvas.getAttribute('data-raw') || '[]'); } catch (e) { raw = []; }

		function draw(mode) {
			canvas.innerHTML = '';
			var w = canvas.clientWidth || card.clientWidth || 640;
			if (mode === 'both') {
				var c = toSeries(clean), r = toSeries(raw);
				new uPlot({ width: w, height: 220, series: [{}, { label: 'clean', stroke: '#0b6aa8' }, { label: 'raw', stroke: '#fd7e14' }] }, [c[0].length ? c[0] : r[0], c[1], r[1]], canvas);
			} else {
				var data = mode === 'raw' ? toSeries(raw) : toSeries(clean);
				new uPlot({ width: w, height: 220, series: [{}, { label: mode, stroke: '#0b6aa8' }] }, data, canvas);
			}
		}

		if (!card.dataset.bound) {
			card.querySelectorAll('input[type=radio]').forEach(function(input) {
				input.addEventListener('change', function() { draw(currentMode(card)); });
			});
			card.dataset.bound = '1';
		}

		if (!clean.length && !raw.length) {
			canvas.innerHTML = '<div class="scalar-plot-empty">No data in the last 24h.</div>';
		} else {
			draw(currentMode(card));
		}
		card.dataset.rendered = '1';
		return true;
	}

	var observer = null;

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
