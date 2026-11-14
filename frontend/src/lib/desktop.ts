export type DesktopBridge = {
  command: (message: unknown) => Promise<void>;
  bounds: (rect: { x: number; y: number; width: number; height: number }) => void;
  overlay: (key: string, visible: boolean) => void;
  window: (action: "minimize" | "maximize" | "close") => void;
  onEvent: (callback: (message: { type: string; message?: string; maximized?: boolean; key?: string; y?: number }) => void) => () => void;
};

declare global {
  interface Window { referent?: DesktopBridge }
}

export const desktop = () => typeof window !== "undefined" ? window.referent : undefined;
