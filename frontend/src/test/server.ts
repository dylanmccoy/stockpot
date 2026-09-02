// The MSW server for the test suite. `setupTests.ts` starts it with
// `onUnhandledRequest: "error"` so no test can silently hit the network.

import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
