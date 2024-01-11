/*
 * Copyright (c) 2023 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

import {
  DOMWidgetModel,
  DOMWidgetView,
  ISerializers,
  WidgetView
} from "@jupyter-widgets/base";

import {MODULE_NAME, MODULE_VERSION} from "./version";
import {RENDERDOC_LOGO_SVG} from "./renderdoc_logo";

// Import the CSS
import "../css/widget.css";

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
      status_connection: false,
      status_logs: "",
      mouse_pos_x: 0,
      mouse_pos_y: 0,
      enable_renderdoc: false
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
}

export class SSVRenderView extends DOMWidgetView {
  private _stream_img_element: HTMLImageElement | null = null;
  private _status_frame_stats_element: HTMLSpanElement | null = null;
  private _status_resolution_element: HTMLSpanElement | null = null;
  private _log_button_element: HTMLButtonElement | null = null;
  private _log_element: HTMLElement | null = null;
  private _focussed: boolean = false;

  initialize(parameters: WidgetView.IInitializeParameters) {
    super.initialize(parameters);
  }

  render() {
    // Render HTML
    this.el.classList.add("ssv-colors");
    if(getComputedStyle(document.documentElement).getPropertyValue("--colab-primary-surface-color").length > 0)
      this.el.classList.add("ssv-colab-support");

    this.el.classList.add("ssv-render-widget");

    switch (this.model.get("streaming_mode")) {
      case StreamingMode.JPG:
      case StreamingMode.PNG:
        this._stream_img_element = document.createElement("img");
        this._stream_img_element.className = "ssv-render-viewport";
        this._stream_img_element.setAttribute("draggable", "false");
        this.el.appendChild(this._stream_img_element);
        break;
      default:
        console.error(
          `Unsupported streaming mode '${this.model.get("streaming_mode")}'!`
        );
    }

    // Status bar
    this.create_status_bar();

    // Setup callbacks
    this.stream_data_changed();
    this.model.on("change:stream_data", this.stream_data_changed, this);

    if (this._stream_img_element) {
      setInterval(() => {
        this.send({"heartbeat": 0});
        this.slow_update();
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
    if (this._stream_img_element == null)
      return;
    this._stream_img_element.addEventListener(
      "mousemove",
      (event: MouseEvent) => {
        /*mousePos = {
          x: event.clientX,// / target.width,
          y: event.clientY,// / target.height
        };*/

        if (event?.target == null || !(event.target instanceof HTMLElement))
          return;

        const rect = event.target.getBoundingClientRect();
        this.model.set("mouse_pos_x", Math.round(event.clientX - rect.left));
        this.model.set("mouse_pos_y", Math.round(rect.height - (event.clientY - rect.top)));
        this.model.save_changes();
      }
    );
    this._stream_img_element.addEventListener(
      "mousedown",
      (event: MouseEvent) => {
        this.send({"mousedown": 0});
      }
    );
    this._stream_img_element.addEventListener(
      "mouseup",
      (event: MouseEvent) => {
        this.send({"mouseup": 0});
      }
    );
    this._stream_img_element.addEventListener(
      "mouseover",
      (event: MouseEvent) => {
        this._focussed = true;
      }
    );
    this._stream_img_element.addEventListener(
      "mouseleave",
      (event: MouseEvent) => {
        this._focussed = false;
      }
    );
    window.addEventListener("keypress", this.on_keypress);
    window.addEventListener("keydown", this.on_keydown);
    window.addEventListener("keyup", this.on_keyup);
    window.addEventListener("wheel", this.on_wheel, {passive: false});
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
      // TODO: FPS counter
      this._status_frame_stats_element.innerText = `? FPS`;
    }
    if (this._status_resolution_element) {
      this._status_resolution_element.innerText = `${this._stream_img_element?.width ?? 0} x ${this._stream_img_element?.height ?? 0}`;
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
    this._status_frame_stats_element = status_frame_stats;

    // Canvas resolution
    const status_resolution = document.createElement("span");
    status_resolution.className = "ssv-status-resolution";
    status_bar_div.appendChild(status_resolution);
    this._status_resolution_element = status_resolution;

    // Connection status
    const status_connection = document.createElement("span");
    status_connection.className = "ssv-status-connection";
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

  stream_data_changed() {
    if (!this._stream_img_element) return;

    //this.el.textContent = this.model.get('stream_data');
    this._stream_img_element.src = this.model.get("stream_data");
  }
}
