// Copyright (c) Jupyter Development Team.
// Distributed under the terms of the Modified BSD License.

// Add any needed widget imports here (or from controls)
// import {} from '@jupyter-widgets/base';

import { createTestModel } from "./utils";

import { SSVRenderModel } from "../index";

describe("SSVRenderWidget", () => {
  describe("SSVRenderModel", () => {
    it("should be createable", () => {
      const model = createTestModel(SSVRenderModel);
      expect(model).toBeInstanceOf(SSVRenderModel);
      expect(model.get("streaming_mode")).toEqual("png");
    });

    it("should be createable with a value", () => {
      const state = { streaming_mode: "jpg" };
      const model = createTestModel(SSVRenderModel, state);
      expect(model).toBeInstanceOf(SSVRenderModel);
      expect(model.get("streaming_mode")).toEqual("jpg");
    });
  });
});
