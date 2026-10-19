declare module "@wonderful/app-sdk" {
  export interface WonderfulAPI {
    fetch(path: string, options?: RequestInit): Promise<Response>;
    get<T = unknown>(path: string): Promise<T>;
    post<T = unknown>(path: string, body?: unknown): Promise<T>;
    put<T = unknown>(path: string, body?: unknown): Promise<T>;
    del(path: string): Promise<void>;
    /** Open an authenticated WebSocket to a controller endpoint (e.g. `/communications/{id}/live`). Internal apps only. */
    openSocket(path: string): WebSocket;
    /** Open a WebSocket to one of this app's socket functions, by slug. The SDK resolves the route and credential for the app's mode. Works in external (share-link) mode too. */
    openFunctionSocket(slug: string): WebSocket;
    invokeFunction<T = unknown>(slug: string, options?: { method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH"; params?: Record<string, unknown> }): Promise<T>;
  }

  export interface WonderfulContext {
    tenantId: string;
    workspaceId: string;
    userId: string;
    userName: string;
    /** The app's own id. Useful for calling app-scoped platform endpoints. */
    appId?: string;
    /** The viewer's primary role in this app, when the session resolved one.
     *  Undefined for anonymous viewers. Owners / apps:edit holders bypass only
     *  legacy role gates, never permission gates. */
    appRole?: string;
    /** Session snapshot for UI shaping. Protected calls resolve authorization live. */
    appRoles?: string[];
    appPermissions?: string[];
    appGroupIds?: string[];
    appPermissionGrants?: AppPermissionGrant[];
    /** Effective Wonderful UI language, e.g. "en", "pt-BR", or "zh-Hant".
     * Undefined when this browser has no explicit preference, allowing apps to
     * use their own browser-locale fallback. */
    language?: string;
    /** Text direction resolved by the Wonderful host for the active language. */
    direction?: "ltr" | "rtl";
    theme: "light" | "dark";
    apiBaseUrl: string;
    /** Base URL for function invocation in external mode (e.g. "/app-functions/TOKEN"). */
    functionBaseUrl?: string;
  }

  export type AppPermissionScope =
    | { type: "all" }
    | { type: "relation"; relation: string }
    | { type: "resource_ids"; resource_ids: string[] };

  export interface AppPermissionGrant {
    permission: string;
    scope: AppPermissionScope;
  }

  export interface WonderfulSDK {
    context: WonderfulContext;
    api: WonderfulAPI;
    /** Record a custom analytics event, viewable in the app's Analytics tab. Works in every mode, incl. share links. */
    track(name: string, properties?: Record<string, unknown>): void;
    /** Evaluate a per-app A/B feature flag for the current visitor: false (off/unknown), true (on), or the assigned variant key. Stable per visitor. */
    getFlag(key: string): boolean | string;
  }

  export function useWonderful(): WonderfulSDK;

  export interface AppWidgetProps {
    /** Slug (or id) of the app that exposes the widget. */
    app: string;
    /** The widget's key in that app's wonderful.json. */
    widget: string;
    /** Workspace of that app. Defaults to this app's workspace; set it to embed from another workspace, or when the slug exists in several. The viewer must be a member. */
    workspaceId?: string;
    /** Values passed to the widget component as `params`. */
    params?: Record<string, unknown>;
    /** Placement only — a widget renders at the size its author declared. */
    className?: string;
  }

  /**
   * Embeds a widget another Wonderful App exposes, as a live instance of that
   * app: it runs in the source app's own session, so its data and actions stay
   * under the source app's permissions and the viewer needs access to it.
   */
  export function AppWidget(props: AppWidgetProps): JSX.Element | null;
}
