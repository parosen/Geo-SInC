"""Utilities"""

import os
from ipywidgets import widgets, Layout, Box, GridspecLayout


def get_local_path():
    return os.path.dirname(os.path.realpath(__file__))

# Basic mcq
def create_multiple_choice_widget(description, options, correct_answer, hint):
    """Create multiple choices widget."""
    if correct_answer not in options:
        options.append(correct_answer)

    correct_answer_index = options.index(correct_answer)

    radio_options = [(words, i) for i, words in enumerate(options)]
    alternativ = widgets.RadioButtons(
        options = radio_options,
        description = '',
        disabled = False,
        indent = False,
        align = 'center',
    )

    description_out = widgets.Output(layout=Layout(width='auto'))
    with description_out:
        print(description)

    feedback_out = widgets.Output()

    def check_selection(b):
        a = int(alternativ.value)
        if a==correct_answer_index:
            s = '\x1b[6;30;42m' + "correct!" + '\x1b[0m' +"\n"
        else:
            s = '\x1b[5;30;41m' + "try again" + '\x1b[0m' +"\n"
        with feedback_out:
            feedback_out.clear_output()
            print(s)
        return

    check = widgets.Button(description="check")
    check.on_click(check_selection)

    hint_out = widgets.Output()

    def hint_selection(b):
        with hint_out:
            print(hint)

        with feedback_out:
            feedback_out.clear_output()
            print(hint)

    hintbutton = widgets.Button(description="hint")
    hintbutton.on_click(hint_selection)

    return widgets.VBox(
        [description_out, alternativ, widgets.HBox([hintbutton, check]), feedback_out], 
        layout=Layout(
            display='flex',
            flex_flow='column',
            align_items='stretch',
            width='auto',
        )
    )



# Pre-defined multiple choices answers for smallbaselineApp_aria.ipynb

tcoh_vs_scoh = create_multiple_choice_widget(
    '',
    ['A', 'B', 'C', 'D'],
    'C',
    '[hint]: one that is considered noise in network inversion but could have high spatial coherence.',
)

inv_quality = create_multiple_choice_widget(
    '',
    ['A', 'B', 'C', 'D'],
    'B',
    '[hint]: one that could indicate both decorrelation noise and possible unwrapping errors.',
)
