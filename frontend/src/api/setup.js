import { get, post } from "./client";

export const setupApi = {
  status:      () => get("/api/setup/status"),
  setLocation: (path) => post("/api/setup/location", { path }),
};
