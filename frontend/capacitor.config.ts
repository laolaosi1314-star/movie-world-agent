import type { CapacitorConfig } from "@capacitor/core";

// 跨端：同一套 React 代码 → H5（移动网页）+ iOS/Android App（Capacitor 封装）。
// 接入方式见 README：「跨端（App）」一节。
const config: CapacitorConfig = {
  appId: "com.movieworld.agent",
  appName: "影视世界",
  webDir: "dist",
  server: {
    androidScheme: "https",
  },
};

export default config;
