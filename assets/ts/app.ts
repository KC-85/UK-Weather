import { initialiseWeatherMap } from "./map";

type Htmx = {
  ajax: (
    method: "GET",
    url: string,
    options: {
      target: string;
      swap: "innerHTML";
    },
  ) => Promise<unknown>;
};

declare global {
  interface Window {
    htmx?: Htmx;
  }
}

type Coordinates = {
  latitude: number;
  longitude: number;
};

type RegionSelection = {
  code: string;
};

const dispatchCoordinates = ({ latitude, longitude }: Coordinates): void => {
  document.dispatchEvent(
    new CustomEvent<Coordinates>("weather:location-found", {
      detail: { latitude, longitude },
    }),
  );
};

document.addEventListener("click", (event: MouseEvent): void => {
  const target = event.target as HTMLElement | null;
  const button = target?.closest<HTMLElement>("[data-use-location]");

  if (!button || !navigator.geolocation) return;

  button.setAttribute("aria-busy", "true");
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      dispatchCoordinates(coords);
      button.removeAttribute("aria-busy");
    },
    () => button.removeAttribute("aria-busy"),
  );
});

document.addEventListener("weather:region-selected", (event: Event): void => {
  const selection = (event as CustomEvent<RegionSelection>).detail;
  const mapContainer = document.querySelector<HTMLElement>("#weather-map");
  const urlTemplate = mapContainer?.dataset.regionPanelUrlTemplate;

  if (!selection?.code || !urlTemplate) return;

  if (!window.htmx) {
    console.error("HTMX is unavailable; the region panel cannot be loaded.");
    return;
  }

  const panelUrl = urlTemplate.replace(
    "REGION_CODE",
    encodeURIComponent(selection.code),
  );

  void window.htmx.ajax("GET", panelUrl, {
    target: "#weather-panel",
    swap: "innerHTML",
  });
});

document.addEventListener("DOMContentLoaded", initialiseWeatherMap);
