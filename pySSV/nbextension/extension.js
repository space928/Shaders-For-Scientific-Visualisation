/*
 * Copyright (c) 2023 Thomas Mathieson.
 * Distributed under the terms of the MIT license.
 */

// Entry point for the notebook bundle containing custom model definitions.
//
define(function() {
    "use strict";

    window['requirejs'].config({
        map: {
            '*': {
                'pySSV': 'nbextensions/pySSV/index',
            },
        }
    });
    // Export the required load_ipython_extension function
    return {
        load_ipython_extension : function() {}
    };
});