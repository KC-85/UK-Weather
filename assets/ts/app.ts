import { initialiseWeatherMap } from "./map";

type Coordinates = {
  latitude: number;
  longitude: number;
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

document.addEventListener("DOMContentLoaded", initialiseWeatherMap);
