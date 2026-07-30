import { initialiseWeatherMap } from "./map";

type Htmx = {
  ajax: (
    method: "GET",
    url: string,
    options: {
      source: HTMLElement;
      target: HTMLElement;
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
  name?: string;
};

type HtmxRequestDetail = {
  failed?: boolean;
  successful?: boolean;
  target?: HTMLElement;
  xhr?: XMLHttpRequest;
};

let selectedRegion: RegionSelection | null = null;
let activePanelRequest: XMLHttpRequest | null = null;
const abortedPanelRequests = new WeakSet<XMLHttpRequest>();

const dispatchCoordinates = ({ latitude, longitude }: Coordinates): void => {
  document.dispatchEvent(
    new CustomEvent<Coordinates>("weather:location-found", {
      detail: { latitude, longitude },
    }),
  );
};

const replacePanelWithTemplate = (
  panel: HTMLElement,
  templateId: string,
): boolean => {
  const template = document.querySelector<HTMLTemplateElement>(templateId);

  if (!template) return false;

  const content = template.content.cloneNode(true) as DocumentFragment;
  panel.replaceChildren(content);
  return true;
};

const showRegionPanelLoading = (
  panel: HTMLElement,
  selection: RegionSelection,
): void => {
  replacePanelWithTemplate(panel, "#region-panel-loading");
  const regionName = panel.querySelector<HTMLElement>(
    "[data-region-loading-name]",
  );

  if (regionName) {
    regionName.textContent = selection.name || "the selected region";
  }

  panel.setAttribute("aria-busy", "true");
};

const showRegionPanelError = (panel: HTMLElement): void => {
  replacePanelWithTemplate(panel, "#region-panel-error");
  panel.setAttribute("aria-busy", "false");
};

const loadRegionPanel = (selection: RegionSelection): void => {
  const mapContainer = document.querySelector<HTMLElement>("#weather-map");
  const panel = document.querySelector<HTMLElement>("#weather-panel");
  const urlTemplate = mapContainer?.dataset.regionPanelUrlTemplate;

  if (!selection.code || !urlTemplate || !panel) return;

  selectedRegion = selection;
  showRegionPanelLoading(panel, selection);

  if (!window.htmx) {
    console.error("HTMX is unavailable; the region panel cannot be loaded.");
    showRegionPanelError(panel);
    return;
  }

  const panelUrl = urlTemplate.replace(
    "REGION_CODE",
    encodeURIComponent(selection.code),
  );

  void window.htmx.ajax("GET", panelUrl, {
    source: panel,
    target: panel,
    swap: "innerHTML",
  });
};

document.addEventListener("click", (event: MouseEvent): void => {
  const target = event.target as HTMLElement | null;
  const retryButton = target?.closest<HTMLElement>(
    "[data-region-panel-retry]",
  );

  if (retryButton && selectedRegion) {
    loadRegionPanel(selectedRegion);
    return;
  }

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

  if (selection?.code) loadRegionPanel(selection);
});

document.addEventListener("htmx:beforeRequest", (event: Event): void => {
  const detail = (event as CustomEvent<HtmxRequestDetail>).detail;

  if (detail.target?.id !== "weather-panel" || !detail.xhr) return;

  activePanelRequest = detail.xhr;
});

document.addEventListener("htmx:afterRequest", (event: Event): void => {
  const detail = (event as CustomEvent<HtmxRequestDetail>).detail;
  const panel = detail.target;

  if (
    panel?.id !== "weather-panel" ||
    !detail.xhr ||
    detail.xhr !== activePanelRequest
  ) {
    return;
  }

  activePanelRequest = null;

  if (abortedPanelRequests.has(detail.xhr)) return;

  if (detail.failed || detail.successful === false) {
    showRegionPanelError(panel);
    return;
  }

  panel.setAttribute("aria-busy", "false");
});

document.addEventListener("htmx:sendAbort", (event: Event): void => {
  const detail = (event as CustomEvent<HtmxRequestDetail>).detail;

  if (detail.target?.id === "weather-panel" && detail.xhr) {
    abortedPanelRequests.add(detail.xhr);
  }
});

document.addEventListener("DOMContentLoaded", initialiseWeatherMap);
