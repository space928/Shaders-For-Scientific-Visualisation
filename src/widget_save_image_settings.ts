/*
 * Copyright (c) 2024 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

import {DOMWidgetView} from "@jupyter-widgets/base";

enum SSVImageType {
  JPG = "jpg",
  PNG = "png"
}

type SSVSaveImageSettings = {
  image_type: SSVImageType,
  quality: number,
  size: { width: number, height: number } | null,
  render_buffer: number,
  suppress_ui: boolean
}

class SSVWidgetSaveImageSettingsPanel {
  // @ts-ignore
  private _widget_view: DOMWidgetView;
  // @ts-ignore
  private _widget_root_element: HTMLElement;
  private readonly _save_image_settings: SSVSaveImageSettings;
  private _hidden: boolean = true;
  private _settings_panel_element: HTMLDivElement | null = null;

  public constructor(widget: DOMWidgetView, root: HTMLElement) {
    this._widget_view = widget;
    this._widget_root_element = root;
    this._save_image_settings = {
      image_type: SSVImageType.JPG,
      quality: 95,
      size: null,
      render_buffer: 0,
      suppress_ui: false
    };
  }

  get save_image_settings(): SSVSaveImageSettings {
    return this._save_image_settings;
  }

  get hidden(): boolean {
    return this._hidden;
  }

  set hidden(value: boolean) {
    this._hidden = value;
    if(value)
      this._settings_panel_element?.classList.add("ssv-hidden");
    else
      this._settings_panel_element?.classList.remove("ssv-hidden");
  }

  public render(parent_element: HTMLElement) {
    this._settings_panel_element = document.createElement("div");
    this._settings_panel_element.classList.add("ssv-modal", "ssv-hidden");
    parent_element.appendChild(this._settings_panel_element);
    this._settings_panel_element.style.translate = `0 2.4rem`;  // This is a lazy approach, but it works for now
    this._settings_panel_element.style.width = "20rem";
    // this._settings_panel_element.style.height = "20rem";

    const title_bar = document.createElement("span");
    title_bar.className = "ssv-modal-title-bar";
    this._settings_panel_element.appendChild(title_bar);
    const title_bar_label = document.createElement("label");
    title_bar_label.style.paddingLeft = "14px";
    title_bar_label.style.fontWeight = "bold";
    title_bar_label.innerText = "Image Settings";
    title_bar.appendChild(title_bar_label);

    // Close button
    const close_button = document.createElement("button");
    close_button.textContent = "❌";
    close_button.className = "ssv-button ssv-icon-button";
    close_button.style.marginRight = "0";
    close_button.onclick = () => {
      this.hidden = true;
    };
    title_bar.appendChild(close_button);

    // Image type
    const image_type_span = document.createElement("span");
    image_type_span.className = "ssv-modal-item";
    const image_type_label = document.createElement("label");
    image_type_label.className = "ssv-label";
    image_type_label.innerText = "Image Type:"

    const image_type_combo = document.createElement("select");
    image_type_combo.className = "ssv-input-select";
    for(const v in SSVImageType) {
      const option = document.createElement("option");
      option.textContent = v;
      option.value = v;
      image_type_combo.appendChild(option);
    }
    image_type_combo.onchange = () => {
      //this._save_image_settings.image_type = image_type_combo.value as SSVImageType;
      this._save_image_settings.image_type = (SSVImageType as any)[image_type_combo.value];
    };
    image_type_span.append(image_type_label, image_type_combo);
    this._settings_panel_element.appendChild(image_type_span);

    // Quality slider
    const quality_span = document.createElement("span");
    quality_span.className = "ssv-modal-item";
    const quality_label = document.createElement("label");
    quality_label.className = "ssv-label";
    quality_label.innerText = "Image Quality:"

    const quality_input = document.createElement("input");
    quality_input.className = "ssv-input-number";
    quality_input.style.width = "2rem";
    quality_input.type = "number";
    quality_input.min = "0";
    quality_input.max = "100";
    quality_input.step = "1";
    quality_input.valueAsNumber = this._save_image_settings.quality;
    quality_input.onchange = () => {
      quality_slider.valueAsNumber = quality_input.valueAsNumber;
      this._save_image_settings.quality = quality_input.valueAsNumber;
    };

    const quality_slider = document.createElement("input");
    quality_slider.className = "ssv-input-slider";
    quality_slider.style.flexGrow = "1";
    quality_slider.type = "range";
    quality_slider.min = "0";
    quality_slider.max = "100";
    quality_slider.step = "1";
    quality_slider.valueAsNumber = this._save_image_settings.quality;
    quality_slider.oninput = () => {
      quality_input.valueAsNumber = quality_slider.valueAsNumber;
      this._save_image_settings.quality = quality_slider.valueAsNumber;
    };
    quality_slider.onchange = () => {
      quality_input.valueAsNumber = quality_slider.valueAsNumber;
      this._save_image_settings.quality = quality_slider.valueAsNumber;
    };
    quality_span.append(quality_label, quality_input, quality_slider);
    this._settings_panel_element.appendChild(quality_span);

    // Suppress UI
    const suppress_ui_span = document.createElement("span");
    suppress_ui_span.className = "ssv-modal-item";
    const suppress_ui_label = document.createElement("label");
    suppress_ui_label.className = "ssv-label";
    suppress_ui_label.innerText = "Suppress SSV GUI:"

    const suppress_ui_toggle = document.createElement("input");
    suppress_ui_toggle.className = "ssv-input-checkbox";
    suppress_ui_toggle.type = "checkbox";
    suppress_ui_toggle.value = `${this._save_image_settings.suppress_ui}`;
    suppress_ui_toggle.onchange = () => {
      this._save_image_settings.suppress_ui = suppress_ui_toggle.checked;
    };
    suppress_ui_span.append(suppress_ui_label, suppress_ui_toggle);
    this._settings_panel_element.appendChild(suppress_ui_span);

    // Size enable
    const size_enable_span = document.createElement("span");
    size_enable_span.className = "ssv-modal-item";
    const size_enable_label = document.createElement("label");
    size_enable_label.className = "ssv-label";
    size_enable_label.innerText = "Use Custom Resolution:"

    const size_enable_toggle = document.createElement("input");
    size_enable_toggle.className = "ssv-input-checkbox";
    size_enable_toggle.type = "checkbox";
    size_enable_toggle.value = `${this._save_image_settings.size != null}`;
    size_enable_toggle.onchange = () => {
      if(size_enable_toggle.checked) {
        width_input.disabled = false;
        height_input.disabled = false;
        this._save_image_settings.size = {width: width_input.valueAsNumber, height: height_input.valueAsNumber};
      } else {
        width_input.disabled = true;
        height_input.disabled = true;
        this._save_image_settings.size = null;
      }
    };
    size_enable_span.append(size_enable_label, size_enable_toggle);
    this._settings_panel_element.appendChild(size_enable_span);

    // Size
    const size_controls_span = document.createElement("span");
    size_controls_span.className = "ssv-modal-item";
    const width_control_label = document.createElement("label");
    width_control_label.className = "ssv-label";
    width_control_label.innerText = "Width:";
    const height_control_label = document.createElement("label");
    height_control_label.className = "ssv-label";
    height_control_label.innerText = "Height:";

    const width_input = document.createElement("input");
    width_input.className = "ssv-input-number";
    width_input.type = "number";
    width_input.min = "1";
    width_input.max = "65536";
    width_input.step = "1";
    width_input.valueAsNumber = 1920;
    width_input.onchange = () => {
        this._save_image_settings.size = {width: width_input.valueAsNumber, height: height_input.valueAsNumber};
    }

    const height_input = document.createElement("input");
    height_input.className = "ssv-input-number";
    height_input.type = "number";
    height_input.min = "1";
    height_input.max = "65536";
    height_input.step = "1";
    height_input.valueAsNumber = 1080;
    height_input.onchange = () => {
        this._save_image_settings.size = {width: width_input.valueAsNumber, height: height_input.valueAsNumber};
    }

    width_input.disabled = true;
    height_input.disabled = true;
    size_controls_span.append(width_control_label, width_input, height_control_label, height_input);
    this._settings_panel_element.appendChild(size_controls_span);

    // Render Buffer
    const render_buffer_span = document.createElement("span");
    render_buffer_span.className = "ssv-modal-item";
    const render_buffer_label = document.createElement("label");
    render_buffer_label.className = "ssv-label";
    render_buffer_label.innerText = "Render Buffer:"

    const render_buffer_input = document.createElement("input");
    render_buffer_input.className = "ssv-input-number";
    render_buffer_input.type = "number";
    render_buffer_input.min = "0";
    render_buffer_input.step = "1";
    render_buffer_input.valueAsNumber = 0;
    render_buffer_input.onchange = () => {
      this._save_image_settings.render_buffer = render_buffer_input.valueAsNumber;
    }
    render_buffer_span.append(render_buffer_label, render_buffer_input);
    this._settings_panel_element.appendChild(render_buffer_span);
  }
}

export {SSVWidgetSaveImageSettingsPanel}
