import asyncio
import re
import sys
import threading
from ctypes import windll

import System.Windows.Forms as WinForms
from System import Environment, Threading
from System.ComponentModel import InvalidEnumArgumentException
from System.Media import SystemSounds
from System.Net import SecurityProtocolType, ServicePointManager
from System.Windows.Threading import Dispatcher

import toga
from toga import Key
from toga.command import Separator

from .keys import toga_to_winforms_key
from .libs.proactor import WinformsProactorEventLoop
from .libs.wrapper import WeakrefCallable
from .window import Window


class MainWindow(Window):
    def winforms_FormClosing(self, sender, event):
        # Differentiate between the handling that occurs when the user
        # requests the app to exit, and the actual application exiting.
        if not self.interface.app._impl._is_exiting:  # pragma: no branch
            # If there's an event handler, process it. The decision to
            # actually exit the app will be processed in the on_exit handler.
            # If there's no exit handler, assume the close/exit can proceed.
            self.interface.app.on_exit()
            event.Cancel = True


class App:
    _MAIN_WINDOW_CLASS = MainWindow

    def __init__(self, interface):
        self.interface = interface
        self.interface._impl = self

        # Winforms app exit is tightly bound to the close of the MainWindow.
        # The FormClosing message on MainWindow triggers the "on_exit" handler
        # (which might abort the exit). However, on success, it will request the
        # app (and thus the Main Window) to close, causing another close event.
        # So - we have a flag that is only ever sent once a request has been
        # made to exit the native app. This flag can be used to shortcut any
        # window-level close handling.
        self._is_exiting = False

        # Winforms cursor visibility is a stack; If you call hide N times, you
        # need to call Show N times to make the cursor re-appear. Store a local
        # boolean to allow us to avoid building a deep stack.
        self._cursor_visible = True

        self.loop = WinformsProactorEventLoop()
        asyncio.set_event_loop(self.loop)

    def create(self):
        self.native = WinForms.Application
        self.app_context = WinForms.ApplicationContext()
        self.app_dispatcher = Dispatcher.CurrentDispatcher

        # Check the version of windows and make sure we are setting the DPI mode
        # with the most up to date API
        # Windows Versioning Check Sources : https://www.lifewire.com/windows-version-numbers-2625171
        # and https://docs.microsoft.com/en-us/windows/release-information/
        win_version = Environment.OSVersion.Version
        if win_version.Major >= 6:  # Checks for Windows Vista or later
            # Represents Windows 8.1 up to Windows 10 before Build 1703 which should use
            # SetProcessDpiAwareness(True)
            if (win_version.Major == 6 and win_version.Minor == 3) or (
                win_version.Major == 10 and win_version.Build < 15063
            ):  # pragma: no cover
                windll.shcore.SetProcessDpiAwareness(True)
                print(
                    "WARNING: Your Windows version doesn't support DPI-independent rendering.  "
                    "We recommend you upgrade to at least Windows 10 Build 1703."
                )
            # Represents Windows 10 Build 1703 and beyond which should use
            # SetProcessDpiAwarenessContext(-2)
            elif win_version.Major == 10 and win_version.Build >= 15063:
                windll.user32.SetProcessDpiAwarenessContext(-2)
            # Any other version of windows should use SetProcessDPIAware()
            else:  # pragma: no cover
                windll.user32.SetProcessDPIAware()

        self.native.EnableVisualStyles()
        self.native.SetCompatibleTextRenderingDefault(False)

        # Ensure that TLS1.2 and TLS1.3 are enabled for HTTPS connections.
        # For some reason, some Windows installs have these protocols
        # turned off by default. SSL3, TLS1.0 and TLS1.1 are *not* enabled
        # as they are deprecated protocols and their use should *not* be
        # encouraged.
        try:
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12
        except AttributeError:  # pragma: no cover
            print(
                "WARNING: Your Windows .NET install does not support TLS1.2. "
                "You may experience difficulties accessing some web server content."
            )
        try:
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls13
        except AttributeError:  # pragma: no cover
            print(
                "WARNING: Your Windows .NET install does not support TLS1.3. "
                "You may experience difficulties accessing some web server content."
            )

        # The winforms App impl's create() is deferred so that it can run inside
        # the GUI thread. This means the on_change handler for commands has already
        # been installed - even though we haven't added any commands yet. Temporarily
        # suspend on_change events so we can create all the commands. This will call
        # create_menus when when context exits.
        with self.interface.commands.suspend_updates():
            # Call user code to populate the main window
            self.interface._startup()
            self.create_app_commands()

            self._menu_groups = {}
            self._status_indicators = {}

    def _reset_menubar(self):
        if self.interface.main_window is None:  # pragma: no branch
            # The startup method may create commands before creating the window, so
            # we'll call create_menus again after it returns.
            return

        window = self.interface.main_window._impl
        menubar = window.native.MainMenuStrip
        if menubar:
            menubar.Items.Clear()
        else:
            # The menu bar doesn't need to be positioned, because its `Dock` property
            # defaults to `Top`.
            menubar = WinForms.MenuStrip()
            window.native.Controls.Add(menubar)
            window.native.MainMenuStrip = menubar
            menubar.SendToBack()  # In a dock, "back" means "top".

        return menubar

    def create_menus(self):
        # Reset the menubar.
        menubar = self._reset_menubar()

        # Reset the status indicators. Any existing indicators will be made invisible
        for _, item in self._status_indicators.items():
            item.Visible = False
            item.Dispose()

        self._menu_groups = {}
        self._status_indicators = {}

        submenu = None
        for cmd in self.interface.commands:
            submenu = self._submenu(cmd.group, menubar)
            if isinstance(cmd, Separator):
                if cmd.group.root.is_status_item:
                    submenu.MenuItems.Add("-")
                else:
                    submenu.DropDownItems.Add("-")
            else:
                # Items inside a Notify Icon are MenuItems; in a menubar,
                # they're ToolStripMenuItems
                if cmd.group.root.is_status_item:
                    item = WinForms.MenuItem(cmd.text)
                else:
                    item = WinForms.ToolStripMenuItem(cmd.text)

                item.Click += WeakrefCallable(cmd._impl.winforms_Click)
                if cmd.shortcut is not None:
                    try:
                        item.ShortcutKeys = toga_to_winforms_key(cmd.shortcut)
                    except (
                        ValueError,
                        InvalidEnumArgumentException,
                    ) as e:  # pragma: no cover
                        # Make this a non-fatal warning, because different backends may
                        # accept different shortcuts.
                        print(f"WARNING: invalid shortcut {cmd.shortcut!r}: {e}")

                item.Enabled = cmd.enabled

                cmd._impl.native.append(item)

                # Items inside a Notify Icon are added to MenuItems; in a
                # menubar, they're added to DropDownItems.
                if cmd.group.root.is_status_item:
                    submenu.MenuItems.Add(item)
                else:
                    submenu.DropDownItems.Add(item)

        self._resize_menubar()

    def _resize_menubar(self):
        self.interface.main_window._impl.resize_content()

    def _submenu(self, group, menubar):
        try:
            return self._menu_groups[group]
        except KeyError:
            if group is None:
                submenu = menubar
            elif group.is_status_item:
                submenu = WinForms.ContextMenu()

                notify_icon = WinForms.NotifyIcon()
                notify_icon.Icon = (
                    group.icon._impl.native
                    if group.icon
                    else self.interface.icon._impl.native
                )
                notify_icon.ContextMenu = submenu
                notify_icon.label = group.text
                notify_icon.Visible = True

                self._status_indicators[group] = notify_icon
            else:
                parent_menu = self._submenu(group.parent, menubar)

                # If the group is a top level menu, create a ToolStripMenuItem
                # and it to the menubar. If it's inside a NotifyIcon,
                # create a MenuItem, and add it there; otherwise, it's a
                # normal submenu, so it's added as a DropDownItem.
                if group.parent is None:
                    submenu = WinForms.ToolStripMenuItem(group.text)
                    # If there's no menubar, don't add it. This will happen
                    # if it's a windowless app.
                    if parent_menu:
                        parent_menu.Items.Add(submenu)
                elif group.root.is_status_item:
                    submenu = WinForms.MenuItem(group.text)
                    parent_menu.MenuItems.Add(submenu)
                else:
                    submenu = WinForms.ToolStripMenuItem(group.text)
                    parent_menu.DropDownItems.Add(submenu)

            self._menu_groups[group] = submenu
        return submenu

    def create_app_commands(self):
        self.interface.commands.add(
            # About should be the last item in the Help menu, in a section on its own.
            toga.Command(
                self._menu_about,
                f"About {self.interface.formal_name}",
                group=toga.Group.HELP,
                section=sys.maxsize,
            ),
            #
            toga.Command(None, "Preferences", group=toga.Group.FILE),
            #
            # On Windows, the Exit command doesn't usually contain the app name. It
            # should be the last item in the File menu, in a section on its own.
            toga.Command(
                self._menu_exit,
                "Exit",
                shortcut=Key.MOD_1 + "q",
                group=toga.Group.FILE,
                section=sys.maxsize,
            ),
            #
            toga.Command(
                self._menu_visit_homepage,
                "Visit homepage",
                enabled=self.interface.home_page is not None,
                group=toga.Group.HELP,
            ),
        )

        # The first status item group (by group ordering) gets the app control
        # commands. The app control commands always form the last 2 sections in
        # the group.
        try:
            main_status_item = sorted(
                {
                    item.group
                    for item in self.interface.commands
                    if not isinstance(item, Separator) and item.group.is_status_item
                }
            )[0]
        except IndexError:
            pass
        else:
            self.interface.commands.add(
                toga.Command(
                    self._menu_about,
                    f"About {self.interface.formal_name}",
                    group=main_status_item,
                    section=sys.maxsize - 1,
                ),
                toga.Command(
                    self._menu_visit_homepage,
                    "Visit homepage",
                    enabled=self.interface.home_page is not None,
                    group=main_status_item,
                    section=sys.maxsize - 1,
                ),
                # Quit should always be the last item, in a section on its own
                toga.Command(
                    self._menu_exit,
                    "Exit",
                    group=main_status_item,
                    section=sys.maxsize,
                ),
            )

    def _menu_about(self, widget, **kwargs):
        self.interface.about()

    def _menu_exit(self, widget, **kwargs):
        self.interface.on_exit()

    def _menu_visit_homepage(self, widget, **kwargs):
        self.interface.visit_homepage()

    def winforms_thread_exception(self, sender, winforms_exc):  # pragma: no cover
        # The PythonException returned by Winforms doesn't give us
        # easy access to the underlying Python stacktrace; so we
        # reconstruct it from the string message.
        # The Python message is helpfully included in square brackets,
        # as the context for the first line in the .net stack trace.
        # So, look for the closing bracket and the start of the Python.net
        # stack trace. Then, reconstruct the line breaks internal to the
        # remaining string.
        print("Traceback (most recent call last):")
        py_exc = winforms_exc.get_Exception()
        full_stack_trace = py_exc.StackTrace
        regex = re.compile(
            r"^\[(?:'(.*?)', )*(?:'(.*?)')\]   (?:.*?) Python\.Runtime",
            re.DOTALL | re.UNICODE,
        )

        stacktrace_relevant_lines = regex.findall(full_stack_trace)
        if len(stacktrace_relevant_lines) == 0:
            self.print_stack_trace(full_stack_trace)
        else:
            for lines in stacktrace_relevant_lines:
                for line in lines:
                    self.print_stack_trace(line)
        print(py_exc.Message)

    @classmethod
    def print_stack_trace(cls, stack_trace_line):  # pragma: no cover
        for level in stack_trace_line.split("', '"):
            for line in level.split("\\n"):
                if line:
                    print(line)

    def run_app(self):  # pragma: no cover
        # Enable coverage tracing on this non-Python-created thread
        # (https://github.com/nedbat/coveragepy/issues/686).
        if threading._trace_hook:
            sys.settrace(threading._trace_hook)

        try:
            self.create()

            # This catches errors in handlers, and prints them
            # in a usable form.
            self.native.ThreadException += WeakrefCallable(
                self.winforms_thread_exception
            )

            self.loop.run_forever(self)
        except Exception as e:
            # In case of an unhandled error at the level of the app,
            # preserve the Python stacktrace
            self._exception = e
        else:
            self._exception = None

    def main_loop(self):
        thread = Threading.Thread(Threading.ThreadStart(self.run_app))
        thread.SetApartmentState(Threading.ApartmentState.STA)
        thread.Start()
        thread.Join()

        # If the thread has exited, the _exception attribute will exist.
        # If it's non-None, raise it, as it indicates the underlying
        # app thread had a problem; this is effectibely a re-raise over
        # a thread boundary.
        if self._exception:  # pragma: no cover
            raise self._exception

    def show_about_dialog(self):
        message_parts = []
        if self.interface.version is not None:
            message_parts.append(
                f"{self.interface.formal_name} v{self.interface.version}"
            )
        else:
            message_parts.append(self.interface.formal_name)

        if self.interface.author is not None:
            message_parts.append(f"Author: {self.interface.author}")
        if self.interface.description is not None:
            message_parts.append(f"\n{self.interface.description}")
        self.interface.main_window.info_dialog(
            f"About {self.interface.formal_name}", "\n".join(message_parts)
        )

    def beep(self):
        SystemSounds.Beep.Play()

    def exit(self):  # pragma: no cover
        self._is_exiting = True
        self.native.Exit()

    def set_main_window(self, window):
        self.app_context.MainForm = window._impl.native

    def get_current_window(self):
        for window in self.interface.windows:
            if WinForms.Form.ActiveForm == window._impl.native:
                return window._impl
        return None

    def set_current_window(self, window):
        window._impl.native.Activate()

    def enter_full_screen(self, windows):
        for window in windows:
            window._impl.set_full_screen(True)

    def exit_full_screen(self, windows):
        for window in windows:
            window._impl.set_full_screen(False)

    def show_cursor(self):
        if not self._cursor_visible:
            WinForms.Cursor.Show()
        self._cursor_visible = True

    def hide_cursor(self):
        if self._cursor_visible:
            WinForms.Cursor.Hide()
        self._cursor_visible = False


class SimpleApp(App):
    def create_app_commands(self):
        pass

    def create_menus(self):
        pass


class WindowlessApp(App):
    def _reset_menubar(self):
        pass

    def _resize_menubar(self):
        pass


class DocumentApp(App):  # pragma: no cover
    def create_app_commands(self):
        super().create_app_commands()
        self.interface.commands.add(
            toga.Command(
                lambda w: self.open_file,
                text="Open...",
                shortcut=Key.MOD_1 + "o",
                group=toga.Group.FILE,
                section=0,
            ),
        )
