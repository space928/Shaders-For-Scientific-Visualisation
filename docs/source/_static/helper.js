/*
 * Copyright (c) 2023 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

var cache_require = window.require;

window.addEventListener('load', function() {
  window.require = cache_require;
});
