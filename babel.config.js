/*
 * Copyright (c) 2023 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

module.exports = {
  sourceMap: 'inline',
  presets: [
    [
      '@babel/preset-env',
      {
        targets: {
          node: 'current',
        },
      },
    ],
  ],
};
