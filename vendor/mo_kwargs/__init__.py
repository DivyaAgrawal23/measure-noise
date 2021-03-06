# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Contact: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import absolute_import, division, unicode_literals

from functools import update_wrapper

from mo_dots import get_logger, is_data, to_data, zip as dict_zip, set_default
from mo_future import (
    get_function_arguments,
    get_function_defaults,
    get_function_name,
    text,
    is_text)
from mo_logs import Except

KWARGS = str("kwargs")


def override(kwargs=None):
    """
    THIS DECORATOR WILL PUT ALL PARAMETERS INTO THE `kwargs` PARAMETER AND
    THEN PUT ALL `kwargs` PARAMETERS INTO THE FUNCTION PARAMETERS. THIS HAS
    THE BENEFIT OF HAVING ALL PARAMETERS IN ONE PLACE (kwargs), PLUS ALL
    PARAMETERS ARE EXPLICIT FOR CLARITY.

    OF COURSE, THIS MEANS PARAMETER ASSIGNMENT MAY NOT BE UNIQUE: VALUES CAN
    COME FROM EXPLICIT CALL PARAMETERS, OR FROM THE kwargs PARAMETER. IN
    THESE CASES, PARAMETER VALUES ARE CHOSEN IN THE FOLLOWING ORDER:
    1) EXPLICT CALL PARAMETERS
    2) PARAMETERS FOUND IN kwargs
    3) DEFAULT VALUES ASSIGNED IN FUNCTION DEFINITION
    """

    def output(func):
        func_name = get_function_name(func)
        params = get_function_arguments(func)
        if not get_function_defaults(func):
            defaults = {}
        else:
            defaults = {
                k: v
                for k, v in zip(reversed(params), reversed(get_function_defaults(func)))
            }

        def raise_error(e, a, k):
            packed = set_default(dict(zip(params, a)), k)
            err = text(e)
            e = Except.wrap(e)
            if err.startswith(func_name) and (
                    "takes at least" in err
                    or "takes exactly " in err
                    or "required positional argument" in err
            ):
                missing = [p for p in params if str(p) not in packed]
                given = [p for p in params if str(p) in packed]
                if not missing:
                    raise e
                else:
                    get_logger().error(
                        "Problem calling {{func_name}}:  Expecting parameter {{missing}}, given {{given}}",
                        func_name=func_name,
                        missing=missing,
                        given=given,
                        stack_depth=2,
                        cause=e,
                    )
            raise e

        if kwargs not in params:
            # ADDING A kwargs PARAMETER TO SOME REGULAR METHOD
            def wo_kwargs(*given_args, **given_kwargs):
                settings = given_kwargs.get(kwargs, {})
                ordered_params = dict(zip(params, given_args))
                a, k = params_pack(params, defaults, settings, given_kwargs, ordered_params)
                try:
                    return func(*a, **k)
                except TypeError as e:
                    raise_error(e, a, k)

            return update_wrapper(wo_kwargs, func)

        elif func_name in ("__init__", "__new__") or params[0] in ("self", "cls"):

            def w_bound_method(*given_args, **given_kwargs):
                if len(given_args) == 2 and len(given_kwargs) == 0 and is_data(given_args[1]):
                    # ASSUME SECOND UNNAMED PARAM IS kwargs
                    a, k = params_pack(
                        params, defaults, given_args[1], {params[0]: given_args[0]}, given_kwargs
                    )
                elif kwargs in given_kwargs and is_data(given_kwargs[kwargs]):
                    # PUT args INTO given_kwargs
                    a, k = params_pack(
                        params, defaults, given_kwargs[kwargs], dict_zip(params, given_args), given_kwargs
                    )
                else:
                    a, k = params_pack(params, defaults, dict_zip(params, given_args), given_kwargs)
                try:
                    return func(*a, **k)
                except TypeError as e:
                    raise_error(e, a, k)

            return update_wrapper(w_bound_method, func)

        else:

            def w_kwargs(*given_args, **given_kwargs):
                if len(given_args) == 1 and len(given_kwargs) == 0 and is_data(given_args[0]):
                    # ASSUME SINGLE PARAMETER IS kwargs
                    a, k = params_pack(params, defaults, given_args[0])
                elif kwargs in given_kwargs and is_data(given_kwargs[kwargs]):
                    # PUT given_args INTO given_kwargs
                    a, k = params_pack(
                        params, defaults, given_kwargs[kwargs], dict_zip(params, given_args), given_kwargs
                    )
                else:
                    # PULL kwargs OUT INTO PARAMS
                    a, k = params_pack(params, defaults, dict_zip(params, given_args), given_kwargs)
                try:
                    return func(*a, **k)
                except TypeError as e:
                    raise_error(e, a, k)

            return update_wrapper(w_kwargs, func)

    def params_pack(params, *args):
        """
        :param params:
        :param args:
        :return: (args, kwargs) pair
        """
        settings = {}
        for a in args:
            for k, v in a.items():
                settings[str(k)] = v
        settings[kwargs] = to_data(settings)

        if params and params[0] in ("self", "cls"):
            s = settings.get(params[0])
            if s is None:
                return (
                    [],
                    {k: settings[k] for k in params[1:] if k in settings},
                )
            else:
                return (
                    [s],
                    {k: settings[k] for k in params[1:] if k in settings},
                )
        else:
            return (
                [],
                {k: settings[k] for k in params if k in settings}
            )

    if is_text(kwargs):
        # COMPLEX VERSION @override(kwargs="other")
        return output
    else:
        # SIMPLE VERSION @override
        func, kwargs = kwargs, KWARGS
        return output(func)
