/*
 * Copyright (c) 2023 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

import {
  DOMWidgetModel,
  DOMWidgetView,
  ISerializers,
} from '@jupyter-widgets/base';

import { MODULE_NAME, MODULE_VERSION } from './version';

// Import the CSS
import '../css/widget.css';

enum StreamingMode {
  PNG = "png",
  JPG = "jpg",
  H264 = "h264"
}

export class SSVRenderModel extends DOMWidgetModel {
  defaults() {
    return {
      ...super.defaults(),
      _model_name: SSVRenderModel.model_name,
      _model_module: SSVRenderModel.model_module,
      _model_module_version: SSVRenderModel.model_module_version,
      _view_name: SSVRenderModel.view_name,
      _view_module: SSVRenderModel.view_module,
      _view_module_version: SSVRenderModel.view_module_version,
      streaming_mode: StreamingMode.PNG,
      stream_data: "ts",
      mouse_pos_x: 0,
      mouse_pos_y: 0
    };
  }

  static serializers: ISerializers = {
    ...DOMWidgetModel.serializers,
    // Add any extra serializers here
  };

  static model_name = 'SSVRenderModel';
  static model_module = MODULE_NAME;
  static model_module_version = MODULE_VERSION;
  static view_name = 'SSVRenderView'; // Set to null if no view
  static view_module = MODULE_NAME; // Set to null if no view
  static view_module_version = MODULE_VERSION;
}

/*type MouseEvent = {
  clientX: number;
  clientY: number;
}*/

export class SSVRenderView extends DOMWidgetView {
  private _stream_img_element: HTMLImageElement | null;

  render() {
    this.el.classList.add('ssv-render-widget');

    switch (this.model.get("streaming_mode")) {
      case StreamingMode.JPG:
      case StreamingMode.PNG:
        this._stream_img_element = document.createElement("img");
        this.el.appendChild(this._stream_img_element);
        break;
      default:
        console.error(`Unsupported streaming mode '${this.model.get("streaming_mode")}'!`);
    }

    this.stream_data_changed();
    this.model.on("change:stream_data", this.stream_data_changed, this);

    if(this._stream_img_element) {
      /*let frame_no = 0;
      const on_anim_frame = () => {
        this.model.set("frame_no", frame_no++);
        this.model.save_changes();

        requestAnimationFrame(on_anim_frame);
      };
      requestAnimationFrame(on_anim_frame);*/

      //let mousePos = { x: 0, y: 0 };
      this._stream_img_element.addEventListener('mousemove', (event: MouseEvent) => {
          /*mousePos = {
            x: event.clientX,// / target.width,
            y: event.clientY,// / target.height
          };*/

          if(event?.target == null || !(event.target instanceof HTMLElement))
            return;

          const rect = event.target.getBoundingClientRect();
          this.model.set("mouse_pos_x", Math.round(event.clientX - rect.left));
          this.model.set("mouse_pos_y", Math.round(rect.height - (event.clientY - rect.top)));
          this.model.save_changes();
      });
    }
  }

  stream_data_changed() {
    if(!this._stream_img_element)
      return;

    //this.el.textContent = this.model.get('stream_data');
    this._stream_img_element.src = this.model.get('stream_data');
  }
}
