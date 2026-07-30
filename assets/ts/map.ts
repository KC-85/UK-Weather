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
  Polygon,
} from "geojson";

type RegionCollection = FeatureCollection<Polygon | MultiPolygon>;

const SOURCE_ID = "regions";
const FILL_LAYER_ID = "region-fill";
const LINE_LAYER_ID = "region-outline";

export const initialiseWeatherMap = (): void => {
  const container = document.querySelector<HTMLElement>("#weather-map");

  if (!container || container.dataset.mapReady === "true") {
    return;
  }

  const regionsUrl = container.dataset.regionsUrl;
  const workerUrl = container.dataset.mapWorkerUrl;

  if (!regionsUrl) {
    throw new Error("The map is missing its regions endpoint URL.");
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

  let requestController: AbortController | null = null;
  let selectedRegionId: string | number | null = null;
  let hoveredRegionName: string | null = null;

  const loadVisibleRegions = async (): Promise<void> => {
    requestController?.abort();
    requestController = new AbortController();

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
        signal: requestController.signal,
      });

      if (!response.ok) {
        throw new Error(`Region request failed: ${response.status}`);
      }

      const regions = (await response.json()) as RegionCollection;
      const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;

      source?.setData(regions);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      console.error("Unable to load map regions.", error);
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

    void loadVisibleRegions();
  });

  map.on("moveend", () => {
    void loadVisibleRegions();
  });

  map.on(
    "click",
    FILL_LAYER_ID,
    (
      event: MapMouseEvent & {
        features?: MapGeoJSONFeature[];
      },
    ) => {
      const feature = event.features?.[0];

      if (!feature?.id) {
        return;
      }

      if (selectedRegionId !== null) {
        map.setFeatureState(
          { source: SOURCE_ID, id: selectedRegionId },
          { selected: false },
        );
      }

      selectedRegionId = feature.id;

      map.setFeatureState(
        { source: SOURCE_ID, id: selectedRegionId },
        { selected: true },
      );

      document.dispatchEvent(
        new CustomEvent("weather:region-selected", {
          detail: {
            code: feature.properties?.code,
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
};

const simplificationTolerance = (zoom: number): number => {
  if (zoom <= 5) return 0.01;
  if (zoom <= 7) return 0.005;
  if (zoom <= 9) return 0.001;

  return 0.0002;
};
