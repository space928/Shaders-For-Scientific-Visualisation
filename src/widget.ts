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
import {RENDERDOC_LOGO_SVG} from "./renderdoc_logo";

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

  /**
   * Registers a callback to the on_stream_data event, called whenever new streamed frame data is available to the
   * canvas.
   * @param callback the callback to invoke when new data is available.
   * @param context a value for `this`.
   */
  public on_stream_data(callback: StreamDataEvent, context: any) {
    this._on_stream_data = {event: callback, ctx: context};
  }

  public _handle_comm_msg(msg: KernelMessage.ICommMsgMsg): Promise<void> {
    if (msg.content.data["method"] == "custom") {
      const content = msg.content.data["content"];
      if (content !== null && typeof content === "object") {
        if ("stream_data" in content) {
          if (this._on_stream_data && msg.buffers && msg.buffers.length > 0)
            this._on_stream_data.event.call(this._on_stream_data.ctx, msg.buffers[0]);
        }
      }
    }
    return super._handle_comm_msg(msg);
  }
}

export class SSVRenderView extends DOMWidgetView {
  private _stream_element: HTMLImageElement | HTMLCanvasElement | null = null;
  private _status_frame_stats_element: HTMLButtonElement | null = null;
  private _status_adv_frame_stats_element: HTMLTableCellElement [] = [];
  private _show_advanced_status: boolean = false;
  private _status_resolution_element: HTMLSpanElement | null = null;
  private _log_button_element: HTMLButtonElement | null = null;
  private _log_element: HTMLElement | null = null;
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
        this._video_decoder = new VideoDecoder({output: (frame: VideoFrame) => {
            if(!this._stream_element)
              return;
            this._canvas_ctx?.drawImage(frame, 0, 0);
            frame.close();
          }, error: (error: Error) => {
            console.error(error);
          }});
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

    // Status bar
    this.create_status_bar();

    // Setup callbacks
    // this.stream_data_changed();
    if(this._use_websockets) {
      this._websocket = new WebSocket(this.model.get("websocket_url"));
      this._websocket.addEventListener("open", (event) => { });
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
      (event: Event) => {
        this._focussed = true;
      }
    );
    this._stream_element.addEventListener(
      "mouseleave",
      (event: Event) => {
        this._focussed = false;
      }
    );
    document.addEventListener("keypress", this.on_keypress, {capture: true});
    document.addEventListener("keydown", this.on_keydown, {capture: true});
    document.addEventListener("keyup", this.on_keyup, {capture: true});
    document.addEventListener("wheel", this.on_wheel, {passive: false});
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

  private unregister_events() {
    // It's probably a good idea to unregister any events on the document itself. The events on the element, should be
    // destroyed with the element.
    window.removeEventListener("keypress", this.on_keypress);
    window.removeEventListener("keydown", this.on_keydown);
    window.removeEventListener("keyup", this.on_keyup);
    window.removeEventListener("wheel", this.on_wheel);
  }

// Triggered ~250ms to update UI elements which don't need updating frequently
  private slow_update() {
    if (this._status_frame_stats_element) {
      if (this._show_advanced_status) {
        const times_str: string = this.model.get("frame_times");
        const times = times_str.split(";");
        if (times.length >= 4) {
          this._status_adv_frame_stats_element[0].innerText = times[0];
          this._status_adv_frame_stats_element[1].innerText = times[1];
          this._status_adv_frame_stats_element[2].innerText = times[2];
          this._status_adv_frame_stats_element[3].innerText = times[3];
        }
      } else {
        this._status_frame_stats_element.innerText = `${this.model.get("frame_rate").toFixed(2)} FPS`;
      }
    }
    if (this._status_resolution_element) {
      this._status_resolution_element.innerText = `${this._stream_element?.width ?? 0} x ${this._stream_element?.height ?? 0}`;
    }
  }

  private create_status_bar() {
    const status_bar_div = document.createElement("div");
    status_bar_div.className = "ssv-status-bar";
    this.el.appendChild(status_bar_div);

    // Play + Stop buttons
    const status_play_pause = document.createElement("span");
    status_play_pause.className = "ssv-status-play-pause";
    status_bar_div.appendChild(status_play_pause);
    const play_button = document.createElement("button");
    play_button.textContent = "⏵";
    play_button.className = "ssv-button ssv-icon-button";
    play_button.onclick = () => { this.send({"play": 0}) };
    status_play_pause.appendChild(play_button);
    const stop_button = document.createElement("button");
    stop_button.textContent = "⏹︎";
    stop_button.className = "ssv-button ssv-icon-button";
    stop_button.onclick = () => { this.send({"stop": 0}) };
    status_play_pause.appendChild(stop_button);

    // Frame statistics (FPS counter)
    const status_frame_stats = document.createElement("span");
    status_frame_stats.className = "ssv-status-frame-stats";
    status_bar_div.appendChild(status_frame_stats);
    const frame_status_button = document.createElement("button");
    this._status_frame_stats_element = frame_status_button;
    frame_status_button.textContent = "? FPS";
    frame_status_button.className = "ssv-button";
    status_frame_stats.appendChild(frame_status_button);
    frame_status_button.onclick = () => {
      const show_advanced = !this._show_advanced_status;
      if(this._status_frame_stats_element) {
        if (!this._show_advanced_status) {
          // Create the advanced frame stats table
          const table = document.createElement("table");
          const tbody = document.createElement("tbody");
          table.appendChild(tbody);
          table.className = "ssv-status-frame-stats";
          const r1 = document.createElement("tr");
          const r2 = document.createElement("tr");
          tbody.append(r1, r2);
          tbody.className = "ssv-status-frame-stats";
          const c1 = document.createElement("td");
          const c2 = document.createElement("td");
          const c3 = document.createElement("td");
          const c4 = document.createElement("td");
          c1.className = "ssv-status-frame-stats";
          c2.className = "ssv-status-frame-stats";
          c3.className = "ssv-status-frame-stats";
          c4.className = "ssv-status-frame-stats";
          r1.append(c1, c2);
          r2.append(c3, c4);
          this._status_adv_frame_stats_element = [c1, c2, c3, c4];
          this._status_frame_stats_element.innerText = "";
          this._status_frame_stats_element.appendChild(table);
        } else {
          // Remove the advanced frame stats table
          const table = this._status_frame_stats_element.firstChild;
          if(table)
            this._status_frame_stats_element.removeChild(table);
        }
      }
      this._show_advanced_status = show_advanced;
    };

    // Canvas resolution
    const status_resolution = document.createElement("span");
    status_resolution.className = "ssv-status-resolution";
    status_bar_div.appendChild(status_resolution);
    this._status_resolution_element = status_resolution;

    // Connection status
    const status_connection = document.createElement("span");
    status_connection.className = "ssv-status-connection";
    status_connection.innerText = "⭮ Connecting";
    status_bar_div.appendChild(status_connection);
    this.model.on("change:status_connection", () => {
      if(this.model.get("status_connection")) {
        status_connection.innerText = "🗲 Connected";
        status_connection.classList.toggle("ssv-status-disconnected", false);
      } else {
        status_connection.innerText = "✕ Disconnected";
        status_connection.classList.toggle("ssv-status-disconnected", true);
      }
    }, this);

    // Renderdoc capture button
    const renderdoc_capture = document.createElement("span");
    renderdoc_capture.className = "ssv-status-renderdoc";
    status_bar_div.appendChild(renderdoc_capture);
    const capture_button = document.createElement("button");
    capture_button.innerHTML = RENDERDOC_LOGO_SVG;
    capture_button.className = "ssv-button ssv-icon-button";
    renderdoc_capture.appendChild(capture_button);
    capture_button.style.visibility = this.model.get("enable_renderdoc") ? "visible" : "hidden";
    capture_button.onclick = () => {
      this.send({"renderdoc_capture": 0})
    };
    this.model.on("change:enable_renderdoc", () => {
      capture_button.style.visibility = this.model.get("enable_renderdoc") ? "visible" : "hidden";
    });

    // View Logs button
    const status_log = document.createElement("span");
    status_log.className = "ssv-status-log";
    status_bar_div.appendChild(status_log);
    const log_button = document.createElement("button");
    this._log_button_element = log_button;
    log_button.textContent = "View Log";
    log_button.className = "ssv-button";
    status_log.appendChild(log_button);
    log_button.onclick = () => {
      if(this._log_element) {
        const active = this._log_element.classList.toggle("ssv-log-active");
        if(active)
          log_button.textContent = "Hide Log";
        else
          log_button.textContent = "View Log";
      }
    };

    // Log panel
    const log_div = document.createElement("code");
    log_div.className = "ssv-log";
    this.el.appendChild(log_div);
    this._log_element = log_div;
    this.model.on("change:status_logs", () => {
      if(this._log_element) {
        let log_text: string = this.model.get("status_logs");
        log_text = log_text.replace(/\r\n|\r|\n/g, '<br>');
        log_text = log_text.replace(/\t/g, '&nbsp;&nbsp;&nbsp;&nbsp;');
        if (log_text.includes("[WARNING]")) {
          log_text = "<span class='ssv-log-warn'>" + log_text + "</span>";
          if (this._log_button_element)
            this._log_button_element.textContent += " ⚠️";
        } else if (log_text.includes("[ERROR]")) {
          log_text = "<span class='ssv-log-error'>" + log_text + "</span>";
          if (this._log_button_element)
            this._log_button_element.textContent += " ⛔";
        }

        // Work out if we need to auto-scroll to the bottom of the log.
        // If the scroll position is within 150 pixels of the bottom, then we keep auto-scrolling.
        const auto_scroll = this._log_element.scrollHeight == this._log_element.clientHeight ||
          (this._log_element.scrollHeight - this._log_element.scrollTop - this._log_element.clientHeight) <= 150;

        // You would have to be pretty determined to use this as an XSS entrypoint
        this._log_element.innerHTML = this._log_element.innerHTML + log_text;

        if (auto_scroll)
          this._log_element.scrollTo({top: this._log_element.scrollHeight, behavior: "instant"});
      }
    }, this);
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
