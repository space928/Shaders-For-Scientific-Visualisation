/*
 * Copyright (c) 2024 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

import {RENDERDOC_LOGO_SVG} from "./renderdoc_logo";
import {SSVWidgetSaveImageSettingsPanel} from "./widget_save_image_settings";
import {DOMWidgetView} from "@jupyter-widgets/base";

class SSVStatusBarView {
  private _widget_view: DOMWidgetView;
  private _widget_root_element: HTMLElement;
  private _stream_element: HTMLImageElement | HTMLCanvasElement | null;
  private _status_frame_stats_element: HTMLButtonElement | null = null;
  private _show_advanced_status: boolean = false;
  private _status_adv_frame_stats_element: HTMLTableCellElement[] = [];
  private _status_resolution_element: HTMLSpanElement | null = null;
  private _log_button_element: HTMLButtonElement | null = null;
  private _log_element: HTMLElement | null = null;
  private _save_settings_panel: SSVWidgetSaveImageSettingsPanel;

  public constructor(widget: DOMWidgetView, root: HTMLElement,
                     stream_element: HTMLImageElement | HTMLCanvasElement | null) {
    this._widget_view = widget;
    this._widget_root_element = root;
    this._stream_element = stream_element;
    this._save_settings_panel = new SSVWidgetSaveImageSettingsPanel(widget, root);
  }

  public render() {
    const status_bar_div = document.createElement("div");
    status_bar_div.className = "ssv-status-bar";
    this._widget_root_element.appendChild(status_bar_div);

    // Play + Stop buttons
    this.render_playback_controls(status_bar_div);
    // Frame statistics (FPS counter)
    this.render_frame_stats_control(status_bar_div);
    // Canvas resolution
    this.render_canvas_resolution_control(status_bar_div);
    // Connection status
    this.render_connection_status_control(status_bar_div);
    // Renderdoc capture button
    this.render_renderdoc_capture_control(status_bar_div);
    // Save image button
    this.render_image_save_control(status_bar_div);
    // View Logs button
    this.render_view_logs_control(status_bar_div);


    // Log panel
    this.render_log_panel();
  }

  public slow_update() {
    if (this._status_frame_stats_element) {
      if (this._show_advanced_status) {
        const times_str: string = this._widget_view.model.get("frame_times");
        const times = times_str.split(";");
        if (times.length >= 4 && this._status_adv_frame_stats_element.length == 4) {
          this._status_adv_frame_stats_element[0].innerText = times[0];
          this._status_adv_frame_stats_element[1].innerText = times[1];
          this._status_adv_frame_stats_element[2].innerText = times[2];
          this._status_adv_frame_stats_element[3].innerText = times[3];
        }
      } else {
        this._status_frame_stats_element.innerText = `${this._widget_view.model.get("frame_rate").toFixed(2)} FPS`;
      }
    }
    if (this._status_resolution_element) {
      this._status_resolution_element.innerText = `${this._stream_element?.width ?? 0} x ${this._stream_element?.height ?? 0}`;
    }
  }

  private render_playback_controls(status_bar_div: HTMLDivElement) {
    const status_play_pause = document.createElement("span");
    status_play_pause.className = "ssv-status-play-pause";
    status_bar_div.appendChild(status_play_pause);
    const play_button = document.createElement("button");
    play_button.textContent = "⏵";
    play_button.className = "ssv-button ssv-icon-button";
    play_button.onclick = () => {
      this._widget_view.send({"play": 0})
    };
    status_play_pause.appendChild(play_button);
    const stop_button = document.createElement("button");
    stop_button.textContent = "⏹︎";
    stop_button.className = "ssv-button ssv-icon-button";
    stop_button.onclick = () => {
      this._widget_view.send({"stop": 0})
    };
    status_play_pause.appendChild(stop_button);
  }

  private render_frame_stats_control(status_bar_div: HTMLDivElement) {
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
      if (this._status_frame_stats_element) {
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
          this._status_adv_frame_stats_element = [];
          if (table)
            this._status_frame_stats_element.removeChild(table);
        }
      }
      this._show_advanced_status = show_advanced;
    };
  }

  private render_canvas_resolution_control(status_bar_div: HTMLDivElement) {
    const status_resolution = document.createElement("span");
    status_resolution.className = "ssv-status-resolution";
    status_bar_div.appendChild(status_resolution);
    this._status_resolution_element = status_resolution;
  }

  private render_connection_status_control(status_bar_div: HTMLDivElement) {
    const status_connection = document.createElement("span");
    status_connection.className = "ssv-status-connection";
    status_connection.innerText = "⭮ Connecting";
    status_bar_div.appendChild(status_connection);
    this._widget_view.model.on("change:status_connection", () => {
      if (this._widget_view.model.get("status_connection")) {
        status_connection.innerText = "🗲 Connected";
        status_connection.classList.toggle("ssv-status-disconnected", false);
      } else {
        status_connection.innerText = "✕ Disconnected";
        status_connection.classList.toggle("ssv-status-disconnected", true);
      }
    }, this);
  }

  private render_renderdoc_capture_control(status_bar_div: HTMLDivElement) {
    const renderdoc_capture = document.createElement("span");
    renderdoc_capture.className = "ssv-status-renderdoc";
    status_bar_div.appendChild(renderdoc_capture);
    const capture_button = document.createElement("button");
    capture_button.innerHTML = RENDERDOC_LOGO_SVG;
    capture_button.className = "ssv-button ssv-icon-button";
    renderdoc_capture.appendChild(capture_button);
    capture_button.style.visibility = this._widget_view.model.get("enable_renderdoc") ? "visible" : "hidden";
    capture_button.onclick = () => {
      this._widget_view.send({"renderdoc_capture": 0})
    };
    this._widget_view.model.on("change:enable_renderdoc", () => {
      capture_button.style.visibility = this._widget_view.model.get("enable_renderdoc") ? "visible" : "hidden";
    });
  }

  private render_image_save_control(status_bar_div: HTMLDivElement) {
    const save_image_controls = document.createElement("span");
    save_image_controls.className = "ssv-status-save-image";
    status_bar_div.appendChild(save_image_controls);
    const save_image_button = document.createElement("button");
    save_image_button.textContent = "📷";
    save_image_button.className = "ssv-button ssv-icon-button ssv-combi-button-left";
    save_image_button.onclick = () => {
      this._widget_view.send({"save_image": this._save_settings_panel.save_image_settings})
    };
    save_image_controls.appendChild(save_image_button);
    const save_image_settings_button = document.createElement("button");
    save_image_settings_button.textContent = "⚙️";
    save_image_settings_button.className = "ssv-button ssv-icon-button ssv-combi-button-right";
    save_image_settings_button.onclick = () => {
      this._save_settings_panel.hidden = !this._save_settings_panel.hidden;
    };
    save_image_controls.appendChild(save_image_settings_button);

    this._save_settings_panel.render(save_image_controls);
  }

  private render_view_logs_control(status_bar_div: HTMLDivElement) {
    const status_log = document.createElement("span");
    status_log.className = "ssv-status-log";
    status_bar_div.appendChild(status_log);
    const log_button = document.createElement("button");
    this._log_button_element = log_button;
    log_button.textContent = "View Log";
    log_button.className = "ssv-button";
    status_log.appendChild(log_button);
    log_button.onclick = () => {
      if (this._log_element) {
        const active = this._log_element.classList.toggle("ssv-log-active");
        if (active)
          log_button.textContent = "Hide Log";
        else
          log_button.textContent = "View Log";
      }
    };
  }

  private render_log_panel() {
    const log_div = document.createElement("code");
    log_div.className = "ssv-log";
    this._widget_root_element.appendChild(log_div);
    this._log_element = log_div;
    this._widget_view.model.on("change:status_logs", () => {
      if (this._log_element) {
        let log_text: string = this._widget_view.model.get("status_logs");
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
}

export {SSVStatusBarView};
