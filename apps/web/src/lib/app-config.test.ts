import { describe, expect, it } from "vitest";
import { APP_DESCRIPTION, APP_NAME } from "@/lib/app-config";

describe("app identity", () => {
  it("ships the app's display name and description", () => {
    expect(APP_NAME).toBe("nuScenes Sensor Data Lake");
    expect(APP_DESCRIPTION).toBe(
      "Autonomous-vehicle multi-sensor data lake on Backblaze B2, indexed with the nuScenes devkit"
    );
  });
});
