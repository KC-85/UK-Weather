import {
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
} from "maplibre-gl";

import type {
  GeoJSONSource,
  MapGeoJSONFeature,
  MapMouseEvent,
} from "maplibre-gl";

import type {
  FeatureCollection,
  MultiPolygon,
  Point,
  Polygon,
} from "geojson";

type RegionCollection = FeatureCollection<Polygon | MultiPolygon>;
type SettlementCollection = FeatureCollection<Point>;
type RegionSearchSelection = {
  code: string;
  name: string;
  bounds: [number, number, number, number];
};

const SOURCE_ID = "regions";
const FILL_LAYER_ID = "region-fill";
const LINE_LAYER_ID = "region-outline";
const SETTLEMENT_SOURCE_ID = "settlements";
const SETTLEMENT_CIRCLE_LAYER_ID = "settlement-dots";
const CITY_LABEL_LAYER_ID = "city-labels";
const TOWN_LABEL_LAYER_ID = "town-labels";

export const initialiseWeatherMap = (): void => {
  const container = document.querySelector<HTMLElement>("#weather-map");

  if (!container || container.dataset.mapReady === "true") {
    return;
  }

  const regionsUrl = container.dataset.regionsUrl;
  const settlementsUrl = container.dataset.settlementsUrl;
  const workerUrl = container.dataset.mapWorkerUrl;

  if (!regionsUrl) {
    throw new Error("The map is missing its regions endpoint URL.");
  }

  if (!settlementsUrl) {
    throw new Error("The map is missing its settlements endpoint URL.");
  }

  if (!workerUrl) {
    throw new Error("The map is missing its worker URL.");
  }

  container.dataset.mapReady = "true";
  setWorkerUrl(workerUrl);

  const map = new MapLibreMap({
    container,
    style: "https://demotiles.maplibre.org/style.json",
    center: [-3.5, 54.8],
    zoom: 5,
    minZoom: 4,
    maxZoom: 14,
  });

  map.addControl(new NavigationControl(), "top-right");

  const regionTooltip = document.createElement("div");
  regionTooltip.className = "region-tooltip";
  regionTooltip.hidden = true;
  regionTooltip.setAttribute("role", "tooltip");
  container.append(regionTooltip);

  const settlementTooltip = document.createElement("div");
  settlementTooltip.className = "region-tooltip";
  settlementTooltip.hidden = true;
  settlementTooltip.setAttribute("role", "tooltip");
  container.append(settlementTooltip);

  let regionRequestController: AbortController | null = null;
  let settlementRequestController: AbortController | null = null;
  let selectedRegionId: string | number | null = null;
  let hoveredRegionName: string | null = null;

  const applySelectedRegionState = (): void => {
    if (selectedRegionId === null || !map.getSource(SOURCE_ID)) return;

    map.setFeatureState(
      { source: SOURCE_ID, id: selectedRegionId },
      { selected: true },
    );
  };

  const selectRegion = (regionId: string | number): void => {
    if (selectedRegionId !== null && map.getSource(SOURCE_ID)) {
      map.setFeatureState(
        { source: SOURCE_ID, id: selectedRegionId },
        { selected: false },
      );
    }

    selectedRegionId = regionId;
    applySelectedRegionState();
  };

  const loadVisibleRegions = async (): Promise<void> => {
    regionRequestController?.abort();
    regionRequestController = new AbortController();

    const bounds = map.getBounds();
    const url = new URL(regionsUrl, window.location.origin);

    url.searchParams.set(
      "bbox",
      [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ].join(","),
    );

    url.searchParams.set(
      "tolerance",
      simplificationTolerance(map.getZoom()).toString(),
    );

    try {
      const response = await fetch(url, {
        headers: {
          Accept: "application/geo+json",
        },
        signal: regionRequestController.signal,
      });

      if (!response.ok) {
        throw new Error(`Region request failed: ${response.status}`);
      }

      const regions = (await response.json()) as RegionCollection;
      const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;

      source?.setData(regions);
      applySelectedRegionState();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      console.error("Unable to load map regions.", error);
    }
  };

  const loadVisibleSettlements = async (): Promise<void> => {
    settlementRequestController?.abort();
    settlementRequestController = new AbortController();

    const bounds = map.getBounds();
    const url = new URL(settlementsUrl, window.location.origin);

    url.searchParams.set(
      "bbox",
      [
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ].join(","),
    );
    url.searchParams.set("zoom", map.getZoom().toString());

    try {
      const response = await fetch(url, {
        headers: {
          Accept: "application/geo+json",
        },
        signal: settlementRequestController.signal,
      });

      if (!response.ok) {
        throw new Error(`Settlement request failed: ${response.status}`);
      }

      const settlements = (await response.json()) as SettlementCollection;
      const source = map.getSource(SETTLEMENT_SOURCE_ID) as
        | GeoJSONSource
        | undefined;

      source?.setData(settlements);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      console.error("Unable to load map settlements.", error);
    }
  };

  map.on("load", () => {
    map.addSource(SOURCE_ID, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
      promoteId: "code",
    });

    map.addLayer({
      id: FILL_LAYER_ID,
      type: "fill",
      source: SOURCE_ID,
      paint: {
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          "#f97316",
          "#38bdf8",
        ],
        "fill-opacity": 0.25,
      },
    });

    map.addLayer({
      id: LINE_LAYER_ID,
      type: "line",
      source: SOURCE_ID,
      paint: {
        "line-color": "#e2e8f0",
        "line-width": 1.5,
      },
    });

    map.addSource(SETTLEMENT_SOURCE_ID, {
      type: "geojson",
      data: {
        type: "FeatureCollection",
        features: [],
      },
    });

    map.addLayer({
      id: SETTLEMENT_CIRCLE_LAYER_ID,
      type: "circle",
      source: SETTLEMENT_SOURCE_ID,
      paint: {
        "circle-color": [
          "match",
          ["get", "settlement_type"],
          "city",
          "#f97316",
          "town",
          "#facc15",
          "#e2e8f0",
        ],
        "circle-radius": [
          "interpolate",
          ["linear"],
          ["zoom"],
          4,
          [
            "match",
            ["get", "settlement_type"],
            "city",
            5,
            "town",
            2.5,
            2,
          ],
          10,
          [
            "match",
            ["get", "settlement_type"],
            "city",
            9,
            "town",
            5,
            4,
          ],
        ],
        "circle-stroke-color": "#0b1628",
        "circle-stroke-width": 1.5,
        "circle-opacity": 0.95,
      },
    });

    map.addLayer({
      id: CITY_LABEL_LAYER_ID,
      type: "symbol",
      source: SETTLEMENT_SOURCE_ID,
      minzoom: 4,
      filter: ["==", ["get", "settlement_type"], "city"],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Semibold"],
        "text-size": 13,
        "text-offset": [0, 1.1],
        "text-anchor": "top",
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#f8fafc",
        "text-halo-color": "#0b1628",
        "text-halo-width": 1.5,
      },
    });

    map.addLayer({
      id: TOWN_LABEL_LAYER_ID,
      type: "symbol",
      source: SETTLEMENT_SOURCE_ID,
      minzoom: 7,
      filter: ["==", ["get", "settlement_type"], "town"],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Open Sans Semibold"],
        "text-size": 11,
        "text-offset": [0, 1.1],
        "text-anchor": "top",
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#e2e8f0",
        "text-halo-color": "#0b1628",
        "text-halo-width": 1.25,
      },
    });

    void Promise.all([loadVisibleRegions(), loadVisibleSettlements()]);
  });

  map.on("sourcedata", (event) => {
    if (event.sourceId === SOURCE_ID && event.isSourceLoaded) {
      applySelectedRegionState();
    }
  });

  map.on("moveend", () => {
    void Promise.all([loadVisibleRegions(), loadVisibleSettlements()]);
  });

  map.on(
    "click",
    FILL_LAYER_ID,
    (
      event: MapMouseEvent & {
        features?: MapGeoJSONFeature[];
      },
    ) => {
      const settlementFeatures = map.queryRenderedFeatures(event.point, {
        layers: [SETTLEMENT_CIRCLE_LAYER_ID],
      });
      if (settlementFeatures.length > 0) return;

      const feature = event.features?.[0];

      const regionCode = feature?.properties?.code;

      if (typeof regionCode !== "string" || !regionCode) {
        return;
      }

      selectRegion(regionCode);

      document.dispatchEvent(
        new CustomEvent("weather:region-selected", {
          detail: {
            code: regionCode,
            name: feature.properties?.name,
            longitude: event.lngLat.lng,
            latitude: event.lngLat.lat,
          },
        }),
      );
    },
  );

  map.on(
    "mousemove",
    FILL_LAYER_ID,
    (
      event: MapMouseEvent & {
        features?: MapGeoJSONFeature[];
      },
    ) => {
      const settlementFeatures = map.queryRenderedFeatures(event.point, {
        layers: [SETTLEMENT_CIRCLE_LAYER_ID],
      });
      if (settlementFeatures.length > 0) {
        hoveredRegionName = null;
        regionTooltip.hidden = true;
        return;
      }

      const regionName = event.features?.[0]?.properties?.name;

      map.getCanvas().style.cursor = "pointer";

      if (typeof regionName !== "string" || !regionName) {
        hoveredRegionName = null;
        regionTooltip.hidden = true;
        return;
      }

      if (regionName !== hoveredRegionName) {
        hoveredRegionName = regionName;
        regionTooltip.textContent = regionName;
      }

      regionTooltip.style.transform =
        `translate(${event.point.x + 14}px, ${event.point.y + 14}px)`;
      regionTooltip.hidden = false;
    },
  );

  map.on("mouseenter", FILL_LAYER_ID, () => {
    map.getCanvas().style.cursor = "pointer";
  });

  map.on("mouseleave", FILL_LAYER_ID, () => {
    map.getCanvas().style.cursor = "";
    hoveredRegionName = null;
    regionTooltip.hidden = true;
  });

  map.on(
    "click",
    SETTLEMENT_CIRCLE_LAYER_ID,
    (
      event: MapMouseEvent & {
        features?: MapGeoJSONFeature[];
      },
    ) => {
      const feature = event.features?.[0];
      const regionCode = feature?.properties?.region_code;
      const regionName = feature?.properties?.region_name;

      if (typeof regionCode !== "string" || !regionCode) return;

      selectRegion(regionCode);
      document.dispatchEvent(
        new CustomEvent("weather:region-selected", {
          detail: {
            code: regionCode,
            name:
              typeof regionName === "string" && regionName
                ? regionName
                : undefined,
          },
        }),
      );
    },
  );

  map.on(
    "mousemove",
    SETTLEMENT_CIRCLE_LAYER_ID,
    (
      event: MapMouseEvent & {
        features?: MapGeoJSONFeature[];
      },
    ) => {
      const properties = event.features?.[0]?.properties;
      const name = properties?.name;
      const settlementType = properties?.settlement_type;
      const authorityName = properties?.region_name;

      if (typeof name !== "string" || !name) {
        settlementTooltip.hidden = true;
        return;
      }

      const details = [
        settlementTypeLabel(settlementType),
        typeof authorityName === "string" ? authorityName : "",
      ].filter(Boolean);

      settlementTooltip.textContent = details.length
        ? `${name} · ${details.join(" · ")}`
        : name;
      settlementTooltip.style.transform =
        `translate(${event.point.x + 14}px, ${event.point.y + 14}px)`;
      settlementTooltip.hidden = false;
      regionTooltip.hidden = true;
    },
  );

  map.on("mouseenter", SETTLEMENT_CIRCLE_LAYER_ID, () => {
    map.getCanvas().style.cursor = "pointer";
  });

  map.on("mouseleave", SETTLEMENT_CIRCLE_LAYER_ID, () => {
    map.getCanvas().style.cursor = "";
    settlementTooltip.hidden = true;
  });

  document.addEventListener(
    "weather:region-search-selected",
    (event: Event): void => {
      const selection = (event as CustomEvent<RegionSearchSelection>).detail;

      if (!selection?.code || selection.bounds.length !== 4) return;

      const [west, south, east, north] = selection.bounds;
      selectRegion(selection.code);
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        {
          padding: 80,
          maxZoom: 9,
          duration: 900,
        },
      );

      document.dispatchEvent(
        new CustomEvent("weather:region-selected", {
          detail: {
            code: selection.code,
            name: selection.name,
          },
        }),
      );
    },
  );
};

const simplificationTolerance = (zoom: number): number => {
  if (zoom <= 5) return 0.01;
  if (zoom <= 7) return 0.005;
  if (zoom <= 9) return 0.001;

  return 0.0002;
};

const settlementTypeLabel = (value: unknown): string => {
  if (value === "city") return "City";
  if (value === "town") return "Town";
  return "";
};
