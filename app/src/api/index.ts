import { fetch } from "expo/fetch";
import { File } from "expo-file-system";

import { SERVER_TOKEN, SERVER_URL } from "../config";
import { makeApi } from "./client";

export const api = makeApi(SERVER_URL, SERVER_TOKEN, fetch as never, (uri) => new File(uri).bytes());
export { ApiError } from "./client";
export type * from "./types";
