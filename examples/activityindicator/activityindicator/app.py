import toga
from toga.constants import CENTER, ROW
from toga.style import Pack


class ExampleActivityIndicatorApp(toga.App):
    # Button callback functions
    def do_stuff(self, widget, **kwargs):
        if self.spinner.is_running:
            self.spinner.stop()
            self.button.text = "Start"
        else:
            self.spinner.start()
            self.button.text = "Stop"

    def startup(self):
        # Set up main window
        self.main_window = toga.MainWindow()

        self.spinner = toga.ActivityIndicator(style=Pack(margin_left=10))
        self.button = toga.Button(
            "Start", on_press=self.do_stuff, style=Pack(margin_right=10)
        )

        box = toga.Box(
            children=[self.button, self.spinner],
            style=Pack(direction=ROW, height=20, margin=20, align_items=CENTER, flex=1),
        )

        # Add the content on the main window
        self.main_window.content = box
        self.main_window.size = (200, 200)

        # Show the main window
        self.main_window.show()


def main():
    return ExampleActivityIndicatorApp(
        "Activity Indicator", "org.beeware.toga.examples.activityindicator"
    )


if __name__ == "__main__":
    app = main()
    app.main_loop()
