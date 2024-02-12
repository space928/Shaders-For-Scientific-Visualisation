/*
 * Copyright (c) 2023-2024 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

import {
  DOMWidgetModel,
  DOMWidgetView,
  ISerializers,
  WidgetView
} from "@jupyter-widgets/base";
import {KernelMessage} from "@jupyterlab/services";

import {MODULE_NAME, MODULE_VERSION} from "./version";
import {SSVStatusBarView} from "./widget_status_bar";

// Import the CSS
import "../css/widget.css";

enum StreamingMode {
  PNG = "png",
  JPG = "jpg",
  H264 = "h264",
  VP8 = "vp8",
  VP9 = "vp9",
  HEVC = "hevc",
  MPEG4 = "mpeg4",
  MJPEG = "mjpeg"
}

interface StreamDataEvent {
  (args: ArrayBuffer | ArrayBufferView): void;
}

interface DownloadFileEvent {
  (filename: string, data: ArrayBuffer | ArrayBufferView): void;
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
      streaming_mode: StreamingMode.PNG.toString(),
      canvas_width: 0,
      canvas_height: 0,
      stream_data_binary: new ArrayBuffer(0),
      stream_data_ascii: "",
      use_websockets: false,
      websocket_url: "",
      status_connection: false,
      status_logs: "",
      mouse_pos_x: 0,
      mouse_pos_y: 0,
      enable_renderdoc: false,
      frame_rate: 0,
      frame_times: ""
    };
  }

  static serializers: ISerializers = {
    ...DOMWidgetModel.serializers
    // Add any extra serializers here
  };

  static model_name = "SSVRenderModel";
  static model_module = MODULE_NAME;
  static model_module_version = MODULE_VERSION;
  static view_name = "SSVRenderView"; // Set to null if no view
  static view_module = MODULE_NAME; // Set to null if no view
  static view_module_version = MODULE_VERSION;

  private _on_stream_data: {event: StreamDataEvent, ctx: any} | null = null;
  private _on_download_file: {event: DownloadFileEvent, ctx: any} | null = null;

  /**
   * Registers a callback to the on_stream_data event, called whenever new streamed frame data is available to the
   * canvas.
   * @param callback the callback to invoke when new data is available.
   * @param context a value for `this`.
   */
  public on_stream_data(callback: StreamDataEvent, context: any) {
    this._on_stream_data = {event: callback, ctx: context};
  }

  /**
   * Registers a callback to the on_download_file event, called whenever the kernel wants to create a file download
   * from a byte array.
   * @param callback the callback to invoke when new data is available.
   * @param context a value for `this`.
   */
  public on_download_file(callback: DownloadFileEvent, context: any) {
    this._on_download_file = {event: callback, ctx: context};
  }

  public _handle_comm_msg(msg: KernelMessage.ICommMsgMsg): Promise<void> {
    if (msg.content.data["method"] == "custom") {
      const content = msg.content.data["content"];
      if (content !== null && typeof content === "object") {
        if ("stream_data" in content) {
          if (this._on_stream_data && msg.buffers && msg.buffers.length > 0)
            this._on_stream_data.event.call(this._on_stream_data.ctx, msg.buffers[0]);
        } else if ("download_file" in content) {
          let filename = "download";
          if(content["download_file"] && typeof content["download_file"] === "object"
             && "name" in content["download_file"]) {
            const v = content["download_file"]["name"];
            if (v && typeof v === "string")
              filename = v;
          }
          if (this._on_download_file && msg.buffers && msg.buffers.length > 0)
            this._on_download_file.event.call(this._on_download_file.ctx, filename, msg.buffers[0])
        }
      }
    }
    return super._handle_comm_msg(msg);
  }
}

export class SSVRenderView extends DOMWidgetView {
  private _stream_element: HTMLImageElement | HTMLCanvasElement | null = null;
  private _widget_status_bar: SSVStatusBarView | null = null;
  private _focussed: boolean = false;
  private _text_decoder: TextDecoder = new TextDecoder('utf-8');
  private _streaming_mode: StreamingMode = StreamingMode.JPG;
  private _use_websockets: boolean = false;
  private _websocket: WebSocket | null = null;
  private _video_decoder: VideoDecoder | null = null;
  private _canvas_ctx: CanvasRenderingContext2D | null = null;

  initialize(parameters: WidgetView.IInitializeParameters) {
    super.initialize(parameters);
  }

  render() {
    // Render HTML
    this.el.classList.add("ssv-colors");
    if(getComputedStyle(document.documentElement).getPropertyValue("--colab-primary-surface-color").length > 0)
      this.el.classList.add("ssv-colab-support");
    this.el.classList.add("ssv-render-widget");

    this.render_canvas();

    // Status bar
    this._widget_status_bar = new SSVStatusBarView(this, this.el, this._stream_element);
    this._widget_status_bar.render();

    // Setup callbacks
    // this.stream_data_changed();
    if(this._use_websockets) {
      this._websocket = new WebSocket(this.model.get("websocket_url"));
      this._websocket.addEventListener("open", () => { });
      this._websocket.addEventListener("message", (event) => {
        const data: Blob = event.data;
        data.arrayBuffer().then((d)=> {
          this.stream_data_changed(d);
        });
      });
    } else {
      this.model.on("change:stream_data_ascii", () => { this.stream_data_changed(this.model.get("stream_data_ascii")); }, this);
      this.model.on("change:stream_data_binary", () => { this.stream_data_changed(this.model.get("stream_data_binary")); }, this);
      (this.model as SSVRenderModel).on_stream_data(this.stream_data_changed, this);
    }

    (this.model as SSVRenderModel).on_download_file(this.download_file, this);

    if (this._stream_element) {
      const slow_update = setInterval(() => {
        try {
          this.send({"heartbeat": 0});
          this.slow_update();
        } catch (e) {
          this.model.set("status_connection", false);
          clearInterval(slow_update);
        }
      }, 250);

      //let mousePos = { x: 0, y: 0 };
      this.register_events();
    }
  }

  remove() {
    super.remove();

    this.unregister_events();
  }

  private render_canvas() {
    this._streaming_mode = StreamingMode[this.model.get("streaming_mode") as keyof typeof StreamingMode];
    this._use_websockets = this.model.get("use_websockets");
    switch (this._streaming_mode) {
      case StreamingMode.JPG:
      case StreamingMode.PNG:
      case StreamingMode.MJPEG:
        this._stream_element = document.createElement("img");
        this._stream_element.className = "ssv-render-viewport";
        this._stream_element.setAttribute("draggable", "false");
        this.el.appendChild(this._stream_element);
        break;

      case StreamingMode.VP8:
      case StreamingMode.VP9:
      case StreamingMode.HEVC:
      case StreamingMode.H264:
        this._stream_element = document.createElement("canvas");
        this._stream_element.className = "ssv-render-viewport";
        this._stream_element.width = this.model.get("canvas_width");
        this._stream_element.height = this.model.get("canvas_height");
        this._canvas_ctx = this._stream_element.getContext("2d");
        this.el.appendChild(this._stream_element);
        // TODO: Polyfill for Firefox users...
        this._video_decoder = new VideoDecoder({
          output: (frame: VideoFrame) => {
            if (!this._stream_element)
              return;
            this._canvas_ctx?.drawImage(frame, 0, 0);
            frame.close();
          }, error: (error: Error) => {
            console.error(error);
          }
        });
        let codec_str: string;
        switch (this._streaming_mode) {
          case StreamingMode.VP8:
            codec_str = 'vp8';
            break;
          case StreamingMode.VP9:
            codec_str = 'vp09.03.31.08';
            break;
          case StreamingMode.HEVC:
            codec_str = 'hev1.1.6.L93.B0';
            break;
          //case StreamingMode.MPEG4:
          //  codec_str = 'mp4v.60'; // https://developer.mozilla.org/en-US/docs/Web/Media/Formats/codecs_parameter#mp4v.oo.v
          //  break;
          case StreamingMode.H264:
            codec_str = 'avc1.64001f';
        }
        this._video_decoder.configure({
          codec: codec_str,
          optimizeForLatency: true,
          hardwareAcceleration: "no-preference",
          codedWidth: this._stream_element.width,
          codedHeight: this._stream_element.height,
        });
        break;

      default:
        console.error(
          `Unsupported streaming mode '${this.model.get("streaming_mode")}'!`
        );
    }

    if (this._streaming_mode == StreamingMode.MJPEG && this._stream_element) {
      (this._stream_element as HTMLImageElement).src = this.model.get("websocket_url");
    }
  }

  private register_events() {
    if (this._stream_element == null)
      return;
    this._stream_element.addEventListener(
      "mousemove",
      (event: Event) => {
        const evt = event as MouseEvent;
        if (evt?.target == null || !(evt.target instanceof HTMLElement))
          return;

        const rect = evt.target.getBoundingClientRect();
        this.model.set("mouse_pos_x", Math.round(evt.clientX - rect.left));
        this.model.set("mouse_pos_y", Math.round(rect.height - (evt.clientY - rect.top)));
        this.model.save_changes();
      }
    );
    this._stream_element.addEventListener(
      "contextmenu",
      (event: Event) => {
        event.preventDefault();
        event.stopPropagation();
      }
    );
    this._stream_element.addEventListener(
      "mousedown",
      (event: Event) => {
        const evt = event as MouseEvent;
        this.send({"mousedown": evt.button});
        evt.preventDefault();
        evt.stopPropagation();
      }
    );
    this._stream_element.addEventListener(
      "mouseup",
      (event: Event) => {
        const evt = event as MouseEvent;
        this.send({"mouseup": evt.button});
        evt.preventDefault();
        evt.stopPropagation();
      }
    );
    this._stream_element.addEventListener(
      "mouseover",
      () => {
        this._focussed = true;
      }
    );
    this._stream_element.addEventListener(
      "mouseleave",
      () => {
        this._focussed = false;
      }
    );
    document.addEventListener("keypress", this.on_keypress, {capture: true});
    document.addEventListener("keydown", this.on_keydown, {capture: true});
    document.addEventListener("keyup", this.on_keyup, {capture: true});
    document.addEventListener("wheel", this.on_wheel, {passive: false});
  }

  private unregister_events() {
    // It's probably a good idea to unregister any events on the document itself. The events on the element, should be
    // destroyed with the element.
    window.removeEventListener("keypress", this.on_keypress);
    window.removeEventListener("keydown", this.on_keydown);
    window.removeEventListener("keyup", this.on_keyup);
    window.removeEventListener("wheel", this.on_wheel);
  }

  private on_keypress = (event: KeyboardEvent) => {
    if (this._focussed) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }

  private on_keydown = (event: KeyboardEvent) => {
    if (this._focussed) {
      this.send({"keydown": event.key});
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }

  private on_keyup = (event: KeyboardEvent) => {
    if (this._focussed) {
      this.send({"keyup": event.key});
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }

  private on_wheel = (event: WheelEvent) => {
    if (this._focussed) {
      this.send({"wheel": event.deltaY});
      event.preventDefault();
    }
  }

  private download_file(filename: string, data: ArrayBuffer | ArrayBufferView) {
    const a_element = document.createElement("a");
    /*const blob = new Blob([data], {type: "text/plain"});
    const b64 = URL.createObjectURL(blob);*/
    // Our files happen to already be base64 encoded, so we can avoid the Blob and object URL creation
    const b64 = this._text_decoder.decode(data);
    a_element.download = filename;
    a_element.href = b64;

    a_element.addEventListener('click', () => {
      setTimeout(() => {
        URL.revokeObjectURL(b64);
      }, 1000);
    }, false);

    a_element.click();
  }

  // Triggered ~250ms to update UI elements which don't need updating frequently
  private slow_update() {
    this._widget_status_bar?.slow_update();
  }

  stream_data_changed(stream_data: ArrayBuffer | ArrayBufferView | string) {
    if (!this._stream_element) return;

    switch (this._streaming_mode) {
      case StreamingMode.JPG:
      case StreamingMode.PNG:
        //(this._stream_element as HTMLImageElement).src = this.model.get("stream_data");
        //(this._stream_element as HTMLImageElement).src = this._text_decoder.decode(this.model.get("stream_data"));
        if (typeof stream_data === "string")
          (this._stream_element as HTMLImageElement).src = stream_data as string;
        else
          (this._stream_element as HTMLImageElement).src = this._text_decoder.decode(stream_data);
        //(this._stream_element as HTMLImageElement).src = stream_data as string;
        break;
      //case StreamingMode.MJPEG:
      case StreamingMode.H264:
      //case StreamingMode.HEVC:
      //case StreamingMode.MPEG4:
      case StreamingMode.VP8:
      case StreamingMode.VP9:
        if (!this._video_decoder || typeof stream_data === "string") return;
        this._video_decoder.decode(new EncodedVideoChunk({type:"key", duration:1, timestamp:1, data:stream_data}));
        break;
    }
  }
}
