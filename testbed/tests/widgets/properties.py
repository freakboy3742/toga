from pytest import approx, fixture

import toga
from toga.colors import CORNFLOWERBLUE, RED, TRANSPARENT, color as named_color
from toga.fonts import BOLD, FANTASY, ITALIC, NORMAL, SERIF, SYSTEM
from toga.style.pack import CENTER, COLUMN, JUSTIFY, LEFT, LTR, RIGHT, RTL, TOP

from ..assertions import assert_color
from ..data import COLORS, TEXTS
from .probe import get_probe

# An upper bound for widths
MAX_WIDTH = 2000


@fixture
def verify_font_sizes():
    return True


async def test_enabled(widget, probe):
    "The widget can be enabled and disabled"
    # Widget is initially enabled
    assert widget.enabled
    assert probe.enabled

    # Disable the widget
    widget.enabled = False
    await probe.redraw("Widget should be disabled")

    assert not widget.enabled
    assert not probe.enabled

    # Enable the widget
    widget.enabled = True
    await probe.redraw("Widget should be enabled")

    assert widget.enabled
    assert probe.enabled


async def test_enable_noop(widget, probe):
    "Changing the enabled status on the widget is a no-op"
    # Widget reports as enabled
    assert widget.enabled

    # Attempt to disable the widget
    widget.enabled = False
    await probe.redraw("Widget should be disabled")

    # Widget still reports as enabled
    assert widget.enabled


async def test_focus(widget, probe):
    "The widget can be given focus"
    # Add a separate widget that can take take focus
    other = toga.TextInput()
    widget.parent.add(other)
    other_probe = get_probe(other)

    other.focus()
    await probe.redraw("A separate widget should be given focus")
    assert not probe.has_focus
    assert other_probe.has_focus

    widget.focus()
    await probe.redraw("Widget should be given focus")
    assert probe.has_focus
    assert not other_probe.has_focus


async def test_focus_noop(widget, probe):
    "The widget cannot be given focus"
    # Add a separate widget that can take take focus
    other = toga.TextInput()
    widget.parent.add(other)
    other_probe = get_probe(other)

    other.focus()
    await probe.redraw("A separate widget should be given focus")
    assert not probe.has_focus
    assert other_probe.has_focus

    # Widget has *not* taken focus
    widget.focus()
    await probe.redraw("Widget should be given focus")
    assert not probe.has_focus
    assert other_probe.has_focus


async def test_text(widget, probe):
    "The text displayed on a widget can be changed"
    for text in TEXTS:
        widget.text = text
        await probe.redraw(f"Widget text should be {str(text)!r}")

        assert widget.text == str(text)
        assert probe.text == str(text)


async def test_text_value(widget, probe):
    "The text value displayed on a widget can be changed"
    for text in TEXTS:
        widget.value = text
        await probe.redraw(f"Widget value should be {str(text)!r}")

        assert widget.value == str(text)
        assert probe.value == str(text)


async def test_placeholder(widget, probe):
    "The placeholder displayed by a widget can be changed"
    # Placeholder visibility can be focus dependent, so add another
    # widget that can take take focus
    other = toga.TextInput()
    widget.parent.add(other)
    other.focus()

    # Set a value and a placeholder.
    widget.value = "Hello"
    widget.placeholder = "placeholder"
    await probe.redraw("Widget placeholder should not be visible")

    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    assert not probe.placeholder_visible

    # Clear value, making placeholder visible
    widget.value = None
    await probe.redraw("Widget placeholder should be visible")

    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    assert probe.placeholder_visible

    # Change placeholder while visible
    widget.placeholder = "replacement"
    await probe.redraw("Widget placeholder is now 'replacement'")

    assert widget.placeholder == "replacement"
    assert probe.placeholder == "replacement"
    assert probe.placeholder_visible

    # Give the widget focus; this may hide the placeholder.
    widget.focus()
    await probe.redraw("Widget has focus")
    assert widget.placeholder == "replacement"
    assert probe.placeholder == "replacement"
    if probe.placeholder_hides_on_focus:
        assert not probe.placeholder_visible
    else:
        assert probe.placeholder_visible

    # Give a different widget focus; this will show the placeholder
    other.focus()
    await probe.redraw("Widget has lost focus")
    assert widget.placeholder == "replacement"
    assert probe.placeholder == "replacement"
    assert probe.placeholder_visible

    # Give the widget focus, again
    widget.focus()
    await probe.redraw("Widget has focus; placeholder may not be visible")
    assert widget.placeholder == "replacement"
    assert probe.placeholder == "replacement"
    if probe.placeholder_hides_on_focus:
        assert not probe.placeholder_visible
    else:
        assert probe.placeholder_visible

    # Change the placeholder text while the widget has focus
    widget.placeholder = "placeholder"
    await probe.redraw("Widget placeholder should be 'placeholder'")

    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    if probe.placeholder_hides_on_focus:
        assert not probe.placeholder_visible
    else:
        assert probe.placeholder_visible

    # Give a different widget focus; this will show the placeholder
    other.focus()
    await probe.redraw("Widget has lost focus; placeholder should be visible")
    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    assert probe.placeholder_visible

    # Focus in and out while a value is set.
    widget.value = "example"
    widget.focus()
    await probe.redraw("Widget has focus; placeholder not visible")
    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    assert not probe.placeholder_visible

    other.focus()
    await probe.redraw("Widget has lost focus, placeholder not visible")
    assert widget.placeholder == "placeholder"
    assert probe.placeholder == "placeholder"
    assert not probe.placeholder_visible


async def test_text_width_change(widget, probe):
    "If the widget text is changed, the width of the widget changes"
    orig_width = probe.width

    # Change the text to something long
    widget.text = "Very long example text"
    await probe.redraw("Widget text should be very long")

    # The widget is now wider than it was previously
    assert probe.width > orig_width


async def test_font(widget, probe, verify_font_sizes):
    "The font size and family of a widget can be changed."
    # Capture the original size and font of the widget
    if verify_font_sizes:
        orig_height = probe.height
        orig_width = probe.width
    orig_font = probe.font
    probe.assert_font_family(SYSTEM)

    # Set the font to larger than its original size
    widget.style.font_size = orig_font.size * 3
    await probe.redraw("Widget font should be larger than its original size")

    # Widget has a new font size
    new_size_font = probe.font
    # Font size in points is an integer; however, some platforms
    # perform rendering in pixels (or device independent pixels,
    # so round-tripping points->pixels->points through the probe
    # can result in rounding errors.
    assert (orig_font.size * 2.5) < new_size_font.size < (orig_font.size * 3.5)

    # Widget should be taller and wider
    if verify_font_sizes:
        assert probe.width > orig_width
        assert probe.height > orig_height

    # Change to a different font
    widget.style.font_family = FANTASY
    await probe.redraw("Widget font should be changed to FANTASY")

    # Font family has been changed
    new_family_font = probe.font
    probe.assert_font_family(FANTASY)

    # Font size hasn't changed
    assert new_family_font.size == new_size_font.size
    # Widget should still be taller and wider than the original
    if verify_font_sizes:
        assert probe.width > orig_width
        assert probe.height > orig_height

    # Reset to original family and size.
    del widget.style.font_family
    del widget.style.font_size
    await probe.redraw(
        message="Widget text should be reset to original family and size"
    )
    assert probe.font == orig_font
    if verify_font_sizes:
        assert probe.height == orig_height
        assert probe.width == orig_width


async def test_font_attrs(widget, probe):
    "The font weight and style of a widget can be changed."
    assert probe.font.weight == NORMAL
    assert probe.font.style == NORMAL

    for family in [SYSTEM, SERIF]:
        widget.style.font_family = family
        for weight in [NORMAL, BOLD]:
            widget.style.font_weight = weight
            for style in [NORMAL, ITALIC]:
                widget.style.font_style = style
                await probe.redraw(
                    message="Widget text font style should be %s" % style
                )
                probe.assert_font_family(family)
                assert probe.font.weight == weight
                assert probe.font.style == style


async def test_color(widget, probe):
    "The foreground color of a widget can be changed"
    for color in COLORS:
        widget.style.color = color
        await probe.redraw("Widget text color should be %s" % color)
        assert_color(probe.color, color)


async def test_color_reset(widget, probe):
    "The foreground color of a widget can be reset"
    # Get the original color
    original = probe.color

    # Set the color to something different
    widget.style.color = RED
    await probe.redraw("Widget text color should be RED")
    assert_color(probe.color, named_color(RED))

    # Reset the color, and check that it has been restored to the original
    del widget.style.color
    await probe.redraw("Widget text color should be restored to the original")
    assert_color(probe.color, original)


async def test_background_color(widget, probe):
    "The background color of a widget can be set"
    for color in COLORS:
        widget.style.background_color = color
        await probe.redraw("Widget text background color should be %s" % color)
        assert_color(probe.background_color, color)


async def test_background_color_reset(widget, probe):
    "The background color of a widget can be reset"
    # Get the original background color
    original = probe.background_color

    # Set the background color to something different
    widget.style.background_color = RED
    await probe.redraw("Widget text background color should be RED")
    assert_color(probe.background_color, named_color(RED))

    # Reset the background color, and check that it has been restored to the original
    del widget.style.background_color
    await probe.redraw(
        message="Widget text background color should be restored to original"
    )
    assert_color(probe.background_color, original)


async def test_background_color_transparent(widget, probe):
    "Background transparency is treated as a color reset"
    widget.style.background_color = TRANSPARENT
    await probe.redraw("Widget text background color should be TRANSPARENT")
    assert_color(probe.background_color, TRANSPARENT)


async def test_alignment(widget, probe):
    """Widget honors alignment settings."""
    # Use column alignment to ensure widget uses all available width
    widget.parent.style.direction = COLUMN

    # Initial alignment is LEFT, initial direction is LTR
    await probe.redraw("Label text direction should be LTR")
    probe.assert_alignment(LEFT)

    # Vertical alignment is not affected by horizontal alignment changes.
    vertical_alignment = probe.vertical_alignment

    for alignment in [RIGHT, CENTER, JUSTIFY]:
        widget.style.text_align = alignment
        await probe.redraw("Label text direction should be %s" % alignment)
        probe.assert_alignment(alignment)
        assert probe.vertical_alignment == vertical_alignment

    # Clearing the alignment reverts to default alignment of LEFT
    del widget.style.text_align
    await probe.redraw("Label text direction should be reverted to LEFT")
    probe.assert_alignment(LEFT)

    # If text direction is RTL, default alignment is RIGHT
    widget.style.text_direction = RTL
    await probe.redraw("Label text direction should be RTL")
    probe.assert_alignment(RIGHT)

    # If text direction is expliclty LTR, default alignment is LEFT
    widget.style.text_direction = LTR
    await probe.redraw("Label text direction should be LTR")
    probe.assert_alignment(LEFT)


async def test_vertical_alignment_top(widget, probe):
    """Text is vertically aligned to the top of the widget."""
    assert probe.vertical_alignment == TOP


async def test_flex_widget_size(widget, probe):
    "The widget can expand in either axis."
    # Container is initially a non-flex row widget of fixed size.
    # Paint the background so we can easily see it against the background.
    widget.style.flex = 0
    widget.style.width = 100
    widget.style.height = 200
    widget.style.background_color = CORNFLOWERBLUE
    await probe.redraw("Widget should have fixed 100x200 size")

    # Check the initial widget size
    # Match isn't exact because of pixel scaling on some platforms
    assert probe.width == approx(100, rel=0.01)
    assert probe.height == approx(200, rel=0.01)

    # Drop the fixed height, and make the widget flexible
    widget.style.flex = 1
    del widget.style.height

    # Widget should now be 100 pixels wide, but as tall as the container.
    await probe.redraw("Widget should be 100px wide now")
    assert probe.width == approx(100, rel=0.01)
    assert probe.height > 300

    # Make the parent a COLUMN box
    del widget.style.width
    widget.parent.style.direction = COLUMN

    # Widget should now be the size of the container
    await probe.redraw("Widget should be the size of container now")
    assert probe.width > 300
    assert probe.height > 300

    # Revert to fixed height
    widget.style.height = 150

    await probe.redraw("Widget should be reverted to fixed height")
    assert probe.width > 300
    assert probe.height == approx(150, rel=0.01)

    # Revert to fixed width
    widget.style.width = 150

    await probe.redraw("Widget should be reverted to fixed width")
    assert probe.width == approx(150, rel=0.01)
    assert probe.height == approx(150, rel=0.01)


async def test_flex_horizontal_widget_size(widget, probe):
    "Check that a widget that is flexible in the horizontal axis resizes as expected"
    # Container is initially a non-flex row box.
    # Initial widget size is small (but non-zero), based on content size.
    probe.assert_width(1, 160)
    probe.assert_height(1, 50)

    # Make the widget flexible; it will expand to fill horizontal space
    widget.style.flex = 1

    # widget has expanded width, but has the same height.
    await probe.redraw(
        message="Widget width should be expanded but has the same height"
    )
    probe.assert_width(350, MAX_WIDTH)
    probe.assert_height(2, 50)
    assert probe.width > 350
    assert probe.height <= 50

    # Make the container a flexible column box
    # This will make the height the flexible axis
    widget.parent.style.direction = COLUMN

    # Widget is still the width of the screen
    # and the height hasn't changed
    await probe.redraw(
        message="Widget width should be still the width of the screen without height change"
    )
    assert probe.width > 350
    probe.assert_width(350, MAX_WIDTH)
    probe.assert_height(2, 50)

    # Set an explicit height and width
    widget.style.width = 300
    widget.style.height = 200

    # Widget is approximately the requested size
    # (Definitely less than the window size)
    await probe.redraw("Widget should be changed to 300px width x 200px height")
    probe.assert_width(290, 330)
    probe.assert_height(190, 230)
