"""A head-to-head reader study.

The reader inspects all variants of an image and selects the best one.
"""
from abc import abstractmethod
from typing import Dict, List

import meerkat as mk
import pandas as pd
from meerkat.interactive.app.src.lib.component.abstract import SlotsMixin


class ReaderStudyTemplate(mk.gui.html.div):
    """An interface for per-example or head-to-head reader studies.

    Recommendations:
        * Shuffle the dataframe before passing it to the reader study.

    TODOs:
        * Label in dataframe or with UI components - need to bind
          dataframe cells to UI values
    """

    def __init__(
        self,
        df: mk.DataFrame,
        columns: List[str],
        label_df: mk.DataFrame = None,
        ncols: int = None,
    ):
        """
        Args:
            df: The dataframe containing the images to compare.
            columns: The columns of the dataframe containing the images to compare.
            label_df: A dataframe containing the labels for the images.
                Columns should include:
                    * ``image_id``: Values are the primary key of the ``df``.
                    * ``category``: The name of the category.
                    * ``label``: The value for the associated category.
            ncols: The number of columns for panels in the reader study.
        """
        super().__init__([])

        self.row = mk.Store(0)
        self.on_save = self.on_save.partial(self)
        self.on_load = self.on_load.partial(self)
        self.on_previous = self.on_previous.partial(self)
        self.on_next = self.on_next.partial(self)

        self.df = df.mark()
        if isinstance(columns, str):
            columns = [columns]
        self.columns = columns
        self._column_to_scorers = {column: self.build_scorers() for column in columns}
        self._default_scores = self._get_scores()
        if ncols is None:
            ncols = len(columns)
        self.ncols = ncols

        # TODO: Add support for initializing with empty table.
        if label_df is None:
            label_df = self._get_dummy_label_df()
        label_df = label_df.mark()
        self.label_df = label_df

        view = self.build()
        self.append(view)

    def _get_dummy_label_df(self):
        """Build a dummy label dataframe."""
        record = {"image_id": "__dummy__", "method": "__dummy__"}
        for name, scorer in self._column_to_scorers[self.columns[0]].items():
            record[name] = self.get_value(scorer).value
        return mk.DataFrame.from_pandas(pd.DataFrame.from_records([record]))

    @mk.endpoint()
    def on_previous(self):
        self._on_save()
        self.row.set(max(0, self.row - 1))
        self._on_load()

    @mk.endpoint()
    def on_next(self):
        self._on_save()
        self.row.set(min(self.row + 1, len(self.df) - 1))
        self._on_load()

    # Make wrappers because endpoints cannot be called in a nested context.
    @mk.endpoint()
    def on_load(self):
        self._on_load()

    @mk.endpoint()
    def on_save(self):
        self._on_save()

    def _on_load(self):
        """Load the labels into the scorer components (if they exist)."""
        image_id = self.df.primary_key[self.row]
        if image_id not in self.label_df["image_id"]:
            df = self._default_scores.copy()
            df["image_id"] = image_id
            self.label_df.set(mk.concat([self.label_df, df]))

        df = self.label_df[self.label_df["image_id"] == image_id]

        # Update the UI components to the appropriate values.
        for method, scorers in self._column_to_scorers.items():
            df_method = df[df["method"] == method]
            for category, scorer in scorers.items():
                if category in df_method:
                    value = df_method[category]
                    if len(value) > 1:
                        raise ValueError(f"Multiple values for {category} - {value}.")
                    self.set_value(scorer, value[0])

    def _on_save(self):
        """Save the labels for the selected row."""
        image_id = self.df.primary_key[self.row]
        label_df = self.label_df
        scores_df = self._get_scores()
        scores_df["image_id"] = image_id

        # This is a simple way of editing the dataframe.
        # TODO: This method concatenates dataframes and is called every time the
        # dataframe needs to be saved, which may affect performance.
        label_df = self.label_df[self.label_df["image_id"] != image_id]
        self.label_df.set(mk.concat([label_df, scores_df]))

    def _get_scores(self) -> mk.DataFrame:
        """Convert the scorers into a dataframe."""
        records = []
        for column, scorers in self._column_to_scorers.items():
            record = {
                category: self.get_value(scorer).value
                for category, scorer in scorers.items()
            }
            record["method"] = column
            records.append(record)

        df = pd.DataFrame.from_records(records)
        return mk.DataFrame.from_pandas(df)

    # def load_label_df(self, path):
    #     """Load the label dataframe from disk."""
    #     self.label_df = mk.DataFrame.from_csv(path)

    @abstractmethod
    def build_scorers(self) -> Dict[str, mk.gui.Component]:
        """Build the scorers for a column.

        This method will only be called once per column in the __init__ method.

        Args:
            column: The column to build the scorers for.

        Returns:
            A dictionary mapping the name of the scorer to the scorer.
        """
        pass

    def build_scorer_component(self, scorers: Dict[str, mk.gui.Component]):
        """Build the scorer component."""
        components = [
            mk.gui.html.div(
                [
                    mk.gui.Markdown(
                        name,
                        classes="font-bold text-slate-600 text-sm",
                    ),
                    scorer,
                ]
            )
            for name, scorer in scorers.items()
        ]
        return mk.gui.html.div(components, classes="gap-2")

    @mk.reactive()
    def _get_data(self, row, column):
        """Get the data for the selected row."""
        return self.df[column].formatters["base"].encode(self.df[row][column])

    def build(self):
        """Build the view."""
        # Make a gallery for each column to be displayed.
        # TODO: Save/Load on page change.
        display_df = (lambda row: self.df[self.row : self.row + 1])(self.row)
        cell_size = mk.Store(50)
        galleries = [
            mk.gui.html.div(
                [
                    mk.gui.Gallery(
                        display_df,
                        main_column=column,
                        allow_selection=False,
                        per_page=1,
                        cell_size=cell_size,
                    )
                ],
                classes="col-span-1",
            )
            for column in self.columns
        ]

        # Build the scorers for each column.
        scorer_components = [
            self.build_scorer_component(self._column_to_scorers[column])
            for column in self.columns
        ]

        previous = mk.gui.Button(
            title="",
            icon="ArrowLeft",
            on_click=self.on_previous,
        )
        next = mk.gui.Button(title="", icon="ArrowRight", on_click=self.on_next)
        # save = mk.gui.Button(title="", icon="Save", on_click=self.on_save)

        gallery_scorers = mk.gui.html.div(
            [
                mk.gui.html.div([gallery, scorer])
                for gallery, scorer in zip(galleries, scorer_components)
            ],
            classes=f"grid grid-cols-{self.ncols} gap-2 h-full",
        )
        buttons = mk.gui.html.gridcols3(
            [
                previous,
                mk.gui.Markdown(
                    "### Example "
                    + mk.str(self.row + 1)
                    + "/"
                    + mk.str(mk.len(self.df))
                ),
                next,
            ],
            classes="justify-between justify-items-center bg-slate-100 items-center",
        )
        return mk.gui.html.div([buttons, gallery_scorers], classes="h-screen gap-y-10")

    def get_value(self, scorer):
        """Get the value from the scorer.

        This function gets the current value from the scorer (e.g. Slider, RadioGroup).

        Args:
            scorer: The scorer to get the value from.

        Returns:
            The value of the scorer.

        Raises:
            ValueError: If the scorer has no ``value`` or ``selected`` attribute.
        """
        if hasattr(scorer, "value"):
            return scorer.value
        elif hasattr(scorer, "selected"):
            return scorer.selected
        else:
            raise ValueError(
                f"Scorer {scorer} has no ``value`` or ``selected`` attribute."
            )

    def set_value(self, scorer, value):
        """Set the value for the scorer.

        This function sets the current value for the scorer (e.g. Slider, RadioGroup).

        Args:
            scorer: The scorer to set the value for.

        Raises:
            ValueError: If the scorer has no ``value`` or ``selected`` attribute.
        """
        if hasattr(scorer, "value"):
            scorer.value.set(value)
        elif hasattr(scorer, "selected"):
            scorer.selected.set(value)
        else:
            raise ValueError(
                f"Scorer {scorer} has no ``value`` or ``selected`` attribute."
            )


def _find_scorers(scorers: SlotsMixin):
    """Find all the scorers in a SlotsMixin."""
    _scorers = []
    if isinstance(scorers, SlotsMixin):
        _scorers.extend(_find_scorers(scorers.slots))
    else:
        _scorers.append(scorers)
