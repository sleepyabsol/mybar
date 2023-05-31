#TODO: Implement dynamic icons!
#TODO: Finish Mocp line!


__all__ = (
    'Field',
)


import asyncio
import threading
import time

from . import DEBUG
from . import field_funcs
from . import _setups
from . import utils
from .errors import *
from .formatting import FormatterFieldSig
from .templates import FieldSpec
from ._types import (
    FieldName,
    Icon,
    PTY_Icon,
    TTY_Icon,
    FormatStr,
    Args,
    Kwargs,
)

from collections.abc import Callable, Sequence
from typing import (
    NamedTuple,
    NoReturn,
    ParamSpec,
    Required,
    TypeAlias,
    TypeVar
)

Bar_T = TypeVar('Bar')
Field = TypeVar('Field')
P = ParamSpec('P')


class Field:
    '''
    Continuously generates and formats one bit of information in a :class:`Bar`.
    Pre-existing default Fields can be looked up by name.

    :param name: A unique identifier for the new field, defaults to `func.`:attr:`__name__`
    :type name: :class:`str`

    :param func: The Python function to run at every `interval` if no `constant_output` is set
    :type func: :class:`Callable[[*Args, **Kwargs], str]`

    :param icon: The field icon, defaults to ``''``.
        Placed before field contents or in place
        of ``{icon}`` in `template`, if provided
    :type icon: :class:`str`

    :param template: A curly-brace format string.
        This parameter is **required** if `icon` is ``None``.
        Valid placeholders:
            - ``{icon}`` references `icon`
            - ``{}`` references field contents
        Example:
            When the field's current contents are ``'69F'`` and its icon is ``'TEMP'``,
            ``template='[{icon}]: {}'`` shows as ``'[TEMP]: 69F'``
    :type template: :class:`_types.FormatStr`

    :param interval: How often in seconds field contents are updated, defaults to ``1.0``
    :type interval: :class:`float`

    :param align_to_seconds: Update contents at the start of each second, defaults to ``False``
    :type align_to_seconds: :class:`bool`

    :param timely: Run the field as soon as possible after every refresh, defaults to ``False``
    :type timely: :class:`bool`

    :param overrides_refresh: Updates to this field re-print the bar between refreshes, defaults to ``False``
    :type overrides_refresh: :class:`bool`

    :param threaded: Run this field in a separate thread, defaults to ``False``
    :type threaded: :class:`bool`

    :param always_show_icon: Show icons even when contents are empty, defaults to ``False``
    :type always_show_icon: :class:`bool`

    :param run_once: Permanently set contents by running `func` only once, defaults to ``False``
    :type run_once: :class:`bool`

    :param constant_output: Permanently set contents instead of running a function
    :type constant_output: :class:`str`, optional

    :param bar: Attach the :class:`Field` to this :class:`Bar`
    :type bar: :class:`Bar`, optional

    :param args: Positional args passed to `func`
    :type args: :class:`Args`, optional

    :param kwargs: Keyword args passed to `func`
    :type kwargs: :class:`Kwargs`, optional

    :param setup: A special callback that updates `kwargs` with static data that `func` would otherwise have to evaluate every time it runs
    :type setup: :class:`Callable[P, Kwargs]`, optional

    :param icons: A pair of icons used in different cases.
        Note: The `icon` parameter sets both of these automatically.
        The first string is intended for graphical (PTY) environments where support for Unicode is more likely.
        The second string is intended for terminal (TTY) environments where only ASCII is supported.
        This enables the same :class:`Field` instance to use the most optimal icon automatically.
    :type icons: tuple[:class:`_types.PTY_Icon`, :class:`_types.TTY_Icon`], optional


    :raises: :exc:`errors.IncompatibleArgsError` when
        neither `func` nor `constant_output` are given
    :raises: :exc:`errors.IncompatibleArgsError` when
        neither `icon` nor `template` are given
    :raises: :exc:`TypeError` when `func` is not callable
    :raises: :exc:`TypeError` when `setup`, if given, is not callable
    '''
    _default_fields = {

        'hostname': {
            'name': 'hostname',
            'func': field_funcs.get_hostname,
            'run_once': True
        },

        'host': {
            'name': 'host',
            'func': field_funcs.get_host,
            'kwargs': {
                'fmt': '{nodename}',
            },
            'run_once': True
        },

        'uptime': {
            'name': 'uptime',
            'func': field_funcs.get_uptime,
            'setup': _setups.setup_uptime,
            'timely': True,
            'align_to_seconds': True,
            'kwargs': {
                'fmt': '{days}d:{hours}h:{mins}m',
                'sep': ':'
            },
            'icons': [' ', 'Up '],
        },

        'cpu_usage': {
            'name': 'cpu_usage',
            'func': field_funcs.get_cpu_usage,
            'interval': 2,
            'threaded': True,
            'icons': [' ', 'CPU '],
        },

        'cpu_temp': {
            'name': 'cpu_temp',
            'func': field_funcs.get_cpu_temp,
            'interval': 5,
            'threaded': True,
            'icons': [' ', ''],
        },

        'mem_usage': {
            'name': 'mem_usage',
            'func': field_funcs.get_mem_usage,
            'interval': 5,
            'icons': [' ', 'Mem '],
        },

        'disk_usage': {
            'name': 'disk_usage',
            'func': field_funcs.get_disk_usage,
            'interval': 4,
            'icons': [' ', '/:'],
        },

        'battery': {
            'name': 'battery',
            'func': field_funcs.get_battery_info,
            'threaded': True,
            'icons': [' ', 'Bat '],
        },

        'net_stats': {
            'name': 'net_stats',
            'func': field_funcs.get_net_stats,
            'interval': 4,
            'threaded': True,
            'icons': [' ', ''],
        },

        'datetime': {
            'name': 'datetime',
            'func': field_funcs.get_datetime,
            'align_to_seconds': True,
            'timely': True,
            'kwargs': {
                'fmt': "%Y-%m-%d %H:%M:%S"
            },
        }

    }

    def __init__(
        self,
        *,
        name: FieldName = None,
        func: Callable[P, str] = None,
        icon: str = '',
        template: FormatStr = None,
        interval: float = 1.0,
        align_to_seconds: bool = False,
        timely: bool = False,
        overrides_refresh: bool = False,
        threaded: bool = False,
        always_show_icon: bool = False,
        run_once: bool = False,
        constant_output: str = None,
        bar: Bar_T = None,
        args: Args = None,
        kwargs: Kwargs = None,
        setup: Callable[P, P.kwargs] = None,

        # Set this to use different icons for different output streams:
        icons: Sequence[PTY_Icon, TTY_Icon] = None,
    ) -> None:

        if constant_output is None:
            #NOTE: This will change when dynamic icons and templates are implemented.
            if func is None:
                raise IncompatibleArgsError(
                    f"Either a function that returns a string or "
                    f"a constant output string is required."
                )
            if not callable(func):
                raise TypeError(
                    f"Type of 'func' must be callable, not {type(func)}"
                )

        if name is None and callable(func):
            name = func.__name__
        self.name = name

        self._func = func
        self.args = () if args is None else args
        self.kwargs = {} if kwargs is None else kwargs

        if setup is not None and not callable(setup):
            # `setup` was given but is of the wrong type.
            raise TypeError(
                f"Type of 'setup' must be callable, not {type(setup)}"
            )
        self._setupfunc = setup

        if icons is None:
            icons = (icon, icon)
        self._icons = icons

        if template is None and icons is None:
            raise IncompatibleArgsError(
                "An icon is required when `template` is None."
            )
        self.template = template

        self.is_async = asyncio.iscoroutinefunction(func)

        if self.is_async or threaded or timely:
            self._callback = func
        else:
            # Wrap synchronous functions if they aren't special:
            self._callback = self._asyncify

        self._bar = bar

        self.timely = utils.str_to_bool(timely)
        self.align_to_seconds = utils.str_to_bool(align_to_seconds)
        self.always_show_icon = utils.str_to_bool(always_show_icon)
        self._buffer = None
        self.constant_output = constant_output
        self.interval = float(interval)
        self.overrides_refresh = utils.str_to_bool(overrides_refresh)
        self.run_once = utils.str_to_bool(run_once)

        self.threaded = utils.str_to_bool(threaded)
        self._do_setup()

    def __repr__(self) -> str:
        cls = type(self).__name__
        name = self.name
        # attrs = utils.join_options(...)
        return f"{cls}({name=})"

    def __eq__(self, other: Field) -> bool:
        if not all(
            getattr(self, attr) == getattr(other, attr)
            for attr in (
                'align_to_seconds',
                'always_show_icon',
                'constant_output',
                'template',
                '_icons',
            )
        ):
            return False

        if self._func is None:
            if self.constant_output == other.constant_output:
                return True
        elif (
            self._func is other._func
            and self.args == other.args
            and self.kwargs == other.kwargs
        ):
            return True
        return False

    @classmethod
    def from_default(
        cls: Field,
        name: str,
        *,
        overrides: FieldSpec = {},
        source: dict[FieldName, FieldSpec] = None,
        fmt_sig: FormatStr = None
    ) -> Field:
        '''Quickly get a default Field and customize its parameters.

        :param name: Name of the default :class:`Field` to access or customize
        :type name: :class:`str`

        :param overrides: Custom parameters that override those of the default Field
        :type overrides: :class:`_types.FieldSpec`, optional

        :param source: The :class:`dict` in which to look up default fields,
            defaults to :attr:`Field._default_fields`
        :type source: dict[:class:`_types.FieldName`, :class:`_types.FieldSpec`]

        :returns: A new :class:`Field`
        :rtype: :class:`Field`
        :raises: :exc:`errors.DefaultFieldNotFoundError` when `source` does not contain `name`
        '''
        if source is None:
            source = cls._default_fields

        try:
            default: FieldSpec = source[name].copy()
        except KeyError:
            raise DefaultFieldNotFoundError(
                f"{name!r} is not the name of a default Field."
            ) from None

        if 'kwargs' in overrides and 'kwargs' in default:
            # default['kwargs'].update(overrides['kwargs'])
            # default['kwargs'] |= overrides['kwargs']
            overrides['kwargs'] = default['kwargs'] | overrides['kwargs']

        spec = default | overrides
        field = cls(**spec)
        field._fmt_sig = fmt_sig
        return field

    @classmethod
    def from_format_string(cls, fmt: FormatStr) -> Field:
        '''
        Get a :class:`Field` from a curly-brace field in a format string.

        :param template: The format string to convert
        :type template: :class`FormatStr`
        '''
        sig = FormatterFieldSig.from_str(fmt)
        field = cls.from_default(sig.name)
        field._fmtsig = fmt
        return field

    @property
    def icon(self) -> str:
        '''The field icon as determined by the output stream of its bar.
        It defaults to the TTY icon (:attr:`self._icons[1]`) if no bar is set.
        '''
        if self._bar is None:
            return self._icons[1]  # Default to using the terminal icon.
        return self._icons[self._bar._stream.isatty()]

    async def _asyncify(self, *args, **kwargs) -> str:
        '''Wrap a synchronous function in a coroutine for simplicity.'''
        return self._func(*args, **kwargs)

    @staticmethod
    def _format_contents(
        text: str,
        icon: str,
        template: FormatStr = None,
        always_show_icon: bool = False
    ) -> str:
        '''A helper function that formats field contents.'''
        if template is None:
            if always_show_icon or text:
                return icon + text
            else:
                return text
        else:
            return template.format(text, icon=icon)

    def _auto_format(self, text: str) -> 'Contents':
        '''Non-staticmethod _format_contents...'''
        if self.template is None:
            if self.always_show_icon or text:
                return self.icon + text
            else:
                return text
        else:
            return self.template.format(text, icon=self.icon)

    def as_generator(self, once: bool = False) :
        yield self._func

    def _do_setup(self, args: Args = None, kwargs: Kwargs = None) -> None:
        # Use the pre-defined _setupfunc() to gather constant variables
        # for func() which might only be evaluated at runtime:
        if self._setupfunc is None:
            return

        if args is None:
            args = self.args
        if kwargs is None:
            kwargs = self.kwargs

        try:
            if asyncio.iscoroutinefunction(self._setupfunc):
                setupvars = asyncio.run(
                    self._setupfunc(*self.args, **self.kwargs)
                )
            else:
                setupvars = self._setupfunc(*self.args, **self.kwargs)

        # If _setupfunc raises FailedSetup with a backup value,
        # use it as the field's new constant_output:
        except FailedSetup as e:
            backup = e.backup
            self.constant_output = self._auto_format(backup)
            return

        # On success, give new values to kwargs to pass to _func().
        # return setupvars
        kwargs['setupvars'] = setupvars


##    # For threaded fields, still run continuously!!!

    def sync_run(self, once: bool = None) -> 'Contents':
        # Do not run fields which have a constant output;
        # only set their bar buffer.
        if self.constant_output is not None:
            return self._auto_format(self.constant_output)

        if self.is_async:
            result = asyncio.run(self._func(*self.args, **self.kwargs))
        else:
            result = self._func(*self.args, **self.kwargs)
        contents = self._auto_format(result)

        return contents

    def gen_run(self, once: bool = None) -> 'Contents':
        # Do not run fields which have a constant output;
        # only set their bar buffer.
        if self.constant_output is not None:
            return self._auto_format(self.constant_output)

        while True:
            if self.is_async:
                result = self._func(*self.args, **self.kwargs)
            else:
                result = asyncio.run(self._func(*self.args, **self.kwargs))
            contents = self._auto_format(result)

            yield contents

    async def run(self, bar: Bar_T, once: bool) -> None:
        '''
        Run an async :class:`Field` callback and send its output to a
        status bar.

        :param bar: Send results to this status bar
        :type bar: :class:`Bar`

        :param once: Run the Field function once
        :type once: :class:`bool`
        '''
        self._check_bar(bar)
        # Do not run fields which have a constant output;
        # only set their bar buffer.
        if self.constant_output is not None:
            contents = self._format_contents(
                self.constant_output,
                self.icon,
                self.template,
                self.always_show_icon
            )
            bar._buffers[self.name] = contents
            return

        func = self._callback
        running = bar._can_run.is_set
        clock = time.monotonic
        using_format_str = (self.template is not None)
        last_val = None

        # Use the pre-defined _setupfunc() to gather constant variables
        # for func() which might only be evaluated at runtime:
        if self._setupfunc is not None:
            try:
                if asyncio.iscoroutinefunction(self._setupfunc):
                    setupvars = (
                        await self._setupfunc(*self.args, **self.kwargs)
                    )
                else:
                    setupvars = self._setupfunc(*self.args, **self.kwargs)

            # If _setupfunc raises FailedSetup with a backup value,
            # use it as the field's new constant_output and update the
            # bar's buffer:
            except FailedSetup as e:
                backup = e.backup
                contents = self._format_contents(
                    backup,
                    self.icon,
                    self.template,
                    self.always_show_icon
                )
                self.constant_output = contents
                bar._buffers[self.name] = str(contents)
                return

            # On success, give new values to kwargs to pass to func().
            self.kwargs['setupvars'] = setupvars

        # Run at least once at the start to ensure bars have contents:
        result = await func(*self.args, **self.kwargs)
        last_val = result
        contents = self._auto_format(result)
        bar._buffers[self.name] = contents

        if self.run_once or once:
            return

        if self.align_to_seconds:
            # Sleep until the beginning of the next second.
            clock = time.time
            await asyncio.sleep(1 - (clock() % 1))
        start_time = clock()

        # The main loop:
        while running():
            result = await func(*self.args, **self.kwargs)
            # Latency from nonzero execution times causes drift, where
            # sleeps become out-of-sync and the bar skips field updates.
            # This is especially noticeable in fields that update
            # routinely, such as the time.

            # To negate drift, when sleeping until the beginning of the
            # next cycle, we must also compensate for latency.
            await asyncio.sleep(
                # Time until next refresh:
                self.interval - (
                    # Get the current latency, which can vary:
                    clock() % self.interval
                    # (clock() - start_time) % self.interval  # Preserve offset
                )
            )

            if result == last_val:
                continue
            last_val = result

            if using_format_str:
                contents = self.template.format(result, icon=self.icon)
            else:
                if self.always_show_icon or result:
                    contents = self.icon + result
                else:
                    contents = result

            bar._buffers[self.name] = contents

            # Send new field contents to the bar's override queue and print a
            # new line between refresh cycles.
            if self.overrides_refresh:
                try:
                    bar._override_queue.put_nowait((self.name, contents))

                except asyncio.QueueFull:
                    # Since the bar buffer was just updated, do nothing if the
                    # queue is full. The update may still show while the queue
                    # handles the current override.
                    # If not, the line will update at the next refresh cycle.
                    pass

    def run_threaded(self, bar: Bar_T, once: bool) -> None:
        '''
        Run a blocking :class:`Field` func and send its output to a
        status bar.

        :param bar: Send results to this status bar
        :type bar: :class:`Bar`

        :param once: Run the Field function once
        :type once: :class:`bool`
        '''
        self._check_bar(bar)

        # Do not run fields which have a constant output;
        # only set their bar buffer.
        if self.constant_output is not None:
            contents = self._format_contents(
                self.constant_output,
                self.icon,
                self.template,
                self.always_show_icon
            )
            bar._buffers[self.name] = contents
            return

        func = self._callback
        running = bar._can_run.is_set
        clock = time.monotonic
        using_format_str = (self.template is not None)
        last_val = None

        # If the field's callback is asynchronous,
        # it must be run in a new event loop.
        local_loop = asyncio.new_event_loop()

        # Use the pre-defined _setupfunc() to gather constant variables
        # for func() which might only be evaluated at runtime:
        if self._setupfunc is not None:
            try:
                if asyncio.iscoroutinefunction(self._setupfunc):
                    setupvars = local_loop.run_until_complete(
                        self._setupfunc(*self.args, **self.kwargs)
                    )
                else:
                    setupvars = self._setupfunc(*self.args, **self.kwargs)

            # If _setupfunc raises FailedSetup with a backup value,
            # use it as the field's new constant_output and update the
            # bar buffer:
            except FailedSetup as e:
                backup = e.args[0]
                contents = self._format_contents(
                    backup,
                    self.icon,
                    self.template,
                    self.always_show_icon
                )
                self.constant_output = contents
                bar._buffers[self.name] = str(contents)
                return

            # On success, give new values to kwargs to pass to func().
            self.kwargs['setupvars'] = setupvars

        # Run at least once at the start to ensure bar is not empty:
        if self.is_async:
            result = local_loop.run_until_complete(
                func(*self.args, **self.kwargs)
            )
        else:
            result = func(*self.args, **self.kwargs)
        last_val = result
        contents = self._format_contents(
            result,
            self.icon,
            self.template,
            self.always_show_icon
        )
        bar._buffers[self.name] = contents

        if self.run_once or once:
            local_loop.stop()
            local_loop.close()
            bar._threads.pop(self.name)  # Eventually, id(self)
            return

        step = bar._thread_cooldown
        needed = round(self.interval / step)
        count = 0
        first_cycle = True

        if self.align_to_seconds:
            # Sleep until the beginning of the next second.
            clock = time.time
            time.sleep(1 - (clock() % 1))

        start_time = clock()
        while running():

            # Sleep until the next refresh cycle in little steps to
            # check if the bar has stopped.
            if count < needed and not first_cycle:
                count += 1

                # Latency from nonzero execution times causes drift,
                # where sleeps become out-of-sync and the bar skips
                # field updates.
                # This is especially noticeable in fields that update
                # routinely, such as the time.

                # To negate drift, when sleeping until the beginning of
                # the next cycle, we must also compensate for latency.
                time.sleep(
                    step - (
                        # Get the current latency, which can vary:
                        clock() % step
                        # (clock() - start_time) % step To preserve offset
                    )
                )
                continue

            count = 0
            if first_cycle:
                first_cycle = False

            if self.is_async:
                result = local_loop.run_until_complete(
                    func(*self.args, **self.kwargs)
                )
            else:
                result = func(*self.args, **self.kwargs)

            if result == last_val:
                continue
            last_val = result

            if using_format_str:
                contents = self.template.format(result, icon=self.icon)
            else:
                if self.always_show_icon or result:
                    contents = self.icon + result
                else:
                    contents = result

            bar._buffers[self.name] = contents

            # Send new field contents to the bar's override queue and print a
            # new line between refresh cycles.
            if self.overrides_refresh:
                try:
                    bar._override_queue._loop.call_soon_threadsafe(
                        bar._override_queue.put_nowait, (self.name, contents)
                    )

                except asyncio.QueueFull:
                    # Since the bar buffer was just updated, do nothing if the
                    # queue is full. The update may still show while the queue
                    # handles the current override.
                    # If not, the line will update at the next refresh cycle.
                    pass

        local_loop.stop()
        local_loop.close()

    @staticmethod
    def _check_bar(
        bar: Bar_T,
        raise_on_fail: bool = True
    ) -> NoReturn | bool:
        '''
        Check if a bar has the right attributes to use a run() function.
        If these attributes are missing,
            return ``False`` if `raise_on_fail` is ``True``,
            or raise :exc:`InvalidBarError` if `raise_on_fail` is ``False``.

        :param bar: The status bar object to test
        :type bar: :class:`Bar`

        :param raise_on_fail: Raise an exception if `bar` fails the check,
            defaults to ``False``
        :type raise_on_fail: :class:`bool`

        :raises: :exc:`InvalidBarError` if the bar fails
            :func:`_check_bar()` and lacks required attributes
        '''
        required_attrs = (
            '_buffers',
            '_can_run',
            '_override_queue',
            '_stream',
        )
        if any(not hasattr(bar, a) for a in required_attrs):
            if no_error:
                return False
            raise InvalidBarError(
                f"Status bar {bar!r} is missing certain attributes"
                f" required to run `Field.run()`"
                f" and `Field.run_threaded()`."
            ) from None
        return True

    def make_thread(self, bar: Bar_T, run_once: bool) -> None:
        '''
        Return a thread that runs the :class:`Field`'s callback.

        :param bar: Send results to this status bar
        :type bar: :class:`Bar`

        :param once: Run the Field function once
        :type once: :class:`bool`
        '''
        thread = threading.Thread(
            target=self.run_threaded,
            args=(bar, run_once),
            name=self.name  # #NOTE Eventually, id(self)
        )
        return thread


FieldPrecursor: TypeAlias = FieldName | Field | FormatterFieldSig
from . import _types
_types.FieldPrecursor = FieldPrecursor

