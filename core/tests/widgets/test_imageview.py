from pathlib import Path
from unittest.mock import ANY

import pytest
from travertino.size import at_least

import toga
from toga.style.pack import Pack
from toga.widgets.imageview import rehint_imageview
from toga_dummy.utils import (
    assert_action_not_performed,
    assert_action_performed,
    assert_action_performed_with,
)


@pytest.fixture
def app():
    return toga.App("ImageView Test", "org.beeware.toga.widgets.imageview")


@pytest.fixture
def widget(app):
    return toga.ImageView()


def test_widget_created(widget):
    "A empty ImageView can be created"

    # interface/impl round trips
    assert widget._impl.interface is widget
    assert_action_performed(widget, "create ImageView")
    assert_action_performed_with(widget, "set image", image=None)
    assert_action_performed(widget, "refresh")

    assert widget.image is None


def test_widget_created_with_args(app):
    "An ImageView can be created with argumentgs"
    image = toga.Image(Path("resources") / "toga.png")
    widget = toga.ImageView(image=image)

    # interface/impl round trips
    assert widget._impl.interface is widget
    assert_action_performed(widget, "create ImageView")
    assert_action_performed_with(widget, "set image", image=image)
    assert_action_performed(widget, "refresh")

    # Image attribute is set
    assert widget.image == image


def test_disable_no_op(widget):
    "ImageView doesn't have a disabled state"

    # Enabled by default
    assert widget.enabled

    # Try to disable the widget
    widget.enabled = False

    # Still enabled.
    assert widget.enabled


def test_focus_noop(widget):
    "Focus is a no-op."

    widget.focus()
    assert_action_not_performed(widget, "focus")


def test_set_image_str(widget):
    "The image can be set with a string"
    widget.image = "resources/toga.png"
    assert_action_performed_with(widget, "set image", image=ANY)
    assert_action_performed(widget, "refresh")

    assert isinstance(widget.image, toga.Image)
    assert widget.image.path == Path(toga.__file__).parent / "resources" / "toga.png"


def test_set_image_path(widget):
    "The image can be set with a Path"
    widget.image = Path("resources") / "toga.png"
    assert_action_performed_with(widget, "set image", image=ANY)
    assert_action_performed(widget, "refresh")

    assert isinstance(widget.image, toga.Image)
    assert widget.image.path == Path(toga.__file__).parent / "resources" / "toga.png"


def test_set_image(widget):
    "The image can be set with an Image instance"
    image = toga.Image(Path("resources") / "toga.png")

    widget.image = image
    assert_action_performed_with(widget, "set image", image=image)
    assert_action_performed(widget, "refresh")

    assert widget.image == image


def test_set_image_none(app):
    "The image can be cleared"
    widget = toga.ImageView(image="resources/toga.png")
    assert widget.image is not None

    widget.image = None
    assert_action_performed_with(widget, "set image", image=None)
    assert_action_performed(widget, "refresh")

    assert widget.image is None


@pytest.mark.parametrize(
    "params, expected_width, expected_height, expected_preserve_aspect_ratio",
    [
        # Intrinsic image size
        (dict(style=Pack()), 60, 40, True),
        (dict(style=Pack(), scale=2), 120, 80, True),
        # Fixed width
        (dict(style=Pack(width=150)), 150, 100, True),
        (dict(style=Pack(width=150), scale=2), 300, 200, True),
        # Fixed height
        (dict(style=Pack(height=80)), 120, 80, True),
        (dict(style=Pack(height=80), scale=2), 240, 160, True),
        # Explicit image size
        (dict(style=Pack(width=37, height=42)), 37, 42, False),
        (dict(style=Pack(width=37, height=42), scale=2), 74, 84, False),
        # Intrinsic image size, flex widget
        (dict(style=Pack(flex=1)), at_least(60), at_least(40), True),
        (dict(style=Pack(flex=1), scale=2), at_least(120), at_least(80), True),
        # Fixed width, flex widget
        (dict(style=Pack(width=150, flex=1)), 150, at_least(100), True),
        (dict(style=Pack(width=150, flex=1), scale=2), 300, at_least(200), True),
        # Fixed height, flex widget
        (dict(style=Pack(height=80, flex=1)), at_least(120), 80, True),
        (dict(style=Pack(height=80, flex=1), scale=2), at_least(240), 160, True),
        # Explicit image size, flex widget
        (dict(style=Pack(width=37, height=42, flex=1)), 37, 42, False),
        (dict(style=Pack(width=37, height=42, flex=1), scale=2), 74, 84, False),
    ],
)
def test_rehint_image(
    app,
    params,
    expected_width,
    expected_height,
    expected_preserve_aspect_ratio,
):
    image = toga.Image(path="resources/toga.png")

    width, height, preserve_aspect_ratio = rehint_imageview(image=image, **params)
    assert width == expected_width
    assert height == expected_height
    assert preserve_aspect_ratio == expected_preserve_aspect_ratio


@pytest.mark.parametrize(
    "params",
    [
        # Default scale
        dict(style=Pack()),
        # Explicit width/height
        dict(style=Pack(width=100)),
        dict(style=Pack(height=200)),
        dict(style=Pack(width=100, height=200)),
        # 2x Scale
        dict(style=Pack(), scale=2),
    ],
)
def test_rehint_empty_image(params):
    width, height, preserve_aspect_ratio = rehint_imageview(image=None, **params)
    assert width == 0
    assert height == 0
    assert not preserve_aspect_ratio
