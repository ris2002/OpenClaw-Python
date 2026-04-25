import { get, post } from "./client";

export const authApi = {
  status:    () => get("/api/auth/status"),
  loginUrl:  () => get("/api/auth/gmail/login"),
  signOut:   () => post("/api/auth/signout"),
};
